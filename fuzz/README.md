# Sustained core API campaigns

Deterministic mutation-based differential testing exercises the public line,
table, progress, spinner and capability resolver functions. This is not
coverage-guided fuzzing; the validated driver framing is not a parser target.
Native writes and signal behavior are tested separately by POSIX qualification.

```sh
python3 fuzz/run.py --goose /absolute/checkout/build/goose --seconds 600 --max-cases 1000000 --output .build/campaign-new
```

The compiler must be in a clean Git checkout at GOOSE_REVISION and report a
matching version. Its binary hash, checkout commit, actual C-backend versions
and hashes, source hashes, flags, case counts and effective limits are retained.
A binary hash records identity, not a reproducible-build attestation.

Every seed executes before mutations: all byte values, styles/colors,
capability-policy combinations, exact and overflowing table budgets, label
limits and large counters. Composed mutations can reach combinations beyond
individual seeds. Every batch executes optimized, checked-debug and ASan/UBSan
binaries against a separate Python arbitrary-precision/byte reference.

Duration OR case budget stops the run; actual elapsed time, stop reason,
per-function and per-mode counts are reported. A brief smoke cannot qualify
sustained execution. Accepted runs require all modes and entry points to run.
Sources and measured binaries must remain unchanged; drift rejects the run.

Linux child controls: CPU hard5s, wall8s, file8MiB,32descriptors, core dumps off.
The actual effective limits are recorded. Inputs, outputs and traces are bounded.
Goose and ASan reserve large virtual regions, so no low RLIMIT_AS is installed;
hard RSS or virtual-memory containment is explicitly unqualified. Timeouts kill
and reap the owned process group. Only trusted local binaries are run.

Failures retain full batch input, JSON cases, expected/actual output, logs,
effective limits and a replay command. Replay validates the same driver schema
before building. This reproduces cases against the current checked source; to
reproduce the original environment, first restore the recorded source/toolchain
identities and flags. Runtime/build/harness failures are not silently labeled
API mismatches. Unexpected trace bytes also fail the protocol.

Successful evidence retains all per-batch hashes/statuses plus seed/generator
identity; input sequences are deterministic. No campaign proves absence of bugs,
complete value coverage, native-adapter behavior or portability.
