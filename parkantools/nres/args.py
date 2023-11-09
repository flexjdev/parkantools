import glob
import logging

from enum import Enum
from pathlib import Path

from . import nres_archiver

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
    unarchiving_parser = subparsers.add_parser(
        Command.unarchive.name,
        help='Unarchive Parkan archive(s). Supports lib, rlb and msh files.'
    )
    unarchiving_parser.add_argument(
        'files',
        nargs='*',
        help='Path(s) to Nres archive(s)'
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

    # Special unarchiving arguments
    # TODO: recursive unarchiving
    # unarchiving_parser.add_argument(
    #     '-r',
    #     '--recursive',
    #     action='store_true',
    #     help='Unarchive recursively'
    # )



def name_without_extension(archive_path):
    return Path(archive_path).stem


def run(args):
    if args.command == Command.unarchive.name:

        # Evaluate glob patterns in input
        paths = [Path(path) for ptrn in args.files for path in glob.glob(ptrn)]
        file_paths = [path for path in paths if path.is_file()]

        for archive_path in file_paths:
            name = name_without_extension(archive_path)
            try:
                nres_archiver.unarchive(
                    archive_path,
                    args.output_directory,
                    name,
                    "",
                    args.dry_run,
                    args.force
                )
            except ValueError as error:
                logger.error(f"Failed to unarchive {archive_path}: {error}")
            finally:
                pass