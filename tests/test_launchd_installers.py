from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def read_script(name: str) -> str:
    return (ROOT / "scripts" / name).read_text(encoding="utf-8")


def test_cbb_forecast_installer_stages_dashboard_and_champion_outside_desktop():
    text = read_script("install_cbb_model_refresh_launchd.sh")

    assert 'MANAGED_BASE="$HOME/Library/Application Support/StatFactory/CBB"' in text
    assert 'WEB_ROOT="$MANAGED_BASE/dashboard_runtime"' in text
    assert 'MODEL_ROOT="$MANAGED_BASE/champion_runtime"' in text
    assert 'STAGER="$SOURCE_WEB_ROOT/scripts/stage_cbb_background_runtime.sh"' in text
    assert '"runtime_policy": "managed_app_support_v1"' in text
    assert '"model_root": sys.argv[2]' in text
    assert '"web_root": sys.argv[3]' in text


def test_cbb_runtime_stager_rebuilds_private_champion_venv_and_verifies_identity():
    text = read_script("stage_cbb_background_runtime.sh")

    assert "rsync -a --delete" in text
    assert "--exclude '.streamlit/secrets.toml'" in text
    assert 'rm -rf "$MANAGED_MODEL_ROOT/.venv"' in text
    assert '"$BASE_PY" -m venv "$MANAGED_MODEL_ROOT/.venv"' in text
    assert "Frozen CBB V1.1.3B source identity verified" in text
    assert 'chmod 600 "$MANAGED_MODEL_ROOT/.env"' in text


def test_cbb_auto_grade_requires_managed_runtime_and_is_macos_bash_compatible():
    text = read_script("install_cbb_auto_grade_launchd.sh")

    assert 'EXPECTED_WEB_ROOT="$MANAGED_BASE/dashboard_runtime"' in text
    assert 'RUNTIME_POLICY="$(config_value runtime_policy)"' in text
    assert '"managed_app_support_v1"' in text
    assert "readarray" not in text
    assert 'bash "$STAGER" --web-only "$SOURCE_WEB_ROOT"' in text


def test_both_cbb_launchd_installers_force_headless_managed_runtime():
    for filename in (
        "install_cbb_model_refresh_launchd.sh",
        "install_cbb_auto_grade_launchd.sh",
    ):
        text = read_script(filename)
        assert 'Library/Application Support/StatFactory/CBB' in text
        assert '"STAT_FACTORY_HEADLESS_AUTOMATION": "1"' in text
        assert '"PYTHONNOUSERSITE": "1"' in text
        assert '"WorkingDirectory"' in text


def test_forecast_installer_handles_missing_cached_credentials_without_set_e_abort():
    text = read_script("install_cbb_model_refresh_launchd.sh")

    assert "credential_status=0" in text
    assert "if \"$PY\" - \"$SOURCE_WEB_ROOT\" \"$ENV_PATH\" <<'PY'" in text
    assert "else\n  credential_status=$?\nfi" in text
