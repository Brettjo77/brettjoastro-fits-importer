# Optional: keeping the Mac and a PC archive in sync

*Skip this whole page unless you keep an archive on another computer. Nothing
here is installed until you configure it. Written for the author's setup (a
Windows PC called SKYLARKPC sharing `E:\Astro Image Data`); change the names to
yours.*

No permanent connection between the machines is needed. The Mac connects to the PC's share only when it has something to file, using the password saved in your keychain, and disconnects when done. Checks run twice a day (09:00 and 21:00) plus straight after every import.

## Part A: on the Mac (about 10 minutes, once)

1. Save the share password in the keychain, once.
   Finder, Go, Connect to Server, type `smb://astro@SKYLARKPC/AstroImageData` (your PC's name and share), click Connect, enter the password, and tick **Remember this password in my keychain**. Once it has mounted you can eject it; the Mac now knows how to reconnect on its own.

2. Tell the engine where the share lives, once (adds two lines to your config):

       python3 - <<'PY'
       import json,os
       p=os.path.expanduser("~/Library/Application Support/Astro Import/config.json")
       os.makedirs(os.path.dirname(p), exist_ok=True)
       c=json.load(open(p)) if os.path.exists(p) else {}
       c["ASTRO_ARCHIVE_MOUNT"]="/Volumes/AstroImageData"
       c["ASTRO_ARCHIVE_URL"]="smb://astro@SKYLARKPC/AstroImageData"
       json.dump(c,open(p,"w"),indent=2); print("config updated")
       PY

3. Run (or re-run) the installer — see [INSTALL.md](INSTALL.md). With an archive configured it now also loads the twice-daily ship agent (`com.brettjohnson.astro-ship`).

4. See the plan before anything moves:

       python3 ~/bin/astro-import.py --ship --dry-run

   Expect: the share mounts by itself, then a list of targets with file counts. The S50 Pro targets appear because they are not yet stamped in the ledger; they will be adopted (already on E:), not recopied. Any frames you moved out of their Day folders by hand show as "missing on Mac" and are skipped for now.

5. Run it for real:

       python3 ~/bin/astro-import.py --ship

   The report ends with "Frames cleared from a camera and not yet PC-verified: N". That number falls to zero after Part B has run.

From here on you do nothing on the Mac: every import ships by itself when the PC is on, and the agent catches up at 09:00 and 21:00.

## Part B: on the PC (about 3 minutes, once)

1. Copy the `pc` folder from the zip to somewhere permanent, for example `E:\Astro Image Data\Claude outputs\pc`.

2. Open PowerShell as administrator (right-click, Run as administrator), go to that folder, and register the sweep:

       cd "E:\Astro Image Data\Claude outputs\pc"
       powershell -ExecutionPolicy Bypass -File .\install_sweep.ps1

   It registers a scheduled task called **Astro archive sweep** that runs at every logon and daily at 03:30.

3. Run it once now:

       Start-ScheduledTask -TaskName 'Astro archive sweep'

   Wait a minute, then look in `E:\Astro Image Data\_verify`: `verified.jsonl` lists every file the PC has re-hashed and confirmed, `problems.jsonl` should not exist or be empty, `status.json` is the summary.

4. Back on the Mac, the next ship (09:00, 21:00, or `python3 ~/bin/astro-import.py --ship`) reads `verified.jsonl` and stamps the ledger. The "not yet PC-verified" number is the one to watch; zero means the PC holds everything the Mac does.

## If something looks wrong

The share does not mount by itself: repeat Part A step 1 and make sure the keychain box was ticked. Ship says "not reachable": the PC is off or asleep; nothing is lost, it retries next time. `problems.jsonl` has lines: look at each one; those files are never retried silently. Logs: `~/Library/Logs/astro-ship.log` on the Mac, `E:\Astro Image Data\_verify\sweep_*.log` on the PC.
