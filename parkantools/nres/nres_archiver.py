import logging
import os
import struct

from pathlib import Path
from parkanio.fileio import *

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


    def decode(buffer):
        metadata = struct.unpack(ArchivedFileMetadata.STRUCT_FORMAT, buffer)
        type, size, x, name, offset, id = metadata

        return ArchivedFileMetadata(
            type.decode('utf-8').rstrip('\x00'),
            size,
            name.decode('utf-8').rstrip('\x00'),
            offset,
            id
        )


    def bytes(self):
        return struct.pack(
            ArchivedFileMetadata.STRUCT_FORMAT,
            self.file_type,
            self.file_size,
            0x0000, # x
            bytes(self.file_name, 'utf-8'),
            self.file_offset,
            self.file_id
        )


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


    def decode(buffer):
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

        return NresArchiveMetadata(0x0000, file_count, archive_size)


    def bytes(self):
        return struct.pack(
            NresArchiveMetadata.STRUCT_FORMAT,
            NresArchiveMetadata.SIGNATURE,
            0x0100,
            self.file_count,
            self.archive_size
        )


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
        metadata = ArchivedFileMetadata.decode(entry_buffer)

        entries.append(metadata)

    return entries


def unpack_file(metadata, archive_file, out_dir, archive_name, dry_run, force):
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

    if not can_modify_file(full_out_path, force):
        return

    if dry_run:
        logger.info(f"Dry-run: skipping writing file {full_out_path}")
        return

    with open(full_out_path, 'wb') as out_file:
        bytes_written = out_file.write(file_buffer)
        logger.debug(f"Copied {bytes_written} bytes to {full_out_path}")


def unarchive(archive_path, out_dir, arch_name, include, dry_run, force):
    logger.info(f"Unarchiving {archive_path} to {out_dir}")
    with open(archive_path, 'rb') as arch_file:  # archive file
        logger.debug("Reading and decoding archive metadata")
        metadata_buffer = arch_file.read(NresArchiveMetadata.METADATA_SIZE)
        metadata = NresArchiveMetadata.decode(metadata_buffer)
        logger.debug(f"Metadata: {metadata}")

        # Calculate position at which the table of contents should start
        toc_size = metadata.file_count * ArchivedFileMetadata.METADATA_SIZE
        toc_offset = metadata.archive_size - toc_size

        logger.debug(f"Seeking start of table of contents at {toc_offset:#x}")
        arch_file.seek(toc_offset, 0)
        toc_buffer = arch_file.read(toc_size)
        toc = decode_table_of_contents(toc_buffer, metadata.file_count)

        for entry in toc:
            logger.debug(f"Processing toc entry: {entry}")
            unpack_file(entry, arch_file, out_dir, arch_name, dry_run, force)


def archive(file_paths, out_path, dry_run, force):

    if not can_modify_file(out_path, force):
        return

    file_count = len(file_paths)
    file_sizes = []
    # Do this now so we fail early if something is wrong with one of the files,
    # Before we even create the archive
    for path in file_paths:
        file_sizes.append(os.path.getsize(path))

    total_size = NresArchiveMetadata.METADATA_SIZE \
        + sum(file_sizes) \
        + file_count * ArchivedFileMetadata.METADATA_SIZE

    header = NresArchiveMetadata(0x0000, file_count, total_size)

    logger.info(f"Creating archive at {out_path}")
    with open(out_path, 'wb') as arch_file:
        arch_file.write(header.bytes())

        toc_entries = []
        file_id = 0
        for path in file_paths:

            file_offset = arch_file.tell()
            file_name = name(path)

            with open(path, 'rb') as file:
                file_type = struct.unpack('4s', file.read(4))[0]
                file.seek(0)
                arch_file.write(file.read())
                file_size = file.tell()

            toc_entry = ArchivedFileMetadata(
                file_type,
                file_size,
                file_name,
                file_offset,
                file_id
            )

            logger.debug(f"Appending entry to table of contents: {toc_entry}")
            toc_entries.append(toc_entry)
            file_id += 1

        for entry in toc_entries:
            arch_file.write(entry.bytes())
