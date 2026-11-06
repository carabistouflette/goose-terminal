// SPDX-License-Identifier: Apache-2.0
import terminal from "..";
import std;

fn main() {
    var out = str("sentinel");
    let plain = terminal::Capabilities { .. };
    for tty in [false, true] {
        for dumb in [false, true] {
            for no_color in [false, true] {
                for width in [-1, 0, 1, 2, 80, 512, 513] {
                    let facts = terminal::Facts { tty: tty, dumb: dumb, no_color: no_color, columns: width };
                    let auto = terminal::resolve(facts);
                    assert(auto.color == (tty && !dumb && !no_color));
                    assert(auto.redraw == (tty && !dumb && width >= 2 && width <= 512));
                    assert(auto.columns == (if width >= 2 && width <= 512 { width } else { 80 }));
                    assert(terminal::resolve(facts, terminal::Color.Always).color);
                    assert(!terminal::resolve(facts, terminal::Color.Never).color);
                    assert(terminal::resolve(facts, terminal::Color.Always).redraw == auto.redraw);
                }
            }
        }
    }
    assert(terminal::line(plain, terminal::Style.Success, "A\x1b\\\xff\n", out) == terminal::Error.None);
    assert(out == "A\\x1b\\\\\\xff\\x0a\n");
    let live = terminal::Capabilities { color: true, redraw: true, columns: 80 };
    assert(terminal::line(live, terminal::Style.Success, "ok", out) == terminal::Error.None);
    assert(out == "\x1b[32mok\x1b[0m\n");
    let cells = [terminal::Cell { bytes: "a" }, terminal::Cell { bytes: "b" }, terminal::Cell { bytes: "long" }, terminal::Cell { bytes: "\x1b" }];
    assert(terminal::table(plain, cells, 2, out) == terminal::Error.None);
    assert(out == "a     b\nlong  \\x1b\n");
    assert(terminal::table(plain, cells, 3, out) == terminal::Error.InvalidArgument && out.len == 0);
    assert(terminal::table(plain, cells, 0, out) == terminal::Error.InvalidArgument && out.len == 0);
    assert(terminal::table(plain, cells, 9223372036854775807, out) == terminal::Error.InvalidArgument && out.len == 0);
    assert(terminal::progress(live, 1, 3, 6, "work", false, out) == terminal::Error.None);
    assert(out == "\r\x1b[2K[##----] 1/3 work");
    assert(terminal::progress(live, 3, 3, 6, "work", true, out) == terminal::Error.None);
    assert(out == "\r\x1b[2K[######] 3/3 work\n");
    assert(terminal::spinner(plain, 3, "work", false, out) == terminal::Error.None && out == "\\ work\n");
    assert(terminal::spinner(live, 0, "work", true, out) == terminal::Error.None && out == "\r\x1b[2Kdone work\n");
    for value in [-9223372036854775808, -1] {
        assert(terminal::spinner(live, value, "", false, out) == terminal::Error.InvalidArgument && out.len == 0);
        assert(terminal::progress(live, value, 10, 4, "", false, out) == terminal::Error.InvalidArgument && out.len == 0);
    }
    assert(terminal::progress(live, 1, 0, 4, "", false, out) == terminal::Error.InvalidArgument && out.len == 0);
    assert(terminal::progress(live, 11, 10, 4, "", false, out) == terminal::Error.InvalidArgument && out.len == 0);
    assert(terminal::progress(live, 1, 10, 0, "", false, out) == terminal::Error.InvalidArgument && out.len == 0);
    var large: u8[>..] = [];
    for i in 4096 { large.push(0xff); }
    assert(terminal::line(plain, terminal::Style.Plain, large, out) == terminal::Error.None && out.len == 16385);
    large.push(0xff);
    assert(terminal::line(plain, terminal::Style.Plain, large, out) == terminal::Error.LimitExceeded && out.len == 0);
    assert(terminal::progress(live, 0, 1, 1, large, false, out) == terminal::Error.LimitExceeded && out.len == 0);
    assert(terminal::spinner(live, 0, large, false, out) == terminal::Error.LimitExceeded && out.len == 0);
    let invalid = terminal::Capabilities { columns: -9223372036854775808 };
    assert(terminal::line(invalid, terminal::Style.Plain, "x", out) == terminal::Error.InvalidArgument && out.len == 0);
    // Exact width boundary: 8 visible bytes needs at least 9 columns.
    let narrow = terminal::Capabilities { columns: 9 };
    assert(terminal::progress(narrow, 0, 1, 1, "", false, out) == terminal::Error.None);
    let too_narrow = terminal::Capabilities { columns: 8 };
    assert(terminal::progress(too_narrow, 0, 1, 1, "", false, out) == terminal::Error.LimitExceeded && out.len == 0);
    let empty: terminal::Cell[0] = [];
    assert(terminal::table(terminal::Capabilities { columns: 2 }, empty, 16, out) == terminal::Error.None && out.len == 0);
    print("API checks passed");
}
