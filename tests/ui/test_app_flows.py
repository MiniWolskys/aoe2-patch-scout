# SPDX-License-Identifier: GPL-3.0-or-later
"""The app's flows in the page: versions, capture, details, comparison, export, diagnostics."""

from collections.abc import Callable
from typing import Any

from playwright.sync_api import Page, expect
from support.ui_data import calls, change, change_set, fixture_data, startup_data, version

type OpenShell = Callable[..., Page]


def with_versions(*rows: dict[str, Any], **overrides: Any) -> dict[str, Any]:
    """Fixture data whose library already holds some versions."""
    data = fixture_data(startup=startup_data(versions=list(rows)))
    return data | overrides


def test_the_list_shows_every_version_newest_first(open_shell: OpenShell) -> None:
    page = open_shell(data=with_versions(version("new", "PUP build"), version("old", "Live build")))

    expect(page.locator("#versions-count")).to_have_text("2")
    expect(page.locator(".version-row__name")).to_have_text(["PUP build", "Live build"])


def test_a_prerelease_version_is_flagged(open_shell: OpenShell) -> None:
    page = open_shell(data=with_versions(version("one", "PUP", prerelease=True)))

    expect(page.locator(".version-row__marks .icon--warning")).to_have_count(1)


def test_a_version_without_stats_says_so(open_shell: OpenShell) -> None:
    page = open_shell(
        data=with_versions(version("one", "Broken", stats_available=False, stats_reason="test"))
    )

    expect(page.locator(".version-row__marks .tag--muted")).to_have_text("NO STATS")


def test_opening_a_version_shows_its_details(open_shell: OpenShell) -> None:
    page = open_shell(data=with_versions(version("one", "Live build")))

    expect(page.locator("#details-view")).to_be_visible()
    expect(page.locator("#details-title")).to_have_text("Live build")
    expect(page.locator("#first-launch")).to_be_hidden()


def test_the_details_list_the_source_and_the_stats_status(open_shell: OpenShell) -> None:
    page = open_shell(data=with_versions(version("one", "Live build")))

    expect(page.locator("#details-fields")).to_contain_text("D:/Games/AoE2DE")
    expect(page.locator("#details-fields")).to_contain_text("Unit and tech stats are available.")


def test_the_prerelease_tickbox_saves_straight_away(open_shell: OpenShell) -> None:
    page = open_shell(data=with_versions(version("one", "Live build")))

    page.locator("#details-prerelease").check()

    assert calls(page, "update_version")[-1][:3] == ["one", None, True]
    expect(page.locator("#details-prerelease-badge")).to_be_visible()


def test_deleting_a_version_asks_first(open_shell: OpenShell) -> None:
    page = open_shell(data=with_versions(version("one", "Live build")))

    page.locator("#details-delete").click()

    expect(page.locator("#confirm-scrim")).to_be_visible()
    expect(page.locator("#confirm-text")).to_contain_text("Live build")
    page.locator("#confirm-no").click()
    expect(page.locator("#confirm-scrim")).to_be_hidden()
    assert calls(page, "delete_version") == []


def test_the_capture_dialog_offers_the_folder_detection_found(open_shell: OpenShell) -> None:
    data = fixture_data()
    data["candidates"] = [
        {
            "path": "D:/Games/AoE2DE",
            "source": "steam",
            "steam_build_id": "24094652",
            "prerelease_hint": False,
            "game_build": "101.103.48987.0",
        }
    ]
    page = open_shell(data=data)

    page.locator("#capture-button").click()

    expect(page.locator("#capture-scrim")).to_be_visible()
    expect(page.locator("#capture-folder")).to_have_value("D:/Games/AoE2DE")
    expect(page.locator("#capture-folder-help")).to_contain_text("101.103.48987.0")
    expect(page.locator("#capture-label")).not_to_have_value("")


def test_the_capture_dialog_explains_when_nothing_was_found(open_shell: OpenShell) -> None:
    page = open_shell()

    page.locator("#capture-button").click()

    expect(page.locator("#capture-folder-help")).to_contain_text("Click Browse")


