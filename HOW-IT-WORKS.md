# How it works — in plain English

*No code in this document. This is the logic of the BrettjoAstro FITS Importer,
written for astronomers rather than programmers.*

---

## The one promise

Every decision in this tool flows from a single rule: **a frame only counts as
backed up when the copy on your Mac has been proven, byte for byte, to match
the camera.** Not "the copy finished without an error message" — proven, by
reading the file back off your disk and comparing its cryptographic
fingerprint (SHA-256) with the original. Until that proof exists, the tool
treats the frame as *not backed up*, whatever else may have happened.

Everything else — the ledger, the reports, the cleanup offers, the refusal to
ever delete from the ASIAir — is that promise applied consistently.

## What happens when you plug a camera in

A small watcher notices the drive mount, sends a notification, and opens the
control panel in your browser. The panel scans the camera — reading only —
and shows you three things: which targets have new frames (newest night at
the top), which calibration frames would pair with them, and a preview of
exactly which folders the import would create. Nothing has been copied yet;
you are looking at a plan, not a result.

You tick what you want, press Import, and watch. If the tool needs a decision
from you — naming a new target, or linking flats it isn't sure about — it
asks in plain language and waits. When it finishes you get a green banner, a
chime, and a report you can trust.

## The ledger — a memory that never forgets

At the heart of the system is one file: the **ledger**, a lifetime register of
every frame ever imported — its fingerprint, exposure, night, camera, filter,
and where it went. Entries are *never deleted*. When you archive a finished
target off your Mac, its history stays in the ledger, which is why the tool
never re-imports things you archived, and why it can tell you months later
exactly what a given night produced.

The ledger lives in your Mac's Application Support folder, and a mirror copy
is continuously published to a second folder of your choosing. Point that
mirror at iCloud Drive (a one-line setting, and how the author runs it) and
even a full machine rebuild can't erase the tool's memory — tested by fire:
one full Mac wipe, zero history lost. Left at its default, the mirror is
another folder on the same disk: browsable, but not rebuild-proof.

## Day folders

Each target's frames are filed by *observing night*: `M 8_sub Day 1`,
`Day 2`, and so on. A night that gets interrupted — a yanked cable, a crash —
resumes into the **same** Day folder, not a new one; the Day number belongs
to the night, not to the import attempt — and an import that brings two
nights at once files them as two Days. Each camera numbers its own days,
so the same nebula shot on two telescopes keeps two clean, separate stories.

A Seestar also saves *stacks*. Every stacking session keeps its own: a later
stack that simply carries on the same session (same exposure and filter, more
subs) supersedes the earlier one, but a filter change or a restarted stack is
a new session with its own keeper — never "the biggest number tonight wins".
Stacks are only ever added to your Mac, never pruned by an import.

## Calibration — matched, then asked

For ASIAir sessions, the tool keeps a library of every dark, flat, and bias
you've ever shot, and pairs each night's lights with calibration that
actually fits: same gain, same exposure for darks, same filter, same focal
length, same rotator angle, taken near in time. Matching pairs are shown on
the scan card **before** the import, each with a tick-box — untick anything
you disagree with. Darks and biases are exact science and link quietly;
flats are where mistakes hurt, so a flat set that looks like it belongs to a
different setup stops the import and asks you directly, describing itself:
how many frames, what date, what rotation, versus what your lights used.

## What SAFE means

The Seestar fills up, and sooner or later you'll want to clear it. The tool
will only ever offer to delete a camera folder when **every single file in
it** is proven: copied to your Mac and fingerprint-checked there at import,
by *this* camera (two Seestars can write files with identical names), and
unchanged on the camera since — a stack the camera re-saved is copied again
first. One unproven file makes the whole folder NOT SAFE. That's what the
word SAFE means in the offer. The default answer is always No; nothing is
deleted without your explicit Yes. You get the offer after an import, and
any time after that from **clear…** on a row the panel shows as backed up.

Because that Yes can come a while after the question, the tool checks
**again** at the moment of deletion — the same camera still plugged in, every
file still proven — and deletes exactly the files that passed, nothing that
appeared since.

There is exactly one kind of file that doesn't have to be backed up itself:
a JPEG *preview* of a frame that already is. The S50 Pro writes a small JPEG
beside every sub; when the FIT it previews is proven, the JPEG isn't data,
so it isn't imported and it doesn't hold the folder back. A JPEG with no FIT
beside it is different — it's the only copy of whatever it shows, so it
counts like anything else, and the tool tells you it's there.

