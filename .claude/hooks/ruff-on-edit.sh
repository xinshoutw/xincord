#!/bin/sh
# PostToolUse: format an edited Python file and apply ruff's safe fixes. F401 stays unfixable so
# an import added one edit before its first use is not deleted in between.
file=$(jq -r '.tool_input.file_path // empty')
case "${file}" in
  *.py | *.pyi) ;;
  *) exit 0 ;;
esac
cd "${CLAUDE_PROJECT_DIR}" || exit 0
uv run --locked ruff format --quiet "${file}"
uv run --locked ruff check --fix --unfixable F401 --quiet "${file}" > /dev/null
exit 0
