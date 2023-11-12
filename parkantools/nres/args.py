import glob
import logging

from enum import Enum
from pathlib import Path

from nres import nres_archiver
from parkanio.fileio import *

logger = logging.getLogger(__name__)

class Command(Enum):
    unarchive = 'unarchive'
    archive = 'archive'


commands = [command.name for command in Command]


def setup_subparser(subparsers):
    # Subparsers for archiving and unarchiving commands
    archiving_parser = subparsers.add_parser(
        Command.archive.name,
        help='Create a Parkan archive.'
    )
    archiving_parser.add_argument(
        'name',
        help='The name of the archive to create. Should include extension.'
    )
    archiving_parser.add_argument(
        'files',
        nargs='*',
        help='File(s) or directories to archive'
    )

    unarchiving_parser = subparsers.add_parser(
        Command.unarchive.name,
        help='Unarchive Parkan archive(s). Supports lib, rlb and msh files.'
    )
    unarchiving_parser.add_argument(
        'files',
        nargs='*',
        help='File(s) or directories to archive'
    )

    archive_parsers = [archiving_parser, unarchiving_parser]

    # Arguments common to archiving and unarchiving
    for parser in archive_parsers:
        parser.add_argument(
            '-d',
            '--output_directory',
            help=''
        )
        parser.add_argument(
            '-n',
            '--dry_run',
            action='store_true',
            help=''
        )
        parser.add_argument(
            '-f',
            '--force',
            action='store_true',
            help='Overwrite existing files'
        )

    # TODO: recursive unarchiving
    # with archiving, we don't have extension information
    # unarchiving_parser.add_argument(
    #     '-r',
    #     '--recursive',
    #     action='store_true',
    #     help='Unarchive recursively'
    # )

    return archive_parsers


def unarchive(args):
    # Evaluate glob patterns in input
    paths = [Path(path) for ptrn in args.files for path in glob.glob(ptrn)]
    file_paths = [path for path in paths if path.is_file()]
    file_paths += [path for path in args.files]

    for archive_path in file_paths:
        logger.debug(f"Unarchiving: {archive_path}")
        name = name_without_extension(archive_path)
        try:
            dry_run = args.dry_run
            out_dir = args.output_directory
            full_out_dir = Path(out_dir).joinpath(name)

            create_directory_if_needed(full_out_dir, dry_run)

            nres_archiver.unarchive(
                archive_path,
                args.output_directory,
                name,
                "",  # TODO: include parameter (only unarchive matching files)
                dry_run,
                args.force
            )

        except ValueError as error:
            logger.error(f"Failed to unarchive {archive_path}: {error}")

        finally:
            pass


def archive(args):
    dry_run = args.dry_run
    out_dir = args.output_directory
    archive_name = args.name
    create_directory_if_needed(out_dir, dry_run)

    out_path = Path(out_dir).joinpath(archive_name)

    in_files = collect_files_to_archive(args.files)
    nres_archiver.archive(in_files, out_path, dry_run, args.force)


def run(args):
    if args.command == Command.unarchive.name:
        unarchive(args)

    elif args.command == Command.archive.name:
        archive(args)

    else:
        raise ValueError(f"Unsupported command: {args.command}")