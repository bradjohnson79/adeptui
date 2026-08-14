"""Model Storage — category roots, register/import folders, discovery & validation."""

from .store import (
    DEFAULT_PREFERRED_ROOT,
    ROOT_CATEGORIES,
    category_root,
    get_registered_folders,
    get_roots,
    load_model_storage,
    preferred_root,
    register_folder,
    set_root,
    unregister_folder,
)
from .classify import classify_folder
from .validate import probe_availability, validate_registration

__all__ = [
    "DEFAULT_PREFERRED_ROOT",
    "ROOT_CATEGORIES",
    "classify_folder",
    "category_root",
    "get_registered_folders",
    "get_roots",
    "load_model_storage",
    "preferred_root",
    "probe_availability",
    "register_folder",
    "set_root",
    "unregister_folder",
    "validate_registration",
]
