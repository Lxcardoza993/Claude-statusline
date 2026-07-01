# Claude Statusline

> 中文 | [English](README.md)

给 Claude Code 用的精简状态栏——**git 分支 · 模型 · 实时上下文百分比(带色条)· 运行中子 agent 数**——外加 50 % 自动压缩 + 会话启动健康检查,且能扛过 CC 更新。

![license](https://img.shields.io/badge/license-MIT-blue)
![python](https://img.shields.io/badge/python-3.10%2B-blue)
![claude-code](https://img.shields.io/badge/Claude%20Code-2.1%2B-purple)
![platform](https://img.shields.io/badge/platform-linux%20%7C%20macOS%20%7C%20WSL2-lightgrey)
![stars](https://img.shields.io/github/stars/Lxcardoza993/Claude-statusline)

## 🖥️ 效果演示

Claude Code 终端底部那一行(颜色在真实终端里实时显示):

```
⎇ main | Opus 4.8 | ▰▰▰▰▱▱▱▱▱▱  ctx 42% | ⛬ 1/3
```

| 段 | 含义 |
|---|---|
| `⎇ main` | 当前 git 分支(dirty 时带 `*`) |
| `Opus 4.8` | 当前模型 |
| `▰▰▰▰▱▱▱▱▱▱  ctx 42%` | 上下文占用——bar 在 **≥ 40 % 变黄**、**≥ 50 % 变红**(自动压缩触发点) |
| `◬ 1/3` | 运行中子 agent——**本会话 1 个 / 全部会话 3 个**(递归统计 workflow 子 agent) |

## ✨ 特性

- **一行状态栏**——git 分支(±dirty)· 模型 · 上下文 % + 10 格色条 · 运行中子 agent(本会话/全局,递归统计 workflow 子 agent)
- **50 % 自动压缩**——上下文到 50 % 就压缩(默认约 80 %),给你留更多工作空间
- **会话启动健康检查**——每次开 session 跑一次快检,在 CC 更新或 cc-switch 切 profile 造成回退**咬人之前**就抓出来
- **cc-switch 安全**——把 env 变量 + 状态栏写进**每一个** profile,切 profile 不再清空你的配置
- **可移植**——无硬编码路径,认 `CLAUDE_CONFIG_DIR`
- **零依赖**——纯 Python 3.10+ 标准库,不用 `pip install`

## 📦 安装

### 方式 A——插件(推荐)

带自动健康检查钩子、`/claude-statusline:install|healthcheck|restore` 命令,可用 `/plugin update` 升级。

```
/plugin marketplace add Lxcardoza993/Claude-statusline
/plugin install claude-statusline@claude-statusline-market
/claude-statusline:install
```

然后**重启 Claude Code**。SessionStart 钩子安装即自动激活——它**不**写进你的 `settings.json`,所以 cc-switch 切 profile 抹不掉它(env 变量会被抹,钩子不会)。

### 方式 B——一行 bash(备选)

不装插件、不带命令——只接 `settings.json` + 拷贝 `statusline.py`。适合锁定机器或不想装插件的场景。

```bash
curl -fsSL https://raw.githubusercontent.com/Lxcardoza993/Claude-statusline/main/install.sh | bash
```

然后**重启 Claude Code**。以后升级重跑同一行即可。

## ⚙️ 写入了什么

| 定制项 | 位置 | 效果 |
|---|---|---|
| `statusLine` | `~/.claude/settings.json` | `python3 ~/.claude/statusline.py` 渲染该行 |
| `CLAUDE_AUTOCOMPACT_PCT_OVERRIDE=50` | `env` | 上下文到 50 % 自动压缩 |
| `CLAUDE_CODE_AUTO_COMPACT_WINDOW=300000` | `env` | 压缩窗口 |
| `autoCompactEnabled=true` | 顶层 | 启用自动压缩 |
| SessionStart 钩子 | 插件 | 每次会话启动跑快检 |

## 🔄 cc-switch 兼容

[cc-switch](https://github.com/farion1231/cc-switch) 把 profile 存成 `~/.claude/profiles/*.json` 里的完整 `settings.json` 快照,切换时覆盖 `~/.claude/settings.json`。安装器会探测到这一点,把 env 变量 + `statusLine` 写进**每一个** profile,这样切 profile 不再清掉你的定制。

## 🩺 Claude Code 更新之后

CC 更新可能改 env 变量名或挪走二进制。SessionStart 钩子会自动捕获并以警告形式提示。手动跑完整检查:

```
/claude-statusline:healthcheck
```

若某项失败,`/claude-statusline:install`(或重跑 `install.sh`)即可修复。安装器幂等,首次编辑每个文件建 `<file>.bak` 备份。

## 📁 仓库结构

```
.claude-plugin/marketplace.json      # 市场清单(仓库根 = 市场)
claude-statusline/                   # 插件
  .claude-plugin/plugin.json         # 插件清单
  hooks/hooks.json                   # SessionStart → healthcheck.py --hook
  commands/{install,healthcheck,restore}.md
  scripts/{statusline,install,healthcheck}.py
install.sh                           # 非插件一行安装器
```

## 🤝 致谢

- **[OpenClaw 中文社区](https://github.com/OpenClaw)**——聚焦 Claude Code / OpenClaw 等智能体工具的中文技术社区。社区里关于钩子机制、`${CLAUDE_PLUGIN_ROOT}` 内联替换、插件打包的讨论直接塑造了本项目的设计。🙏
- **[Linux.do](https://linux.do)**——中文开发者社区。本仓库背后许多 WSL2、代理网络、Claude Code 配置保留的实践经验都来自该社区的分享与打磨。🙏

## 📄 许可证

MIT——见 [LICENSE](LICENSE)。
