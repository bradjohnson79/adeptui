"""FLUX prompt assembly for Adept UI. Not the Qwen 13-block compiler."""

from .crs_single_view import FluxCrsPromptPackage, compile_flux_crs_single_view

__all__ = ["FluxCrsPromptPackage", "compile_flux_crs_single_view"]
