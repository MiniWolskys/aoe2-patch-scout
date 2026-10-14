# SPDX-License-Identifier: GPL-3.0-or-later
"""The app's flows in the page: versions, capture, details, comparison, export, diagnostics."""

from collections.abc import Callable
from typing import Any

from playwright.sync_api import Page, expect
from support.ui_data import (
    PIXEL,
    calls,
    change,
    change_set,
    entry,
    fixture_data,
    open_details,
    show_changes,
    startup_data,
    version,
)

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


def test_the_gear_shows_a_versions_details(open_shell: OpenShell) -> None:
    page = open_shell(data=with_versions(version("one", "Live build")))
    open_details(page)

    expect(page.locator("#details-view")).to_be_visible()
    expect(page.locator("#details-title")).to_have_text("Live build")
    expect(page.locator("#first-launch")).to_be_hidden()


def test_the_details_list_the_source_and_the_stats_status(open_shell: OpenShell) -> None:
    page = open_shell(data=with_versions(version("one", "Live build")))
    open_details(page)

    expect(page.locator("#details-fields")).to_contain_text("D:/Games/AoE2DE")
    expect(page.locator("#details-fields")).to_contain_text("Unit and tech stats are available.")


def test_the_prerelease_tickbox_saves_straight_away(open_shell: OpenShell) -> None:
    page = open_shell(data=with_versions(version("one", "Live build")))
    open_details(page)

    page.locator("#details-prerelease").check()

    assert calls(page, "update_version")[-1][:3] == ["one", None, True]
    expect(page.locator("#details-prerelease-badge")).to_be_visible()


def test_deleting_a_version_asks_first(open_shell: OpenShell) -> None:
    page = open_shell(data=with_versions(version("one", "Live build")))
    open_details(page)

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


def _detected(data: dict[str, Any]) -> dict[str, Any]:
    """Detection finds a live Steam install; a pre-release build sits in another folder."""
    data["candidates"] = [
        {
            "path": "D:/Games/AoE2DE",
            "source": "steam",
            "steam_build_id": "1",
            "prerelease_hint": False,
            "game_build": "101.103.48987.0",
        }
    ]
    data["validations"] = {
        "D:/Games/AoE2DE": {
            "valid": True,
            "path": "D:/Games/AoE2DE",
            "game_build": "101.103.48987.0",
        },
        "E:/Preview/AoE2DE": {
            "valid": True,
            "path": "E:/Preview/AoE2DE",
            "game_build": "101.103.60000.0",
        },
        "C:/Windows": {"valid": False, "reason": "missing resources"},
    }
    return data


def test_a_typed_folder_is_the_one_captured(open_shell: OpenShell) -> None:
    page = open_shell(data=_detected(fixture_data()))
    page.locator("#capture-button").click()
    expect(page.locator("#capture-folder")).to_have_value("D:/Games/AoE2DE")

    page.locator("#capture-folder").fill("E:/Preview/AoE2DE")
    page.locator("#capture-start").click()

    expect(page.locator("#capture-scrim")).to_be_hidden()
    [started] = calls(page, "start_capture")
    assert started[0] == "E:/Preview/AoE2DE"
    assert started[1].startswith("101.103.60000.0")  # the label follows the folder's build


def test_an_invalid_typed_folder_is_never_captured(open_shell: OpenShell) -> None:
    page = open_shell(data=_detected(fixture_data()))
    page.locator("#capture-button").click()
    expect(page.locator("#capture-folder")).to_have_value("D:/Games/AoE2DE")

    page.locator("#capture-folder").fill("C:/Windows")
    page.locator("#capture-start").click()

    expect(page.locator("#capture-folder-help")).to_contain_text("isn't a game install")
    expect(page.locator("#capture-scrim")).to_be_visible()
    assert calls(page, "start_capture") == []


def test_a_label_the_user_typed_is_kept_when_the_folder_changes(open_shell: OpenShell) -> None:
    page = open_shell(data=_detected(fixture_data()))
    page.locator("#capture-button").click()
    expect(page.locator("#capture-folder")).to_have_value("D:/Games/AoE2DE")

    page.locator("#capture-label").fill("Creator build")
    page.locator("#capture-folder").fill("E:/Preview/AoE2DE")
    page.locator("#capture-start").click()

    [started] = calls(page, "start_capture")
    assert started[:2] == ["E:/Preview/AoE2DE", "Creator build"]


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
    # Started from the first-launch screen, with nothing else to show: the progress opens.
    expect(page.locator("#capture-view")).to_be_visible()
    expect(page.locator("#capture-view-meta")).to_contain_text("40%")


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


