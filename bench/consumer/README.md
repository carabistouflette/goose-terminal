# Honk consumer profiling

This recorder exercises the real Honk and Goose executables with a local,
dependency-free fixture. It measures `honk check --frozen` and a two-target
`honk test --frozen`, comparing presentation disabled, plain redirected stderr,
and automatically styled stderr on a drained 80-column PTY. The fixture and
lockfile are prepared and warmed before timing; no fake compiler or network is
used. All six combinations run in deterministically shuffled order per batch.

```sh
python3 bench/consumer/record.py \
  --honk /absolute/path/to/honk \
  --honk-source /absolute/path/to/honk-checkout \
  --goose /absolute/path/to/pinned/goose \
  --runs 5 --output .build/consumer-recording
```

The output directory must not exist. `--runs 1 --phase-iterations 10` is an
execution smoke check. The supplied Honk must implement `--progress`; its exact
binary hash and checkout commit, status and relevant source hashes are recorded.
Build flags for externally supplied binaries are explicitly unknown. The
recorder does not infer that a matching source checkout produced a binary.

The recorder builds `phases.goose` with `-O2 --cc gcc`, recording the flags,
compiler version and measured binary hash. Those separate retained-buffer
phases measure rendering, probing a nonterminal destination, and checked writes
to `/dev/null`; compilation is outside their timed loops. Their fixed phase
order is not randomized, and they do not measure real terminal output latency.

Each consumer sample retains elapsed nanoseconds, exit status, output lengths,
SHA256 hashes and exact stdout/stderr files. The tests require byte-identical
stdout across presentation modes, actual completed-target output, final command
summaries, no ANSI in redirected output, and no CR/erase controls in Honk's
complete snapshots. A baseline warmup verifies both real target bodies executed.
Source/compiler/binary identities are captured before compilation and checked
again after measurement; drift rejects the manifest while preserving raw files.

No CPU affinity or environmental isolation is applied. Platform, CPU information,
allowed affinity, relevant explicit environment policy and fixture hashes are
retained. Parent environment values, credentials, and arbitrary environment
variables are not copied into the report. Temporary fixture paths appear in
Honk's retained stdout. Raw results include slower runs. These measurements
include staging, compiler and subprocess startup and should not be interpreted
as isolated renderer overhead, a speed ranking or production throughput.
