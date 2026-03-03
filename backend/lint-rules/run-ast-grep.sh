#!/usr/bin/env bash
set -u -o pipefail

AST_GREP_CONFIG="${AST_GREP_CONFIG:-lint-rules/sgconfig.yml}"
AST_GREP_PATH="${AST_GREP_PATH:-src}"

if ! command -v ast-grep >/dev/null 2>&1; then
  echo "ast-grep is not installed or not on PATH." >&2
  exit 127
fi

ast-grep -c "$AST_GREP_CONFIG" scan "$AST_GREP_PATH"
status=$?

if [ "$status" -ne 0 ]; then
  cat >&2 <<'EOF'

NOTE FOR THE CODE AGENT:
These ast-grep findings come from project-specific rules written by the user.
Treat the findings as intentional by default, but do not assume the rules are perfect.
If a reported issue looks incorrect, too broad, or misses an important edge case,
do not silently work around it. Tell the user which rule seems wrong or incomplete,
explain why, and suggest how the rule should be adjusted.

EOF
fi

exit "$status"