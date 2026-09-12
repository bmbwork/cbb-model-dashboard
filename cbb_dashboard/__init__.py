"""CBB Model Dashboard v1.1 Intelligence Terminal."""

from .conference_filter_runtime import install_conference_filter_runtime as _install_conference_filter_runtime
from .premium_ui_patch import apply_premium_ui_patch as _apply_premium_ui_patch

_apply_premium_ui_patch()
_install_conference_filter_runtime()
