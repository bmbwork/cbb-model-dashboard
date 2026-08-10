from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_help_dots_use_visible_css_tooltip_not_native_title_only():
    app = (ROOT / "app.py").read_text(encoding="utf-8")
    intel = (ROOT / "cbb_dashboard" / "intelligence.py").read_text(encoding="utf-8")
    ui = (ROOT / "cbb_dashboard" / "ui.py").read_text(encoding="utf-8")

    assert 'class="help-dot" data-tooltip=' in app
    assert 'class="help-dot" data-tooltip=' in intel
    assert 'class="help-dot" title=' not in app
    assert 'class="help-dot" title=' not in intel
    assert '.help-dot::after' in ui
    assert 'content:attr(data-tooltip)' in ui
    assert '.help-dot:hover::after' in ui
    assert '.help-dot:focus::after' in ui


def test_help_dots_are_keyboard_focusable():
    app = (ROOT / "app.py").read_text(encoding="utf-8")
    intel = (ROOT / "cbb_dashboard" / "intelligence.py").read_text(encoding="utf-8")
    assert 'tabindex="0"' in app
    assert 'tabindex="0"' in intel
