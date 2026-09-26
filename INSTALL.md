# Installing and updating

The same package installs on a **Mac** or a **Windows 11 PC** — one version,
the same features on both ([PARITY.md](PARITY.md)). Each computer keeps its
own ledger. A second computer is **not** needed.

- [Mac](#first-install-mac)
- [Windows 11](#windows-11)

## First install (Mac)

You need Python from [python.org](https://www.python.org/downloads/) (not
Apple's built-in one — [why](README.md#macos-permissions--read-this-once-save-a-week))
and `astropy`.


1. Install Python from python.org (download, double-click, follow the steps).
2. Open Terminal: press ⌘-Space, type *Terminal*, press Return.
3. Paste this and press Return — it adds the one library the importer needs:

       /usr/local/bin/python3 -m pip install astropy

4. Download the importer (the green **Code** button → **Download ZIP**, or a
   release zip) and double-click it in Downloads to unpack it.
5. In Terminal, paste (use the folder name you actually got):

       cd ~/Downloads/importer-1.5.3 && bash install-scripts.sh

   It copies the engine, panel and camera watcher into `~/bin`, installs the
   app wrapper and a **Restart FITS Importer** button on your Desktop, and
   loads the watcher that notices when a camera is plugged in. Your ledger and
   any `config.json` are never touched.

6. Plug in your Seestar or ASIAir. The panel opens in your browser and scans
   the camera — scanning only reads. Tick what you want and press **Import**.
   The first import starts the ledger and backs everything up, verified byte
   for byte.

macOS may ask once whether Python (or the importer app) may read files on a
removable volume: click **Allow**. If the panel ever says
`Operation not permitted`, double-click **Restart FITS Importer** on your
Desktop — that route always works — and see the permissions section of the
README.

**Already have copies of everything on this Mac?** Before your first import,
run `python3 ~/bin/astro-import.py --baseline` instead: it records what is on
the camera *without copying*, and prints an audit of anything it could not
find on disk. Don't use it otherwise — baselined files are not backed up by
this tool.

## Updating (Mac)

1. Quit the panel if it is running (or just carry on — the installer stops it).
2. Download and unpack the new zip in Downloads, then in Terminal:

       cd ~/Downloads/importer-1.5.3 && bash install-scripts.sh

3. Start the panel again: double-click **Restart FITS Importer** on your
   Desktop, or plug a camera in.

Nothing in your ledger, config, or backed-up frames changes during an update.

To check an install any time: `/usr/local/bin/python3 ~/bin/selftest.py` (every line should say PASS or SKIP).

## Optional extras

- **An archive on another computer** (the author ships to a Windows PC):
  [PC-SYNC.md](PC-SYNC.md). Skip it otherwise — nothing about it is installed
  until you configure it.
- **Moving where files go**: copy `config.example.json` to
  `~/Library/Application Support/Astro Import/config.json` and edit.

## Windows 11

No administrator rights are needed.

1. **Python.** If you don't already have Python 3 from
   [python.org](https://www.python.org/downloads/windows/), install it. On
   the first screen, tick **Add python.exe to PATH**.
2. **Unzip.** Download the importer zip, right-click it → **Extract All…**.
3. **Install.** Open the extracted folder and double-click
   **Install on Windows.cmd**.
   - If Windows says "Windows protected your PC", click **More info** →
     **Run anyway**. The scripts aren't code-signed.
   - The installer adds `astropy` if it's missing.
   - It copies the importer to `%LOCALAPPDATA%\BrettjoAstro\bin`.
   - It starts the camera watcher now and at every logon.
   - It puts **Restart FITS Importer** on your Desktop.
   - When `E:\Astro Image Data` exists, it schedules the ship to it at 09:30
     and 21:30, half an hour after the Mac's.
   - When the PC already runs the archive sweep, it points the sweep at the
     new version, which reads the Mac's and the PC's ship logs.
4. **Plug in the Seestar or ASIAir.** A notification appears and the panel
   opens (`http://127.0.0.1:8765`). Tick what you want and press **Import**.
   The first import starts this PC's own ledger.
   - Frames go to your C: workbench, `%USERPROFILE%\Documents\Astro\…`.
   - Verified frames are then filed into `E:\Astro Image Data`, the same as
     the Mac's ship does.
5. **Check the install** any time. Open **Terminal** (right-click Start →
   Terminal; it opens PowerShell) and run:

       py -3 -X utf8 "$env:LOCALAPPDATA\BrettjoAstro\bin\selftest.py"

   (In the old Command Prompt, write `%LOCALAPPDATA%` instead of
   `$env:LOCALAPPDATA`.)

   Every line should say PASS or SKIP. If anything is red, paste the output
   back to Claude.

**Bring your Mac's settings over** (custom target names, the never-import
list, the scope table — never the ledger):

1. On the Mac:

       python3 ~/bin/astro-import.py --export-settings

   This writes `fits-importer-settings.json` to your Desktop.
2. Copy that file to the PC, for example through the E: share.
3. On the PC, in Terminal:

       py -3 -X utf8 "$env:LOCALAPPDATA\BrettjoAstro\bin\astro-import.py" --import-settings "C:\path\to\fits-importer-settings.json"

   Add `--dry-run` first to preview. It only adds what's missing and never
   overwrites a name the PC already has.

**Updating on Windows:** unzip the new version and double-click
**Install on Windows.cmd** again. Your ledger, config and frames are never
touched.