def test_a_beta_branch_prefills_the_prerelease_tickbox(open_shell: OpenShell) -> None:
    data = fixture_data()
    data["candidates"] = [
        {
            "path": "D:/Games/AoE2DE",
            "source": "steam",
            "steam_build_id": "1",
            "prerelease_hint": True,
            "game_build": "101.103.48987.0",
        }
    ]
    page = open_shell(data=data)

    page.locator("#capture-button").click()

    expect(page.locator("#capture-prerelease")).to_be_checked()


def test_escape_closes_the_capture_dialog(open_shell: OpenShell) -> None:
    page = open_shell()

    page.locator("#capture-button").click()
    expect(page.locator("#capture-scrim")).to_be_visible()
    page.keyboard.press("Escape")

    expect(page.locator("#capture-scrim")).to_be_hidden()


def test_starting_a_capture_closes_the_dialog_and_shows_progress(open_shell: OpenShell) -> None:
    data = fixture_data()
    data["candidates"] = [
        {
            "path": "D:/Games/AoE2DE",
            "source": "steam",
            "steam_build_id": "1",
            "prerelease_hint": False,
            "game_build": "101.103.48987.0",
        }
    ]
    data["captureStatuses"] = [
        {
            "running": True,
            "label": "Live build",
            "phase": "stats",
            "fraction": 0.4,
            "detail": "",
            "result": {},
        }
    ]
    page = open_shell(data=data)

    page.locator("#capture-button").click()
    page.locator("#capture-start").click()

    expect(page.locator("#capture-scrim")).to_be_hidden()
    assert calls(page, "start_capture")[0][0] == "D:/Games/AoE2DE"
    expect(page.locator(".version-row--capture")).to_be_visible()
    expect(page.locator(".version-row--capture .version-row__meta")).to_contain_text("40%")


def test_the_progress_view_lists_every_step(open_shell: OpenShell) -> None:
    data = fixture_data(
        startup=startup_data(
            capture={
                "running": True,
                "label": "Live build",
                "phase": "icons",
                "fraction": 0.7,
                "detail": "",
                "result": {},
            }
        )
    )
    page = open_shell(data=data)

    expect(page.locator("#capture-view")).to_be_visible()
    expect(page.locator(".step")).to_have_count(7)
    expect(page.locator('.step[data-state="running"] .step__name')).to_have_text("Icons")
    expect(page.locator('.step[data-state="done"]')).to_have_count(4)


def test_the_comparison_opens_with_overall_selected(open_shell: OpenShell) -> None:
    page = open_shell(data=with_versions(version("new", "PUP build"), version("old", "Live build")))

    page.locator(".version-row").nth(1).click(modifiers=["Control"])

    expect(page.locator("#comparison-view")).to_be_visible()
    expect(page.locator("#comparison-title")).to_have_text("Overall")
    expect(page.locator("#picker-old-name")).to_have_text("Live build")
    expect(page.locator("#picker-new-name")).to_have_text("PUP build")


def test_the_comparison_shows_old_and_new_values(open_shell: OpenShell) -> None:
    page = open_shell(data=with_versions(version("new", "PUP build"), version("old", "Live build")))
    page.locator(".version-row").nth(1).click(modifiers=["Control"])

    row = page.locator(".change-row").first
    expect(row.locator(".value-old")).to_have_text("100")
    expect(row.locator(".value-new")).to_have_text("110")
    expect(row.locator(".change-row__name")).to_contain_text("Knight")
    expect(row.locator(".change-row__note")).to_contain_text("all civilizations")


def test_the_civ_list_keeps_the_chronicles_civs_apart(open_shell: OpenShell) -> None:
    page = open_shell(data=with_versions(version("new", "PUP build"), version("old", "Live build")))
    page.locator(".version-row").nth(1).click(modifiers=["Control"])

    expect(page.locator(".civ-list__group")).to_have_text("Chronicles")
    expect(page.locator(".civ-row__name")).to_have_text(["Overall", "Franks", "Spartans"])


def test_a_civ_added_in_the_new_build_shows_a_new_tag(open_shell: OpenShell) -> None:
    page = open_shell(data=with_versions(version("new", "PUP build"), version("old", "Live build")))
    page.locator(".version-row").nth(1).click(modifiers=["Control"])

    expect(page.locator(".civ-row .tag--new")).to_have_count(1)


