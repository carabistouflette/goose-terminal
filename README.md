# goose-terminal

Experimental bounded terminal rendering for Goose. Apache-2.0.

The first release provides safe styled lines, rectangular ASCII tables, progress
bars and spinner frames. Rendering replaces caller-owned output; errors leave
it empty. The core has no terminal I/O, environment reads, timers, native code or global
state. An [optional POSIX adapter](native/README.md) supplies detection and checked
writes without changing the core interface.

## Design contract

- All payloads are bytes: printable ASCII passes through, backslash becomes
  `\\`, other bytes become lowercase `\xNN`. Unicode is escaped byte by byte.
- Only enum-selected styles and explicitly enabled live frames emit controls.
- Applications supply terminal facts to a pure capability resolver. `Always`
  forces styles, never redraw. `NO_COLOR` is supplied as nonempty/present policy
  chosen by the application; `dumb` means unsupported ANSI capabilities.
- Maximum input: 4096 bytes per line/frame, 65536 bytes per table, 1024 cells,
  16 columns, 256 rows. Maximum configured terminal width: 512; output: 131072 bytes.
  Styled lines ignore terminal width and may wrap (at most 16384 visible bytes).
- Tables take flat row-major cells and a column count; widths include escape
  spellings and two spaces between columns. Oversized layouts are rejected,
  never silently truncated. Empty tables are valid with a valid column count.
- Tables and live frames reserve the final terminal column. Each table row ends
  with newline. Live frames begin with CR + erase-line, and only a final live
  frame ends with newline. Plain frames always end in newline.
  Serialize writes, re-probe after resize, finish on cancellation where possible,
  and handle partial writes yourself. No renderer can restore a failed sink.
- Inputs must not borrow from output. Goose checks ordinary source ownership;
  allocator failure and hostile native code are outside the error contract.

## Quickstart

Requires Git, CMake 3.27+, a C/C++20 toolchain, Make and Python 3. No runtime
native dependency is added by the library. From this standalone directory:

```sh
make setup
make check test test-debug test-sanitize test-posix test-posix-sanitize bench-smoke
.toolchain/goose/build/goose run examples/status.goose
```

For a compiler already built at the exact pinned revision, pass
`GOOSE=/absolute/path/to/goose` to Make. See [contribution checks](CONTRIBUTING.md).

```goose
import terminal from "/path/to/goose-terminal";
import std;
fn main() {
    let caps = terminal::resolve(terminal::Facts { .. });
    var out: u8[>..] = [];
    let error = terminal::line(caps, terminal::Style.Success, "ready", out);
    assert(error == terminal::Error.None && out == "ready\n");
    // Pass out to the application's checked output writer.
}
```

The example uses stdlib output, which exposes no write status; production
applications should use a writer that reports partial writes/errors.

## Supported interface

Import `terminal.goose`. Names are in namespace `terminal`. Only the types,
constants and functions documented here are supported; `detail_*` functions are
unchecked implementation details (Goose has no package-private visibility).

| Function | Parameters after capabilities | Result |
| --- | --- | --- |
| `resolve` | `Facts`, optional `Color` (default Auto); no capabilities input | `Capabilities` |
| `line` | `Style`, byte slice, output buffer | `Error` |
| `table` | `Cell` slice, column count, output buffer | `Error` |
| `progress` | completed, total, bar width, label, final, output buffer | `Error` |
| `spinner` | tick, label, final, output buffer | `Error` |

All numbers are `i64`; all payloads are `const u8[:]`; output is `u8[>..]&`.
`Cell` has one field, `bytes: const u8[:]`. `Style` is Plain, Emphasis, Success,
Warning or Failure; styles affect `line` only. `Color` is Auto, Always or Never.

`Facts` defaults to false flags and zero columns; fields are `tty`, `dumb`,
`no_color` and `columns`. These are application-supplied facts about the actual
output destination. `Capabilities` defaults to `color=false`, `redraw=false`,
`columns=80`. Auto color requires tty, no dumb flag and no no_color flag. Always
forces color even when redirected. Redraw requires tty, no dumb flag and known
width in 2..512. Unknown/out-of-range width becomes 80 and disables redraw.
`NO_COLOR` convention is a nonempty environment value; the application chooses
and supplies its policy. This module does not claim to discover terminal facts.

Direct capabilities must have columns in 2..512. Rendering returns
`InvalidArgument` for invalid capabilities, table column count outside 1..16,
nonrectangular table, negative spinner tick, or invalid progress counters/width.
Progress requires total > 0, completed in 0..total and bar width in 1..256.
`final` ends the frame; it does not force completed == total or imply success.
Spinner cycles `|/-\` and renders `done ` on final. Tick is nonnegative and may
be i64's maximum. `LimitExceeded` covers resource limits and layouts wider than
the configured width minus one. Invalid arguments precede payload size checks;
table count limit precedes rectangularity. No error retries or truncation occur.

`Error.None` means a complete buffer was produced, not that bytes were written.
Buffer capacity may be retained across calls. Each input is bounded before byte
scanning; tables check aggregate input before escaping any cells. Lines require
O(input + output) work, tables O(cells + input + output), and progress
O(label bytes + bar width); fixed table width scratch is 16 integers.

Frames and tables must start at column zero. Plain frames do not reposition the
cursor. Live frames include CR/erase-line; no output contains cursor-hide/show
or arbitrary payload escape sequences. A capability snapshot cannot prevent
wrapping if terminal dimensions change between rendering and writing.

## Validation and scope

See [validation](VALIDATION.md), [security](SECURITY.md), and
[benchmarks](bench/README.md). The core is designed without platform-specific
calls; only Linux x86-64 has been executed locally. Other platforms remain
unqualified. No full-screen TUI, Unicode display width, raw ANSI passthrough,
timers, truncation or concurrent writer is included. The optional POSIX module
provides explicit terminal probing and one-step checked writes. The API may
change before 1.0.

The POSIX adapter is opt-in: `import posix from "/path/to/goose-terminal";`.
See its [contract and limitations](native/README.md) before using live output.

## Pinned package imports

Core-only consumers can declare:

```goose
import terminal from "carabistouflette/goose-terminal@v0.1.0-alpha.1";
```

For the optional adapter, one declaration loads both namespaces:

```goose
import posix from "carabistouflette/goose-terminal@v0.1.0-alpha.1";
// terminal_posix::snapshot / write_step and terminal:: renderers are available.
```

When using Honk, declare one `posix` dependency for the core plus adapter. Avoid
declaring two aliases for the same source: Honk stages aliases independently.
Honk's validated consumer uses an independently pinned vendored snapshot with
`--progress auto|always|never` (default never). Complete snapshots preserve child
diagnostics; they do not animate over child output. See the consumer profiling
instructions in [bench/consumer](bench/consumer/README.md).
