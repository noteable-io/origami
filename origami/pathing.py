"""A utility file for any complex path manipulations or validations"""

from pathlib import PurePath


def ensure_relative_path(path: str) -> str:
    """Ensure's that a path is relative or absolute to the same root (could be represented by a relative path)"""
    if (pure_path := PurePath(path)).is_absolute():
        return str(pure_path.relative_to("/"))
    else:
        return str(pure_path)
