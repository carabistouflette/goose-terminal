/* SPDX-License-Identifier: Apache-2.0 */
#define _POSIX_C_SOURCE 200809L
#include <errno.h>
#include <pthread.h>
#include <signal.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#include <sys/ioctl.h>
#include <time.h>
#include <unistd.h>

typedef struct { const uint8_t *data; int64_t len; } gt_bytes;
typedef struct { int64_t *data; int64_t len; } gt_meta;
enum { GT_MAX_OUTPUT = 131072 };

/* Only stdout/stderr are supported. No borrowed descriptor is ever closed. */
static int gt_fd(int64_t fd) { return fd == STDOUT_FILENO || fd == STDERR_FILENO; }
int64_t gt_posix_snapshot(int64_t fd, gt_meta meta) {
    if (meta.len != 5 || !meta.data) return EINVAL;
    memset(meta.data, 0, 5 * sizeof(int64_t));
    meta.data[2] = 1; /* conservative on invalid fd / absent TERM */
    if (!gt_fd(fd)) return EINVAL;
    const char *term = getenv("TERM");
    const char *no_color = getenv("NO_COLOR");
    meta.data[2] = !term || !term[0] || strncmp(term, "dumb", 5) == 0;
    meta.data[3] = no_color && no_color[0];
    errno = 0;
    if (!isatty((int)fd)) return errno == ENOTTY ? 0 : errno;
    meta.data[0] = 1;
    struct winsize size;
    memset(&size, 0, sizeof size);
    if (ioctl((int)fd, TIOCGWINSZ, &size) < 0) return errno;
    meta.data[1] = size.ws_col;
    return 0;
}

/* One syscall, with thread-local SIGPIPE protection. A blocking fd can block.
 * meta = written bytes, operation errno, signal-mask cleanup errno.
 * Status: 0 success (possibly short), 1 invalid, 2 OS, 3 EINTR, 4 EAGAIN.
 * Environment and descriptor ownership must remain stable during each call. */
int64_t gt_posix_write(int64_t fd, gt_bytes bytes, gt_meta meta) {
    if (meta.len != 3 || !meta.data) return 1;
    memset(meta.data, 0, 3 * sizeof(int64_t));
    if (!gt_fd(fd) || bytes.len < 0 || bytes.len > GT_MAX_OUTPUT || (bytes.len && !bytes.data)) {
        meta.data[1] = EINVAL; return 1;
    }
    if (!bytes.len) return 0;
    sigset_t pipe_set, old_mask, pending;
    if (sigemptyset(&pipe_set) < 0 || sigaddset(&pipe_set, SIGPIPE) < 0) {
        meta.data[1] = errno; return 2;
    }
    int error = pthread_sigmask(SIG_BLOCK, &pipe_set, &old_mask);
    if (error) { meta.data[1] = error; return 2; }
    if (sigpending(&pending) < 0) {
        meta.data[1] = errno;
        meta.data[2] = pthread_sigmask(SIG_SETMASK, &old_mask, NULL);
        return 2;
    }
    int had_pipe = sigismember(&pending, SIGPIPE);
    ssize_t written = write((int)fd, bytes.data, (size_t)bytes.len);
    error = written < 0 ? errno : 0;
    if (written >= 0) meta.data[0] = written;
    meta.data[1] = error;
    if (error == EPIPE && !had_pipe) {
        const struct timespec zero = {0, 0};
        /* Do not spin on unrelated signals. If interrupted, leave SIGPIPE
         * blocked and explicitly report cleanup failure rather than deliver it. */
        if (sigtimedwait(&pipe_set, NULL, &zero) < 0 && errno != EAGAIN) {
            meta.data[2] = errno;
            return 2;
        }
    }
    meta.data[2] = pthread_sigmask(SIG_SETMASK, &old_mask, NULL);
    if (meta.data[2]) return 2;
    if (!error) return 0;
    if (error == EINTR) return 3;
    if (error == EAGAIN || error == EWOULDBLOCK) return 4;
    return 2;
}
