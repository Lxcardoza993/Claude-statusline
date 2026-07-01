#!/usr/bin/env python3
"""Claude Code statusLine: git 分支(±改动) | 模型名 | 上下文 % + 10格进度条 | 运行中子agent数。
轻量、纯 stdlib、无外部依赖。stdin 收 JSON,stdout 输出一行。
可移植:路径走 $CLAUDE_CONFIG_DIR(默认 ~/.claude),不硬编码用户家目录。"""
import sys, json, os, glob, time, subprocess

CLAUDE_CONFIG_DIR = os.environ.get("CLAUDE_CONFIG_DIR") or os.path.expanduser("~/.claude")
PROJECTS_ROOT = os.path.join(CLAUDE_CONFIG_DIR, "projects")

C_CLEAN  = "\033[38;5;78m"   # 绿色:干净分支
C_DIRTY  = "\033[38;5;214m"  # 橙色:有改动
C_MODEL  = "\033[38;5;245m"  # 灰色:模型名
C_AGENT  = "\033[38;5;176m"  # 淡紫:子agent计数
C_SEP    = "\033[38;5;240m"  # 暗灰:分隔符
C_CTX_OK = "\033[38;5;78m"   # 绿色:上下文<40%
C_CTX_HI = "\033[38;5;221m"  # 黄色:上下文40-50%(逼近自动压缩)
C_CTX_OVER = "\033[38;5;196m" # 红色:上下文>50%(该压缩了)
C_DARK   = "\033[38;5;238m"  # 暗灰:进度条空格
RESET    = "\033[0m"
SEP      = f" {C_SEP}|{RESET} "

# 子agent运行判据:运行中(前台/后台)持续把工具调用追加进自己的 agent-*.jsonl,
# 文件在 RUNNING_WINDOW 秒内被改动即视为运行中;结束/崩溃后文件不再增长,自然归零。
# 90s 兼顾常见停顿(web 抓取、中等 bash)。可按需调整。
RUNNING_WINDOW = 90


def git_segment(cwd):
    try:
        branch = subprocess.run(
            ["git", "-C", cwd, "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True, text=True, timeout=1,
        )
        if branch.returncode != 0:
            return None
        name = branch.stdout.strip() or "HEAD"
        dirty = subprocess.run(
            ["git", "-C", cwd, "status", "--porcelain"],
            capture_output=True, text=True, timeout=1,
        )
        if dirty.stdout.strip():
            return f"{C_DIRTY}⎇ {name}*{RESET}"   # 有未提交改动
        return f"{C_CLEAN}⎇ {name}{RESET}"
    except Exception:
        return None


def _mtime(path):
    try:
        return os.path.getmtime(path)
    except OSError:
        return None


def count_running(subagents_dir, now):
    """该目录下正在运行的子agent数。递归:workflow 子agent 的 jsonl 落在
    subagents/workflows/wf_XXX/ 嵌套层,非递归 glob 会漏算。"""
    try:
        jsonls = glob.glob(os.path.join(subagents_dir, "**", "agent-*.jsonl"),
                           recursive=True)
    except Exception:
        return 0
    running = 0
    for p in jsonls:
        m = _mtime(p)
        if m is not None and now - m <= RUNNING_WINDOW:
            running += 1
    return running


def subagent_segment(data):
    """本会话运行中子agent数 / 全部会话运行中子agent总数,如 1/3。"""
    now = time.time()

    # 本会话:transcript_path 去掉 .jsonl 拼 /subagents 即本会话子agent目录。
    here = 0
    tp = data.get("transcript_path")
    if tp:
        here = count_running(os.path.splitext(tp)[0] + "/subagents", now)

    # 全局:遍历 projects/<工程>/<会话>/subagents 下所有会话。
    total = 0
    try:
        for sdir in glob.glob(os.path.join(PROJECTS_ROOT, "*", "*", "subagents")):
            total += count_running(sdir, now)
    except Exception:
        pass

    if total == 0 and here == 0:
        return None
    return f"{C_AGENT}⛬ {here}/{total}{RESET}"


def _transcript_context_used(transcript_path):
    """从 transcript JSONL 末尾读最近一条 assistant 消息的 usage,返回当前上下文 token 数。
    上下文填充 = input_tokens + cache_read_input_tokens + cache_creation_input_tokens。
    地面真相回退(当 statusLine 输入没给 used_percentage 时用)。"""
    if not transcript_path or not os.path.exists(transcript_path):
        return None
    try:
        with open(transcript_path, "rb") as f:
            f.seek(0, 2)
            size = f.tell()
            f.seek(max(0, size - 65536))   # 只读末尾 64KB
            tail = f.read().decode("utf-8", "ignore")
        last_usage = None
        for line in tail.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except Exception:
                continue
            msg = obj.get("message") or {}
            if isinstance(msg, dict) and msg.get("usage"):
                last_usage = msg["usage"]
        if not last_usage:
            return None
        return (int(last_usage.get("input_tokens", 0))
                + int(last_usage.get("cache_read_input_tokens", 0))
                + int(last_usage.get("cache_creation_input_tokens", 0)))
    except Exception:
        return None


def context_segment(data):
    """上下文占用百分比。优先吃 CC 自带的 context_window.used_percentage
    (CC 自己的口径,最准),缺失则解析 transcript 估算了。"""
    pct = None
    cw = data.get("context_window")

    # 路径 1:CC 自带 used_percentage(权威)
    if isinstance(cw, dict):
        up = cw.get("used_percentage")
        if isinstance(up, (int, float)):
            pct = float(up)

    # 路径 2:transcript 地面真相回退
    if pct is None:
        used = _transcript_context_used(data.get("transcript_path"))
        if used:
            window = None
            if isinstance(cw, dict):
                wsz = cw.get("context_window_size")
                if isinstance(wsz, (int, float)) and wsz > 0:
                    window = wsz
            if window is None:
                m = data.get("model") or {}
                mid = str(m.get("id") or m.get("display_name") or "").lower()
                window = 1000000 if ("1m" in mid or "opus" in mid) else 200000
            pct = used * 100.0 / window

    if pct is None:
        return None

    col = C_CTX_OVER if pct >= 50 else (C_CTX_HI if pct >= 40 else C_CTX_OK)
    filled = max(0, min(10, round(pct / 10)))
    empty = 10 - filled
    bar = C_CTX_OK + "▰" * filled
    if empty:
        bar += C_DARK + "▱" * empty
    bar += RESET
    return f"{bar}  {col}ctx {pct:.0f}%{RESET}"


def main():
    try:
        data = json.load(sys.stdin)
    except Exception:
        data = {}

    cwd = (
        data.get("workspace", {}).get("current_dir")
        or data.get("cwd")
        or os.getcwd()
    )
    model = data.get("model", {}).get("display_name") or "?"

    segments = []

    g = git_segment(cwd)
    if g:
        segments.append(g)

    segments.append(f"{C_MODEL}{model}{RESET}")

    ctx = context_segment(data)
    if ctx:
        segments.append(ctx)

    a = subagent_segment(data)
    if a:
        segments.append(a)

    sys.stdout.write(SEP.join(segments))


if __name__ == "__main__":
    main()
