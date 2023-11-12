import glob
import logging

from pathlib import Path

logger = logging.getLogger()

def collect_files_to_archive(patterns):
    for p in patterns:
        logger.info(Path(p))
    paths = [Path(path) for ptrn in patterns for path in glob.glob(ptrn)]
    file_paths = [path for path in paths if path.is_file()]
    logger.debug(f"Collected {len(file_paths)} from patterns {patterns}")
    return file_paths


def name(path):
    return Path(path).name


def name_without_extension(path):
    return Path(path).stem


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


def can_modify_file(path, force):
    if not Path(path).exists:
        return True
    
    if Path(path).is_file():
        if force:
            return True
        else:
            error_description = \
                f"File {path} already exists, skipping copying. " \
                f"Use -f or --force to enable overwriting existing files."
            logger.info(error_description)
            # raise ValueError(error_description)
            return False

    elif Path(path).is_dir():
        logger.error(f"{path} is a directory, skipping copying.")
        return False

    return True
