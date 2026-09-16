# PLEXIL baseline (execution_plan §1.5, §11.1, §21.5)

## Pin and build (2026-09-17)

- Source: `plexil-group/plexil`, branch `releases/plexil-6`, commit `0e7439fb` (`git describe`: **6.1.3**),
  cloned to `~/Programs/plexil` (`PLEXIL_HOME`).
- Toolchain: g++ 11, CMake 3.22.1, OpenJDK javac 11.0.32,
  Apache Ant 1.10.18 (`~/Programs/apache-ant-1.10.18`, no apt), GNU gperf 3.1 built from source
  (`~/Programs/gperf`; required by the XML parser's generated expression map).
- Executive (CMake, out-of-tree, in-tree install):
  `cd plexil-build && cmake $PLEXIL_HOME -DCMAKE_INSTALL_PREFIX=$PLEXIL_HOME -DSTANDALONE_SIMULATOR=ON -DTEST_EXEC=ON
  -DUDP_ADAPTER=ON -DGPERF=$HOME/Programs/gperf/bin/gperf && make -j16 install` → `bin/{universalExec,TestExec,simulator,analyzePlan}`.
- Java tools (ant on PATH): `make plexil-compiler plexilscript checker` → `jars/PlexilCompiler.jar` etc.
  (The autotools `make tools` stops on missing gperf; CMake with `-DGPERF` is the route.)
- PATH without conda (its python breaks builds); `scripts/` on PATH for `plexilc`, `plexiltest`.
- Upstream example verified: `plexilc examples/basic/SafeDrive.ple` + `scripts/SafeDrive.pst` →
  `plexiltest -p SafeDrive.plx -s SafeDrive.psx` runs to completion ("Pictures taken: 5").

## Adapter: `ros/plexil_capability_adapter` (skeleton)

Option 1 of §1.5 (native InterfaceAdapter calling the ROS 2 boundary) -- smaller than the IPC route, keeps typed
results. `libCapabilityAdapter.so`, loaded by `universalExec -c config/interface-config.xml` (`LibPath`), exposes:

- `Boolean Command ExecuteCapability(String capability, String args_json)` → `/space/capability/execute`
- `String Lookup QueryCapability(String query, String args_json)` → `/space/capability/query`
- `String Lookup LastCapabilityResult()` → JSON {capability, success, failure_kind, failure_reason, evidence}

No mission logic. Verified (offline boundary, domain 91): a plan calling `ExecuteCapability("fly", "{}")` receives
`false` and the boundary's refusal (failure_kind 20) through the adapter.

Open for §21.5: the `QueryCapability` lookup stalls (the plan's second print never appears; exec killed at 45 s) --
lookup threading vs the executor; typed per-capability Commands (NavigateToPose(Real, Real, Real) …); the Mission A
covered plan library; run through the live graph.
