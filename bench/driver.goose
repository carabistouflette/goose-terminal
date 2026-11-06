// SPDX-License-Identifier: Apache-2.0
import terminal from "..";
import os;
import std;
fn render(kind: i64, text: const u8[:], caps: terminal::Capabilities, cells: const terminal::Cell[:], tick: i64, out: u8[>..]&) -> terminal::Error {
    if kind == 1 { return terminal::progress(caps, tick % 101, 100, 20, text, false, out); }
    if kind == 2 { return terminal::table(caps, cells, 4, out); }
    terminal::line(caps, terminal::Style.Success, text, out)
}
fn measure(name: const u8[:], kind: i64, text: const u8[:], cells: const terminal::Cell[:], count: i64, fresh: bool) {
    let caps = terminal::Capabilities { color: true, columns: 512 };
    var out:      u8[>..] = [];
    var checksum: i64     = 0;
    let start = clock_ns();
    for i in count {
        if fresh {
            var temporary: u8[>..] = [];
            let error = render(kind, text, caps, cells, i, temporary);
            checksum += temporary.len + (if error == terminal::Error.None { 0 } else { 1 });
        } else {
            let error = render(kind, text, caps, cells, i, out);
            checksum += out.len + (if error == terminal::Error.None { 0 } else { 1 });
        }
    }
    let elapsed = clock_ns() - start;
    print(name, ",", (if fresh { "fresh" } else { "retained" }), ",", count, ",", elapsed, ",", checksum);
}
fn main() {
    var count: i64 = 10000;
    if arg_count() > 1 {
        var arg_text: u8[>..] = []; arg(1, arg_text);
        let parsed, ok = parse_int(arg_text); assert(ok && parsed > 0 && parsed <= 10000000); count = parsed;
    }
    var ascii: u8[>..] = []; var escaped: u8[>..] = []; var mixed: u8[>..] = [];
    for i in 4096 { ascii.push('a'); escaped.push(0xff); mixed.push((i % 256) as u8); }
    var oversized: u8[>..]             = []; for i in 4097 { oversized.push(0xff); }
    var cells:     terminal::Cell[>..] = [];
    for i in 1024 { cells.push(terminal::Cell { bytes: "bounded table cell" }); }
    for fresh in [false, true] {
        measure("short-ascii", 0, "build completed", cells, count, fresh);
        measure("ascii-4096", 0, ascii, cells, count, fresh);
        measure("escaped-4096", 0, escaped, cells, count, fresh);
        measure("mixed-4096", 0, mixed, cells, count, fresh);
        measure("rejected-4097", 0, oversized, cells, count, fresh);
        measure("progress", 1, "build", cells, count, fresh);
        measure("table-1024", 2, "", cells, count, fresh);
    }
}
