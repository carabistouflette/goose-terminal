# Benchmarks

Builds use the pinned Goose compiler, `-O2 --cc gcc`. Run `make bench-smoke`
for execution checks. For a recording:

```sh
python3 bench/measure.py --goose /absolute/path/to/goose --iterations 10000 --runs 5 --output .build/measurement
```

The output directory must be new. The recorder retains every raw process sample,
source hashes/status/commit, compiler binary hash/version/pin, C compiler, flags,
machine and CPU information. No affinity or environmental isolation is applied.
Compilation and fixture construction are outside the measured intervals.

Workloads cover short ASCII, maximum ASCII, maximum escaping, mixed bytes,
rejection, changing progress counters, and a 1024-cell table. Both fresh and
retained output buffers are measured. Checksums consume output lengths and error
statuses; independent correctness tests validate content. These are single-library
microbenchmarks, not allocations counts, terminal I/O timings or comparative
claims. Run order is fixed; variation and order effects must be considered.
No optimization or speed claim should rely on the smoke recording.
