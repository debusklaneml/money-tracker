#!/usr/bin/env sh
# Beads sync — make your local issue DB match the shared history.
#
# Safe to run ANY time, in any state. It figures out which situation you're in:
#   • no local DB              -> bootstraps the shared history (fresh clone)
#   • have the shared DB       -> 'bd dolt pull' (the normal, git-like sync)
#   • have an INDEPENDENT DB    -> one-time repair: rescue your issues, then adopt
#     the canonical history (only after you confirm; your issues are exported first)
#
# Per the beads docs the steady state is just `bd dolt pull` / `bd dolt push`
# (bootstrap once). This script is the durable front door to that: run it after
# cloning, or any time `bd bootstrap`/`bd dolt pull` errors.
#
# Usage:
#   sh scripts/beads-onboard.sh            # do it
#   sh scripts/beads-onboard.sh --dry-run  # show what it would do
#   sh scripts/beads-onboard.sh --yes      # don't prompt before a repair

set -eu

REMOTE_URL="git+https://github.com/debusklaneml/money-tracker.git"
DRY=0
ASSUME_YES=0
for arg in "$@"; do
	case "$arg" in
		--dry-run) DRY=1 ;;
		--yes | -y) ASSUME_YES=1 ;;
		*) echo "unknown flag: $arg" >&2; exit 2 ;;
	esac
done

run() { # echo + execute, or just echo under --dry-run
	echo "  \$ $*"
	[ "$DRY" -eq 1 ] && return 0
	"$@"
}

if ! command -v bd >/dev/null 2>&1; then
	echo "✗ bd (beads) is not installed. Install it first, then re-run." >&2
	exit 1
fi

cd "$(git rev-parse --show-toplevel)"

# Warn (don't block) if this machine's bd version differs from the team pin in
# .bd-version. Version drift is what causes schema-migration / wedged-DB errors.
if [ -f .bd-version ]; then
	REQ=$(tr -d ' \t\r\n' < .bd-version)
	HAVE=$(bd version 2>/dev/null | sed -n 's/^bd version \([0-9][0-9.]*\).*/\1/p' | head -1)
	if [ -n "$REQ" ] && [ -n "$HAVE" ] && [ "$REQ" != "$HAVE" ]; then
		echo "⚠ bd version mismatch: you have $HAVE, the team pin (.bd-version) is $REQ."
		echo "  Mismatched versions cause schema-migration errors across machines."
		echo "  Upgrade to match, e.g.:  brew upgrade beads   (or your install method)"
		echo "  Continuing anyway…"
		echo ""
	fi
fi

# Always enable the pre-push guard (idempotent).
run git config core.hooksPath .githooks
echo "✓ pre-push guard enabled (core.hooksPath=.githooks)"

# Make sure the Dolt remote is wired (needed for pull/bootstrap).
if ! bd dolt remote list 2>/dev/null | grep -qE '://|git\+'; then
	echo "Dolt remote not configured — adding it…"
	run bd dolt remote add origin "$REMOTE_URL" || true
fi

# --- Situation 1: no local DB -> fresh bootstrap ----------------------------
if [ ! -d .beads/embeddeddolt ]; then
	echo "No local beads DB found — bootstrapping the shared history…"
	run bd bootstrap --yes
	echo "✓ Done. Run 'bd ready' to see the backlog."
	exit 0
fi

# --- Situation 2: local DB exists -> try the normal, git-like sync first -----
echo "Local beads DB found — trying 'bd dolt pull' (the normal sync)…"
if [ "$DRY" -eq 1 ]; then
	echo "  \$ bd dolt pull   # if this fails with 'no common ancestor', a one-time repair runs"
	exit 0
fi

PULL_ERR="${TMPDIR:-/tmp}/bd-pull-err-$$.txt"
if bd dolt pull >"$PULL_ERR" 2>&1; then
	cat "$PULL_ERR"
	rm -f "$PULL_ERR"
	echo "✓ Synced via 'bd dolt pull' — already aligned with the shared history."
	exit 0
fi

# Pull failed. Classify it. Two cases are recoverable by adopting the canonical
# history; anything else we refuse to touch.
WEDGED=0
if grep -qiE "no common ancestor|database exists|unrelated histor" "$PULL_ERR"; then
	echo "⚠ Your local DB is an INDEPENDENT history (no common ancestor with the shared one)."
	echo "  This needs a one-time repair to adopt the canonical history."
elif grep -qiE "failed to open database|pending schema migration|dirty tables|init schema|migrate:" "$PULL_ERR"; then
	echo "⚠ Your local DB won't open — a schema-migration / dirty-state problem,"
	echo "  usually caused by a bd VERSION MISMATCH across machines (run 'bd version';"
	echo "  everyone should be on the same version). bd can't self-export, so we'll"
	echo "  rescue the on-disk JSONL export instead, then adopt the canonical history."
	WEDGED=1
else
	echo "✗ 'bd dolt pull' failed for an unexpected reason:" >&2
	cat "$PULL_ERR" >&2
	echo "  Not touching your local DB. Resolve the above and re-run." >&2
	rm -f "$PULL_ERR"
	exit 1
fi
rm -f "$PULL_ERR"

# Confirm before the destructive (but rescue-backed) repair.
if [ "$ASSUME_YES" -ne 1 ]; then
	printf "Adopt the canonical shared history now? Your local issues are rescued first. [y/N] "
	read -r ANS
	case "$ANS" in
		y | Y | yes | YES) ;;
		*) echo "Aborted — nothing changed."; exit 1 ;;
	esac
fi

RESCUE="${TMPDIR:-/tmp}/beads-local-rescue-$$.jsonl"
echo "Rescuing a copy of your local issues…"
# Prefer a live export; if the DB won't open (wedged), fall back to the on-disk
# JSONL export that bd keeps committed.
if ! bd export --output "$RESCUE" 2>/dev/null || [ ! -s "$RESCUE" ]; then
	if [ -f .beads/issues.jsonl ]; then
		cp .beads/issues.jsonl "$RESCUE" 2>/dev/null || true
		echo "  (DB unreadable — rescued the on-disk .beads/issues.jsonl export instead)"
	fi
fi
COUNT=0
if [ -f "$RESCUE" ]; then
	COUNT=$(grep -c . "$RESCUE" 2>/dev/null) || COUNT=0
fi
echo "  rescued $COUNT local record(s) -> $RESCUE"

echo "Removing the independent local DB and cloning the canonical history…"
rm -rf .beads/embeddeddolt
bd bootstrap --yes

echo ""
echo "✓ Adopted the shared issue history. Verify with: bd ready"
if [ "$COUNT" -gt 0 ]; then
	echo ""
	echo "⚠ You had $COUNT local record(s) saved at:"
	echo "    $RESCUE"
	echo "  If any are REAL work not already on the shared backlog, add them with:"
	echo "    bd import \"$RESCUE\" && bd dolt push"
	echo "  (Skip this if they were just a stale/empty local init.)"
fi
