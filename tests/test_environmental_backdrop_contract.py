from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_full_bleed_photo_backdrop_contract():
    theme = (ROOT / "cbb_dashboard/ui.py").read_text()
    assert "GLOBAL_CSS += BACKGROUND_ART_CSS" in theme
    assert "Full-bleed real sport photography" in theme
    assert "images.pexels.com" in theme
    assert "position:fixed" in theme
    assert "inset:0" in theme
    assert "background-size:cover,cover,cover" in theme
    assert "pointer-events:none" in theme
    assert "data:image/svg+xml" not in theme


def test_glass_surface_and_readability_contract():
    theme = (ROOT / "cbb_dashboard/ui.py").read_text()
    assert "PLAYER_FOCUS_CSS" in theme
    assert "rgba(30,13,16,.64)" in theme
    assert "rgba(255,122,26,.22)" in theme
    assert "backdrop-filter:blur(12px)" in theme
    assert "opacity:1!important" in theme
    assert '[data-testid="stSidebar"]' in theme
    assert "z-index:3!important" in theme


def test_scroll_stability_disables_flicker_prone_compositing():
    theme = (ROOT / "cbb_dashboard/ui.py").read_text()
    assert "SCROLL_STABILITY_CSS" in theme
    assert "Scroll stability: avoid GPU compositor flicker" in theme
    assert "backdrop-filter:none!important" in theme
    assert "transition:none!important" in theme
    assert "will-change:auto!important" in theme
    assert "background-attachment:scroll!important" in theme


def test_cards_are_more_opaque_than_background_art():
    theme = (ROOT / "cbb_dashboard/ui.py").read_text()
    assert "rgba(30,13,16,.90)" in theme
    assert "backdrop-filter:none!important" in theme
