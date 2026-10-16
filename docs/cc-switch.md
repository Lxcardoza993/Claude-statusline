# CC Switch v4 下保住 statusLine

## 问题

CC Switch v4 把 provider 配置存在自己的 SQLite 库(`~/.cc-switch/cc-switch.db`),
切换 provider 时用它重写 `~/.claude/settings.json`。手工加进 settings.json 的
`statusLine` 键在切换后可能丢失。

`install.py` 的 profile 传播针对的是旧版 `~/.claude/profiles/` 目录,
v4 已改为数据库存储,传播不到。

## 解法:写进数据库的两个地方

1. **`providers.settings_config`** —— 每个 claude provider 的 JSON 里加 `statusLine`
   键。切换 provider 时这个 JSON 就是 settings.json 的主体,statusLine 随之落地。
2. **`settings` 表的 `common_config_claude`** —— CC Switch 的「通用配置」,合并进
   所有 provider。在这里也放一份,双保险。

最小注入脚本(改完重启 CC Switch 让它重新读库):

```python
import sqlite3, json, os

db = os.path.expanduser("~/.cc-switch/cc-switch.db")
# Windows 用 python + 正斜杠路径;Linux/macOS 用 python3 ~/.claude/statusline.py
SL = {"type": "command", "command": "python ~/.claude/statusline.py"}

c = sqlite3.connect(db, timeout=15)
for pid, cfg in c.execute(
        "SELECT id, settings_config FROM providers WHERE app_type='claude'").fetchall():
    d = json.loads(cfg) if cfg and cfg.strip() else {}
    d["statusLine"] = SL
    c.execute("UPDATE providers SET settings_config=? WHERE id=?",
              (json.dumps(d, ensure_ascii=False), pid))

row = c.execute("SELECT value FROM settings WHERE key='common_config_claude'").fetchone()
if row:
    d = json.loads(row[0])
    d["statusLine"] = SL
    c.execute("UPDATE settings SET value=? WHERE key='common_config_claude'",
              (json.dumps(d, indent=2, ensure_ascii=False),))
c.commit()
```

## 注意

- 操作前备份:`providers` / `settings` 表改动行的原值先 SELECT 存一份。
- CC Switch 运行中改库后,重启它再在 GUI 里切 provider,避免内存里的旧配置覆盖。
- `common_config_claude` 里如果还有指向旧环境的 hooks 路径,不要顺手套用——
  只改 `statusLine` 一个键。
