"""Focused browser acceptance for period labels and person spirit mapping."""
from __future__ import annotations

import json
from pathlib import Path
from playwright.sync_api import sync_playwright


ROOT = Path(__file__).resolve().parents[1]
URL = "http://127.0.0.1:18134/"
EDGE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
PERIODS = [
    "建党之初和大革命时期",
    "土地革命战争时期",
    "抗日战争时期",
    "解放战争时期",
    "新中国建立与社会主义革命、建设时期",
    "改革开放和社会主义现代化建设新时期",
    "中国特色社会主义新时代",
]


def main() -> None:
    checks: list[str] = []
    errors: list[str] = []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(executable_path=EDGE, headless=True, args=["--no-first-run", "--disable-background-networking"])
        page = browser.new_page(viewport={"width": 1440, "height": 900})
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.goto(URL)
        page.wait_for_function("typeof state !== 'undefined' && state.persons.length >= 20 && state.events.length > 0")

        phase_tabs = page.locator(".history-phase-tab")
        labels = page.locator(".history-phase-tab:not([data-phase='all'])").evaluate_all("tabs => tabs.map(tab => (tab.querySelector('span') || tab).textContent.trim())")
        assert labels == PERIODS, labels
        assert page.locator('[data-phase="land_revolution"] small').inner_text() == "含长征"
        assert page.locator('[data-phase="founding_korea"] small').inner_text() == "新中国巩固时期（含抗美援朝）"
        page.locator('[data-mode="time"]').click()
        page.wait_for_selector('#history-controls:not(.hidden)')
        page.locator('[data-phase="land_revolution"]').click()
        assert page.evaluate("explorer.battleMatchesPhase({start_date:'1935-01-01',end_date:'1935-10-01',phase:'长征'})")
        page.locator('[data-phase="founding_korea"]').click()
        assert not page.evaluate("explorer.battleMatchesPhase({start_date:'1978-01-01',end_date:'1978-12-31',phase:'社会主义建设'})")
        page.locator('[data-phase="construction"]').click()
        assert page.evaluate("explorer.battleMatchesPhase({start_date:'1978-01-01',end_date:'1978-12-31',phase:'改革开放'})")
        checks.append("seven periods, subtitles, battle phase matching and non-overlapping year boundaries")

        options = page.locator("#person-select option").all_inner_texts()
        assert options and all(" · " not in option and not option[:2].endswith(".") for option in options)
        page.locator('[data-mode="person"]').click()
        page.wait_for_function("explorer.journey?.id === state.person.id && !explorer.loading")
        page.locator("#person-spirit-filter").select_option(label="改革创新")
        page.wait_for_function("explorer.journey?.id === state.person.id && !explorer.loading")
        assert page.locator("#person-select option").count() >= 2
        assert page.locator("#person-spirit-filter").input_value() == "改革创新"
        assert page.locator(".person-spirit").is_visible()
        assert page.locator(".person-spirit-evidence").inner_text().startswith("对应行动节点：")
        assert page.locator("[data-node]").count() >= 10
        checks.append("person spirit filter, name-only selector and source-derived journey evidence")

        page.locator('[data-mode="time"]').click()
        page.locator('[data-phase="land_revolution"]').click()
        assert page.locator("#year-input").input_value() == "1935"
        page.set_viewport_size({"width": 390, "height": 844})
        page.wait_for_timeout(150)
        assert page.evaluate("document.documentElement.scrollWidth <= 390")
        checks.append("time phase is visually distinct and remains within a 390px viewport")
        assert not errors, errors
        browser.close()

    report = {"checks": checks, "errors": errors}
    path = ROOT / "自动部署" / "logs" / "phase-spirit-ui-acceptance.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"PASS: {len(checks)} browser checks")


if __name__ == "__main__":
    main()
