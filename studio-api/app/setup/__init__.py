"""Normalized Setup Wizard services.

The legacy :mod:`app.setup_wizard` module remains the compatibility facade.
"""

from .orchestrator import (
    browse_setup_path,
    diagnose_component,
    execute_recommended_action,
    get_operation,
    get_prepare_plan,
    get_setup_status,
    refresh_component_source,
    respond_to_checkpoint,
    start_choose_install_location,
    start_link_existing_pack,
    start_prepare,
)

__all__ = [
    "browse_setup_path",
    "diagnose_component",
    "execute_recommended_action",
    "get_operation",
    "get_prepare_plan",
    "get_setup_status",
    "refresh_component_source",
    "respond_to_checkpoint",
    "start_choose_install_location",
    "start_link_existing_pack",
    "start_prepare",
]
