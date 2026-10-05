"""Static contracts for the visible history and red-spirit presentation."""
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INDEX = (ROOT / "static" / "index.html").read_text(encoding="utf-8")
APP = (ROOT / "static" / "app.js").read_text(encoding="utf-8")
EXPLORER = (ROOT / "static" / "history-explorer.js").read_text(encoding="utf-8")
AI = (ROOT / "static" / "ai-panel.js").read_text(encoding="utf-8")
CSS = (ROOT / "static" / "app.css").read_text(encoding="utf-8")


def test_time_module_uses_the_seven_standard_periods():
    labels = [
        "建党之初和大革命时期",
        "土地革命战争时期",
        "抗日战争时期",
        "解放战争时期",
        "新中国建立与社会主义革命、建设时期",
        "改革开放和社会主义现代化建设新时期",
        "中国特色社会主义新时代",
    ]
    for label in labels:
        assert label in INDEX
        assert f"label: '{label}'" in EXPLORER
    assert 'data-phase="long_march"' not in INDEX
    assert "state.timePhase === 'long_march'" not in EXPLORER
    assert "state.timePhase === 'land_revolution' && state.year >= 1934" in EXPLORER
    assert "phaseAliases" in EXPLORER
    assert "'长征'" in EXPLORER


def test_event_and_time_controls_have_distinct_visual_hooks():
    assert '.mode-tab[data-mode="time"].active' in (ROOT / "static" / "app.css").read_text(encoding="utf-8")
    assert ".history-controls" in (ROOT / "static" / "app.css").read_text(encoding="utf-8")
    assert "border-top:3px solid var(--green)" in (ROOT / "static" / "app.css").read_text(encoding="utf-8")


def test_person_options_show_names_without_pinyin_initial_prefix():
    assert '<option value="${safeText(person.id)}">${safeText(person.name)}</option>' in APP
    assert '${safeText(initial)} · ${safeText(person.name)}' not in APP


def test_red_spirit_is_visible_and_people_are_mapped_to_keywords():
    assert 'id="spirit-manifesto-title"' in INDEX
    assert "本事件体现的红色精神" in APP
    assert "const PERSON_SPIRITS =" in EXPLORER
    assert EXPLORER.count("': [") >= 20
    assert 'id="person-spirit-filter"' in INDEX
    assert "person-spirit-evidence" in EXPLORER


def test_navigation_drawer_and_category_focus_hooks_exist():
    assert 'id="mobile-nav-toggle"' in INDEX
    assert 'id="event-list-drawer"' in INDEX
    assert "function focusEvent(event)" in APP
    assert "function setEventListDrawer(expanded)" in APP
    assert ".controlbar.nav-collapsed" in CSS


def test_speech_fallback_finishes_and_expands_drawer():
    assert "window.setEventListDrawer?.(false)" in AI
    assert "window.setEventListDrawer?.(true)" in AI
    assert "speechTimer" in AI
    assert "utterance.onend = finish" in AI


def test_anti_japanese_category_uses_year_boundaries():
    assert "year >= 1937 && year <= 1945" in APP
    assert "year >= 1927 && year <= 1936" in APP
    assert "(!hasYear && themes.includes(\"anti_japanese\"))" in APP


def test_map_content_layers_reduce_desktop_visual_clutter():
    assert "event-cluster-marker" in APP
    assert "coordinateCounts" in APP
    assert "renderEventListDrawer(group)" in APP
    assert "state.mode === 'person' || state.mode === 'time'" in APP
    assert "source_location_envelope" in EXPLORER
    assert "troop-count-marker" in EXPLORER
    assert ".troop-player-control.is-collapsed" in CSS
