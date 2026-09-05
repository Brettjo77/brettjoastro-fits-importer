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
to the night, not to the import attempt. Each camera numbers its own days,
so the same nebula shot on two telescopes keeps two clean, separate stories.

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
it** passes the fingerprint test against your Mac's copies — every file,
JPEG previews and all, which is why photo modes back up their JPEGs
verified alongside the FITs. One unproven file makes the whole folder NOT
SAFE. That's what the word SAFE means in the offer. The default answer is
always No; nothing is deleted without your explicit Yes.

And when the camera holds something the tool does not understand — a new
firmware folder, a file type it has never seen — it says so, plainly, on
the panel and in every report: *on camera, not backed up by this tool*.
What it cannot read, it will never call safe.

The ASIAir is different: it is treated as a **backup of record**, and the
tool will never offer to delete anything from it, full stop.

## Several telescopes, one system

The same importer serves the ZWO ASIAir (recognising which telescope shot
each session from the optics' focal length) and multiple Seestars — S30 Pro,
original S30, S50, S50 Pro — each identified from its own files and given its own
folder tree, its own day numbering, and its own presence-tracking. Plug in
whichever camera you like; the tool works out the rest.

## When things go wrong

Interruptions are expected, not exceptional. A copy that dies mid-file leaves
only a `.partial` that the next run overwrites — never a half-file counted
as a backup. A resumed import picks up exactly where the last one stopped,
skipping everything already proven. And if history ever does get untidy,
repair commands exist to merge split nights, renumber folders, and re-verify
the whole library against the ledger — the same audit you can run any time
for reassurance:

*"5,126 files checked, zero problems"* is what a healthy library says.

## What can never happen

No frame is marked imported without byte-level proof. No deletion is offered
unless everything in the folder is proven backed up, and none happens without
your Yes. The ASIAir is never deleted from at all. An empty or half-mounted
scan can never convince the ledger that files vanished. And the ledger itself
never forgets — archiving your finished work is safe by design.

That's the whole idea: **your photons, provably safe, with a memory.**
