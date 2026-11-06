#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
set -euo pipefail
link_flags=(-no-pie)
for argument in "$@"; do
    case "$argument" in -c|-E|-S) link_flags=(); break ;; esac
done
exec "${SANITIZER_CC:-gcc}" -fsanitize=address,undefined -fno-sanitize-recover=all -fno-omit-frame-pointer -fno-pie "${link_flags[@]}" "$@"
