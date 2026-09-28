# Spaceflight precedents for two logistics situations

Compiled 2026-09-28. All URLs fetched/verified via web search+fetch this session.
"Situation-level" = the exact situation occurred (item's recorded location ≠ actual
location, or two identical-part-number units confused by serial number).
"Category-level" = supports the general phenomenon/motivation but is not itself the
specific incident.

---

## (A) Recorded location ≠ actual physical location

### A1 — SITUATION-LEVEL: REALM/ML locates a CTB that manual IMS search misplaced
A Cargo Transfer Bag (CTB) that had been reported lost on ISS for about a year was
not found by human review of the (barcode-based) inventory records — that review
pointed to the wrong modules — and was only correctly localized once RFID data was
run through the REALM team's ML tools.

- Date: bag went missing c. 2019; correctly localized around/by **April 20, 2020**
  (crew needed it that day).
- Primary source: NASA JSC / METECS, *"Intra-Spacecraft RFID Localization"*
  (J. Berger, P. W. Fink, L. D. Rodriguez), NASA NTRS record **20210020182**,
  published 2021-08-09. https://ntrs.nasa.gov/citations/20210020182 (confirmed
  loading; abstract text not extractable from the pptx, but title/authors/date
  verified live on the NTRS record page).
- Corroborating account (same REALM team, contractor site — could not force a
  direct fetch to complete in-session, but content was independently returned,
  verbatim and consistently, by three separate search queries, so treat as
  secondary/high-confidence): METECS, *"REALM Team Directs Crew to Missing Cargo
  Transfer Bag on ISS."* https://www.metecs.com/realm-team-directs-crew-to-missing-cargo-transfer-bag-on-iss
- Quote: **"The CTB was reported lost approximately a year ago, but was not
  required by the crew until April 20th, 2020. Initial human inspection of raw
  data indicated that the missing CTB was likely in Node 1 or PMA 1, but
  localizing to the rack level had proven exceedingly difficult... Tagnet and
  Fangorn were able to localize the CTB to the Node 4 location."**

### A2 — CATEGORY-LEVEL: IMS's crew-dependent model is the stated reason items go missing
- Primary source: NASA JSC, *"Logistics Reduction: RFID Enabled Autonomous
  Logistics Management (REALM) (LR-REALM)"* (M. K. McKinley), NTRS record
  **20210015701**, 2021-05-06. https://ntrs.nasa.gov/citations/20210015701
  (record page confirmed live; full PDF at
  https://ntrs.nasa.gov/api/citations/20210015701/downloads/20200506%20REALM%20STI%20Review%20Document.pdf
  loads but is not machine-text-extractable).
- Quote (from NTRS record description): **"the current Inventory Management
  System (IMS) on ISS is heavily dependent upon crew involvement for finding
  and cataloging item locations."**
- Supporting secondary reporting on the same NASA program (Harvard Business
  School AI Institute, citing NASA/REALM figures): **"[IMS] tracks about
  130,000 items — with 64,000 items listed as 'active' and an estimated 3,000
  items classified as 'lost.'"** — https://aiinstitute.hbs.edu/lost-in-space-can-the-crowd-help-nasa-find-items-on-the-international-space-station/
  (secondary/journalistic; use only to corroborate scale, not as primary citation).

### A3 — CATEGORY-LEVEL: ISS Program's own rationale for the IMS bar-code label
- Primary source: ISS Program, **SSP 50007B**, *"Space Station Inventory
  Management System Bar Code Label Requirements and Specification,"* mirrored at
  https://everyspec.com/NASA/NASA-JSC/NASA-SSP-PUBS/SSP_50007B_29662/ (confirmed
  loading).
- Quote: **"The IMS label is designed for tracking and monitoring of loose,
  stowed, and installed hardware while on-orbit and on the ground."**
- Note: NASA OIG *"NASA's Management of ISS Extravehicular Activity Spacesuits"*
  (IG-25-012, 2025-09-30, https://oig.nasa.gov/wp-content/uploads/2025/09/final-report-ig-25-012-nasas-management-of-iss-extravehicular-activity-spacesuits.pdf)
  documents chronic EMU/EVA spare-parts supply shortfalls but I could not extract
  a specific location-mismatch quote from it in this session — flagged here as a
  lead for follow-up, not used as evidence above.

---

## (B) Identical part number, serial numbers confused

**No ISS- or Shuttle-specific situation-level case was found** despite targeted
searches of NASA OIG/GAO reports, GIDEP alert descriptions, ISS Daily Summary
Reports, and NASA lessons-learned material. The closest verified real-world
precedent is from a NASA science mission (not ISS):

### B1 — SITUATION-LEVEL (spaceflight, non-ISS): wrong serial-numbered preamp installed on THEMIS FM3
During SCM (search-coil magnetometer) refurbishment on the THEMIS mission
(NASA Explorer Program, multi-spacecraft, launched 2007), a preamp bearing
serial number 3 — same part number as, but not the correct unit for, flight
model FM3 — was installed by mistake in place of serial number 6. The error was
caught when calibration data came back about 5x too high; correction was
verified by reading serial number labels, and all other SCM preamps on the
spacecraft were then visually re-inspected against their serial numbers.

- Date: refurbishment/discovery documented **2006-06-22**.
- Primary source: UC Berkeley Space Sciences Laboratory / THEMIS project,
  Problem/Failure Report **PFR-196**, *"FM3 SCM wrong preamp installed."*
  https://themis.ssl.berkeley.edu/themisftp/1%20Management/1.3%20Systems%20Engineering/8.%20PFRs/thm_pfr_196_FM3_SCM_wrong_preamp_installed.pdf
  (URL confirmed to load — fetch tool retrieved the binary PDF but could not
  cleanly extract machine-readable text; the description above is corroborated
  across three independent extraction passes).
- Best available near-verbatim fragment recovered from the document: **"the
  calibration signal was about five times higher than it should be."** Treat
  the rest of the incident description as a close paraphrase, not a verified
  verbatim quote — flagged as lower-confidence wording, though the facts
  (wrong serial installed, same part number, caught via serial-number check)
  were consistent across all extraction attempts.

### B2 — CATEGORY-LEVEL: ISS labeling requires serial number precisely because part number alone cannot distinguish physically identical units
- Same source as A3, SSP 50007B.
  https://everyspec.com/NASA/NASA-JSC/NASA-SSP-PUBS/SSP_50007B_29662/
- Quote: **"The bar code label includes part number and serial number
  information and shall be placed on the item."**

---

## Leads not resolved (for follow-up, not cited above)
- NASA OIG IG-18-001, *"NASA's Management of Spare Parts for its Flight
  Projects"* (2017-10-05) — general spares-accountability findings across
  GSFC/JPL/KSC/MSFC; did not yield a specific swapped-serial-number incident in
  this session. https://oig.nasa.gov/docs/IG-18-001.pdf
- "Inventory and Stowage Officer Lessons Learned" (National Academies
  hosted PDF) — title suggests ISS-specific situation-level anecdotes but the
  fetch tool could not extract readable text this session.
  https://sites.nationalacademies.org/cs/groups/depssite/documents/webpage/deps_063600.pdf
- ICES conference papers on REALM (ICES-2024-073, ICES-2025-096,
  ICES-2025-125) likely contain the IMS accuracy percentage / crew-hours
  figures used to justify REALM, but their PDFs would not parse as text via
  the fetch tool in this session; worth a manual read.
