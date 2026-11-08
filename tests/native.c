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

static int write_fault, calls;
#if !defined(__APPLE__)
static int restore_fault, wait_fault, pending_fault, pending_calls, wait_calls;
#endif
static ssize_t gt_test_write(int fd, const void *p, size_t n) {
    calls++;
    if (write_fault) { errno = write_fault; return -1; }
    return write(fd, p, n);
}
#if !defined(__APPLE__)
static int gt_test_pthread_sigmask(int how, const sigset_t *set, sigset_t *old) {
    if (restore_fault && how == SIG_SETMASK) return EINVAL;
    return pthread_sigmask(how, set, old);
}
static int gt_test_sigpending(sigset_t *set) {
    pending_calls++;
    if (pending_fault == pending_calls) { errno = EIO; return -1; }
    return sigpending(set);
}
static int gt_test_sigwait(const sigset_t *set, int *signal) {
    wait_calls++;
    if (wait_fault) return EINTR;
    return sigwait(set, signal);
}
#endif
/* Compile the production source itself under test-only syscall substitutions.
 * No linker --wrap feature, alternate implementation or production hook. */
#define write gt_test_write
#if !defined(__APPLE__)
#define pthread_sigmask gt_test_pthread_sigmask
#define sigwait gt_test_sigwait
#define sigpending gt_test_sigpending
#endif
#include "../native/posix.c"
#undef sigpending
#undef sigwait
#undef pthread_sigmask
#undef write

