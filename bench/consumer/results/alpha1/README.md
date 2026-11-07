# Alpha.1 real consumer recording

Seven deterministically shuffled batches retain all 42 real Honk samples and
21 separate phase samples. No speedup/regression or cross-library ranking is
claimed. Broadly overlapping ranges and compiler/staging variation do not justify
optimizing the renderer for this consumer. No post-measurement hot-path change
was made.

Measured library commit: `5df0556cbc2898bec0f9343f29191088992cbd88`.
Measured Honk checkout: `dcdb05c951597bb4c34b92bb37006bb049e97af7`.
Both were clean; hashes identify the actual external binaries. Honk was built
using `make build` and the pinned Goose compiler; the recorder correctly labels
external binary flags as not inferred. Later commits add publication evidence
and documentation; renderer/adapter source hashes remain unchanged.

## Real commands

Milliseconds, seven samples in each cell. `never` disables presentation, `plain`
uses redirected `--progress always`, and `pty` uses `--progress auto` on a drained
80-column terminal. Real Goose processes and two target bodies execute; stdout
is identical across modes, and output policy assertions pass.

| Command | Mode | Median ms | Min–max ms |
| --- | --- | ---: | ---: |
| check | never | 22.786 | 21.099–26.299 |
| check | plain | 21.415 | 19.041–24.796 |
| check | pty | 22.647 | 20.087–24.214 |
| test | never | 539.002 | 507.474–576.932 |
| test | plain | 535.698 | 510.454–552.227 |
| test | pty | 523.370 | 495.909–555.042 |

## Isolated phases

Nanoseconds per operation, seven batches of 10,000 iterations. These exclude
compiler startup. Probe is a nonterminal destination; write is `/dev/null`, not
terminal latency. Phase order is fixed and buffers are retained.

| Phase | Median ns/op | Min–max ns/op |
| --- | ---: | ---: |
| render | 180.33 | 77.97–221.90 |
| probe-nontty | 475.42 | 310.89–588.01 |
| write-devnull | 1499.81 | 1022.87–1685.06 |

No CPU pinning/environment isolation was applied. All raw stdout/stderr,
phase CSV files, raw.jsonl records, exact source/compiler/binary hashes, fixture
hashes, CPU/platform and explicit environment policy are retained in this folder.
Temporary fixture paths in stdout are expected. Slower runs are preserved.

Reproduce with the [recorder](../../README.md), a fresh output directory, the
recorded Honk source/binary and the pinned compiler. The final manifest is
accepted only when source and binary identities still match after measurement.
