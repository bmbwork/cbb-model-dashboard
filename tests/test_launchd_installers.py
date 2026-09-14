from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_auto_grade_installer_quotes_managed_python_path_in_command_substitution():
    text = (ROOT / "scripts" / "install_cbb_auto_grade_launchd.sh").read_text(encoding="utf-8")

    # The managed runtime lives under ~/Library/Application Support/... .
    # If $PY is unquoted here, Bash splits the interpreter path at the space and
    # attempts to execute ~/Library/Application instead of the Python binary.
    assert 'MODEL_ROOT="$("$PY" - "$CONFIG_PATH" <<\'PY\'' in text
    assert 'MODEL_ROOT="$($PY - "$CONFIG_PATH"' not in text


def test_both_cbb_launchd_installers_force_headless_managed_runtime():
    for filename in (
        "install_cbb_model_refresh_launchd.sh",
        "install_cbb_auto_grade_launchd.sh",
    ):
        text = (ROOT / "scripts" / filename).read_text(encoding="utf-8")
        assert 'Library/Application Support/StatFactory/CBB/venv' in text
        assert '"STAT_FACTORY_HEADLESS_AUTOMATION": "1"' in text
        assert '"PYTHONNOUSERSITE": "1"' in text
