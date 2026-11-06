// SPDX-License-Identifier: Apache-2.0
namespace terminal;
import std;

const MAX_INPUT_BYTES = 4096;
const MAX_TABLE_INPUT_BYTES = 65536;
const MAX_CELLS = 1024;
const MAX_COLUMNS = 16;
const MAX_ROWS = 256;
const MAX_WIDTH = 512;
const MAX_OUTPUT_BYTES = 131072;

enum Error { None, InvalidArgument, LimitExceeded }
enum Color { Auto, Always, Never }
enum Style { Plain, Emphasis, Success, Warning, Failure }
struct Facts { tty: bool = false, dumb: bool = false, no_color: bool = false, columns: i64 = 0 }
struct Capabilities { color: bool = false, redraw: bool = false, columns: i64 = 80 }
struct Cell { bytes: const u8[:] }

// Unknown/invalid width falls back to 80 for plain layouts, disables redraw.
fn resolve(facts: Facts, color: Color = Color.Auto) -> Capabilities {
    let known_width = facts.columns >= 2 && facts.columns <= MAX_WIDTH;
    Capabilities {
        color:   color == Color.Always || (color == Color.Auto && facts.tty && !facts.dumb && !facts.no_color),
        redraw:  facts.tty && !facts.dumb && known_width,
        columns: if known_width { facts.columns } else { 80 },
    }
}
fn detail_valid(caps: Capabilities) -> bool { caps.columns >= 2 && caps.columns <= MAX_WIDTH }
fn detail_byte_width(c: u8) -> i64 {
    if c == '\\' { 2 } else if c >= 32 && c <= 126 { 1 } else { 4 }
}
fn detail_escaped_width(text: const u8[:]) -> i64 {
    var width: i64 = 0;
    for c in text { width += detail_byte_width(c); }
    width
}
// Append printable spans in bulk. No application-defined formatting is called.
fn detail_append_safe(text: const u8[:], out: u8[>..]&) {
    let hex = "0123456789abcdef";
    var start: i64 = 0;
    for c, i in text {
        if c >= 32 && c <= 126 && c != '\\' { continue; }
        out.append(text[start..i]);
        if c == '\\' { out.append("\\\\"); }
        else {
            out.append("\\x");
            out.push(hex[(c >> 4) as i64]);
            out.push(hex[(c & 15) as i64]);
        }
        start = i + 1;
    }
    out.append(text[start..]);
}
fn detail_style_code(style: Style) -> const u8[:] {
    if style == Style.Emphasis { "\x1b[1m" }
    else if style == Style.Success { "\x1b[32m" }
    else if style == Style.Warning { "\x1b[33m" }
    else if style == Style.Failure { "\x1b[31m" }
    else { "" }
}
fn line(caps: Capabilities, style: Style, text: const u8[:], out: u8[>..]&) -> Error {
    out.clear();
    if !detail_valid(caps) { return Error.InvalidArgument; }
    if text.len > MAX_INPUT_BYTES { return Error.LimitExceeded; }
    let styled = caps.color && style != Style.Plain;
    if styled { out.append(detail_style_code(style)); }
    detail_append_safe(text, out);
    if styled { out.append("\x1b[0m"); }
    out.push('\n');
    Error.None
}

