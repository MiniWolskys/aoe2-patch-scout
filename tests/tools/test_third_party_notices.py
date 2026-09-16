# SPDX-License-Identifier: GPL-3.0-or-later
"""The generated third-party notices (docs/legal.md checklist)."""

from pathlib import Path

import third_party_notices as notices

REPOSITORY = Path(__file__).resolve().parents[2]


def test_every_bundled_package_is_listed() -> None:
    rendered = notices.render()
    for name in notices.BUNDLED:
        assert f"**{name} " in rendered, name


def test_a_package_that_is_not_installed_is_flagged() -> None:
    assert "check before releasing" in notices.describe("not-a-real-package")


def test_the_licence_of_a_package_without_metadata_comes_from_the_legal_notes() -> None:
    assert "LGPL-3.0" in notices.describe("genieutils-py")


def test_the_notice_says_no_game_content_ships() -> None:
    assert "ships **no game content**" in notices.render()


def test_the_bundled_fonts_and_icons_are_named() -> None:
    rendered = notices.render()
    assert "Barlow Semi Condensed" in rendered
    assert "Lucide" in rendered


def test_the_file_in_the_repository_is_up_to_date() -> None:
    """The release workflow runs the same check before building."""
    assert notices.main(["--check", "--output", str(REPOSITORY / "THIRD_PARTY_NOTICES")]) == 0


def test_writing_the_file_reports_success(tmp_path: Path) -> None:
    target = tmp_path / "NOTICES"
    assert notices.main(["--output", str(target)]) == 0
    assert target.read_text(encoding="utf-8").startswith("# Third-party notices")


def test_the_check_fails_when_the_file_is_missing(tmp_path: Path) -> None:
    assert notices.main(["--check", "--output", str(tmp_path / "absent")]) == 1
