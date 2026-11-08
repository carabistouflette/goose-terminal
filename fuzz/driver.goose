// SPDX-License-Identifier: Apache-2.0
// Trusted bounded campaign encoding; product payloads/options are fuzzed.
import terminal from "..";
import binary;
import os;
import std;
fn append_u32(value: u32, out: u8[>..]&) {
    for shift in [0, 8, 16, 24] { out.push(((value >> shift) & 255) as u8); }
}
fn main() {
    assert(arg_count() == 3);
    var path:        u8[>..] = []; arg(1, path);
    var output_path: u8[>..] = []; arg(2, output_path);
    var data:        u8[>..] = []; assert(read_file(path, data));
    assert(data.len <= 8388608);
    var reader = binary::reader(data);
    var out = str("sentinel");
    var result: u8[>..] = [];
    var cases:  i64     = 0;
    let styles = [terminal::Style.Plain, terminal::Style.Emphasis, terminal::Style.Success, terminal::Style.Warning, terminal::Style.Failure];
    let policies = [terminal::Color.Auto, terminal::Color.Always, terminal::Color.Never];
    while reader.pos < data.len {
        assert(cases < 32);
        let h, ok = binary::read_bytes(reader, 40); assert(ok && h[0] <= 4);
        let columns, c_ok = binary::read_i64le(h, 4);
        let a, a_ok = binary::read_i64le(h, 12);
        let b, b_ok = binary::read_i64le(h, 20);
        let c, v_ok = binary::read_i64le(h, 28);
        let count, n_ok = binary::read_u32le(h, 36);
        assert(c_ok && a_ok && b_ok && v_ok && n_ok && count <= 1025);
        assert(h[2] <= 1 && h[3] <= 1);
        if h[0] == 4 { assert(h[1] <= 2 && count == 0 && a >= 0 && a <= 1); }
        else { assert(h[1] <= 1 && (h[0] == 1 || count == 1)); }
        if h[0] == 0 { assert(a >= 0 && a < 5); }
        var cells:         terminal::Cell[>..] = [];
        var payload_bytes: i64                 = 0;
        for i in count {
            let size, size_ok = binary::read_u32le(reader); assert(size_ok && size <= 65536);
            payload_bytes += size;
            assert(payload_bytes <= 1048576);
            let text, text_ok = binary::read_bytes(reader, size); assert(text_ok);
            cells.push(terminal::Cell { bytes: text });
        }
        write_stderr(str("case ", cases, "\n"));
        out.clear(); out.append("sentinel");
        let caps = terminal::Capabilities { color: h[1] != 0, redraw: h[2] != 0, columns: columns };
        var error = terminal::Error.None;
        if h[0] == 0 { error = terminal::line(caps, styles[a], cells[0].bytes, out); }
        else if h[0] == 1 { error = terminal::table(caps, cells, a, out); }
        else if h[0] == 2 { error = terminal::progress(caps, a, b, c, cells[0].bytes, h[3] != 0, out); }
        else if h[0] == 3 { error = terminal::spinner(caps, a, cells[0].bytes, h[3] != 0, out); }
        else {
            let facts = terminal::Facts { tty: h[2] != 0, dumb: h[3] != 0, no_color: a != 0, columns: columns };
            let resolved = terminal::resolve(facts, policies[h[1] as i64]);
            out.clear(); out.push(if resolved.color { 1 } else { 0 }); out.push(if resolved.redraw { 1 } else { 0 });
            append_u32(resolved.columns as u32, out);
        }
        assert(out.len <= terminal::MAX_OUTPUT_BYTES);
        let code: u8 = if error == terminal::Error.None { 0 } else if error == terminal::Error.InvalidArgument { 1 } else { 2 };
        result.push(code); append_u32(out.len as u32, result); result.append(out);
        cases++;
    }
    assert(write_file(output_path, result));
    print("fuzz batch rendered: ", cases);
}
