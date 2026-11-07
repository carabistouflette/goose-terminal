# Optional POSIX adapter

Import `posix` alongside `terminal`; `posix.build` links only native/posix.c with
C11 and pthread support. Importing the core alone adds no native dependency.
See [platform qualification](../PORTABILITY.md) for actual tested coverage.
The adapter owns no descriptors, retains no pointers, and does not change file flags or process-wide signal dispositions.

`terminal_posix::snapshot(fd, color=Auto)` accepts stdout (1) or stderr (2),
returns `{capabilities, tty, os_error}`, and re-probes on each call. A non-TTY is
normal, with width unknown. Other probe failures expose errno; callers can use
conservative output or disable presentation. TERM absent/empty or exactly `dumb`
disables automatic ANSI; nonempty NO_COLOR disables automatic color. TERM is
compared with at most five bytes; NO_COLOR requires only its first byte.
The application must serialize environment mutation and descriptor replacement.
Unknown width disables live redraw; see core width fallback rules.

`write_step(fd, bytes)` validates fd and at most 131072 bytes, then performs one
write syscall. `Write` reports `written`, `error`, `os_error`, `cleanup_error`.
`error` is None, InvalidArgument, OsError, Interrupted, or WouldBlock. None can
be a short write; it does not promise the complete frame was written. Resume
from exactly `written` bytes. Never replay the prefix after an error. An empty
slice succeeds without touching the descriptor; validation still rejects fd
values other than 1/2. Closed standard descriptors report EBADF on eligible
nonempty calls (macOS signal-policy validation takes precedence).

On Linux the calling thread temporarily blocks SIGPIPE, preserving any
preexisting pending SIGPIPE. After EPIPE, a pending check avoids waiting when no
signal exists; EPIPE alone does not prove one was generated. Linux can queue
ignored SIGPIPE while it is blocked. A newly pending signal is consumed
with `sigwait` before the original mask is restored. No automatic retry or
process-wide SIG_IGN is installed. `cleanup_error != 0` means the thread mask may
remain changed; stop using that thread instead of treating it as ordinary
optional output failure. Hostile/reentrant signal handlers and externally raced
SIGPIPE consumption are outside the contract.

On macOS a nonempty write requires an explicit, stable application-owned
`SIGPIPE=SIG_IGN` disposition. The adapter checks it with `sigaction` and returns
`OsError` / `ENOTSUP`, zero bytes written, when it is absent. It does not install
or restore a process-wide policy and does not use the Linux thread-mask method.
Darwin can direct write-generated SIGPIPE to another thread, and its
`F_SETNOSIGPIPE` flag is shared by duplicated descriptors. Therefore neither
thread masking nor a temporarily configured duplicate is a safe substitute.
The application must serialize signal-policy changes for the complete call.
An empty slice needs no signal-policy opt-in and still performs no write.

Snapshot/probing has no SIGPIPE-policy requirement on either platform. The
`examples/posix_status.goose` example performs a write directly and is usable on
Linux as-is; macOS applications must establish the policy explicitly before
using it. The library does not automatically choose that application policy.

Blocking descriptors may block indefinitely. This API provides byte/work limits,
not a write deadline. Deadline-driven applications must supply exclusively owned
nonblocking descriptors and decide how/when to retry WouldBlock. The adapter never
sets O_NONBLOCK on borrowed stdout/stderr, because duplicates share those flags.
Writes are not atomic as a frame, durable, or protected from concurrent writers.
The application owns serialization, resize/cancellation policy and sink errors.

`examples/posix_status.goose` shows checked offset handling. `make test-posix
 test-posix-sanitize` exercises actual PTYs, pipes and linked native fault
injection against the production source without GNU linker extensions. Both
platforms exercise short writes, EINTR/EAGAIN and EPIPE; Linux additionally
qualifies preserved pending signals and signal-mask cleanup failures. Descriptor
flags and application-owned dispositions remain unchanged.
