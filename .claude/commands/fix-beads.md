---
description: Align this machine's beads issue tracker with the team's shared history (works for fresh, already-synced, or independent/orphan local DBs)
allowed-tools: Bash(sh scripts/beads-onboard.sh*), Bash(bd:*), Bash(git pull*), Bash(git checkout main*), Bash(git config*), Bash(git remote*), Bash(ls*), Bash(head*), Bash(cat*), Read
---

You are fixing/aligning this machine's **beads** (issue tracker) so the user is in
sync with the team's shared issue history.

Background you must keep in mind:
- Issues sync over a channel SEPARATE from code: `bd dolt pull` / `bd dolt push`
  (over `refs/dolt/data`), **not** `git pull`. The shared remote is the project's
  GitHub repo.
- In this repo `bd` runs in embedded-Dolt mode, so anyone who ran any `bd` command
  already has a local Dolt DB at `.beads/embeddeddolt/` — even if they thought they
  were "only using the jsonl". Independently-created DBs have an *orphan* history
  ("no common ancestor" / `bd bootstrap` says "database exists").
- `scripts/beads-onboard.sh` is idempotent and state-aware: it bootstraps a fresh
  clone, just `bd dolt pull`s if already aligned, or rescues-then-re-clones an
  orphan DB. It always exports a rescue copy before doing anything destructive.

Do this, narrating each step briefly and plainly (assume a non-expert colleague):

1. **Sync code first.** Run `git pull`. If it warns that the upstream branch was
   deleted / not found, run `git checkout main` then `git pull` again.

2. **Run the aligner.** Run `sh scripts/beads-onboard.sh --yes` from the repo root.
   This enables the pre-push guard and brings the local issue DB onto the shared
   history. (`--yes` is intentional — the script still exports a rescue copy before
   touching anything.)

3. **Handle rescued local work.** Read the script's output. If it printed
   `rescued N record(s)` with **N > 0**, the user may have issues that exist only
   on this machine. Before importing blindly:
   - Show what was rescued (e.g. `head` the rescue file it named, or summarize the
     titles) and ask the user whether those are real issues not already on the
     shared board.
   - If yes, run `bd import "<rescue-file>"` then `bd dolt push`.
   - If they're just a stale/empty local init, skip the import and say so.

4. **Verify success** and report the results:
   - `bd dolt remote list` → should list `origin` (a `git+https://…` URL).
   - `git config core.hooksPath` → should print `.githooks`.
   - `bd ready` → should show the shared backlog (real issue IDs like `bud-…`).

5. **Summarize**: confirm they're aligned, state what (if anything) was rescued or
   imported, and remind them of the steady state — `bd dolt pull` whenever they
   `git pull`, `bd dolt push` whenever they `git push` (automatic in Claude Code
   via the SessionStart hook + the pre-push guard).

Safety rules:
- Never delete anything beyond what `scripts/beads-onboard.sh` does, and never skip
  the rescue export.
- If any step errors, show the EXACT error and point the user to the
  "Beads — Multi-Developer Sync" section of `CLAUDE.md` for recovery; do not guess.
- If `bd` is not installed, stop and tell the user to install it first.
