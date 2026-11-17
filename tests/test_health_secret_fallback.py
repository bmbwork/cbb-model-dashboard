from unittest.mock import MagicMock
from scripts import production_health as health


def test_health_accepts_configured_secret_alias(monkeypatch):
    monkeypatch.setenv('SUPABASE_URL', 'https://example.test')
    monkeypatch.delenv('SUPABASE_SERVICE_ROLE_KEY', raising=False)
    monkeypatch.setenv('SUPABASE_SECRET_KEY', 'test-private-key')
    client = MagicMock()
    client.table.return_value.select.return_value.order.return_value.order.return_value.limit.return_value.execute.return_value.data = [{'slate_date':health.datetime.now(health.TZ).date().isoformat(),'revision':1}]
    factory = MagicMock(return_value=client)
    monkeypatch.setattr(health, 'create_client', factory)
    monkeypatch.setattr(health, 'active_window', lambda day: True)
    health.main()
    factory.assert_called_once_with('https://example.test', 'test-private-key')
