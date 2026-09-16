# SPDX-License-Identifier: GPL-3.0-or-later
"""The frozen app's entry point: PyInstaller needs a script, not a console-script name."""

import sys

from patch_scout.gui.app import main

if __name__ == "__main__":
    sys.exit(main())