def test_the_chronicles_civs_have_their_own_tab(open_shell: OpenShell) -> None:
    page = open_shell(data=with_versions(version("new", "PUP build"), version("old", "Live build")))
    page.locator(".version-row").nth(1).click(modifiers=["Control"])

    tabs = page.get_by_role("tab")
    expect(tabs).to_have_count(2)
    expect(tabs.first).to_have_text("Main game")
    expect(tabs.nth(1)).to_contain_text("Chronicles")
    expect(tabs.first).to_have_attribute("aria-selected", "true")
    expect(page.locator(".civ-row__name")).to_have_text(["Overall", "Franks"])

    tabs.nth(1).click()

    expect(tabs.nth(1)).to_have_attribute("aria-selected", "true")
    expect(page.locator(".civ-row__name")).to_have_text(["Spartans"])
    expect(page.locator("#comparison-title")).to_have_text("Spartans")

    tabs.first.click()
    expect(page.locator("#comparison-title")).to_have_text("Overall")


def test_without_chronicles_changes_there_are_no_tabs(open_shell: OpenShell) -> None:
    data = with_versions(version("new", "PUP build"), version("old", "Live build"))
    data["changeSet"] = change_set(civs=[])
    page = open_shell(data=data)
    page.locator(".version-row").nth(1).click(modifiers=["Control"])

    expect(page.locator(".civ-row__name").first).to_have_text("Overall")
    expect(page.get_by_role("tab")).to_have_count(0)


def test_a_civ_added_in_the_new_build_shows_a_new_tag(open_shell: OpenShell) -> None:
    page = open_shell(data=with_versions(version("new", "PUP build"), version("old", "Live build")))
    page.locator(".version-row").nth(1).click(modifiers=["Control"])

    # Spartans are a Chronicles civ: their tab says something new is inside.
    expect(page.get_by_role("tab").nth(1).locator(".tag--new")).to_have_count(1)
    page.get_by_role("tab").nth(1).click()
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
    show_changes(page)
    expect(page.locator("ins")).to_have_count(0)

    page.locator("#comparison-filters").click()
    page.locator("#filter-low").check()

    expect(page.locator("del")).to_have_text("unit.")
    expect(page.locator("ins")).to_have_text("foot soldier.")


def test_objects_with_no_name_are_hidden_until_the_filter_is_on(open_shell: OpenShell) -> None:
    data = with_versions(version("new", "PUP build"), version("old", "Live build"))
    helper = {"kind": "tech", "id": "172", "name": "#172", "where": None, "icon": None}
    data["changeSet"] = change_set(
        changes=[change(), change(category="techs", entity=helper | {"named": False})]
    )
    page = open_shell(data=data)
    page.locator(".version-row").nth(1).click(modifiers=["Control"])
    show_changes(page)
    expect(page.locator(".change-row__name")).to_have_text(["Knight"])

    page.locator("#comparison-filters").click()
    page.locator("#filter-unnamed").check()

    expect(page.locator(".change-row__name")).to_have_text(["Knight", "#172"])


def _with_unreachable(open_shell: OpenShell, **overrides: Any) -> Page:
    """A comparison on its changes, whose answer with unreachable units adds a campaign hero."""
    hero = {"kind": "unit", "id": "2700", "name": "Finn Arnason", "where": None, "icon": None}
    data = with_versions(
        version("new", "PUP build"),
        version("old", "Live build"),
        unreachableChangeSet=change_set(changes=[change(), change(entity=hero)]),
        **overrides,
    )
    page = open_shell(data=data)
    page.locator(".version-row").nth(1).click(modifiers=["Control"])
    show_changes(page)
    expect(page.locator(".change-row__name")).to_have_text(["Knight"])
    page.locator("#comparison-filters").click()
    return page


def _watch_comparing(page: Page) -> None:
    """Remember in `window.__comparingShown` whether the Comparing… view ever shows."""
    page.evaluate(
        """() => {
          window.__comparingShown = false;
          const view = document.getElementById("comparing-view");
          new MutationObserver(() => {
            window.__comparingShown ||= !view.hidden;
          }).observe(view, { attributes: true });
        }"""
    )


