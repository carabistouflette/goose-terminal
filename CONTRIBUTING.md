# Contributing

Use focused `feat/...`, `fix/...`, or `docs/...` branches and Conventional
Commits (`fix: reject overflowing dimensions`). Each commit is one coherent
change. Do not commit binaries, caches, credentials, or private workspace notes.

Use the exact compiler in GOOSE_REVISION. Run `make setup`, then
`make format check test test-debug test-sanitize bench-smoke`. An existing pinned
compiler can be supplied with `GOOSE=/absolute/path/to/goose`.

Keep the interface small, rendering deterministic, buffers caller-owned, and
errors explicit. Preserve output clearing on failure, aggregate resource limits,
terminal escaping, and independence from application formatting overloads.
Add public behavior regressions and independent oracle cases. Get independent
reviews of behavior changes, resolve actionable findings, and keep CI passing.
Compiler changes require independent review and the complete validation suite.

Profile before optimizing. Retain raw benchmark samples, slower cases, exact
source/compiler identities, flags and platform provenance. CI checks correctness
and benchmark execution, never speed thresholds. See SECURITY.md for reporting.
Releases use semantic versions; never move a published tag.
