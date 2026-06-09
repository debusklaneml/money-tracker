#!/usr/bin/env sh
# Safe beads onboarding — adopt the shared issue history without losing local work.
#
# Run this ONCE after cloning, or any time `bd bootstrap` fails with
#   "Error 1007: can't create database bud; database exists"
# (that error means you already have a local beads DB from an earlier `bd init`,
#  and `bd bootstrap` refuses to overwrite it).
#
# What it does:
#   • enables the pre-push guard (core.hooksPath)
#   • if you have NO local beads DB  -> plain bootstrap from the shared remote
#   • if you DO have a local DB       -> exports a rescue copy, removes the stale
#     local DB, clones the canonical shared history, and tells you how to re-add
#     any local-only issues (it never auto-pushes local junk to the shared history)
#
# Usage:  sh scripts/beads-onboard.sh

set -eu

if ! command -v bd >/dev/null 2>&1; then
	echo "✗ bd (beads) is not installed. Install it first, then re-run." >&2
	exit 1
fi

# Always operate from the repo root so relative paths are correct.
cd "$(git rev-parse --show-toplevel)"

# Enable the pre-push guard (idempotent; harmless to re-run).
git config core.hooksPath .githooks
echo "✓ pre-push guard enabled (core.hooksPath=.githooks)"

# Case 1: no local DB yet — a plain bootstrap is all that's needed.
if [ ! -d .beads/embeddeddolt ]; then
	echo "No local beads DB found — bootstrapping the shared history…"
	bd bootstrap --yes
	echo "✓ Done. Run 'bd ready' to see the backlog."
	exit 0
fi

# Case 2: a local DB exists. Rescue it, then adopt the canonical shared history.
RESCUE="${TMPDIR:-/tmp}/beads-local-rescue-$$.jsonl"
echo "Existing local beads DB found — exporting a rescue copy first…"
bd export --output "$RESCUE" 2>/dev/null || true
COUNT=0
if [ -f "$RESCUE" ]; then
	COUNT=$(grep -c . "$RESCUE" 2>/dev/null) || COUNT=0
fi
echo "  rescued $COUNT local record(s) -> $RESCUE"

echo "Removing the stale local DB and cloning the canonical shared history…"
rm -rf .beads/embeddeddolt
bd bootstrap --yes

echo ""
echo "✓ Adopted the shared issue history. Verify with: bd ready"
if [ "$COUNT" -gt 0 ]; then
	echo ""
	echo "⚠ You had $COUNT local issue record(s) saved at:"
	echo "    $RESCUE"
	echo "  If any are REAL work not already on the shared backlog, add them with:"
	echo "    bd import \"$RESCUE\" && bd dolt push"
	echo "  (Skip this if they were just a stale/empty local init.)"
fi
