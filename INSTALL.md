# Installing and updating

You need a Mac, Python from [python.org](https://www.python.org/downloads/)
(not Apple's built-in one — [why](README.md#macos-permissions--read-this-once-save-a-week)),
and `astropy`. A PC or a second computer is **not** needed.

## First install

1. Install Python from python.org (download, double-click, follow the steps).
2. Open Terminal: press ⌘-Space, type *Terminal*, press Return.
3. Paste this and press Return — it adds the one library the importer needs:

       /usr/local/bin/python3 -m pip install astropy

4. Download the importer (the green **Code** button → **Download ZIP**, or a
   release zip) and double-click it in Downloads to unpack it.
5. In Terminal, paste (use the folder name you actually got):

       cd ~/Downloads/importer-1.4.3 && bash install-scripts.sh

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

## Updating (for example to 1.4.3)

1. Quit the panel if it is running (or just carry on — the installer stops it).
2. Download and unpack the new zip in Downloads, then in Terminal:

       cd ~/Downloads/importer-1.4.3 && bash install-scripts.sh

3. Start the panel again: double-click **Restart FITS Importer** on your
   Desktop, or plug a camera in.

Nothing in your ledger, config, or backed-up frames changes during an update.

## Optional extras

- **An archive on another computer** (the author ships to a Windows PC):
  [PC-SYNC.md](PC-SYNC.md). Skip it otherwise — nothing about it is installed
  until you configure it.
- **Moving where files go**: copy `config.example.json` to
  `~/Library/Application Support/Astro Import/config.json` and edit.