And when the camera holds something the tool does not understand — a new
firmware folder, a file type it has never seen — it says so, plainly, on
the panel and in every report: *on camera, not backed up by this tool*.
What it cannot read, it will never call safe.

The ASIAir is different: it is treated as a **backup of record**, and the
tool will never offer to delete anything from it, full stop.

## Binning a bad night

Some nights aren't worth keeping — three frames before the cloud came in, a
test slew, a target you'll never process. Importing those just to clear
them clutters the archive, so each Seestar row on the panel has a quiet
*discard…* link. It is the one place in the tool that deletes frames that
were never backed up, so it is built to be hard to do by accident: a red
card tells you exactly what the files are and that they have never been
backed up, and it only proceeds when you **type the word DISCARD** — a click
or a "yes" won't do. It never touches the ASIAir. And it only ever offers
files that were **never** backed up: if everything you picked is in fact
already backed up, it just offers the normal SAFE clear instead; if it's a
mix — tonight's three cloudy frames on a target whose earlier nights are
safely imported, or a few stray JPEGs — it offers exactly the never-backed-up
files and leaves the rest where they are.

Afterwards it may ask whether to never import that target again. Say yes
only if you mean it: *every* future session of it would then be left on the
camera. The panel lists anything on that list with new frames under its own
"NOT backed up" heading, with an **import again** button.

Even then, the tool doesn't forget. Before deleting anything it fingerprints
every file and writes it into a separate part of the ledger for things you
chose to bin — marked "still on the camera" until each delete actually
succeeds, so a file the camera refused to let go of is never counted as
gone. The report lists them under their own heading — never as
backed up — and if those same bytes (fingerprint and all) ever turn up on
the same camera again, they're recognised rather than offered as new.

## Several telescopes, one system

