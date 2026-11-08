# Changelog

## Unreleased

- On macOS, a nonempty POSIX write requires the application to set
  `SIGPIPE` to `SIG_IGN`. Otherwise it returns `OsError`/`ENOTSUP` without
  writing; the adapter does not change the process-wide signal disposition.
- Core API campaigns include heterogeneous escaped table padding and run on
  relevant PRs and pushes with bounded automatic budgets.

## v0.1.0-alpha.1

- Optional POSIX terminal detection and checked one-step writes with thread-local
  SIGPIPE protection and explicit partial/error outcomes.
- PTY resize/cancellation and native short-write/signal/descriptor regressions.

- Bounded escaped styled lines and rectangular tables.
- Overflow-safe ASCII progress bars and stateless spinner frames.
- Pure capability policy resolver with conservative defaults.
- Independent seeded oracle, ownership rejection, formatting isolation,
  debug/native sanitizer validation, and reproducible benchmark recorder.
