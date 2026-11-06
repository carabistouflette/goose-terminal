# Security

This experimental library renders arbitrary bytes into bounded buffers. It does
not redact secrets, perform I/O, or authenticate terminal capabilities. Only the
pinned compiler and actually tested platforms are qualified. Applications own
terminal detection, synchronization, output writes and error handling.

Report vulnerabilities privately through GitHub:
https://github.com/carabistouflette/goose-terminal/security/advisories/new

Include the library and compiler commits, platform, a minimal reproducer and
expected versus observed behavior. Do not include credentials or personal data.
Keep exploit details private until a fix or coordinated disclosure is ready.
Security fixes target main and the latest release once releases exist; older
pins are not separately maintained. No response-time guarantee is made.
