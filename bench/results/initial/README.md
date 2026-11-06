# Initial local recording

Source: `b832d42` (full commit in results.json), clean at recording.
Goose source is pinned in GOOSE_REVISION; the manifest also records the actual
compiler version and binary SHA256. Each of five batches runs 10,000 operations
for all fourteen workload/memory-mode pairs. Raw samples are retained in full.

This establishes recorder execution and initial local provenance. Runs were
un-pinned and used fixed workload order, without environmental isolation. No
speedup, cross-library ranking, or production performance claim is made.
The measured executable is excluded from Git; its SHA256 is in results.json.
