# Experiment II held-out extension cases (G2)

Built 2026-09-28 by the orchestrating session and kept outside the repository (`/mnt/SharedData/Research/exp2_hidden`)
while the three extension sessions worked; moved here once the last extension was tagged (research_findings F144,
F146). Categories fixed in docs/heldout_design.md §6 (2026-09-24): "record says the serviceable spare is at the depot
but it sits in another PDU's tray/shelf" and "two identical ORUs with swapped records"; the instances below were never
shown to an extension session.

Both are Mission B with the brief naming the spare by serial (`env.name_serial=true`), the mission form of the visible
case V1 (depot spare ORU-0417 -> PDU-2's shelf, records correct). What differs is the world against the record. The
second loose ORU is ORU-0272 (recorded failed, awaiting return shipment, home `landing_stand/slot_1`), part of the
shared scene every engineer saw.

| case | destination | world (`env.placement`) | record (`env.records`) | what solves it |
|---|---|---|---|---|
| H1 mislocated | PDU-3 shelf | ORU-0417 on **PDU-1's spares shelf**, ORU-0272 on **depot_stand/slot_0**, landing_stand/slot_1 empty | as authored: ORU-0417 at depot slot_0, ORU-0272 at landing slot_1 | read the depot unit (0272, not the named one), find 0417 elsewhere by its serial, deliver it |
| H2 swapped | PDU-1 shelf | ORU-0272 on depot_stand/slot_0, ORU-0417 on **depot_stand/slot_1**, the crate on landing_stand/slot_1 | ORU-0417 at slot_0, ORU-0272 at **slot_1**; the crate's record follows the crate | read both depot units, take the one reading 0417 |

Without reading serials a method takes the unit standing where the record says (ORU-0272 in both) and delivers the
wrong ORU. Precedents (`precedents.md`): H1 situation-level (an ISS cargo transfer bag recorded in one module, found a
year later in another by REALM RFID, NTRS 20210020182); H2 situation-level off-ISS only (THEMIS FM3, a wrong-serial
preamp of the same part number installed, caught by reading the serial labels, PFR-196).

## Files

- `chains/h{1,2}_physical.json` -- the scripted physical checks (every candidate scanned, the real spare picked and
  placed; a temporary engineering contract for scan_label, never committed); `chains/scanview_check.json` -- F145's
  live check of the widened scan view.
- `jobs/*.txt` -- the launch lines as run: `physical` (G2 solvability), `pre` (pre-extension controls at exp2-base),
  `post_ours` + `post_ours_r3` (Ours at exp2-ours, 3 x 2), `post_plexil` (from the PLEXIL checkout at exp2-plexil),
  `post_europa` (from the EUROPA checkout at exp2-europa_plexil), `scanview` + `post_europa_f145` (F145).
- Run directories: `artifacts/runs/exp2/{setup,g2_physical,validation,pre,post,post_superseded,checks}` (moved there
  from the hidden store; absolute paths inside their logs still name the old location). Results: `artifacts/eval/exp2/`
  from `experiments/exp2/tables.py`.
