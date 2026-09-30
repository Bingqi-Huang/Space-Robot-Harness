# Citation keys used in problem.tex, method.tex and setup.tex

Every key below is used with `\citep`/`\citet` in the three sections and has no .bib entry yet. "Sure" = details known
and standard; "verify" = the source is recorded in the repository (research_content.md "Literature anchors",
docs/heldout_design.md §13, experiments/exp2/heldout/precedents.md) but a bibliographic detail (title, number, date,
venue) was not checked against the original; do not fill a verify entry from memory.

| key | reference | status |
|---|---|---|
| acton1996spice | C. H. Acton, "Ancillary data services of NASA's Navigation and Ancillary Information Facility," *Planetary and Space Science* 44(1):65-70, 1996. | sure |
| barker2021lola | M. K. Barker, E. Mazarico, G. A. Neumann, D. E. Smith, M. T. Zuber, J. W. Head, "Improved LOLA elevation maps for south pole landing sites: error estimates and their impact on illumination conditions," *Planetary and Space Science* 203:105119, 2021. The scene uses the Site01 DEM (space_context/earth_visibility.py). | verify (authors, article number) |
| bedraxweiss2004europa | T. Bedrax-Weiss, J. Frank, A. Jónsson, C. McGann, "EUROPA2: Plan Database Services for Planning and Scheduling Applications," NASA NTRS 20050157874, 2004. | verify (venue: ICAPS 2004 workshop or tech report) |
| berger2021rfid | J. Berger, P. W. Fink, L. D. Rodriguez, "Intra-Spacecraft RFID Localization," NASA JSC, NTRS 20210020182, 2021 (presentation). Situation: ISS cargo transfer bag lost ~1 year, found by REALM RFID localization (precedents.md A1). | verify (document type) |
| castano2022ops | R. Castano, T. Vaquero, F. Rossi, V. Verma, E. Van Wyk, D. Allard, et al., "Operations for Autonomous Spacecraft," IEEE Aerospace Conference, 2022. | verify (full author list, pages) |
| cerf2007dtn | V. Cerf, S. Burleigh, A. Hooke, L. Torgerson, R. Durst, K. Scott, K. Fall, H. Weiss, "Delay-Tolerant Networking Architecture," RFC 4838, IETF, 2007. | sure |
| cfr1214403 | 14 CFR §1214.403, Code of Federal Regulations, Title 14, Part 1214. Used for "authorization before altering or removing station property". | verify (section title and the exact wording cited; heldout_design §2, §8) |
| coleman2014moveit | D. Coleman, I. Sucan, S. Chitta, N. Correll, "Reducing the barrier to entry of complex robotic software: a MoveIt! case study," *Journal of Software Engineering for Robotics* 5(1):3-16, 2014. | sure |
| dextre2011rpcm | Dextre's robotic remove-and-replace of a failed RPCM on the ISS, August 2011 (first robotic R&R of failed equipment). Repository sources are news reports (NASASpaceFlight 2011-09; Space.com). | verify (find a NASA or CSA primary source) |
| ecss2008operability | ECSS-E-ST-70-11C, "Space engineering: Space segment operability," ECSS Secretariat, ESA-ESTEC, 31 July 2008. Used for command retries as a parameter (§5.7.5.3i, §5.7.5.4c) and escalation to the next level (§5.7.5.2g). | sure (clause numbers from docs/baselines/authoring_spec.md) |
| estlin2006plexil | T. Estlin, A. Jónsson, C. Pasareanu, R. Simmons, K. Tso, V. Verma, "Plan Execution Interchange Language (PLEXIL)," NASA/TM-2006-213483, 2006. | sure |
| gaier2005apollo | J. R. Gaier, "The Effects of Lunar Dust on EVA Systems During the Apollo Missions," NASA/TM-2005-213610, 2005. Used for Apollo 16/17 LRV battery over-temperature. | verify (that the battery over-temperature account is in this TM) |
| gao1988cannibalization | U.S. General Accounting Office, GAO/NSIAD-88-30BR, 1988 (cannibalization of parts, board approval). | verify (title) |
| huang2007alfus | H.-M. Huang, E. Messina, J. Albus, "Autonomy Levels for Unmanned Systems (ALFUS) Framework, Volume II: Framework Models, Version 1.0," NIST Special Publication 1011-II-1.0, 2007. | sure |
| landon2025delay | L. B. Landon, J. A. Karasinski, L. G. Morissette, K. R. McTigue, M. E. Parisi, S.-C. Wu, T. L. Panontin, "Assessment of the State of Communication Delay Research in Preparation for Missions Beyond Low Earth Orbit," NASA/TM-20250003885, 2025. Used for the 3-14 s one-way lunar delay and the 3 s ground latency. | verify (table number for the 3 s low end) |
| lewis2022uncrewed | M. E. Lewis, C. M. McCleskey, V. R. Alvarez, J. D. Gomez Jr., K. A. Latorella, T. R. Gill, J. M. Perotti, N. P. Zeitlin, "Uncrewed Lunar Surface Operations and Support Activities," ASCEND 2022; NASA NTRS 20220013667. | verify (ASCEND paper number) |
| lim2024viper | Lim et al., VIPER mission operations, Lunar and Planetary Science Conference 2024, abstract #1647. Used for "minute-scale" operational decisions (the 300 s value is ours). | verify (authors, title) |
| macenski2020nav2 | S. Macenski, F. Martín, R. White, J. Ginés Clavero, "The Marathon 2: A Navigation System," IEEE/RSJ IROS, 2020. | sure |
| macenski2022ros2 | S. Macenski, T. Foote, B. Gerkey, C. Lalancette, W. Woodall, "Robot Operating System 2: Design, architecture, and uses in the wild," *Science Robotics* 7(66):eabm6074, 2022. | sure |
| nasa1971apollo15 | NASA Manned Spacecraft Center, "Apollo 15 Mission Report," MSC-05161, December 1971 (p. 94: LRV batteries cooled with covers open). | verify (report number) |
| nasa2015issdsr | NASA, ISS Daily Summary Report, 14 January 2015 (erroneous MDM ammonia indication). | verify (URL) |
| nasa2019issdsr0402 | NASA, ISS Daily Summary Report, 2 April 2019 (BCDU robotic replacement from an on-orbit spare). | verify (URL) |
| nasa2019issdsr0617 | NASA, ISS Daily Summary Report, 17 June 2019 (empty carrier removed before installing a spare). | verify (URL) |
| nasa2019mbsu3 | NASA ISS blog, 2 May 2019 (MBSU-3 replacement; new procedure in ~3 days). Consider adding the Apollo 13 Flight Journal (~34 h) and STS-120 NASA Facts (4 d) listed in heldout_design §8. | verify (URL, title) |
| nasa2020std6002 | NASA-STD-6002D, "Applying Data Matrix Identification Symbols on Aerospace Parts." | verify (revision date) |
| nasa2023lcn | NASA, "Lunar Communications and Navigation Architecture," white paper, 2023 Moon to Mars Architecture Concept Review. Used for "Earth visible from the south pole about half of each sidereal month". | verify (document number, exact wording) |
| nasa2024hpsc | NASA Game Changing Development, "High Performance Spaceflight Computing (HPSC)," project documentation, 2024-2026. | verify (which document; web source) |
| ogs2011filters | ISS Oxygen Generation System recirculation-loop filters clogged and replaced on orbit, NASA NTRS 20110023212, 2011. | verify (title, authors, venue; likely an ICES paper) |
| olsen2003metrics | D. R. Olsen Jr., M. A. Goodrich, "Metrics for evaluating human-robot interactions," PerMIS, 2003. | sure |
| openral | OpenRAL documentation, https://docs.openral.com/reference/reasoner/ (software). | verify (preferred citation form, version) |
| orsula2024srb | A. Orsula et al., Space Robotics Bench (software, v0.0.6 as used). | verify (authors, year, any paper or arXiv version) |
| park2021de440 | R. S. Park, W. M. Folkner, J. G. Williams, D. H. Boggs, "The JPL Planetary and Lunar Ephemerides DE440 and DE441," *The Astronomical Journal* 161(3):105, 2021. | sure |
| rabideau2025cadre | G. Rabideau et al., "Planning, Scheduling, and Execution on the Moon: The CADRE Technology Demonstration Mission," AAMAS, 2025. | verify (author list, pages) |
| riek2012woz | L. D. Riek, "Wizard of Oz studies in HRI: a systematic review and new reporting guidelines," *Journal of Human-Robot Interaction* 1(1):119-136, 2012. | sure |
| themis2007pfr196 | UC Berkeley Space Sciences Laboratory, THEMIS project, Problem/Failure Report PFR-196, "FM3 SCM wrong preamp installed." | verify (date; the key's year is a guess) |
| wilson1927probable | E. B. Wilson, "Probable inference, the law of succession, and statistical inference," *Journal of the American Statistical Association* 22(158):209-212, 1927. | sure |

# Figures needed

| label | where | content |
|---|---|---|
| fig:architecture | method.tex | The step loop of the proposed runtime: mission record (append-only events, reducer), step context (renderer), model, guard, shared capability boundary, verifier, trace; mission control behind the Direct-with-Earth link (store-and-forward). Mark which maps are outside the model (phi, rho, g, v) and which requirement (R2-R6) each answers. |
| fig:site | setup.tex | The simulated lunar base: the five serviced units (PDU-1..3, BESS, ISRU plant), the depot / landing-pad / habitat / return stands, the dock, and LunarBot at a unit's bay. Third-person render from the scene (experiments/video/replay_render.py can pose the scene without stepping physics). |

# Preamble requirements

- `enumitem` (the R1-R6 list in problem.tex uses `[label=R\arabic*]`), `amsmath` (`\text` in method.tex), `xcolor`
  (`\TBD`), `booktabs` (tab:instances). Each section file also carries `\providecommand{\TBD}` so it compiles before
  results.tex.
