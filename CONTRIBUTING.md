# Contributing

Thanks for your interest! A few ways to help:

- **Bug reports & feature requests** — open an [issue](https://github.com/Lxcardoza993/Claude-statusline/issues).
- **Pull requests** — fork, branch from `main`, keep commits focused. For anything beyond a typo, opening an issue first helps align on direction.

## Dev setup

```bash
git clone https://github.com/Lxcardoza993/Claude-statusline.git
cd Claude-statusline
# symlink your ~/.claude/statusline.py to the repo for live editing:
python3 claude-statusline/scripts/install.py --symlink
# verify:
python3 claude-statusline/scripts/healthcheck.py
```

Edit `claude-statusline/scripts/statusline.py`, then restart Claude Code to see changes. Re-run the healthcheck to confirm nothing regressed.

## Scope

This repo keeps the Python **standard-library only** (no `pip install` needed) and the install path **non-destructive** (idempotent, with `.bak` backups on first edit). Please preserve those properties in contributions.