static void same_mask(const sigset_t *before) {
    sigset_t after; assert(pthread_sigmask(SIG_SETMASK, NULL, &after) == 0);
#if defined(__APPLE__)
    const int max_signal = 32;
#elif defined(NSIG)
    const int max_signal = NSIG;
#else
    const int max_signal = 64;
#endif
    for (int signal = 1; signal < max_signal; ++signal)
        assert(sigismember(before, signal) == sigismember(&after, signal));
}
static void raw_write_flag_control(void) {
    int pipefd[2]; assert(pipe(pipefd) == 0);
    const int before_flags = fcntl(pipefd[1], F_GETFL); assert(before_flags >= 0);
    assert(write(pipefd[1], "x", 1) == 1);
    const int after_flags = fcntl(pipefd[1], F_GETFL); assert(after_flags >= 0);
    if (before_flags != after_flags) {
        fprintf(stderr, "raw OS write F_GETFL: before=0x%x after=0x%x delta=0x%x\n",
                (unsigned)before_flags, (unsigned)after_flags,
                (unsigned)(before_flags ^ after_flags));
    }
    assert(close(pipefd[1]) == 0); assert(close(pipefd[0]) == 0);
}
int main(void) {
    raw_write_flag_control();
    int64_t values[5]; gt_meta meta = {values, 3};
    gt_bytes empty = {NULL, 0}, one = {(const uint8_t *)"x", 1};
    assert(gt_posix_write(-1, one, meta) == 1 && values[0] == 0 && values[1] == EINVAL);
    assert(gt_posix_write(1, (gt_bytes){NULL, 1}, meta) == 1);
    assert(gt_posix_write(1, (gt_bytes){one.data, -1}, meta) == 1);
    assert(gt_posix_write(1, (gt_bytes){one.data, 131073}, meta) == 1);
    assert(gt_posix_write(1, empty, meta) == 0 && calls == 0);
    assert(gt_posix_snapshot(-1, (gt_meta){values, 5}) == EINVAL);
#if defined(__APPLE__)
    struct sigaction app_original, app_policy;
    assert(sigaction(SIGPIPE, NULL, &app_original) == 0);
    memset(&app_policy, 0, sizeof app_policy); app_policy.sa_handler = SIG_DFL;
    assert(sigemptyset(&app_policy.sa_mask) == 0);
    assert(sigaction(SIGPIPE, &app_policy, NULL) == 0);
    assert(gt_posix_write(1, one, meta) == 2 && values[0] == 0 && values[1] == ENOTSUP && calls == 0);
    app_policy.sa_handler = SIG_IGN;
    assert(sigaction(SIGPIPE, &app_policy, NULL) == 0);
#endif
    sigset_t before, pending;
#if !defined(__APPLE__)
    sigset_t set;
#endif
    assert(pthread_sigmask(SIG_SETMASK, NULL, &before) == 0);
    int saved = dup(1); assert(saved >= 0);
    int pipefd[2]; assert(pipe(pipefd) == 0);
    assert(dup2(pipefd[1], 1) == 1); close(pipefd[1]);
    /* Darwin records first-write history in F_GETFL (kernel FWASWRITTEN).
     * Settle that OS bookkeeping during fixture setup, before lending the fd.
     * The adapter must still preserve the entire observed flag word exactly. */
    assert(write(1, "x", 1) == 1);
    int flags = fcntl(1, F_GETFL); assert(flags >= 0);
    assert(fcntl(1, F_SETFL, flags | O_NONBLOCK) == 0);
    const int borrowed_flags = fcntl(1, F_GETFL);
    assert(borrowed_flags >= 0 && (borrowed_flags & O_NONBLOCK));
    static uint8_t data[131072]; memset(data, 'x', sizeof data);
    calls = 0;
    assert(gt_posix_write(1, (gt_bytes){data, sizeof data}, meta) == 0);
    assert(values[0] > 0 && values[0] < (int64_t)sizeof data && !values[1] && calls == 1);
    assert(gt_posix_write(1, (gt_bytes){data, sizeof data}, meta) == 4 && values[1] == EAGAIN);
    const int observed_flags = fcntl(1, F_GETFL);
    if (observed_flags != borrowed_flags) {
        fprintf(stderr, "adapter write F_GETFL: before=0x%x after=0x%x delta=0x%x O_NONBLOCK=0x%x O_APPEND=0x%x O_ACCMODE=0x%x\n",
                (unsigned)borrowed_flags, (unsigned)observed_flags,
                (unsigned)(borrowed_flags ^ observed_flags),
                (unsigned)O_NONBLOCK, (unsigned)O_APPEND, (unsigned)O_ACCMODE);
    }
    assert(observed_flags == borrowed_flags); same_mask(&before);
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
    /* Exercise ignored disposition too; Linux can queue it while blocked. */
    struct sigaction ignored; memset(&ignored, 0, sizeof ignored);
    ignored.sa_handler = SIG_IGN; assert(sigemptyset(&ignored.sa_mask) == 0);
    assert(sigaction(SIGPIPE, &ignored, NULL) == 0);
    assert(gt_posix_write(1, one, meta) == 2 && values[1] == EPIPE && values[2] == 0);
    same_mask(&before);
    assert(sigpending(&pending) == 0 && !sigismember(&pending, SIGPIPE));
    assert(sigaction(SIGPIPE, &disposition, NULL) == 0);
#if !defined(__APPLE__)
    /* Synthetic EPIPE has no generated signal: the pending check must skip wait. */
    write_fault = EPIPE; wait_calls = 0;
    assert(gt_posix_write(1, one, meta) == 2 && values[0] == 0 && values[1] == EPIPE && values[2] == 0);
    assert(wait_calls == 0); same_mask(&before);
    assert(sigpending(&pending) == 0 && !sigismember(&pending, SIGPIPE));
    write_fault = 0;
    /* Preserve a SIGPIPE that was already blocked and pending. */
    sigemptyset(&set); sigaddset(&set, SIGPIPE);
    assert(pthread_sigmask(SIG_BLOCK, &set, NULL) == 0); assert(raise(SIGPIPE) == 0);
    assert(gt_posix_write(1, one, meta) == 2 && values[1] == EPIPE);
    assert(sigpending(&pending) == 0 && sigismember(&pending, SIGPIPE));
    int consumed = 0; assert(sigwait(&set, &consumed) == 0 && consumed == SIGPIPE);
    assert(pthread_sigmask(SIG_SETMASK, &before, NULL) == 0);
    /* Failure before writing restores the mask and reports no written bytes. */
    pending_calls = 0; pending_fault = 1;
    int previous_calls = calls;
    assert(gt_posix_write(1, one, meta) == 2 && values[0] == 0 && values[1] == EIO && values[2] == 0);
    assert(calls == previous_calls); same_mask(&before);
    /* Failure after EPIPE preserves the actual pending signal under the mask. */
    pending_calls = 0; pending_fault = 2;
    assert(gt_posix_write(1, one, meta) == 2 && values[1] == EPIPE && values[2] == EIO);
    assert(sigpending(&pending) == 0 && sigismember(&pending, SIGPIPE));
    pending_fault = 0;
    assert(sigwait(&set, &consumed) == 0 && consumed == SIGPIPE);
    assert(pthread_sigmask(SIG_SETMASK, &before, NULL) == 0);
    /* Cleanup failures are reported separately; caller must stop using thread. */
    write_fault = 0; wait_fault = 1;
    assert(gt_posix_write(1, one, meta) == 2 && values[1] == EPIPE && values[2] == EINTR);
    assert(sigpending(&pending) == 0 && sigismember(&pending, SIGPIPE));
    sigset_t leaked; assert(pthread_sigmask(SIG_SETMASK, NULL, &leaked) == 0);
    assert(sigismember(&leaked, SIGPIPE));
    wait_fault = 0;
    assert(sigwait(&set, &consumed) == 0 && consumed == SIGPIPE);
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
#endif
    assert(dup2(saved, 1) == 1); close(saved);
    int closed = dup(1); assert(closed >= 0); close(1);
    assert(gt_posix_snapshot(1, (gt_meta){values, 5}) == EBADF);
    assert(gt_posix_write(1, one, meta) == 2 && values[1] == EBADF);
    assert(dup2(closed, 1) == 1); close(closed);
#if defined(__APPLE__)
    assert(sigaction(SIGPIPE, &app_original, NULL) == 0);
#endif
    puts("native adapter: partial/EINTR/EAGAIN/EPIPE, masks and descriptor flags passed");
}