def test_the_unreachable_filter_updates_the_list_in_place(open_shell: OpenShell) -> None:
    page = _with_unreachable(open_shell, unreachableDelay=1500)
    _watch_comparing(page)

    page.locator("#filter-unreachable").check()

    status = page.locator("#comparison-updating")
    expect(status).to_be_visible()
    expect(status).to_contain_text("Adding the units civilizations can't get")
    expect(page.locator("#comparison-page")).to_have_attribute("aria-busy", "true")
    expect(page.locator(".change-row__name")).to_have_text(["Knight"])

    expect(page.locator(".change-row__name")).to_have_text(["Knight", "Finn Arnason"])
    expect(status).to_be_hidden()
    expect(page.locator("#comparison-page")).not_to_have_attribute("aria-busy", "true")
    expect(page.locator("#filters-panel")).to_be_visible()
    assert page.evaluate("window.__comparingShown") is False
    assert calls(page, "compare_versions")[-1] == ["old", "new", True]


def test_a_quick_answer_to_the_unreachable_filter_does_not_flash(open_shell: OpenShell) -> None:
    page = _with_unreachable(open_shell)
    page.evaluate(
        """() => {
          window.__updatingShown = false;
          const status = document.getElementById("comparison-updating");
          new MutationObserver(() => {
            window.__updatingShown ||= !status.hidden;
          }).observe(status, { attributes: true });
        }"""
    )

    page.locator("#filter-unreachable").check()

    expect(page.locator(".change-row__name")).to_have_text(["Knight", "Finn Arnason"])
    assert page.evaluate("window.__updatingShown") is False


def test_the_last_click_on_the_unreachable_filter_wins(open_shell: OpenShell) -> None:
    page = _with_unreachable(open_shell, unreachableDelay=1000)

    page.locator("#filter-unreachable").check()
    page.locator("#filter-unreachable").uncheck()

    expect(page.locator("#comparison-updating")).to_be_hidden()
    page.wait_for_timeout(1200)  # the first, slower answer has arrived by now
    expect(page.locator(".change-row__name")).to_have_text(["Knight"])
    expect(page.locator("#comparison-updating")).to_be_hidden()
    expect(page.locator("#filter-unreachable")).not_to_be_checked()


def test_a_failed_unreachable_filter_says_so_and_unticks(open_shell: OpenShell) -> None:
    page = _with_unreachable(open_shell, unreachableError="boom")

    page.locator("#filter-unreachable").check()

    expect(page.locator("#toast")).to_contain_text(
        "The units civilizations can't get couldn't be added"
    )
    expect(page.locator("#filter-unreachable")).not_to_be_checked()
    expect(page.locator("#comparison-updating")).to_be_hidden()
    expect(page.locator(".change-row__name")).to_have_text(["Knight"])
    expect(page.locator("#comparison-view")).to_be_visible()


def test_opening_another_version_drops_a_pending_filter_update(open_shell: OpenShell) -> None:
    page = _with_unreachable(open_shell, unreachableDelay=1000)

    page.locator("#filter-unreachable").check()
    page.locator(".version-row").first.click()

    expect(page.locator("#comparison-view")).to_have_attribute("data-alone", "")
    expect(page.locator("#comparison-updating")).to_be_hidden()
    page.wait_for_timeout(1200)
    expect(page.locator("#comparison-view")).to_have_attribute("data-alone", "")


def test_a_projectile_field_is_labelled_as_part_of_its_shooter(open_shell: OpenShell) -> None:
    data = with_versions(version("new", "PUP build"), version("old", "Live build"))
    nested = {"key": "field.attacks", "args": {"class": "#3"}}
    data["changeSet"] = change_set(
        changes=[change(field={"key": "field.projectile", "args": {"field": nested}})]
    )
    page = open_shell(data=data)
    page.locator(".version-row").nth(1).click(modifiers=["Control"])

    expect(page.locator(".change-row__field")).to_have_text("Projectile: Bonus vs #3")


def test_importing_a_version_opens_it(open_shell: OpenShell) -> None:
    data = with_versions(version("old", "Live build"))
    data["importResult"] = {"imported": True, "capture_id": "old", "added": True}
    page = open_shell(data=data)

    page.locator("#import-button").click()

    expect(page.locator("#toast")).to_contain_text("Version imported.")
    # An imported version opens on its own, in its tech tree (D-52).
    expect(page.locator("#tree-view")).to_be_visible()
    assert calls(page, "compare_versions")[-1][:2] == ["old", "old"]
    assert calls(page, "import_version") == [["C:/tmp/live.aoe2snap"]]


