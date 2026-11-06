// SPDX-License-Identifier: Apache-2.0
import terminal from "..";
import posix from "..";
import os;
import std;
fn main() {
    var mode: u8[>..] = []; arg(1, mode);
    if mode == "probe" {
        let snap = terminal_posix::snapshot(1);
        print(snap.tty, " ", snap.capabilities.color, " ", snap.capabilities.redraw, " ", snap.capabilities.columns, " ", snap.os_error);
        return;
    }
    if mode == "write" {
        var text: u8[>..] = []; arg(2, text);
        let result = terminal_posix::write_step(1, text);
        print(result.written, " ", result.os_error, " ", result.cleanup_error);
        return;
    }
    if mode == "invalid" {
        let snap = terminal_posix::snapshot(-1); assert(!snap.tty && snap.os_error != 0);
        let result = terminal_posix::write_step(-1, "x");
        assert(result.error == terminal_posix::WriteError.InvalidArgument && result.written == 0);
        print("invalid adapter arguments rejected"); return;
    }
    if mode == "session" {
        var input: u8[>..] = []; var out: u8[>..] = [];
        var active = false;
        while read_line(input) {
            let snap = terminal_posix::snapshot(1);
            let final = input == "finish" || input == "cancel";
            let label = if input == "cancel" { "cancelled" } else { "working" };
            let error = terminal::spinner(snap.capabilities, 0, label, final, out);
            if error != terminal::Error.None {
                out.clear();
                if active { out.append("\r\x1b[2K\n"); }
                active = false;
            } else { active = snap.capabilities.redraw && !final; }
            let result = terminal_posix::write_step(1, out);
            assert(result.error == terminal_posix::WriteError.None && result.written == out.len && result.cleanup_error == 0);
            write_stderr("ack\n"); input.clear();
        }
        return;
    }
    assert(false);
}
