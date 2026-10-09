#!/bin/sh
# Stop: keep working until the full gate passes.
cd "${CLAUDE_PROJECT_DIR}" || exit 0
if ! output=$(scripts/gate.sh 2>&1); then
  printf 'scripts/gate.sh failed; fix it before stopping.\n' >&2
  printf '%s\n' "${output}" | grep -v '^npm notice' | tail -n 60 >&2
  exit 2
fi
exit 0