def test_opening_a_civ_shows_only_its_changes(open_shell: OpenShell) -> None:
    page = open_shell(data=with_versions(version("new", "PUP build"), version("old", "Live build")))
    page.locator(".version-row").nth(1).click(modifiers=["Control"])

    page.get_by_role("button", name="Franks").click()

    expect(page.locator("#comparison-title")).to_have_text("Franks")
    expect(page.locator(".change-row__name")).to_have_text("Archer")


def test_low_priority_changes_are_hidden_until_the_filter_is_on(open_shell: OpenShell) -> None:
    page = open_shell(data=with_versions(version("new", "PUP build"), version("old", "Live build")))
    page.locator(".version-row").nth(1).click(modifiers=["Control"])
    expect(page.locator("ins")).to_have_count(0)

    page.locator("#comparison-filters").click()
    page.locator("#filter-low").check()

    expect(page.locator("del")).to_have_text("unit.")
    expect(page.locator("ins")).to_have_text("foot soldier.")


def test_the_search_filter_narrows_the_list(open_shell: OpenShell) -> None:
    page = open_shell(data=with_versions(version("new", "PUP build"), version("old", "Live build")))
    page.locator(".version-row").nth(1).click(modifiers=["Control"])

    page.locator("#comparison-filters").click()
    page.locator("#filter-search").fill("nothing matches this")

    expect(page.locator(".change-row")).to_have_count(0)
    expect(page.locator("#comparison-changes")).to_contain_text("No changes to show")


def test_swapping_reopens_the_comparison_the_other_way(open_shell: OpenShell) -> None:
    page = open_shell(data=with_versions(version("new", "PUP build"), version("old", "Live build")))
    page.locator(".version-row").nth(1).click(modifiers=["Control"])

    page.locator("#comparison-swap").click()

    assert calls(page, "compare_versions")[-1][:2] == ["new", "old"]


def test_both_versions_are_tagged_in_the_list(open_shell: OpenShell) -> None:
    page = open_shell(data=with_versions(version("new", "PUP build"), version("old", "Live build")))
    page.locator(".version-row").nth(1).click(modifiers=["Control"])

    expect(page.locator('.version-row[data-side="old"]')).to_have_count(1)
    expect(page.locator('.version-row[data-side="new"]')).to_have_count(1)


def test_a_notice_is_shown_above_the_comparison(open_shell: OpenShell) -> None:
    data = with_versions(version("new", "PUP build"), version("old", "Live build"))
    data["changeSet"] = change_set(
        notices=[
            {
                "kind": "unusually_many_changes",
                "message": {
                    "key": "notice.unusually_many_changes",
                    "args": {"percent": 42, "compared": 1000},
                },
            }
        ]
    )
    page = open_shell(data=data)
    page.locator(".version-row").nth(1).click(modifiers=["Control"])

    expect(page.locator("#comparison-notice")).to_be_visible()
    expect(page.locator("#comparison-notice-text")).to_contain_text("42%")


def test_exporting_shows_a_preview_and_the_embargo_reminder(open_shell: OpenShell) -> None:
    page = open_shell(data=with_versions(version("new", "PUP build"), version("old", "Live build")))
    page.locator(".version-row").nth(1).click(modifiers=["Control"])

    page.locator("#comparison-export").click()

    expect(page.locator("#export-scrim")).to_be_visible()
    expect(page.locator("#export-preview")).to_contain_text("Patch Scout")
    # The new side is marked pre-release in the fixture change set.
    expect(page.locator("#export-embargo")).to_be_visible()


def test_saving_an_export_reports_where_it_went(open_shell: OpenShell) -> None:
    page = open_shell(data=with_versions(version("new", "PUP build"), version("old", "Live build")))
    page.locator(".version-row").nth(1).click(modifiers=["Control"])
    page.locator("#comparison-export").click()

    page.locator("#export-html").click()

    expect(page.locator("#export-status")).to_contain_text("export.txt")
    assert calls(page, "save_export")[-1][2] == "html"


def test_settings_show_the_data_folder(open_shell: OpenShell) -> None:
    page = open_shell()

    page.locator("#settings-button").click()

    expect(page.locator("#settings-scrim")).to_be_visible()
    expect(page.locator("#settings-folder")).to_contain_text("PatchScout")
    expect(page.locator("#settings-backups")).to_be_checked()


