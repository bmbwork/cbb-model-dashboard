"""Contract test: secret inspection must not leak credentials or demand network access."""
from scripts.market_readiness import owls_credential_shape


def test_expected_raw_key_shape():
    assert owls_credential_shape("owlsinsight_" + "a1" * 32) == "expected"
    assert owls_credential_shape("\nowlsinsight_" + "A1" * 32 + " \n") == "expected"


def test_wrong_format_is_diagnosed_without_outputting_secret():
    assert owls_credential_shape(None) == "missing"
    assert owls_credential_shape("") == "missing"
    assert owls_credential_shape("Bearer owlsinsight_" + "a1" * 32) == "bearer_prefix_in_secret"
    assert owls_credential_shape('"owlsinsight_' + "a1" * 32 + '"') == "quoted_secret"
    assert owls_credential_shape("not_an_owls_key") == "unexpected"


def test_shape_diagnostics_are_not_key_values():
    example = "owlsinsight_" + "b2" * 32
    assert example not in owls_credential_shape(example)

def test_nonstandard_present_key_is_advisory_not_fatal(monkeypatch, capsys):
    """Provider may accept credentials outside the documented format."""
    import json
    import sys
    from datetime import datetime
    from types import SimpleNamespace
    from zoneinfo import ZoneInfo
    import scripts.market_readiness as readiness

    today = datetime.now(ZoneInfo("America/Chicago")).date().isoformat()

    class Query:
        def table(self, *_):
            return self
        def select(self, *_):
            return self
        def gte(self, *_):
            return self
        def lte(self, *_):
            return self
        def gt(self, *_):
            return self
        def limit(self, *_):
            return self
        def execute(self):
            return SimpleNamespace(data=[{"slate_date": today, "board_rows": 2}])

    monkeypatch.setitem(sys.modules, "supabase", SimpleNamespace(create_client=lambda *_: Query()))
    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "test-server-key")
    monkeypatch.setenv("OWLS_INSIGHT_API_KEY", "nonstandard_but_provider_can_authenticate")
    monkeypatch.delenv("GITHUB_OUTPUT", raising=False)

    readiness.main()  # Must not raise just because key does not match a regex
    result = json.loads(capsys.readouterr().out)
    assert result["active"] is True
    assert result["provider_key_configured"] is True
    assert result["provider_key_format"] == "unexpected"
