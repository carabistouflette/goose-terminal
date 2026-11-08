# Platform qualification

The rendering core and optional POSIX adapter are qualified separately. A CI
configuration is a test plan; only completed successful jobs establish coverage.
No cross-compilation or emulated execution is counted as native qualification.

| Runner label | Required native execution | C compiler | Qualification |
| --- | --- | --- | --- |
| `ubuntu-24.04` | Linux x86-64 | GCC and Clang | Core and POSIX adapter |
| `ubuntu-24.04-arm` | Linux ARM64 (`aarch64`) | GCC and Clang | Core and POSIX adapter |
| `macos-15` | macOS ARM64 (`arm64`) | Apple Clang | Core/probe; writer with explicit app SIGPIPE policy |

Each job checks `uname` before building, and records the OS, architecture,
compiler version, source commit and pinned Goose compiler revision. Toolchain
caches include runner OS and architecture to prevent reuse across architectures.
The workflow retains separate core, POSIX and benchmark execution logs as
`qualification-<runner>-<compiler>` artifacts for 30 days. A failed job is not
qualification, even when its earlier stages passed; inspect the individual logs.

Core coverage runs formatting/source checks, JIT API/overload checks, optimized
and checked debug binaries, the independent oracle and ownership regressions,
and ASan/UBSan. POSIX coverage runs actual PTY detection/policy/resize/cancellation
checks and the production native implementation under test-only syscall shims,
in normal and sanitizer builds. The shims use preprocessor substitutions in the
test translation unit, so no GNU linker `--wrap` extension is required.

On Linux the native adapter consumes a newly pending SIGPIPE with `sigwait`,
after checking that it is actually pending. Linux can queue an ignored SIGPIPE
while it is blocked, so ignored disposition is not evidence of no pending signal.
A separate synthetic EPIPE case generates no signal and proves the wait is
skipped. Linux tests preserve existing pending signals and the original mask,
and inject pending/wait/restore failures. Signal-cleanup
failure is a fatal thread-state outcome.

Darwin's kernel generates process-directed SIGPIPE for pipe writes. Its
`F_SETNOSIGPIPE` flag lives in the shared file description; `dup` does not isolate
it. Therefore the macOS writer requires a stable, application-owned SIG_IGN
policy, checked read-only before a nonempty write. Without it, the call refuses
with `OsError`/`ENOTSUP` and zero bytes written. The library neither sets global
policy nor modifies borrowed flags. Snapshot/core use is unconditional. The
macOS fixture explicitly installs/inherits SIG_IGN and checks real short writes,
EINTR/EAGAIN/EPIPE plus default-policy refusal. Linux-only signal-mask failure
cases are not presented as macOS coverage. Concurrent signal-policy changes,
reentrant consumption, environment mutation and descriptor replacement remain
outside the contract.

The GNU/ELF non-PIE sanitizer flags are applied only on Linux. macOS uses the
compiler's native sanitizer/linker defaults. No Windows adapter, Unicode display
width support, descriptor deadline, or screen-restoration guarantee is implied.

## Evidence status

At preparation, Linux x86-64 native and sanitizer tests pass locally with GCC
and Clang. ARM64 Linux and macOS jobs must complete before alpha.2 can claim
those platforms. The release qualification receipt records the exact successful
run and downloaded artifacts; a workflow badge alone is insufficient.

Runner labels and native architectures were checked against the official
[GitHub-hosted runner reference](https://docs.github.com/en/actions/reference/runners/github-hosted-runners).
The signal-consumption semantics follow Apple's
[`sigwait` manual](https://developer.apple.com/library/archive/documentation/System/Conceptual/ManPages_iPhoneOS/man2/sigwait.2.html).

The Darwin restriction is based on immutable Apple XNU source:
[`write` generates process-directed SIGPIPE](https://github.com/apple-oss-distributions/xnu/blob/f6217f891ac0bb64f3d375211650a4c1ff8ca1ea/bsd/kern/sys_generic.c#L600),
[`F_SETNOSIGPIPE` changes the fileglob](https://github.com/apple-oss-distributions/xnu/blob/f6217f891ac0bb64f3d375211650a4c1ff8ca1ea/bsd/kern/kern_descrip.c#L2944),
and [`dup` shares that fileglob](https://github.com/apple-oss-distributions/xnu/blob/f6217f891ac0bb64f3d375211650a4c1ff8ca1ea/bsd/kern/kern_descrip.c#L560).

## Descriptor-flag fixture

Darwin's `F_GETFL` can expose the kernel's first-write history bit. The native
raw-write control observed `0x1 -> 0x10001` without invoking this library; the
adapter write observed the same `0x10000` delta. XNU
[sets `FWASWRITTEN` after a successful write](https://github.com/apple-oss-distributions/xnu/blob/f6217f891ac0bb64f3d375211650a4c1ff8ca1ea/bsd/kern/sys_generic.c#L613)
and [returns the flag word through `F_GETFL`](https://github.com/apple-oss-distributions/xnu/blob/f6217f891ac0bb64f3d375211650a4c1ff8ca1ea/bsd/kern/kern_descrip.c#L2865).
The fixture primes its pipe with a raw byte before establishing the borrowed
flag snapshot. It then retains exact full-word equality across adapter writes;
no status bit is masked or exempted. The separate raw-write control remains in
the logs, distinguishing OS bookkeeping from library descriptor mutations.
