import logging
import struct

from pathlib import Path

logger = logging.getLogger(__name__)


class ArchivedFileMetadata:
    STRUCT_FORMAT = '12sII36sII'
    METADATA_SIZE = 64

    def __init__(self, file_type, file_size, file_name, file_offset, file_id):
        self.file_type = file_type
        self.file_size = file_size
        self.file_name = file_name
        self.file_offset = file_offset
        self.file_id = file_id


    def __str__(self):
        return \
            f"Name: {self.file_name}, Type: {self.file_type}, " \
            f"Size: {self.file_size}, Position: {self.file_offset} bytes, " \
            f"ID: {self.file_id}"


    def __init__(self, buffer):
        metadata = struct.unpack(ArchivedFileMetadata.STRUCT_FORMAT, buffer)
        type, size, x, name, offset, id = metadata

        self.file_type = type.decode('utf-8').rstrip('\x00')
        self.file_name = name.decode('utf-8').rstrip('\x00')
        self.file_size = size
        self.file_offset = offset
        self.file_id = id


class NresArchiveMetadata:
    STRUCT_FORMAT = 'IIII'
    SIGNATURE = 0x7365524e  # NRes
    METADATA_SIZE = 16

    def __init__(self, x, file_count, archive_size):
        self.x = x
        self.file_count = file_count
        self.archive_size = archive_size


    def __str__(self):
        return f"Files: {self.file_count}, Size: {self.archive_size}"


    def __init__(self, buffer):
        if len(buffer) != NresArchiveMetadata.METADATA_SIZE:
            error_description = \
                f"Incorrect metadata buffer size. Got {len(buffer)}, " \
                f"expected {NresArchiveMetadata.METADATA_SIZE}"
            raise ValueError(error_description)

        metadata = struct.unpack(NresArchiveMetadata.STRUCT_FORMAT, buffer)
        signature_bytes, x, file_count, archive_size = metadata

        if signature_bytes != NresArchiveMetadata.SIGNATURE:
            error_description = \
                f"Invalid signature. Got {signature_bytes:#x}, expected " \
                f"{NresArchiveMetadata.SIGNATURE:#x}"
            raise ValueError(error_description)

        self.file_count = file_count
        self.archive_size = archive_size


def decode_table_of_contents(buffer, file_count):
    entry_size = ArchivedFileMetadata.METADATA_SIZE
    expected_buffer_size = entry_size * file_count

    if len(buffer) != expected_buffer_size:
        error_description = \
            f"Incorrect toc size for {file_count} files. Got {len(buffer)}, " \
            f"received {expected_buffer_size}"
        raise ValueError(error_description)

    entries = []
    for i in range(file_count):
        entry_start = i * ArchivedFileMetadata.METADATA_SIZE
        entry_end = (i + 1) * ArchivedFileMetadata.METADATA_SIZE

        entry_buffer = buffer[entry_start:entry_end]
        metadata = ArchivedFileMetadata(entry_buffer)

        entries.append(metadata)

    return entries


def create_directory_if_needed(output_dir_path, dry_run):
    path = Path(output_dir_path)
    if path.is_file():
        raise ValueError(f"Output directory is a file")

    if not path.is_dir():
        if dry_run:
            logger.info(f"Dry-run: skipping creating directory at {path}")
            return
        logger.debug(f"Creating directory at {path}")
        path.mkdir(parents=True, exist_ok=True)


def unpack_file(metadata, archive_file, out_dir, archive_name, dry_run, force):
    full_out_dir = Path(out_dir).joinpath(archive_name)
    create_directory_if_needed(full_out_dir, dry_run)

    # Join file name with archive name to give more context in logs
    cxt_name = Path(archive_name).joinpath(metadata.file_name)
    logger.debug(f"Unpacking {cxt_name} ({metadata.file_size}) bytes")

    full_out_path = Path(out_dir).joinpath(cxt_name)
    archive_file.seek(metadata.file_offset, 0)

    # These archives are small by today's standards, it could still be worth
    # adding the ability to configure max buffer size and read in chunks
    file_buffer = archive_file.read(metadata.file_size)

    if len(file_buffer) != metadata.file_size:
        error_description = \
            f"Failed to unpack {cxt_name}: expected to read " \
            f"{metadata.file_size} bytes, actually read {len(file_buffer)}"
        raise ValueError(error_description)

    logger.debug(f"Copying archived file {cxt_name} to {full_out_path}")
    if full_out_path.is_file():
        if not force:
            error_description = \
                f"File {full_out_path} already exists, skipping copying. " \
                f"Use -f or --force to enable overwriting existing files."
            logger.info(error_description)
            # raise ValueError(error_description)
            return  # It's not that serious, log it and move on to the next one

        logger.debug(f"Will overwrite existing file {full_out_path}")

    if dry_run:
        logger.info(f"Dry-run: skipping writing file {full_out_path}")
        return

    with open(full_out_path, 'wb') as out_file:
        bytes_written = out_file.write(file_buffer)
        logger.debug(f"Copied {bytes_written} bytes to {full_out_path}")


def unarchive(archive_path, out_dir, arch_name, include, dry_run, force):
    create_directory_if_needed(out_dir, dry_run)

    logger.info(f"Unarchiving {archive_path} to {out_dir}")
    with open(archive_path, 'rb') as arch_file:  # archive file
        logger.debug("Reading and decoding archive metadata")
        metadata_buffer = arch_file.read(NresArchiveMetadata.METADATA_SIZE)
        metadata = NresArchiveMetadata(metadata_buffer)
        logger.debug(f"Metadata: {metadata}")

        # Calculate position at which the table of contents should start
        toc_size = metadata.file_count * ArchivedFileMetadata.METADATA_SIZE
        toc_offset = metadata.archive_size - toc_size

        logger.debug(f"Seeking start of table of contents at {toc_offset:#x}")
        arch_file.seek(toc_offset, 0)
        toc_buffer = arch_file.read(toc_size)
        toc = decode_table_of_contents(toc_buffer, metadata.file_count)

        for entry in toc:
            unpack_file(entry, arch_file, out_dir, arch_name, dry_run, force)