// Entire preflight precedes rendering; multiplication involves bounded values.
fn table(caps: Capabilities, cells: const Cell[:], columns: i64, out: u8[>..]&) -> Error {
    out.clear();
    if !detail_valid(caps) || columns < 1 || columns > MAX_COLUMNS { return Error.InvalidArgument; }
    if cells.len > MAX_CELLS { return Error.LimitExceeded; }
    if cells.len % columns != 0 { return Error.InvalidArgument; }
    let rows = cells.len / columns;
    if rows > MAX_ROWS { return Error.LimitExceeded; }
    if rows == 0 { return Error.None; }
    var sizes:       i64[MAX_COLUMNS] = [0; MAX_COLUMNS];
    var input_bytes: i64              = 0;
    // Reject aggregate length before inspecting payload bytes.
    for cell in cells {
        if cell.bytes.len > MAX_INPUT_BYTES || cell.bytes.len > MAX_TABLE_INPUT_BYTES - input_bytes { return Error.LimitExceeded; }
        input_bytes += cell.bytes.len;
    }
    for cell, i in cells {
        let width = detail_escaped_width(cell.bytes);
        let col = i % columns;
        if width > sizes[col] { sizes[col] = width; }
    }
    var row_width = 2 * (columns - 1);
    for col in columns { row_width += sizes[col]; }
    // Last column is reserved even for tables: safe if written at column zero.
    if row_width >= caps.columns || rows * (row_width + 1) > MAX_OUTPUT_BYTES { return Error.LimitExceeded; }
    for row in rows {
        for col in columns {
            let text = cells[row * columns + col].bytes;
            detail_append_safe(text, out);
            if col + 1 < columns {
                for padding in sizes[col] - detail_escaped_width(text) + 2 { out.push(' '); }
            }
        }
        out.push('\n');
    }
    Error.None
}
fn detail_append_number(value: i64, out: u8[>..]&) {
    var digits: u8[19] = [0; 19];
    var at:     i64    = 19;
    var remaining = value;
    while true {
        at--;
        digits[at] = '0' + ((remaining % 10) as u8);
        remaining /= 10;
        if remaining == 0 { break; }
    }
    out.append(digits[at..]);
}
fn detail_number_width(value: i64) -> i64 {
    var count: i64 = 1;
    var remaining = value;
    while remaining >= 10 { remaining /= 10; count++; }
    count
}
// floor(completed * width / total), without the overflowing multiplication.
fn detail_filled_cells(completed: i64, total: i64, width: i64) -> i64 {
    let quotient = total / width;
    let remainder = total % width;
    var filled: i64 = 0;
    for i in 1..width + 1 {
        let threshold = quotient * i + (remainder * i + width - 1) / width;
        if completed >= threshold { filled = i; }
    }
    filled
}
fn detail_start_frame(caps: Capabilities, out: u8[>..]&) {
    if caps.redraw { out.append("\r\x1b[2K"); }
}
fn detail_end_frame(caps: Capabilities, final: bool, out: u8[>..]&) {
    if !caps.redraw || final { out.push('\n'); }
}
fn progress(caps: Capabilities, completed: i64, total: i64, width: i64, label: const u8[:], final: bool, out: u8[>..]&) -> Error {
    out.clear();
    if !detail_valid(caps) || total <= 0 || completed < 0 || completed > total || width < 1 || width > 256 { return Error.InvalidArgument; }
    if label.len > MAX_INPUT_BYTES { return Error.LimitExceeded; }
    let visible = width + 5 + detail_number_width(completed) + detail_number_width(total) + detail_escaped_width(label);
    if visible >= caps.columns { return Error.LimitExceeded; }
    detail_start_frame(caps, out);
    out.push('[');
    let filled = detail_filled_cells(completed, total, width);
    for i in width { out.push(if i < filled { '#' } else { '-' }); }
    out.append("] ");
    detail_append_number(completed, out); out.push('/'); detail_append_number(total, out);
    out.push(' '); detail_append_safe(label, out);
    detail_end_frame(caps, final, out);
    Error.None
}
fn spinner(caps: Capabilities, tick: i64, label: const u8[:], final: bool, out: u8[>..]&) -> Error {
    out.clear();
    if !detail_valid(caps) || tick < 0 { return Error.InvalidArgument; }
    if label.len > MAX_INPUT_BYTES { return Error.LimitExceeded; }
    let prefix_width = if final { 5 } else { 2 };
    if prefix_width + detail_escaped_width(label) >= caps.columns { return Error.LimitExceeded; }
    detail_start_frame(caps, out);
    if final { out.append("done "); }
    else { out.push("|/-\\"[tick % 4]); out.push(' '); }
    detail_append_safe(label, out);
    detail_end_frame(caps, final, out);
    Error.None
}
