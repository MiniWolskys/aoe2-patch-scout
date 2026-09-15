# Packaging reference

Facts about building the Windows app, checked in the M0 packaging spike on 2026-09-15:
- **Environment:** Windows 10, Python 3.12.14, PyInstaller 6.22.3, pywebview 6.2.1, genieutils-py 0.1.2.
- **Re-check this page** when any of these versions changes.
- **The spike build was throwaway.** The release build is set up in M5 (D-16).

## One-folder build [verified]

- **Form:** a PyInstaller one-folder, windowed build (no console), made from a `.spec` file. It takes about 12 s with `--clean`.
- **Output:** the exe plus an `_internal\` folder (PyInstaller's default `contents_directory`): 161 files and 28.8 MB, or 12.8 MB zipped.
- **Largest items:** `libcrypto-3-x64.dll` (7.8 MB), `python312.dll` (6.8 MB), the exe with its archive (4.6 MB), `pythonnet\` (3.3 MB) and `libssl-3-x64.dll` (1.5 MB).
  - OpenSSL (9.3 MB in total) is bundled even though the app makes no network calls. Excluding it wasn't tried.
- **Startup:** the window appears in under 1 s, and the page has loaded after about 1.2 s.
- **Paths with spaces:** the build runs unchanged from a folder whose path contains a space.

## genieutils-py as loose, replaceable files (LGPLv3 §4) [verified]

**Spec settings:**

```python
a = Analysis(
    ...,
    hiddenimports=collect_submodules("genieutils"),   # every module, not only the imported ones
    module_collection_mode={"genieutils": "py"},     # .py source files instead of the exe's archive
)
```

- **Where they go:** the modules land as `.py` files in `_internal\genieutils\` and load through `SourceFileLoader`. Without the setting, they load from the exe's archive (`PyiFrozenLoader`).
- **Replaceable:** in a copy of the build, an edit to `_internal\genieutils\versions.py` took effect on the next start, without rebuilding.
- **No bytecode:** the frozen app doesn't write bytecode, so no stale `__pycache__` gets in the way.
- **Documentation:** the setting is described in [PyInstaller's hooks documentation](https://pyinstaller.org/en/v6.22.3/hooks.html). As an `Analysis` argument it is documented in the installed source (`PyInstaller\building\build_main.py`), not on the spec-file page.

## WebView2 engine detection [verified]

- **How pywebview picks the engine on Windows:** it uses WinForms, and picks Edge Chromium (`edgechromium`) when the WebView2 Runtime is registered and .NET 4.6.2 or later is installed (`webview\platforms\winforms.py`, `_is_chromium`).
- **Missing runtime: pywebview doesn't fail.** It logs "MSHTML is deprecated" and silently runs on MSHTML, the Internet Explorer 11 engine.
  - If the runtime is registered but fails to start, pywebview logs an error and the window stays blank.
- **Which engine is running:** `webview.renderer`, e.g. `"edgechromium"` or `"mshtml"`.
- **Detecting the runtime before start,** with [Microsoft's documented check](https://learn.microsoft.com/en-us/microsoft-edge/webview2/concepts/distribution):
  - Read the `pv` value under `HKLM\SOFTWARE\WOW6432Node\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}` (64-bit Windows), or the same key under `HKCU\Software\Microsoft\EdgeUpdate\Clients\`.
  - The runtime is installed when that value exists and isn't `0.0.0.0`.
  - On the test machine: HKLM `pv` = `153.0.4234.32`; no HKCU key.
  - The .NET call `CoreWebView2Environment.GetAvailableBrowserVersionString` agrees, but it works only once pywebview has loaded the WebView2 assemblies. So the registry check is the one to use before start.
- **Download page for users:** https://developer.microsoft.com/microsoft-edge/webview2/consumer/
- **What the app does (D-40, `gui/webview2.py`, `gui/app.py`):**
  1. Before `webview.start`, it reads both `pv` values above. A missing or empty value, or `0.0.0.0`, means not installed.
  2. If the runtime is missing, a native Windows message box (`MessageBoxW`, text from the i18n catalog) offers to open the download page. **Yes** hands the URL to the user's default browser; either way the app exits with code 1 and opens no window. The app itself makes no network access (D-02).
  3. After start, if `webview.renderer` isn't `"edgechromium"`, the same message shows and the window closes.

## Serving the frontend

- **pywebview serves local pages through Bottle,** which picks each file's type with Python's `mimetypes`.
  - On Windows, `mimetypes` also reads the registry, which other software can change.
  - Chromium refuses ES modules served as `text/plain`.
- **So the app pins the types it serves** before starting (`gui/web_files.py`): `text/javascript` for `.js`, `text/css`, `image/svg+xml`, `font/ttf`.
  - On the dev machine (2026-09-15), `.js` already mapped to `text/javascript`, and `.ttf` to nothing.
- **Page path:** pywebview resolves a relative page path against `sys.argv[0]`, which is `.venv\Scripts` under `uv run` (`webview/util.py`, `get_app_root`). The app passes the absolute path of `index.html`.

## Antivirus and SmartScreen

- **Microsoft Defender** [verified]: a custom scan without elevation (`MpCmdRun -Scan -ScanType 3`) found no threats in the build folder or its zip. A local scan isn't the same as the reputation check Windows runs on a downloaded file.
- **SmartScreen** [verified by the maintainer]: it only reacts to files that carry the Mark of the Web, e.g. a zip downloaded from GitHub.
  - **How it was tested:** the mark (`Zone.Identifier` stream, `ZoneId=3`) was added to a copy of the spike zip, which was then extracted with Explorer's Extract All.
  - **First run:** "Windows protected your PC" appeared, and **Run anyway** worked.
  - **Later runs:** no warning for that extracted copy.
  - **So** every user of an unsigned build sees the warning once. The release notes need to explain it (see [legal.md](../legal.md#code-signing-o-6)).
