"""Wiki Page Compiler — records are evidence; pages are synthesized views."""

from .page_compiler import compile_wiki_bundle, get_compiled_wiki
from .promotion import detect_explicit_wiki_write, promote_explicit_wiki_text
from .readability import assert_wiki_readability

__all__ = [
    "assert_wiki_readability",
    "compile_wiki_bundle",
    "detect_explicit_wiki_write",
    "get_compiled_wiki",
    "promote_explicit_wiki_text",
]
