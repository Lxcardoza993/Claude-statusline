---
description: Restore the CC config after ~/.claude was wiped or on a fresh machine
allowed-tools: Bash(python3 *)
---

For restoring after `~/.claude` was wiped, after a fresh install, or when the status line / auto-compact stopped working. Run the installer — it recreates `~/.claude/settings.json` if missing and wires everything:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/install.py"
```

Then tell the user to **restart Claude Code**. After restart:
- the status line shows (git branch · model · context % with a 10-cell bar · running subagent count)
- auto-compact triggers at 50% context
- the SessionStart hook auto-checks the config on every session start, so future regressions (CC update, profile switch) are caught and surfaced automatically

If the user doesn't use cc-switch, only `~/.claude/settings.json` is touched. If they do, all profiles are kept in sync.
