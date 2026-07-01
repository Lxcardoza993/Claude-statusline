---
description: Install/repair the shared CC config (statusLine + auto-compact env + healthcheck) into ~/.claude/settings.json
argument-hint: "[--symlink]"
allowed-tools: Bash(python3 *)
---

Wire the shared Claude Code customizations into the user's `~/.claude/`. Run the installer:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/install.py" $ARGUMENTS
```

The installer is idempotent and backs up each edited file to `<file>.bak` (first edit only). It:
- copies `statusline.py` to `~/.claude/statusline.py` (pass `--symlink` to symlink instead, for live-edit dev)
- writes into `~/.claude/settings.json`:
  - `statusLine.command` → `python3 ~/.claude/statusline.py`
  - `env.CLAUDE_AUTOCOMPACT_PCT_OVERRIDE=50` (auto-compact at 50% context)
  - `env.CLAUDE_CODE_AUTO_COMPACT_WINDOW=300000`
  - `autoCompactEnabled=true`
- if cc-switch profiles exist at `~/.claude/profiles/`, propagates the same fields into every profile (so profile switches don't wipe them)

After it runs, show the user the summary and remind them to **restart Claude Code** so the env vars load into the running process. The status line appears immediately after restart.
