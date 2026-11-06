/* SPDX-License-Identifier: Apache-2.0 */
#define _POSIX_C_SOURCE 200809L
#include <assert.h>
#include <errno.h>
#include <fcntl.h>
#include <pthread.h>
#include <signal.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <unistd.h>

typedef struct { const uint8_t *data; int64_t len; } gt_bytes;
typedef struct { int64_t *data; int64_t len; } gt_meta;
int64_t gt_posix_write(int64_t, gt_bytes, gt_meta);
int64_t gt_posix_snapshot(int64_t, gt_meta);
ssize_t __real_write(int, const void *, size_t);
int __real_pthread_sigmask(int, const sigset_t *, sigset_t *);
int __real_sigtimedwait(const sigset_t *, siginfo_t *, const struct timespec *);
static int write_fault, restore_fault, wait_fault, calls;
ssize_t __wrap_write(int fd, const void *p, size_t n) {
    calls++;
    if (write_fault) { errno = write_fault; return -1; }
    return __real_write(fd, p, n);
}
int __wrap_pthread_sigmask(int how, const sigset_t *set, sigset_t *old) {
    if (restore_fault && how == SIG_SETMASK) return EINVAL;
    return __real_pthread_sigmask(how, set, old);
}
int __wrap_sigtimedwait(const sigset_t *set, siginfo_t *info, const struct timespec *time) {
    if (wait_fault) { errno = EINTR; return -1; }
    return __real_sigtimedwait(set, info, time);
}
static void same_mask(const sigset_t *before) {
    sigset_t after; assert(pthread_sigmask(SIG_SETMASK, NULL, &after) == 0);
    for (int signal = 1; signal < 64; ++signal)
        assert(sigismember(before, signal) == sigismember(&after, signal));
}
int main(void) {
    int64_t values[5]; gt_meta meta = {values, 3};
    gt_bytes empty = {NULL, 0}, one = {(const uint8_t *)"x", 1};
    assert(gt_posix_write(-1, one, meta) == 1 && values[0] == 0 && values[1] == EINVAL);
    assert(gt_posix_write(1, (gt_bytes){NULL, 1}, meta) == 1);
    assert(gt_posix_write(1, (gt_bytes){one.data, -1}, meta) == 1);
    assert(gt_posix_write(1, (gt_bytes){one.data, 131073}, meta) == 1);
    assert(gt_posix_write(1, empty, meta) == 0 && calls == 0);
    assert(gt_posix_snapshot(-1, (gt_meta){values, 5}) == EINVAL);
    sigset_t before, pending, set;
    assert(pthread_sigmask(SIG_SETMASK, NULL, &before) == 0);
    int saved = dup(1); assert(saved >= 0);
    int pipefd[2]; assert(pipe(pipefd) == 0);
    assert(dup2(pipefd[1], 1) == 1); close(pipefd[1]);
    int flags = fcntl(1, F_GETFL); assert(flags >= 0);
    assert(fcntl(1, F_SETFL, flags | O_NONBLOCK) == 0);
    static uint8_t data[131072]; memset(data, 'x', sizeof data);
    calls = 0;
    assert(gt_posix_write(1, (gt_bytes){data, sizeof data}, meta) == 0);
    assert(values[0] > 0 && values[0] < (int64_t)sizeof data && !values[1] && calls == 1);
    assert(gt_posix_write(1, (gt_bytes){data, sizeof data}, meta) == 4 && values[1] == EAGAIN);
    assert(fcntl(1, F_GETFL) == (flags | O_NONBLOCK)); same_mask(&before);
    for (int error = 0; error < 3; ++error) {
        write_fault = error == 0 ? EINTR : error == 1 ? EAGAIN : EIO;
        assert(gt_posix_write(1, one, meta) == (error == 0 ? 3 : error == 1 ? 4 : 2));
        assert(values[0] == 0 && values[1] == write_fault && values[2] == 0); same_mask(&before);
    }
    write_fault = 0;
    close(pipefd[0]); /* no reader: actual SIGPIPE must not kill this process */
    struct sigaction disposition, after; assert(sigaction(SIGPIPE, NULL, &disposition) == 0);
    assert(gt_posix_write(1, one, meta) == 2 && values[1] == EPIPE);
    same_mask(&before);
    assert(sigpending(&pending) == 0 && !sigismember(&pending, SIGPIPE));
    assert(sigaction(SIGPIPE, NULL, &after) == 0 && disposition.sa_handler == after.sa_handler);
    /* Preserve a SIGPIPE that was already blocked and pending. */
    sigemptyset(&set); sigaddset(&set, SIGPIPE);
    assert(pthread_sigmask(SIG_BLOCK, &set, NULL) == 0); assert(raise(SIGPIPE) == 0);
    assert(gt_posix_write(1, one, meta) == 2 && values[1] == EPIPE);
    assert(sigpending(&pending) == 0 && sigismember(&pending, SIGPIPE));
    const struct timespec zero = {0, 0}; assert(sigtimedwait(&set, NULL, &zero) == SIGPIPE);
    assert(pthread_sigmask(SIG_SETMASK, &before, NULL) == 0);
    /* Cleanup failures are reported separately; caller must stop using thread. */
    write_fault = 0; wait_fault = 1;
    assert(gt_posix_write(1, one, meta) == 2 && values[1] == EPIPE && values[2] == EINTR);
    assert(sigpending(&pending) == 0 && sigismember(&pending, SIGPIPE));
    sigset_t leaked; assert(pthread_sigmask(SIG_SETMASK, NULL, &leaked) == 0);
    assert(sigismember(&leaked, SIGPIPE));
    wait_fault = 0;
    assert(sigtimedwait(&set, NULL, &zero) == SIGPIPE);
    assert(pthread_sigmask(SIG_SETMASK, &before, NULL) == 0);
    write_fault = EIO; restore_fault = 1;
    assert(gt_posix_write(1, one, meta) == 2 && values[1] == EIO && values[2] == EINVAL);
    restore_fault = 0; assert(pthread_sigmask(SIG_SETMASK, &before, NULL) == 0);
    write_fault = 0;
    int sink = open("/dev/null", O_WRONLY); assert(sink >= 0);
    assert(dup2(sink, 1) == 1); close(sink);
    restore_fault = 1;
    assert(gt_posix_write(1, one, meta) == 2 && values[0] == 1 && values[1] == 0 && values[2] == EINVAL);
    restore_fault = 0; assert(pthread_sigmask(SIG_SETMASK, &before, NULL) == 0);
    assert(dup2(saved, 1) == 1); close(saved);
    int closed = dup(1); assert(closed >= 0); close(1);
    assert(gt_posix_snapshot(1, (gt_meta){values, 5}) == EBADF);
    assert(gt_posix_write(1, one, meta) == 2 && values[1] == EBADF);
    assert(dup2(closed, 1) == 1); close(closed);
    puts("native adapter: partial/EINTR/EAGAIN/EPIPE, masks and descriptor flags passed");
}
