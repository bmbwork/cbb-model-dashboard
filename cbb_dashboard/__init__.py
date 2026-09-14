"""CBB Model Dashboard package.

UI runtime patches are installed only inside an active Streamlit script context.
Background automation imports (grading, forecasting, market/storage workers) must
remain headless and must not pull the dashboard UI dependency graph.
"""


def _running_in_streamlit() -> bool:
    try:
        from streamlit.runtime.scriptrunner import get_script_run_ctx
    except Exception:
        return False
    try:
        return get_script_run_ctx(suppress_warning=True) is not None
    except TypeError:
        return get_script_run_ctx() is not None
    except Exception:
        return False


if _running_in_streamlit():
    from .conference_filter_runtime import install_conference_filter_runtime as _install_conference_filter_runtime
    from .premium_ui_patch import apply_premium_ui_patch as _apply_premium_ui_patch

    _apply_premium_ui_patch()
    _install_conference_filter_runtime()
