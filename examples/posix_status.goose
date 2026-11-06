// SPDX-License-Identifier: Apache-2.0
import terminal from "..";
import posix from "..";
import os;
import std;
fn main() {
    let snapshot = terminal_posix::snapshot(1);
    if snapshot.os_error != 0 { exit(1); }
    var out: u8[>..] = [];
    assert(terminal::line(snapshot.capabilities, terminal::Style.Success, "ready", out) == terminal::Error.None);
    var offset: i64 = 0;
    for attempt in 64 {
        let result = terminal_posix::write_step(1, out[offset..]);
        offset += result.written;
        if result.cleanup_error != 0 { exit(1); }
        if result.error == terminal_posix::WriteError.Interrupted { continue; }
        if result.error != terminal_posix::WriteError.None { exit(1); }
        if offset == out.len { return; }
        if result.written == 0 { exit(1); }
    }
    exit(1);
}
