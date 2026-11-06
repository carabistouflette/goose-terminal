// SPDX-License-Identifier: Apache-2.0
// Optional POSIX adapter. Importing terminal alone never links this module.
namespace terminal_posix;
import .terminal;
import std;

enum WriteError { None, InvalidArgument, OsError, Interrupted, WouldBlock }
struct Write { written: i64 = 0, error: WriteError = WriteError.None, os_error: i64 = 0, cleanup_error: i64 = 0 }
struct Snapshot { capabilities: terminal::Capabilities, tty: bool = false, os_error: i64 = 0 }
extern fn detail_snapshot(fd: i64, meta: i64[:]) -> i64 = "gt_posix_snapshot";
extern fn detail_write(fd: i64, bytes: const u8[:], meta: i64[:]) -> i64 = "gt_posix_write";

fn snapshot(fd: i64, color: terminal::Color = terminal::Color.Auto) -> Snapshot {
    var meta: i64[5] = [0; 5];
    let error = detail_snapshot(fd, meta);
    let facts = terminal::Facts { tty: meta[0] != 0, dumb: meta[2] != 0, no_color: meta[3] != 0, columns: meta[1] };
    Snapshot { capabilities: terminal::resolve(facts, color), tty: facts.tty, os_error: error }
}
// One write only; caller handles short writes and retry policy using written.
// Descriptor flags/ownership and process-wide signal dispositions are untouched.
fn write_step(fd: i64, bytes: const u8[:]) -> Write {
    var meta: i64[3] = [0; 3];
    let status = detail_write(fd, bytes, meta);
    let error = if status == 0 { WriteError.None }
        else if status == 1 { WriteError.InvalidArgument }
        else if status == 3 { WriteError.Interrupted }
        else if status == 4 { WriteError.WouldBlock }
        else { WriteError.OsError };
    Write { written: meta[0], error: error, os_error: meta[1], cleanup_error: meta[2] }
}