def test_an_archive_that_cant_be_imported_says_why(open_shell: OpenShell) -> None:
    data = with_versions(version("old", "Live build"))
    data["importResult"] = {"imported": False, "error": "newer_version"}
    page = open_shell(data=data)

    page.locator("#import-button").click()

    expect(page.locator("#toast")).to_contain_text("saved by a newer Patch Scout")


def test_exporting_a_pre_release_version_asks_first(open_shell: OpenShell) -> None:
    data = with_versions(version("pup", "PUP", prerelease=True))
    data["details"]["pup"] = data["details"]["__default"] | {
        "capture_id": "pup",
        "prerelease": True,
    }
    page = open_shell(data=data)
    open_details(page)

    page.locator("#details-export").click()
    expect(page.locator("#confirm-title")).to_have_text("Export a pre-release version?")
    page.locator("#confirm-yes").click()

    expect(page.locator("#toast")).to_contain_text("Saved to C:/tmp/live.aoe2snap")
    assert calls(page, "export_version") == [["pup"]]


def test_a_failed_comparison_says_so_and_goes_back(open_shell: OpenShell) -> None:
    data = with_versions(version("new", "PUP build"), version("old", "Live build"))
    data["changeSet"] = None  # the bridge answers nothing usable
    page = open_shell(data=data)
    page.locator(".version-row").nth(1).click(modifiers=["Control"])

    expect(page.locator("#toast")).to_contain_text("The comparison failed")
    expect(page.locator("#comparing-view")).to_be_hidden()


def test_the_image_export_draws_the_page_for_a_video(open_shell: OpenShell) -> None:
    import base64
    import io

    from PIL import Image

    page = open_shell(data=with_versions(version("new", "PUP build"), version("old", "Live build")))
    page.locator(".version-row").nth(1).click(modifiers=["Control"])
    show_changes(page)
    page.locator("#comparison-export").click()
    page.locator("#export-image").click()

    expect(page.locator("#export-status")).to_contain_text("Saved 1 image(s)")
    [[images, name]] = calls(page, "save_images")
    assert name == "Overall"
    png = base64.b64decode(images[0].removeprefix("data:image/png;base64,"))
    with Image.open(io.BytesIO(png)) as drawn:
        assert drawn.size == (1920, 1080)
        # Something was drawn beyond the background: the title, rows and values.
        assert len(drawn.convert("RGB").getcolors(maxcolors=1 << 20) or []) > 50


def test_a_version_that_cant_be_deleted_stays_and_says_why(open_shell: OpenShell) -> None:
    data = with_versions(version("old", "Live build"))
    data["deleteResult"] = {"deleted": False, "error": "locked", "versions": []}
    page = open_shell(data=data)
    open_details(page)
    page.locator("#details-delete").click()
    page.locator("#confirm-yes").click()

    expect(page.locator("#toast")).to_contain_text("couldn't be deleted: locked")
    expect(page.locator("#details-view")).to_be_visible()


def test_an_export_the_system_refuses_says_why(open_shell: OpenShell) -> None:
    data = with_versions(version("new", "PUP build"), version("old", "Live build"))
    data["saveResult"] = {"saved": False, "error": "Access is denied"}
    page = open_shell(data=data)
    page.locator(".version-row").nth(1).click(modifiers=["Control"])
    page.locator("#comparison-export").click()
    page.locator("#export-text").click()

    expect(page.locator("#export-status")).to_contain_text("Couldn't save there: Access is denied")


def test_minor_changes_wait_for_their_filter(open_shell: OpenShell) -> None:
    data = with_versions(version("new", "PUP build"), version("old", "Live build"))
    search = change(field={"key": "field.search_radius", "args": {}}, level="detail")
    data["changeSet"] = change_set(changes=[change(), search], entries=[entry(change(), search)])
    page = open_shell(data=data)
    page.locator(".version-row").nth(1).click(modifiers=["Control"])
    show_changes(page)
    expect(page.locator(".change-row__field")).to_have_text(["Hit points"])

    page.locator("#comparison-filters").click()
    page.locator("#filter-details").check()

    expect(page.locator(".change-row__field")).to_have_text(["Hit points", "Search radius"])


