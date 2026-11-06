// SPDX-License-Identifier: Apache-2.0
import terminal from "..";
import std;
fn format(value: i64, out: u8[>..]&) { out.append("\x1b]52;c;bad\x07"); }
fn min(a: i64, b: i64) -> i64 { a }
fn main() {
    var out: u8[>..] = [];
    assert(terminal::progress(terminal::Capabilities { .. }, 1, 3, 6, "safe", false, out) == terminal::Error.None);
    assert(out == "[##----] 1/3 safe\n");
    assert(terminal::spinner(terminal::Capabilities { .. }, 9223372036854775807, "safe", false, out) == terminal::Error.None);
    assert(out == "\\ safe\n");
    print("overload isolation passed");
}
