# Contract changes for Observatory UX phase 1 (contract/targets.json, 25 Oct 2026)

For Brett. Every change to `contract/targets.json` made in this phase, and the things
left alone for you to decide. The new file's hash is in `contract/shipped.sha256`
(`10a7e46637053b4666c375f47b1c780bb98ba6ec0510a1012b87bb84fa6d8185`), so the installers
will update an unedited installed copy; an edited one gets the new copy beside it as
`targets.json.new`.

No name, alias or code was added or changed. No entry was added, removed or merged.

## 1. Filled in (plan §6.6)

| Target | Field | Was | Now |
| --- | --- | --- | --- |
| LDN 1373, Middle Heart Nebula | type | (empty) | Dark nebula |
| LDN 1373, Middle Heart Nebula | constellation | (empty) | Cassiopeia |
| Barnard 144, Fish on a Platter Nebula | type | (empty) | Dark nebula |
| Barnard 144, Fish on a Platter Nebula | constellation | (empty) | Cygnus |

RA/Dec were not added for either: I am not sure enough of the values to write them
into the file. If you want them, say so and give me a source (or your AstroLog entry).

## 2. One spelling per kind: the bare "Nebula" labels (plan §6.6)

Fourteen entries said just "Nebula". Each is changed only where the object's identity
makes the kind certain. After this, no entry is a bare "Nebula".

| Target | Was | Now |
| --- | --- | --- |
| M 16, Eagle Nebula | Nebula | Emission nebula |
| M 42, Orion Nebula | Nebula | Emission nebula |
| NGC 6888, Crescent Nebula | Nebula | Emission nebula (see note A) |
| NGC 7000, North America Nebula | Nebula | Emission nebula |
| NGC 7023, Iris Nebula | Nebula | Reflection nebula |
| NGC 7380, Wizard Nebula | Nebula | Emission nebula |
| NGC 7635, Bubble Nebula | Nebula | Emission nebula |
| IC 1318, Sadr Region | Nebula | Emission nebula |
| IC 1805, Heart Nebula | Nebula | Emission nebula |
| IC 5067, Pelican Nebula | Nebula | Emission nebula |
| C 9 / Sh2-155, Cave Nebula | Nebula | Emission nebula |
| Sh2-129, Flying Bat and Squid Nebulae | Nebula | Emission nebula (see note B) |
| Sh2-132, Lion Nebula | Nebula | Emission nebula |
| Sh2-171, Teddy Bear Nebula | Nebula | Emission nebula |

Note A. The Crescent is an emission nebula blown by a Wolf-Rayet star. Thor's Helmet
(NGC 2359) is the same kind of object and is labelled "Wolf-Rayet nebula" in the file.
I left Thor's Helmet as it is (it was not a bare "Nebula") and gave the Crescent the
common label. If you would rather both say "Wolf-Rayet nebula", or both "Emission
nebula", say which.

Note B. Sh2-129 (the Flying Bat) is an HII region; the Squid (Ou 4) inside it is a
bipolar outflow, not an HII region. The entry is the pair, under the Sh2 code, so it
takes "Emission nebula".

The kind labels now in use (one spelling each): Emission nebula, Dark nebula,
Reflection nebula, Planetary nebula, Supernova remnant, Galaxy, Open cluster,
Globular cluster, plus the specific ones already there: Cluster + nebula (NGC 2264),
Wolf-Rayet nebula (NGC 2359), Interstellar comet, Star, Galaxy group, Milky Way region.
The test suite (chain HN) now fails if a bare "Nebula" comes back or a new spelling
appears.

## 3. Left alone, for you to decide (not in the brief)

These 19 entries still have no type or constellation. They were not asked for, so I
did not touch them. Suggested values, if you want them filled in one go:

| Target | Suggested type | Suggested constellation |
| --- | --- | --- |
| M 83, Southern Pinwheel Galaxy | Galaxy | Hydra |
| NGC 253, Sculptor Galaxy | Galaxy | Sculptor |
| NGC 1333, Reflection Nebula | Reflection nebula | Perseus |
| NGC 2070, Tarantula Nebula | Emission nebula | Dorado |
| NGC 2736, Pencil Nebula | Supernova remnant | Vela |
| NGC 3372, Carina Nebula | Emission nebula | Carina |
| NGC 5128, Centaurus A | Galaxy | Centaurus |
| NGC 5139, Omega Centauri | Globular cluster | Centaurus |
| NGC 6334, Cat's Paw Nebula | Emission nebula | Scorpius |
| NGC 6357, Lobster Nebula | Emission nebula | Scorpius |
| NGC 6369, Little Ghost Nebula | Planetary nebula | Ophiuchus |
| NGC 6559, Emission Nebula | Emission nebula | Sagittarius |
| IC 2177, Seagull Nebula | Emission nebula | Monoceros |
| IC 4604, Rho Ophiuchi | Reflection nebula | Ophiuchus |
| IC 1318A, Sadr Region, part A | Emission nebula | Cygnus |
| Sh2-261, Lower's Nebula | Emission nebula | Orion |
| LDN 1622, Boogeyman Nebula | Dark nebula | Orion |
| Sh2-157, Lobster Claw Nebula | Emission nebula | Cassiopeia |
| Comet 3I/ATLAS | (has Interstellar comet) | none: it moves |

The Squid: plan §6.6 also names "the Squid". It is already merged into Sh2-129
(18 Oct), which now carries "Emission nebula" and Cepheus, so nothing more was needed.

## 4. Two things the plan asks to report, not change (§6.6)

- The 2 target names the importer doesn't recognise (184 frames): run
  `--targets-draft` on the PC to list them; nothing was added here.
- "Dark nebula LDN 386" / "Eagle Nebula (LDN 386)": LDN 386 was merged into M 16 on
  18 Oct, so those frames count under the Eagle. The archive folder named
  "Eagle Nebula (LDN 386)" is untouched (the archive's names always win).