def test_an_effect_sentence_reads_in_words(open_shell: OpenShell) -> None:
    data = with_versions(version("new", "PUP build"), version("old", "Live build"))
    attack = {"key": "field.attacks_basic", "args": {"class": "Pierce"}}
    target = {"key": "effect.class_target", "args": {"class": "Archer"}}
    sentence = change(
        category="techs",
        field={"key": "effect.attribute", "args": {"target": target, "attribute": attack}},
        stat_icon=None,
        old="",
        new="+1",
    )
    data["changeSet"] = change_set(changes=[sentence])
    page = open_shell(data=data)
    page.locator(".version-row").nth(1).click(modifiers=["Control"])

    expect(page.locator(".change-row__field")).to_have_text("Archer class: Pierce attack")


def test_a_unit_with_several_changed_fields_is_one_row(open_shell: OpenShell) -> None:
    data = with_versions(version("new", "PUP build"), version("old", "Live build"))
    speed = change(field={"key": "field.speed", "args": {}}, old="1.35", new="1.4")
    data["changeSet"] = change_set(changes=[change(), speed], entries=[entry(change(), speed)])
    page = open_shell(data=data)
    page.locator(".version-row").nth(1).click(modifiers=["Control"])

    expect(page.locator(".change-row")).to_have_count(1)
    expect(page.locator(".change-row__field")).to_have_text(["Hit points", "Movement speed"])
    expect(page.locator(".value-new")).to_have_text(["110", "1.4"])


def test_long_old_and_new_values_do_not_overlap(open_shell: OpenShell) -> None:
    data = with_versions(version("new", "PUP build"), version("old", "Live build"))
    status = change(
        category="civ_availability",
        field={"key": "field.node_status", "args": {}},
        stat_icon=None,
        old="ResearchRequired",
        new="ResearchedCompleted",
        scope={"kind": "all_except", "civs": ["Achaemenids", "Athenians", "Spartans"]},
    )
    data["changeSet"] = change_set(changes=[status], entries=[entry(status)])
    page = open_shell(data=data)
    page.locator(".version-row").nth(1).click(modifiers=["Control"])
    show_changes(page)

    old = page.locator(".value-old").bounding_box()
    new = page.locator(".value-new").bounding_box()
    note = page.locator(".change-row__note").first.bounding_box()
    assert old is not None and new is not None and note is not None
    assert old["x"] + old["width"] <= new["x"]
    assert new["x"] + new["width"] <= note["x"]


def test_each_change_detail_sits_on_its_own_line(open_shell: OpenShell) -> None:
    data = with_versions(version("new", "PUP build"), version("old", "Live build"))
    commands = [
        change(
            category="techs",
            field={"key": "field.effect_command", "args": {}},
            stat_icon=None,
            old="",
            new=f"type 4 a=2705 b=-1 c={number} d=1",
            detail={
                "key": "detail.effect_command",
                "args": {"effect": "Bodkin Arrow", "command": number},
            },
        )
        for number in (167, 168, 169)
    ]
    data["changeSet"] = change_set(changes=commands, entries=[entry(*commands)])
    page = open_shell(data=data)
    page.locator(".version-row").nth(1).click(modifiers=["Control"])
    show_changes(page)

    details = page.locator(".change-row__detail")
    expect(details).to_have_count(3)
    for index in range(3):
        value = page.locator(".change-values").nth(index).bounding_box()
        detail = details.nth(index).bounding_box()
        assert value is not None and detail is not None
        assert value["y"] <= detail["y"] + detail["height"] / 2 <= value["y"] + value["height"]


def test_a_new_unit_says_how_many_values_it_leaves_out(open_shell: OpenShell) -> None:
    data = with_versions(version("new", "PUP build"), version("old", "Live build"))
    hit_points = change(old="", new="65")
    data["changeSet"] = change_set(
        changes=[hit_points], entries=[entry(hit_points, kind="added", hidden=12)]
    )
    page = open_shell(data=data)
    page.locator(".version-row").nth(1).click(modifiers=["Control"])

    expect(page.locator(".change-row__kind")).to_have_text("Added:")
    expect(page.locator(".change-row__hidden")).to_contain_text("12 more values")


def test_the_search_filter_narrows_the_list(open_shell: OpenShell) -> None:
    page = open_shell(data=with_versions(version("new", "PUP build"), version("old", "Live build")))
    page.locator(".version-row").nth(1).click(modifiers=["Control"])
    show_changes(page)

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
    show_changes(page)

    expect(page.locator("#comparison-notice")).to_be_visible()
    expect(page.locator("#comparison-notice-text")).to_contain_text("42%")


