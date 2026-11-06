# goose-terminal

Experimental bounded terminal rendering for Goose. Apache-2.0.

The first release provides safe styled lines, rectangular ASCII tables, progress
bars and spinner frames. Rendering replaces caller-owned output; errors leave
it empty. No terminal I/O, environment reads, timers, native code or global state.

## Design contract

- All payloads are bytes: printable ASCII passes through, backslash becomes
  `\\`, other bytes become lowercase `\xNN`. Unicode is escaped byte by byte.
- Only enum-selected styles and explicitly enabled live frames emit controls.
- Applications supply terminal facts to a pure capability resolver. `Always`
  forces styles, never redraw. `NO_COLOR` is supplied as nonempty/present policy
  chosen by the application; `dumb` means unsupported ANSI capabilities.
- Maximum input: 4096 bytes per line/frame, 65536 bytes per table, 1024 cells,
  16 columns, 256 rows. Maximum display width: 512; output: 131072 bytes.
- Tables take flat row-major cells and a column count; widths include escape
  spellings and two spaces between columns. Oversized layouts are rejected,
  never silently truncated. Empty tables are valid with a valid column count.
- Live frames reserve the final terminal column, begin with CR + erase-line,
  and only a final frame ends with newline. Plain frames always end in newline.
  Serialize writes, re-probe after resize, finish on cancellation where possible,
  and handle partial writes yourself. No renderer can restore a failed sink.
- Inputs must not borrow from output. Goose checks ordinary source ownership;
  allocator failure and hostile native code are outside the error contract.

The interface and exact tested platform coverage will be documented alongside
validation before release. This repository is under active development.
