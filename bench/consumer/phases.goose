// SPDX-License-Identifier: Apache-2.0
// Separate bounded phases: no compiler subprocess inside measured intervals.
import terminal from "../..";
import posix from "../..";
import os;
import std;
fn report(name: const u8[:], count: i64, elapsed: i64, checksum: i64) {
    write_stderr(str(name, ",", count, ",", elapsed, ",", checksum, "\n"));
}
fn main() {
    var text: u8[>..] = []; arg(1, text);
    let count, ok = parse_int(text); assert(ok && count > 0 && count <= 10000000);
    let caps = terminal::Capabilities { .. };
    var out:      u8[>..] = [];
    var checksum: i64     = 0;
    var start = clock_ns();
    for i in count {
        assert(terminal::progress(caps, i % 101, 100, 12, "test", true, out) == terminal::Error.None);
        checksum += out.len;
    }
    report("render", count, clock_ns() - start, checksum);
    checksum = 0; start = clock_ns();
    for i in count {
        let snapshot = terminal_posix::snapshot(1);
        assert(snapshot.os_error == 0 && !snapshot.tty);
        checksum += snapshot.capabilities.columns;
    }
    report("probe-nontty", count, clock_ns() - start, checksum);
    checksum = 0; start = clock_ns();
    for i in count {
        let result = terminal_posix::write_step(1, out);
        assert(result.error == terminal_posix::WriteError.None && result.written == out.len && result.cleanup_error == 0);
        checksum += result.written;
    }
    report("write-devnull", count, clock_ns() - start, checksum);
}
