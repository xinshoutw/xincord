#!/bin/sh
# Stop: keep working until the full gate passes; skip it when nothing changed since it last passed.
cd "${CLAUDE_PROJECT_DIR}" || exit 0
stamp=$(git rev-parse --git-path stop-gate-passed)
head=$(git rev-parse HEAD 2>/dev/null)
if [ -n "${head}" ] && [ -z "$(git status --porcelain)" ] && [ "$(cat "${stamp}" 2>/dev/null)" = "${head}" ]; then
  exit 0
fi
if ! output=$(scripts/gate.sh 2>&1); then
  printf 'scripts/gate.sh failed; fix it before stopping.\n' >&2
  printf '%s\n' "${output}" | grep -v '^npm notice' | tail -n 60 >&2
  exit 2
fi
[ -z "$(git status --porcelain)" ] && printf '%s\n' "${head}" > "${stamp}"
exit 0
