import base64
import hashlib
import json
import pandas as pd
import pytest
from bs4 import BeautifulSoup
from cbb_dashboard.team_logos import ASSET_ROOT, bundled_logo_source
from cbb_dashboard import premium_ui_patch
from cbb_dashboard.intelligence import game_card_grid_html


@pytest.mark.parametrize("team", ["Oklahoma", "Baylor", "West Virginia", "Creighton", "La Salle", "Saint Louis", "Duke", "North Carolina"])
def test_real_verified_logo_available_without_espn_network(team, monkeypatch):
    monkeypatch.setattr(premium_ui_patch, "_fetch_json", lambda url: (_ for _ in ()).throw(AssertionError("network lookup")))
    html=premium_ui_patch._logo_html(team,"20260404")
    img=BeautifulSoup(html,"html.parser").find("img")
    assert img and img['src'].startswith('data:image/png;base64,')
    raw=base64.b64decode(img['src'].split(',',1)[1])
    assert raw[:8]==b'\x89PNG\r\n\x1a\n'
    assert len(raw)>100
    assert 'cbb-logo-fallback' not in html


def test_every_bundled_asset_matches_its_recorded_digest():
    directory=json.loads((ASSET_ROOT/'directory.json').read_text())
    assert len(directory['teams'])>=300
    for team in directory['teams']:
        raw=(ASSET_ROOT/team['asset']).read_bytes()
        assert hashlib.sha256(raw).hexdigest()==team['sha256']


def test_active_game_grid_contains_both_logo_images(monkeypatch):
    premium_ui_patch.apply_premium_ui_patch()
    monkeypatch.setattr(premium_ui_patch, "_fetch_json", lambda url: {})
    board=pd.DataFrame([{'Away Team':'Oklahoma','Home Team':'Baylor','Target Date':'2026-04-04',
       'Model Pick':'Oklahoma','Win Probability':.554,'Fair Spread':-.02,'Fair Moneyline':-124,
       'Projected Away Score':80.1,'Projected Home Score':80.2,'Model Version':'1.1.3B'}])
    html=game_card_grid_html(board)
    images=BeautifulSoup(html,'html.parser').select('.cbb-logo-matchup img')
    assert len(images)==2
    assert all(i['src'].startswith('data:image/png;base64,') for i in images)


def test_unknown_team_is_not_assigned_a_different_teams_logo():
    assert bundled_logo_source('Definitely not a team')==''
