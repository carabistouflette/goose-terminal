#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
set -euo pipefail
# Keep this nonempty for macOS's older system Bash under `set -u`.
flags=(-fsanitize=address,undefined -fno-sanitize-recover=all -fno-omit-frame-pointer)
if [[ "$(uname -s)" == Linux ]]; then
    flags+=(-fno-pie)
    link=true
    for argument in "$@"; do
        case "$argument" in -c|-E|-S) link=false; break ;; esac
    done
    if $link; then flags+=(-no-pie); fi
fi
exec "${SANITIZER_CC:-gcc}" "${flags[@]}" "$@"