The same importer serves the ZWO ASIAir (recognising which telescope shot
each session from the optics' focal length) and multiple Seestars — S30 Pro,
original S30, S50, S50 Pro — each identified from its own files and given its own
folder tree, its own day numbering, and its own presence-tracking. Plug in
whichever camera you like; the tool works out the rest.

## Mac or Windows — or both

The same importer runs on a Mac and on a Windows 11 PC, built from one set
of files with one version number, so both do exactly the same things (the
few unavoidable differences, like how a plugged-in camera is noticed, are
listed in PARITY.md). On Windows a camera arrives as a drive letter, and the
tool recognises it by what is on it — an `Autorun` folder is the ASIAir, a
`MyWorks` folder is a Seestar.

Each computer keeps **its own ledger**. They are never merged or shared:
a ledger describes copies on *that* machine, and the SAFE rule must never
trust a copy that lives somewhere else. Each publishes to its own mirror
folder, writes its own ship log on the archive, and refuses to adopt the
other's ledger. What *can* travel between them is settings — your custom
target names, the never-import list and the scope table — with one export
and one import.

In the author's setup the PC holds the archive (E:) and does the stacking on
its fast C: drive, so a Windows import lands on C: like the Mac's does in
Documents, and is then filed into the archive on E: and verified there.

## Filing into the archive

If you keep an archive on another computer (PC-SYNC.md), the Mac files its
verified frames into it after an import and twice a day. Calibration frames
go with their lights, into the night's `calibration` folder. The archive's
own names and Day numbers always win.

From 1.7.0 the Mac never deletes, renames or writes over anything on the
archive. It creates each frame under its final name, only if that name is
free, then reads it back. Its log on the archive says "started" before each
frame and "shipped" only after the read-back matched. Because nothing needs
deleting, the share can be set up so that it *can't* delete anything there.

Then the PC checks. It re-reads every shipped frame from its own disk,
bypassing Windows' cache, and only that check makes a frame count as safe in
two places. Every night it also lists the archive and hashes new files, so
the Sync tab still to come can tell what is where. Every five minutes it does
what the Mac asked for and leaves a heartbeat, so the Mac can tell it's awake.

Only one computer files into the archive at a time. The one doing it holds a
lock and renews it every minute, so a lock left by a crash goes stale after
ten minutes instead of blocking the archive for hours.

## The line at the top of the panel

The top of the panel answers one question: are you safe? **Everything is
safe** means every frame you have cleared off a camera also has a checked
copy in the archive. Otherwise it counts the ones that don't yet: **N
frames only on the Mac** (*only on this PC* on Windows) are frames already
cleared from a camera whose one verified copy is still on this computer.
They drop out of the count once the PC's sweep has re-checked their copy in
the archive. Without an archive on another computer they stay in it,
because their only copy really is here. Hover over the count to read this
in a sentence.

A new computer says *Nothing imported yet*. And if the tool can't read its
own ledger, the line says *Status unknown* rather than guess: it never says
safe when it can't tell.

## What you can delete from the Mac

The Dashboard tab has a section called **Space on this Mac**. It shows which folders the importer filed on this computer you can now delete. A frame counts as safe to delete only when the PC's sweep has re-hashed its copy in the archive and it matched.

Everything else is kept:
- frames shipped but not yet re-checked
- frames that aren't in the archive
- frames that have changed since import
- anything in those folders the importer didn't file, such as your processing work

A folder is only ever called safe as a whole when everything in it is safe; otherwise the view names the Day folders that are. The importer never deletes anything from your Mac. You delete the green folders yourself.

## Astro Desk: what is still to process

The panel's **To process** tab (the Archive tab until 1.7.0) opens with the live list from `projects.json` (below). Under it sits a list of every folder on the archive. A folder's state there comes from the live list when the folder is known to it; otherwise from the August 2026 drive scan (the `dataset.json` that scan left on E:, which the importer never updates), marked "(Aug scan)": captured, stacked, or in processing. The biggest come first.

Click a target to see:
- its state and the reason for it
- its hours, nights and filters
- what the folder holds: each night with its frames, the masters, processed files and finished pictures

From there:
- **Open folder:** opens it in File Explorer (Finder on a Mac), ready to drag the nights into PixInsight, SyQon or Lightroom.
- **Open** next to a master or picture: opens it in its usual app, so a master opens in PixInsight.
- **Start Siril here:** starts Siril with that folder as its working folder.
- **Copy path:** copies where the folder is.

The tab only reads. It never changes anything in the archive. It only opens folders and pictures that are inside the archive, never programs.

## The project layer: "you captured this, now process it"

Once frames ship to the archive they are safe — and easily forgotten. `--projects` writes one small file, `projects.json`, that remembers for you. It changes nothing in your frames or the archive: it reads, and writes that one file (plus a copy in Import Status once this computer has published there). It is safe to delete and rebuild at any time.

Where it lands: on the Mac `~/Library/Application Support/Astro Import/projects.json`, on the PC `%LOCALAPPDATA%\Astro Import\projects.json`. To rebuild it:

- Mac, in Terminal: `python3 ~/bin/astro-import.py --projects`
- PC, in Terminal (PowerShell): `py -3 -X utf8 "$env:LOCALAPPDATA\BrettjoAstro\bin\astro-import.py" --projects`

The PC rebuilds it by itself every night (at logon and 03:30, after the archive sweep and inventory), so the PC's list is never older than last night. The PC's list is the complete one: it can see the masters on E: and the finished pictures. The Mac's list says what it could not check.

A **project** is one object in the sky. A **dataset** is that object on one scope (a wide Seestar mosaic and an Askar close-up are two pieces of work). Each dataset gets a status, worked out from facts, never typed in:

- **Capturing** — the last session is recent (within the quiet period, 14 observing nights by default), so you're probably still adding nights. The Archive tab says when the first capturing dataset becomes ready.
- **Ready to process** — the quiet period has passed and nothing has been started. This is the list to look at in front of the telly.
- **In progress** — a master (a file named master…, …integration…, …_stacked…) is saved in the target's folder on the archive (E:). The Seestar's own `Stacked_…` files never count; only your work does. Processing on C: that hasn't been saved to the target's folder isn't seen.
- **Done** — a finished picture in `E:\Final Astro Images` carries the target's catalogue code in its filename (`NGC7023_Iris_Nebula__2026-10_FRA400.jpg`). The scope comes from the filename (FRA400, 107PHQ, S30Pro…) or from the folder it sits in (a folder called `Askar FRA400` or `ZWO Askar Scopes`). A picture that names no scope counts only when the object has one dataset; if it has two, the dataset says "unscoped final" and stays where it was. A filename that names both Askars marks both done.

Nights are noon to noon, like the Day folders, and the quiet period is counted in those nights. To change the 14 days, put `"ASTRO_QUIET_PERIOD_DAYS": 21` (say) in config.json.

**Calibration goes with the session** (Brett, 13 Oct). For an ASIAir dataset the To process row and the Observatory say what darks, flats and bias are linked to its lights (the frames the import paired with that night, in the Day folder's `calibration` folder, and a mosaic's shared set on the target folder), night by night in a target's drawer. A ready set with no darks or flats linked says so in its reason, because it can't be processed without them. The Seestar calibrates itself, so its rows say nothing about calibration. The Mac's calibration links travel to the PC in the ledger snapshot with the lights.

**Where the data is** says "on this Mac" (or "on this PC") only when the frame is still in the importer's folder on this computer right now — you clear your own disks by hand, and the importer checks the disk, not its memory. "On the archive" means the ship has filed it. "On the PC (per its ledger)" means the other computer's ledger says so and this one can't look.

The one fact you can set by hand is per dataset: **open** ("I'm keeping this going all season — leave it as capturing") or **complete** ("that's enough light — count it as ready now"). AstroLog will set it later; until then, make a file called `capture-state.json` in the same folder as `projects.json`, for example:

```
{"datasets": {"NGC7023|FRA400|Shinfield": "open", "M42|S30P|Shinfield": "complete"}}
```

The key is target id, scope id and site, exactly as `projects.json` writes them. A finished picture or a saved master still wins: an object with a final reads done whatever the file says.

The facts come from this computer's ledger, the PC's inventory of the archive, and the `Final Astro Images` folder.

**How the PC knows what the Mac captured.** Each ship leaves a copy of that computer's ledger rows, `ledger-snapshot.json`, in its own folder under the archive's `_verify` (the Mac's in `_verify\mac`). The other computer's `--projects` reads it by itself, so the PC's nightly list carries the Mac's sessions without anyone copying a file. A computer that has never imported (the PC, usually) says so and lists the other's. A snapshot older than 36 hours, or written by a newer importer, is flagged at the top of the list. Another snapshot can still be added with `--with-ledger <file>`; a frame in both is counted once.

**The first time on the PC.** Install 1.7.0 on the Mac first and run one ship, so the snapshot is on the archive. Then install on the PC and run `--projects` once (or press **Refresh** on the Archive tab); after that the nightly sweep keeps it fresh. The panel's **Dashboard** on the PC shows the Mac's record, with a banner saying so and how old it is, because the PC has no ledger of its own.

**The names** come from `contract/targets.json` and `contract/scopes.json` beside the engine (`~/bin/contract` on the Mac, `%LOCALAPPDATA%\BrettjoAstro\bin\contract` on the PC): one list of what each object and each scope is called. `--targets-draft` writes `targets-draft.json` beside `projects.json` with every name in your ledger (and in the other computer's snapshot, so it works on the PC too, with the Mac's custom names) the contract doesn't know. Open it, add each one to `targets.json` as a new target or as an alias on an existing one, and run `--targets-draft` again.

**Editing the contract, and updates.** The file carries its own editing notes at the top. An update replaces your installed copy only when it is still the one we shipped, unchanged (the installer checks its hash against `contract/shipped.sha256`). A copy you have edited is kept, and the newer shipped copy lands beside it as `targets.json.new`: open both, carry your additions across, then delete the `.new`.

**Messages on the Archive tab.** Warnings (an old snapshot, names the contract doesn't know, ledger rows that couldn't be read) sit at the top of the list, in a box you can't miss. What a button did, or why it couldn't, appears under its own row.

Not yet: the Starfront S50 Pro and the rented Tenerife S30 Pro can't be told apart from the home Seestars of the same model, because the importer doesn't record which unit a frame came from. Until it does, their frames count under the Shinfield entry.

On the Mac, "done" isn't checked unless `E:\Final Astro Images` is shared and `"ASTRO_FINALS_DIR": "/Volumes/Final Astro Images"` is in config.json; until then a finished object can show as ready on the Mac. "In progress" needs the share mounted (the masters come from the PC's inventory).

On the To process tab, **To process** and **In progress** sit at the top, newest capture first, with the date the list was worked out and any warnings. Each row shows the scope, where the data is, hours and nights, and has an **Open in Explorer** (**Open in Finder** on the Mac) button straight to that object's folder on the archive. A row not yet on the archive says so instead. The folder list below it is the Observatory's view, for everything else.

## The Observatory: the whole archive at a glance

The panel's **Observatory** tab is the Astro Archive Observatory, the page built in August 2026 from a one-off scan of the drive, now fed by the importer. It opens on an overview, the job first: what each scope captured last (its last three sessions; click a scope's name and the card becomes a calendar timeline of that scope's projects, one row per object with a dot per session, the quiet period shaded, over the last 90 nights, a year or all time), then what to process next on the PC, and under those the headline figure, the two figures that matter (to process, in progress), hours by scope and where the hours went. Then the tabs: Targets, Coverage (every target against every scope), Pipeline, Nights (a heatmap), Sky, Footprints, Equipment (the scopes) and Data health. Click a target anywhere for its story: sessions night by night, and each dataset (one object on one scope) with why it has the state it has, what to do next, and two buttons: **Open in Explorer** (**Open in Finder** on the Mac), straight to its folder on the archive, and **Show in To process**.

Its facts are the To process list's. `--projects` writes two files side by side from one pass, `projects.json` and `observatory.json`, so the two views never disagree; the tab reads the second. They are rebuilt after each import and each ship on the Mac, each night on the PC, and whenever you press **Refresh now** on either tab. The states are the four you know: still capturing, to process, in progress, done. Names, codes and sky positions come from `contract/targets.json`; a target name the contract doesn't know isn't on the page at all (Data health says how many, `--targets-draft` lists them). Nothing is typed in apart from `capture-state.json`, and nothing on the archive is touched.

**Which computer's list you see.** The PC's is the complete one: it sees the masters on the archive and the finished pictures. Each night, after its sweep, the PC publishes its `projects.json` and `observatory.json` into its own folder on the archive (`_verify\pc`). The Mac's panel shows that published list while it is under 48 hours old, and says so at the top; otherwise it shows the Mac's own, with the Mac's limits: "in progress" needs the share mounted and "done" needs `ASTRO_FINALS_DIR`. The PC's list is complete up to the Mac's last ship (that is when the Mac's sessions reach the archive).

