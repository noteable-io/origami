from pathlib import PurePath

def ensure_relative_path(path: str) -> str:
    if (pure_path := PurePath(path)).is_absolute():
        return str(pure_path.relative_to("/"))
    else:
        return str(pure_path)
