import argparse
import logging.config
import nres.args

import logging

def setup_logging(level):
    format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    filename = 'parkantools.log'
    config = logging.basicConfig(level=level, format=format, filename=filename)
    logging.config = config

    # set up logging to console
    console = logging.StreamHandler()
    console.setLevel(level)
    console_log_format = '%(name)-12s: %(levelname)-8s %(message)s'
    console.setFormatter(logging.Formatter(console_log_format))
    logging.getLogger('').addHandler(console)  # Add to root logger


if __name__ == "__main__":
    package_description = \
        "Collection of tools for working with proprietary file and " \
        "archive formats used in Parkan games."

    parser = argparse.ArgumentParser(description=package_description)

    subparsers = parser.add_subparsers(dest='command', required=True)
    nres.args.setup_subparser(subparsers)

    verbosity_group = parser.add_mutually_exclusive_group()
    verbosity_group.add_argument(
        '-v',
        '--verbose',
        action='store_true',
        help=''
    )
    verbosity_group.add_argument(
        '-s',
        '--silent',
        action='store_true',
        help=''
    )

    args = parser.parse_args()

    if args.silent:
        pass  # Errors still get printed to console (stderr?) - probably ok
    elif args.verbose:
        setup_logging(logging.DEBUG)
    else:
        setup_logging(logging.INFO)

    logger = logging.getLogger(__name__)

    if args.dry_run:
        logger.info(f"{__name__} is in dry-run mode: no changes will be made")

    if args.command in nres.args.commands:
        nres.args.run(args)
