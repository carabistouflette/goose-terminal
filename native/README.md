# Optional POSIX adapter

Import `posix` alongside `terminal`; `posix.build` links only native/posix.c with
C11 and pthread support. Importing the core alone adds no native dependency.
Only Linux x86-64 has been qualified. The adapter owns no descriptors, retains
no pointers, and does not change file flags or process-wide signal dispositions.

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
values other than 1/2. Closed standard descriptors report EBADF on nonempty calls.

The calling thread temporarily blocks SIGPIPE, preserving any preexisting
pending SIGPIPE. A newly generated broken-pipe signal is consumed before the
original mask is restored. No automatic syscall retry or process-wide SIG_IGN
is installed. `cleanup_error != 0` means the thread mask may remain changed;
stop using that thread for work, rather than treating it as an ordinary optional
output error. Hostile/reentrant signal handlers and concurrent descriptor
replacement are outside the contract. A separately delivered SIGPIPE racing the
write cannot be distinguished from the write-generated signal.

Blocking descriptors may block indefinitely. This API provides byte/work limits,
not a write deadline. Deadline-driven applications must supply exclusively owned
nonblocking descriptors and decide how/when to retry WouldBlock. The adapter never
sets O_NONBLOCK on borrowed stdout/stderr, because duplicates share those flags.
Writes are not atomic as a frame, durable, or protected from concurrent writers.
The application owns serialization, resize/cancellation policy and sink errors.

`examples/posix_status.goose` shows checked offset handling. `make test-posix
 test-posix-sanitize` exercises actual PTYs, pipes and linked native fault
injection: short writes, EINTR, EAGAIN, EPIPE survival, preserved pending signals,
unchanged signal dispositions/masks/descriptor flags, and cleanup failures.
