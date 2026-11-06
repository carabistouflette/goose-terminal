# Security

This experimental library renders arbitrary bytes into bounded buffers. The rendering core does
not redact secrets, perform I/O, or authenticate terminal capabilities. The
optional POSIX adapter probes borrowed stdout/stderr and performs checked raw
byte writes; it does not escape input itself. Pass renderer output to it, and
read native/README.md for blocking and signal-cleanup requirements. Only the
pinned compiler and actually tested platforms are qualified. Applications own
terminal detection, synchronization, output writes and error handling.

Report vulnerabilities privately through GitHub:
https://github.com/carabistouflette/goose-terminal/security/advisories/new

Include the library and compiler commits, platform, a minimal reproducer and
expected versus observed behavior. Do not include credentials or personal data.
Keep exploit details private until a fix or coordinated disclosure is ready.
Security fixes target main and the latest release once releases exist; older
pins are not separately maintained. No response-time guarantee is made.
