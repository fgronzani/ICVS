"""Common utilities for PySUS collectors."""
from __future__ import annotations

from pathlib import Path


def ensure_file_list(download_result) -> list[Path]:
    """
    Normalize PySUS download() return value to a list of Path objects.

    PySUS download() may return:
    - A single filepath string
    - A list of filepath strings
    - A single Path object
    - A list of Path objects
    - None
    """
    if download_result is None:
        return []

    if isinstance(download_result, (str, Path)):
        return [Path(download_result)]

    if isinstance(download_result, (list, tuple)):
        return [Path(f) for f in download_result if f]

    return []
