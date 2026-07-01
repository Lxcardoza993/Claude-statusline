---
description: Run a full health check on the CC config (binary env-var recognition + statusline + settings + profiles)
allowed-tools: Bash(python3 *)
---

Run the full (non-hook) health check:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/healthcheck.py"
```

Show the user the ✅/❌ report. Key checks:
- CC binary still recognizes the auto-compact env vars (flags a future CC update that renamed them)
- `statusline.py` exists and runs (emits a `ctx` segment)
- `~/.claude/settings.json` has `PCT_OVERRIDE=50`, `WINDOW=300000`, `autoCompactEnabled`, and `statusLine` wired
- every cc-switch profile has the same (if cc-switch is used)

If any ❌: explain the likely cause (a CC update renamed an env var, or a cc-switch profile switch wiped the fields) and suggest running `/claude-statusline:install` to repair. Note that the SessionStart hook already runs a fast version of this check automatically every session — this command is the thorough version including the binary grep.
