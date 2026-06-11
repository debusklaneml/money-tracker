# Agent Instructions

This project tracks work as **GitHub issues** on `debusklaneml/money-tracker`. See
`CLAUDE.md` for the full issue-tracking conventions and the repo-wide
`agentic_dev_workflow.md` for the workflow model (Epic issues, sub-issues, native
`blocked by` dependencies, and the `/next` · `/claim` · `/plan-ingest` commands).

## Quick Reference

```bash
gh issue list --search "is:open -is:blocked no:assignee"   # the ready set
gh issue view <issue#> --json title,body,labels            # view issue details
gh issue edit <issue#> --add-assignee @me                  # claim before touching code
gh pr create --draft --fill --body "Closes #<issue#>"      # draft PR on first push
```

Claim before you touch code, one branch + worktree per issue, draft PR on first push.
Discovered follow-up work becomes a new GitHub issue, not a TODO comment.

## Non-Interactive Shell Commands

**ALWAYS use non-interactive flags** with file operations to avoid hanging on confirmation prompts.

Shell commands like `cp`, `mv`, and `rm` may be aliased to include `-i` (interactive) mode on some systems, causing the agent to hang indefinitely waiting for y/n input.

**Use these forms instead:**
```bash
# Force overwrite without prompting
cp -f source dest           # NOT: cp source dest
mv -f source dest           # NOT: mv source dest
rm -f file                  # NOT: rm file

# For recursive operations
rm -rf directory            # NOT: rm -r directory
cp -rf source dest          # NOT: cp -r source dest
```

**Other commands that may prompt:**
- `scp` - use `-o BatchMode=yes` for non-interactive
- `ssh` - use `-o BatchMode=yes` to fail instead of prompting
- `apt-get` - use `-y` flag
- `brew` - use `HOMEBREW_NO_AUTO_UPDATE=1` env var