def test_exporting_shows_a_preview_and_the_embargo_reminder(open_shell: OpenShell) -> None:
    page = open_shell(data=with_versions(version("new", "PUP build"), version("old", "Live build")))
    page.locator(".version-row").nth(1).click(modifiers=["Control"])
    show_changes(page)

    page.locator("#comparison-export").click()

    expect(page.locator("#export-scrim")).to_be_visible()
    expect(page.locator("#export-preview")).to_contain_text("Patch Scout")
    # The new side is marked pre-release in the fixture change set.
    expect(page.locator("#export-embargo")).to_be_visible()


def test_saving_an_export_reports_where_it_went(open_shell: OpenShell) -> None:
    page = open_shell(data=with_versions(version("new", "PUP build"), version("old", "Live build")))
    page.locator(".version-row").nth(1).click(modifiers=["Control"])
    show_changes(page)
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


def test_a_change_with_a_stat_icon_shows_the_icon(open_shell: OpenShell) -> None:
    data = with_versions(version("new", "PUP build"), version("old", "Live build"))
    data["changeSet"] = change_set(changes=[change()], stat_icons={"hp": {"hash": "h" * 64}})
    data["icons"] = {"h" * 64: PIXEL}
    page = open_shell(data=data)

    page.locator(".version-row").nth(1).click(modifiers=["Control"])

    expect(page.locator('img.change-row__stat[data-stat="hp"]')).to_have_count(1)


def test_labels_line_up_whether_or_not_their_stat_has_an_icon(open_shell: OpenShell) -> None:
    data = with_versions(version("new", "PUP build"), version("old", "Live build"))
    plain = change(field={"key": "field.search_radius", "args": {}}, stat_icon=None)
    data["changeSet"] = change_set(
        changes=[change(), plain],
        entries=[entry(change(), plain)],
        stat_icons={"hp": {"hash": "h" * 64}},
    )
    data["icons"] = {"h" * 64: PIXEL}
    page = open_shell(data=data)
    page.locator(".version-row").nth(1).click(modifiers=["Control"])
    show_changes(page)
    page.locator("#comparison-filters").click()
    page.locator("#filter-details").check()

    expect(page.locator(".change-row__field")).to_have_count(2)
    slots = page.locator(".change-row__stat")
    expect(slots).to_have_count(2)
    boxes = [slots.nth(index).bounding_box() for index in range(2)]
    assert boxes[0] is not None and boxes[1] is not None
    assert boxes[0]["width"] == boxes[1]["width"] == 18


def test_a_stat_without_an_icon_leaves_no_gap(open_shell: OpenShell) -> None:
    data = with_versions(version("new", "PUP build"), version("old", "Live build"))
    data["changeSet"] = change_set(changes=[change()])
    page = open_shell(data=data)

    page.locator(".version-row").nth(1).click(modifiers=["Control"])

    expect(page.locator(".change-row__stat")).to_have_count(0)


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
    open_details(page)
    title = page.locator("#details-title")

    for name in ("First", "Second"):
        title.focus()
        page.keyboard.press("Enter")
        page.locator("#details-view input.input").fill(name)
        page.keyboard.press("Enter")
        title = page.locator("#details-title")
        expect(title).to_have_text(name)

    assert [call[1] for call in calls(page, "update_version")] == ["First", "Second"]


def test_a_civ_bonus_list_keeps_its_lines_across_the_wide_columns(open_shell: OpenShell) -> None:
    """Vietnamese on 101.103.54800.0: the bonus text read as one squeezed block."""
    data = with_versions(version("new", "PUP build"), version("old", "Live build"))
    bonus = change(
        category="bonuses",
        field={"key": "field.civ_bonus_text", "args": {}},
        stat_icon=None,
        old=None,
        new=None,
        words=[
            {"kind": "same", "text": "Archer civilization\n"},
            {"kind": "removed", "text": "• Conscription free\n"},
            {"kind": "same", "text": "• Archers +20% HP"},
        ],
    )
    data["changeSet"] = change_set(changes=[bonus])
    page = open_shell(data=data)
    page.locator(".version-row").nth(1).click(modifiers=["Control"])
    show_changes(page)

    values = page.locator(".change-values--block")
    expect(values).to_have_count(1)
    expect(values.locator("del")).to_have_text("• Conscription free")
    lines = values.evaluate(r"element => element.innerText.split('\n').filter(Boolean)")
    assert lines == ["Archer civilization", "• Conscription free", "• Archers +20% HP"]
    field = page.locator(".change-row__field")
    values_box, field_box = values.bounding_box(), field.bounding_box()
    assert values_box is not None and field_box is not None
    assert values_box["width"] > field_box["width"]
