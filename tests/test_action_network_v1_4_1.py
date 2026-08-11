from pathlib import Path
import pandas as pd

from cbb_dashboard.action_network_provider import ActionNetworkConfig, ActionNetworkMarketProvider
from cbb_dashboard.data import normalize_board
from cbb_dashboard.intelligence import market_pulse_html
from cbb_dashboard.market import attach_market_to_board, market_records, normalize_market_import

ROOT = Path(__file__).resolve().parents[1]


def test_action_config_builds_authorized_url_and_header():
    cfg = ActionNetworkConfig(
        api_key="secret",
        api_base_url="https://licensed.example/api/",
        slate_path_template="ncaab/{yyyy}/{mm}/{dd}/markets",
        auth_header="X-Api-Key",
        auth_prefix="",
    )
    provider = ActionNetworkMarketProvider(cfg)
    assert provider._url(cfg.slate_path_template, "2026-11-14") == "https://licensed.example/api/ncaab/2026/11/14/markets"
    assert provider._headers() == {"X-Api-Key": "secret"}


def test_action_parser_accepts_ticket_money_count_and_line_shape(board_df):
    provider = ActionNetworkMarketProvider(ActionNetworkConfig(
        api_key="x", api_base_url="https://licensed.example", slate_path_template="/{date}"
    ))
    row = board_df.iloc[0].copy()
    row["Start Time UTC"] = "2026-01-10T20:00:00Z"
    payload = {
        "updated_at":"2026-01-10T19:00:00Z",
        "ticket_count":1842,
        "signals":[{"name":"Big Money"}],
        "markets":[{
            "type":"spread",
            "outcomes":[
                {"team":"Home Tech","bets_percentage":0.38,"money_percentage":0.64,"line":-4.5,"opening_line":-3.0},
                {"team":"Away State","bets_percentage":0.62,"money_percentage":0.36,"line":4.5,"opening_line":3.0},
            ]
        }]
    }
    parsed = provider.parse_market_payload(payload, row, "evt-1")
    spread = parsed[parsed["Market Type"].eq("spread")].iloc[0]
    assert spread["Provider"] == "action_network"
    assert spread["Source Label"] == "Action Network"
    assert spread["Home Ticket %"] == 38
    assert spread["Home Money %"] == 64
    assert spread["Ticket Count"] == 1842
    assert spread["Activity Level"] == "high"
    assert spread["Provider Signals"] == "Big Money"
    assert spread["Opening Home Line"] == -3.0
    assert spread["Home Line"] == -4.5


def test_action_ticket_count_persists_into_records_and_market_pulse(board_df):
    raw = board_df.iloc[[0]].copy()
    raw["Model Run At UTC"] = "2026-01-10T19:25:00Z"
    board, _ = normalize_board(raw)
    snap = normalize_market_import(pd.DataFrame([{
        "Slate Date":"2026-01-10","Game ID":"101","Snapshot Time UTC":"2026-01-10T19:20:00Z",
        "Market Type":"spread","Provider":"action_network","Source Label":"Action Network",
        "Home Ticket %":30,"Home Money %":55,"Home Line":-4.5,"Opening Home Line":-3,
        "Ticket Count":1842,"Provider Signals":"Big Money","Snapshot Role":"decision",
    }]))
    records = market_records(snap, "tester")
    assert records[0]["ticket_count"] == 1842
    assert records[0]["provider_signals"] == "Big Money"
    out = attach_market_to_board(board, snap)
    html = market_pulse_html(out.iloc[0])
    assert "1,842 tracked bets" in html
    assert "Action Network" in html


def test_action_adapter_remains_archival_but_is_not_wired_as_primary():
    source = (ROOT / "app.py").read_text()
    provider = (ROOT / "cbb_dashboard" / "action_network_provider.py").read_text()
    assert "Refresh Action Network market data" not in source
    assert "ACTION_NETWORK_API_KEY" not in source
    assert "actionnetwork.com" not in provider.lower()
    assert "consumer website" in provider.lower()


def test_v141_market_schema_has_action_sample_fields_and_rls():
    sql = (ROOT / "supabase" / "market_terminal_v1_4_1.sql").read_text().lower()
    assert "ticket_count bigint" in sql
    assert "provider_signals text" in sql
    assert "enable row level security" in sql
    assert "grant select" in sql
    assert "for insert" not in sql and "for update" not in sql and "for delete" not in sql
