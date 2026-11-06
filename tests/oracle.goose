// SPDX-License-Identifier: Apache-2.0
import terminal from "..";
import binary;
import os;
import std;

fn main() {
    assert(arg_count() == 2);
    var path: u8[>..] = []; arg(1, path);
    var data: u8[>..] = []; assert(read_file(path, data));
    var reader = binary::reader(data);
    var out = str("sentinel");
    var cases: i64 = 0;
    let styles = [terminal::Style.Plain, terminal::Style.Emphasis, terminal::Style.Success, terminal::Style.Warning, terminal::Style.Failure];
    let errors = [terminal::Error.None, terminal::Error.InvalidArgument, terminal::Error.LimitExceeded];
    while reader.pos < data.len {
        let h, ok = binary::read_bytes(reader, 48); assert(ok);
        let columns, c_ok = binary::read_i64le(h, 4);
        let a, a_ok = binary::read_i64le(h, 12);
        let b, b_ok = binary::read_i64le(h, 20);
        let c, v_ok = binary::read_i64le(h, 28);
        let count, n_ok = binary::read_u32le(h, 36);
        let expected_size, e_ok = binary::read_u32le(h, 40);
        assert(c_ok && a_ok && b_ok && v_ok && n_ok && e_ok && h[44] < 3);
        var cells: terminal::Cell[>..] = [];
        for i in count {
            let size, size_ok = binary::read_u32le(reader); assert(size_ok);
            let text, text_ok = binary::read_bytes(reader, size); assert(text_ok);
            cells.push(terminal::Cell { bytes: text });
        }
        let expected, expected_ok = binary::read_bytes(reader, expected_size); assert(expected_ok);
        let caps = terminal::Capabilities { color: h[1] != 0, redraw: h[2] != 0, columns: columns };
        out.clear(); out.append("sentinel");
        var error = terminal::Error.InvalidArgument;
        if h[0] == 0 { error = terminal::line(caps, styles[a], cells[0].bytes, out); }
        else if h[0] == 1 { error = terminal::table(caps, cells, a, out); }
        else if h[0] == 2 { error = terminal::progress(caps, a, b, c, cells[0].bytes, h[3] != 0, out); }
        else if h[0] == 3 { error = terminal::spinner(caps, a, cells[0].bytes, h[3] != 0, out); }
        else { assert(false); }
        if error != errors[h[44] as i64] || out != expected {
            print("oracle mismatch: ", cases); assert(false);
        }
        assert(out.len <= terminal::MAX_OUTPUT_BYTES);
        cases++;
    }
    print("oracle cases passed: ", cases);
}
