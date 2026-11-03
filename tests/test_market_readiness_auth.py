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
