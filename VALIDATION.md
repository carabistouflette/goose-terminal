# Validation

Local validation uses Linux x86-64 and Goose
`eadca409f68210893f366e60d0c2f0dc29a339be`. The compiler source was clean at
validation. No other platform is qualified. Remote CI was not run as part of this local
validation snapshot; check the public repository Actions for subsequent runs.

`make check test test-debug test-sanitize` covers formatting, source checks,
JIT API/overload execution, optimized API/oracle binaries, checked debug API/oracle
binaries (`--debug --no-bce`), checked debug API with ASan/UBSan and optimized
oracle with ASan/UBSan. Sanitizers use GCC, standalone binaries, no recovery,
frame pointers and non-PIE linking. They do not prove absence of defects:
Goose's mmap-backed data stacks do not expose every logical bound to ASan.

The independent Python oracle uses arbitrary-precision multiplication/division
for progress, independently spells all escaped bytes, and constructs padded
tables. Seed `0x6005e` produces 9157 cases per binary, including every byte,
all styles, widths 1..256, values around fill thresholds, i64 extrema,
invalid dimensions, row/cell/byte limits and error output clearing. Every
operation starts with a sentinel output to catch stale/partial failure output.

`tests/api.goose` exercises policy combinations, direct capability rejection,
known frames/tables, narrow empty tables and exact input/layout limits.
`tests/ownership.py` accepts four valid controls and requires compiler
rejection of the four corresponding payload/output aliases. Hostile application
numeric formatting cannot inject bytes into progress counters.

Two independent reviewers examined the design, then the implementation. Their
findings led to empty-table correction, clearer width/cleanup contracts,
implementation-detail names, and exhaustive bigint-based threshold checks.
A final review covers the complete code/test/documentation package.

`make bench-smoke` exercises fourteen workload/memory-mode pairs without speed
thresholds. The benchmark recorder retains raw samples and provenance; its
measurements are microbenchmarks, not comparative speed or allocation claims.
No live terminal, native capability probe, partial-write sink, or Unicode width
behavior is claimed or tested because those are outside the core contract.

Final checks also passed from a fresh standalone local Git clone using the same
external pinned compiler (`make check test`). Final oracle fixtures pass 9157
cases in each of optimized, checked-debug and sanitized binaries. Review fixes
include accepted exact aggregate-input/output table budgets and benchmark
identity checks before/after recording. Raw initial samples are retained in
bench/results/initial; measured source is identified independently of later
measurement-documentation commits.
