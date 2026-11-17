#!/usr/bin/env sh
# Install the RecapLion skill for one or more AI agents.
#
#   ./install.sh                 # auto-detect installed agents
#   ./install.sh claude codex    # pick targets
#   ./install.sh --dir ~/my/skills
#   curl -fsSL https://raw.githubusercontent.com/malilion/RecapLion/main/install.sh | sh
#
# Targets:
#   claude   ~/.claude/skills   (Claude Code)
#   agents   ~/.agents/skills   (shared location read by Codex and other Agent Skills clients)
#   codex    same as agents
# Other agents: pass their skills folder with --dir.
set -eu

NAME="github-year-review"
REPO="https://github.com/malilion/RecapLion"
HERE=$(CDPATH= cd -- "$(dirname -- "$0")" 2>/dev/null && pwd || echo "")
SRC="$HERE/skills/$NAME"
TMP=""

if [ ! -f "$SRC/SKILL.md" ]; then
  command -v git >/dev/null 2>&1 || { echo "git is required" >&2; exit 1; }
  TMP=$(mktemp -d)
  git clone --depth 1 -q "$REPO" "$TMP/RecapLion"
  SRC="$TMP/RecapLion/skills/$NAME"
fi

dir_for() {
  case "$1" in
    claude) echo "$HOME/.claude/skills" ;;
    agents|codex) echo "$HOME/.agents/skills" ;;
    *) echo "" ;;
  esac
}

TARGETS=""
if [ "$#" -gt 0 ] && [ "$1" = "--dir" ]; then
  [ "$#" -ge 2 ] || { echo "--dir needs a path" >&2; exit 1; }
  DIRS="$2"
elif [ "$#" -gt 0 ]; then
  TARGETS="$*"
else
  [ -d "$HOME/.claude" ] && TARGETS="$TARGETS claude"
  { [ -d "$HOME/.codex" ] || [ -d "$HOME/.agents" ]; } && TARGETS="$TARGETS agents"
  [ -n "$TARGETS" ] || TARGETS="agents"
fi

if [ -z "${DIRS:-}" ]; then
  DIRS=""
  for t in $TARGETS; do
    d=$(dir_for "$t")
    [ -n "$d" ] || { echo "unknown target: $t" >&2; exit 1; }
    case " $DIRS " in *" $d "*) ;; *) DIRS="$DIRS $d" ;; esac
  done
fi

for d in $DIRS; do
  mkdir -p "$d"
  rm -rf "${d:?}/$NAME"
  cp -R "$SRC" "$d/$NAME"
  find "$d/$NAME" -name __pycache__ -prune -exec rm -rf {} + 2>/dev/null || true
  echo "✓ installed $NAME → $d/$NAME"
done

[ -n "$TMP" ] && rm -rf "$TMP"
echo "Ask your agent: \"Make my GitHub year in review\" (or run scripts/recap.py --user <login>)."