def test_purging_backups_reports_how_many_went(open_shell: OpenShell) -> None:
    page = open_shell()
    page.locator("#settings-button").click()

    page.locator("#settings-purge").click()

    expect(page.locator("#settings-status")).to_contain_text("3")


def test_diagnostics_show_the_environment_and_the_log(open_shell: OpenShell) -> None:
    page = open_shell()

    page.locator("#diagnostics-button").click()

    expect(page.locator("#diagnostics-scrim")).to_be_visible()
    expect(page.locator("#diagnostics-environment")).to_contain_text("0.0.0-test")
    expect(page.locator("#diagnostics-log")).to_contain_text("save 95%")


def test_the_whole_app_runs_without_console_errors(
    console_errors: list[str], open_shell: OpenShell
) -> None:
    page = open_shell(data=with_versions(version("new", "PUP build"), version("old", "Live build")))
    page.locator(".version-row").nth(1).click(modifiers=["Control"])
    page.get_by_role("button", name="Franks").click()
    page.locator("#comparison-export").click()
    page.locator("#export-close").click()

    assert console_errors == []


def test_a_comparison_of_identical_versions_says_nothing_changed(open_shell: OpenShell) -> None:
    data = with_versions(version("new", "PUP build"), version("old", "Live build"))
    data["changeSet"] = change_set(identical=True, changes=[], civs=[])
    page = open_shell(data=data)

    page.locator(".version-row").nth(1).click(modifiers=["Control"])

    expect(page.locator("#comparison-changes")).to_contain_text("No changes to show")


def test_a_change_with_a_stat_icon_marks_the_field(open_shell: OpenShell) -> None:
    data = with_versions(version("new", "PUP build"), version("old", "Live build"))
    data["changeSet"] = change_set(changes=[change()])
    page = open_shell(data=data)

    page.locator(".version-row").nth(1).click(modifiers=["Control"])

    expect(page.locator('.change-row__stat[data-stat="hp"]')).to_have_count(1)


def test_the_comparison_fits_the_minimum_window(page: Page, open_shell: OpenShell) -> None:
    """The comparison must work at 1120px wide, the minimum window size (D-42)."""
    page.set_viewport_size({"width": 1120, "height": 640})
    open_shell(data=with_versions(version("new", "PUP build"), version("old", "Live build")))
    page.locator(".version-row").nth(1).click(modifiers=["Control"])

    export = page.locator("#comparison-export")
    expect(export).to_be_visible()
    box = export.bounding_box()
    assert box is not None
    assert box["x"] + box["width"] <= 1120
    overflow = page.evaluate(
        "() => document.documentElement.scrollWidth - document.documentElement.clientWidth"
    )
    assert overflow == 0


def test_a_finished_capture_leaves_the_row_to_its_version(open_shell: OpenShell) -> None:
    """Once a capture produced a version, that version's own row replaces the progress row."""
    data = with_versions(version("one", "Live build"))
    data["startup"]["capture"] = {
        "running": False,
        "label": "Live build",
        "phase": "save",
        "fraction": 1.0,
        "detail": "",
        "result": {"capture_id": "one", "stats_available": True},
    }
    page = open_shell(data=data)

    expect(page.locator(".version-row--capture")).to_have_count(0)
    expect(page.locator(".version-row__name")).to_have_text(["Live build"])


def test_a_capture_that_produced_nothing_keeps_its_row(open_shell: OpenShell) -> None:
    data = fixture_data()
    data["startup"]["capture"] = {
        "running": False,
        "label": "Broken",
        "phase": "files",
        "fraction": 1.0,
        "detail": "",
        "result": {"error": "that folder is not an install"},
    }
    page = open_shell(data=data)

    expect(page.locator(".version-row--capture")).to_have_count(1)
    expect(page.locator("#capture-result")).to_contain_text("that folder is not an install")


def test_a_version_can_be_renamed_twice_from_the_keyboard(open_shell: OpenShell) -> None:
    page = open_shell(data=with_versions(version("one", "Live build")))
    title = page.locator("#details-title")

    for name in ("First", "Second"):
        title.focus()
        page.keyboard.press("Enter")
        page.locator("#details-view input.input").fill(name)
        page.keyboard.press("Enter")
        title = page.locator("#details-title")
        expect(title).to_have_text(name)

    assert [call[1] for call in calls(page, "update_version")] == ["First", "Second"]
