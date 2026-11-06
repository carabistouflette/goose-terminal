// SPDX-License-Identifier: Apache-2.0
import terminal from "..";
import os;
import std;
fn main() {
    // Conservative default: this example makes no native terminal assumptions.
    let caps = terminal::resolve(terminal::Facts { .. });
    var out: u8[>..] = [];
    let cells = [terminal::Cell { bytes: "library" }, terminal::Cell { bytes: "status" }, terminal::Cell { bytes: "goose-terminal" }, terminal::Cell { bytes: "ready" }];
    assert(terminal::table(caps, cells, 2, out) == terminal::Error.None);
    write_stdout(out);
    assert(terminal::progress(caps, 3, 3, 12, "checks", true, out) == terminal::Error.None);
    write_stdout(out);
    assert(terminal::line(caps, terminal::Style.Success, "Untrusted: \x1b]52;c;payload\x07", out) == terminal::Error.None);
    write_stdout(out);
}
