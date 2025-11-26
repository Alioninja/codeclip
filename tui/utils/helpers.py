from pathlib import Path
from ..config import (
    IGNORED_DIRS, IGNORED_DIR_PREFIXES, 
    IGNORED_FILES, IGNORED_FILE_PREFIXES,
    LANGUAGE_MAP
)

def _normalized_parts(value):
    """Return normalized, case-insensitive path parts."""
    normalized = str(Path(value)).lower()
    return tuple(part for part in Path(normalized).parts if part)


IGNORED_DIRS_COMPONENTS = [_normalized_parts(name) for name in IGNORED_DIRS]
IGNORED_DIRS_BASENAMES = {parts[0] for parts in IGNORED_DIRS_COMPONENTS if len(parts) == 1}
IGNORED_FILES_NORMALIZED = {name.lower() for name in IGNORED_FILES}


def is_ignored_dir(name):
    """Check if directory should be ignored."""
    if name in ('.', '..'):
        return False
    if name.lower() in IGNORED_DIRS_BASENAMES:
        return True
    return any(name.startswith(prefix) for prefix in IGNORED_DIR_PREFIXES)


def is_ignored_file(name):
    """Check if file should be ignored."""
    if name.lower() in IGNORED_FILES_NORMALIZED:
        return True
    return any(name.startswith(prefix) for prefix in IGNORED_FILE_PREFIXES)


def path_contains_ignored_dir(path):
    """Check if path contains any ignored directory."""
    path_parts = _normalized_parts(path)
    if not path_parts:
        return False
    for ignored_parts in IGNORED_DIRS_COMPONENTS:
        if not ignored_parts:
            continue
        if len(ignored_parts) == 1:
            if ignored_parts[0] in path_parts:
                return True
            continue
        parts_range = len(path_parts) - len(ignored_parts) + 1
        if parts_range < 1:
            continue
        for index in range(parts_range):
            if path_parts[index:index + len(ignored_parts)] == ignored_parts:
                return True
    return False

def get_language(ext):
    """Get language identifier for a file extension."""
    return LANGUAGE_MAP.get(ext.lower(), '')
