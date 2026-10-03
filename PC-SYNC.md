# Optional: keeping the Mac and a PC archive in sync

*Skip this whole page unless you keep an archive on another computer. Nothing
here is installed until you configure it. Written for a setup like the author's (a
Windows PC sharing `E:\Astro Image Data`, called YOURPC below); change the names
to yours.*

No permanent connection between the machines is needed. When the Mac has something to file it connects to the PC's share by itself, using the password saved in your keychain. The share then stays connected until you eject it, or the Mac sleeps or restarts: the importer never disconnects it. The Mac ships twice a day (09:00 and 21:00) and straight after an import: a Terminal import connects the share first, a panel import ships only when the share is already connected (1.7.0).

The PC then checks every shipped frame from its own disk. Only that check counts as proof that a frame is safe on the archive.

## Part A: on the Mac (about 10 minutes, once)

1. Save the share password in the keychain, once.
   Finder, Go, Connect to Server, type `smb://youruser@YOURPC/AstroImageData` (your PC's name and share), click Connect, enter the password, and tick **Remember this password in my keychain**. Once it has mounted you can eject it; the Mac now knows how to reconnect on its own.

2. Tell the engine where the share lives, once (adds two lines to your config):

       python3 - <<'PY'
       import json,os
       p=os.path.expanduser("~/Library/Application Support/Astro Import/config.json")
       os.makedirs(os.path.dirname(p), exist_ok=True)
       c=json.load(open(p)) if os.path.exists(p) else {}
       c["ASTRO_ARCHIVE_MOUNT"]="/Volumes/AstroImageData"
       c["ASTRO_ARCHIVE_URL"]="smb://youruser@YOURPC/AstroImageData"
       json.dump(c,open(p,"w"),indent=2); print("config updated")
       PY

3. Run (or re-run) the installer — see [INSTALL.md](INSTALL.md). With an archive configured it now also loads the twice-daily ship agent (`com.brettjohnson.astro-ship`).

4. See the plan before anything moves:

       python3 ~/bin/astro-import.py --ship --dry-run

   Expect: the share mounts by itself, then a list of targets with file counts, and on its own line how many of them are calibration frames. Frames that are already on E: are adopted (recorded), not copied again. A frame you gathered into a `lights/lights` folder with Collect Lights is found by its original name at the end of the new one, the same size and the same bytes as the ledger says, and filed under its original name (1.7.0). Anything still not found shows as "missing on Mac" and is skipped for now.

5. Run it for real:

       python3 ~/bin/astro-import.py --ship

   The report ends with "Frames cleared from a camera and not yet PC-verified: N". That number falls to zero once the PC has checked them (Part B).

From here on you do nothing on the Mac: imports ship when the share is up, and the agent catches up at 09:00 and 21:00. If the share can't be reached, the log line says why (the share isn't mounted, the folder has none of the camera folders, or `_verify\mac` can't be written) and nothing is lost: it tries again next time.

## Part B: on the PC (about 5 minutes, once)

From 1.7.0 the PC's side is the importer itself, in Python: the old `sweep.ps1` is retired.

1. Install the importer on the PC: unzip it and double-click **Install on Windows.cmd** (see the Windows section of [INSTALL.md](INSTALL.md)). With `E:\Astro Image Data` in place it also:
   - makes the folders `_verify\pc` (only the PC writes there), `_verify\mac` and `_verify\mac\requests` (the Mac's), `_verify\lock` (the ship lock) and `_Quarantine\ship-incomplete`;
   - sets up the scheduled task **Astro archive sweep**, at every logon and daily at 03:30. It checks every shipped frame (`--sweep`), lists the archive (`--inventory`) and hashes new files (`--hash`), all from this disk;
   - sets up **Astro sync requests**, every 5 minutes. It writes a heartbeat (`_verify\pc\pc-heartbeat.json`) so the Mac can tell the PC is awake, and does what the Mac asked for in `_verify\mac\requests`.

   If an older **Astro archive sweep** was set up from an administrator prompt, the installer can't replace it and says so. Open PowerShell as administrator, run this, then run the installer again:

       Unregister-ScheduledTask -TaskName 'Astro archive sweep' -Confirm:$false

   The old script files (for example `_Index\sweep\sweep.ps1`) stay where they are. They are yours to delete.

2. Run the sweep once now:

       Start-ScheduledTask -TaskName 'Astro archive sweep'

   Wait a few minutes (the first run also lists and hashes the whole archive, which takes a few hours in the background), then look in `E:\Astro Image Data\_verify\pc`:
   - `verified.jsonl` lists every frame the PC has re-read from its own disk, bypassing Windows' cache, and confirmed;
   - `problems.jsonl` should not exist or be empty;
   - `status.json` is the summary, with the same fields as before.

   The old `_verify\verified.jsonl` is still read, and never written again.

3. Back on the Mac, the next ship reads `_verify\pc\verified.jsonl` (and the old file) and stamps the ledger. The "not yet PC-verified" number is the one to watch: zero means the PC holds everything the Mac does. The panel's header shows the same number ("N frames only on the Mac"), and says "Everything is safe" at zero.

## Part C: the share's rights (1.7.0, once both computers have 1.7.0)

From 1.7.0 the share's user (`astro`) can be denied Delete on the archive (decision D7), so nothing on the Mac can ever delete, rename or move a frame there. The ship no longer needs Delete: it creates each frame under its final name, only if that name is free, and reads it back. Leave the rights as they are until **both** computers run 1.7.0: an older Mac's ship needs Delete and would just go quiet.

1. On the PC, try the new rights on a test folder first. Open PowerShell as administrator:

       cd "$env:LOCALAPPDATA\BrettjoAstro\bin\pc"
       powershell -ExecutionPolicy Bypass -File .\set-archive-rights.ps1 -Scratch -Apply

   This makes `E:\Astro Image Data\_rights-check`, laid out like the archive, with the new rights on it. Nothing else changes. Without `-Apply` it only shows what it would do.

2. On the Mac, with the share mounted, in Terminal:

       /usr/local/bin/python3 ~/bin/astro-import.py --check-share-rights

   It tries each thing the Mac may and may not do there (create and write a frame, never delete or rename one; write only in `_verify\mac` and `_verify\lock`) and marks each answer PASS or FAIL. All PASS means the rights are right. A FAIL on the very first line means macOS can't create a file under these rights: leave the archive as it is and tell Claude.

3. When every answer is PASS, put the rights on the archive itself (PowerShell as administrator, same folder):

       powershell -ExecutionPolicy Bypass -File .\set-archive-rights.ps1 -Apply

   It saves today's rights first (in `%LOCALAPPDATA%\Astro Import\rights-backup`) and prints the commands that put them back exactly. It also lists any folder that doesn't take rights from above (the new rule can't reach those), and says if the share itself gives `astro` Full Control. The importer needs only Change there; with Full Control, `astro` could change the rights on the frames it filed. The script prints the two commands that set Change. To take the new rights off again:

       powershell -ExecutionPolicy Bypass -File .\set-archive-rights.ps1 -Undo -Apply

   Delete `_rights-check` on the PC yourself when you no longer need it.

With these rights Finder on the Mac can't rename, move or bin anything on the share either. That's the point: tidy the archive on the PC. What they guard against is accidents (Finder, a script, a bug); they can't stop someone who has the share's password from changing a file's contents, so the PC's own backups still matter.

The PC's two tasks run while you are signed in to the PC (a locked screen is fine). Signed out, nothing runs and the Mac sees the PC as asleep.

## A copy that was cut off half-way

If the share goes away in the middle of a copy (the PC sleeps, the network drops), the unfinished copy stays on the archive under the frame's real name. The Mac can't remove it, and never tries.

- The Mac's log in `_verify\mac\shipped.jsonl` says "started" for that frame and never "shipped", so the frame is not counted as shipped and the Mac asks the PC for a sweep straight away.
- Once no ship is running and ten minutes have passed, the PC moves that copy, and only it, into `_Quarantine\ship-incomplete\`, under the same path. It notes the move in `_verify\pc\quarantine.jsonl`. This is the one thing the PC moves by itself.
- The Mac's next ship sends the frame again, to the same path and the same Day.
- If every byte arrived after all (only the "shipped" row, or the read-back over the share, failed), the PC reads the copy whole and correct and leaves it, and the Mac's next ship records it as shipped without sending it again.

The PC never moves anything else: not frames you copied by hand, not your processing files, not a file that was there before that ship started, and not one bigger than the frame being sent. Those turn up as a line in `problems.jsonl` instead. Remove anything in `_Quarantine` yourself once you're happy.

Copies a 1.6 ship left behind (names ending `.partial`, `.mac.partial` or `.BAD`) are listed by every sweep, in `status.json` and the sweep's log, and left where they are. To move them into `_Quarantine\old-partials` (PowerShell on the PC):

    py -3 -X utf8 "$env:LOCALAPPDATA\BrettjoAstro\bin\astro-import.py" --sweep --move-old-partials

## If the PC runs the importer too (1.5.0)

The importer also runs on Windows 11: see the Windows section of [INSTALL.md](INSTALL.md) and [PARITY.md](PARITY.md). The PC then imports to its own workbench on C: and ships into `E:\Astro Image Data` with the same code, at 09:30 and 21:30, half an hour after the Mac. It keeps its own ledger, and from 1.7.0 writes its ship log in its own folder, `_verify\pc\shipped-pc.jsonl`. The sweep reads every computer's log, the old ones in `_verify` too. Only one computer ships at a time: the lock is `_verify\lock\ship.lock`, renewed every minute by the computer that holds it. Another computer breaks it only after ten minutes without renewal, and notes that in its own ship log.

## If something looks wrong

- **The share doesn't mount by itself:** repeat Part A step 1 and make sure the keychain box was ticked.
- **Ship says "not reachable":** the line says why. "The share isn't mounted": the PC is off or asleep; nothing is lost, it retries next time. "Can't write in _verify/mac" with "Privacy & Security": macOS is keeping the ship away from the share; allow it in System Settings, Privacy & Security.
- **"N file(s) wait for the PC to set aside an unfinished copy":** see the section above; the PC sets them aside within minutes when it's awake, and at 03:30 otherwise.
- **`problems.jsonl` has lines:** look at each one; those files are never retried by themselves.
- **Logs:** on the Mac, `~/Library/Logs/astro-ship.log`. On the PC, `E:\Astro Image Data\_verify\pc\sweep_*.log`, and the importer's own `%LOCALAPPDATA%\Astro Import\Logs\astro-import.console.log`.