**A copy as one file**, to open on another computer or to send: on the Mac, in Terminal, `/usr/local/bin/python3 ~/bin/astro-import.py --observatory`; on the PC, in Terminal (PowerShell), `py -3 -X utf8 "$env:LOCALAPPDATA\BrettjoAstro\bin\astro-import.py" --observatory`. It writes `observatory.html` beside `projects.json` (add a file name after `--observatory` to put it elsewhere; it will never write under the archive, over one of the importer's own files, or over a file that isn't an Observatory page).

**Sky positions.** A target with no position in `contract/targets.json` is listed but sits off the sky map and the footprints. To place it, add `"ra"` (hours, as a decimal) and `"dec"` (degrees, as a decimal) to its entry, as on Andromeda: `"ra": 0.712, "dec": 41.27`. Your copy then counts as edited, so the next update leaves `targets.json.new` beside it to merge.

## When things go wrong

Interruptions are expected, not exceptional. A copy that dies mid-file leaves
only a `.partial` that the next run overwrites — never a half-file counted
as a backup. A resumed import picks up exactly where the last one stopped,
skipping everything already proven. And if history ever does get untidy,
repair commands exist to merge split nights, renumber folders, and re-verify
the whole library against the ledger — the same audit you can run any time
for reassurance:

*"5,126 files checked, zero problems"* is what a healthy library says.

A copy into the archive that is cut off half-way (the PC sleeps, the network
drops) stays "started" in the log and is never counted. The PC moves that
copy, and only it, into `_Quarantine\ship-incomplete`, and the Mac sends the
frame again to the same place. If every byte got there after all, the copy
stays and the Mac's next ship simply records it. The PC never moves anything
else on its own.

## What can never happen

No frame is marked imported without byte-level proof. The cleanup never
offers a folder unless everything in it is proven backed up, and nothing is
cleared without your Yes. The only way to delete frames that were never
backed up is a discard you ask for yourself and confirm by typing the word —
and even that is recorded. The ASIAir is never deleted from at all. An empty or half-mounted
scan can never convince the ledger that files vanished. And the ledger itself
never forgets — archiving your finished work is safe by design.

That's the whole idea: **your photons, provably safe, with a memory.**
