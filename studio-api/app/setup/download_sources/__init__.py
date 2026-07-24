"""Download Sources: GitHub CLI, Hugging Face CLI, and manual URL workflows."""

from .service import (
    detect_download_sources,
    install_cli,
    list_source_files,
    remove_source_override,
    save_source_override,
    start_cli_sign_in,
    verify_source_url,
)
from .url_parse import parse_source_url

__all__ = [
    "detect_download_sources",
    "install_cli",
    "list_source_files",
    "parse_source_url",
    "remove_source_override",
    "save_source_override",
    "start_cli_sign_in",
    "verify_source_url",
]
