#!/usr/bin/env python3
"""Claude Code statusLine: git 分支(±改动) | 模型名 | 上下文 % + 10格进度条 | 运行中子agent数。
轻量、纯 stdlib、无外部依赖。stdin 收 JSON,stdout 输出一行。
可移植:路径走 $CLAUDE_CONFIG_DIR(默认 ~/.claude),不硬编码用户家目录。

性能优化(2026-08-13):
- git 段:非 git 目录零 fork(向上 stat 找 .git);合并为单次 `git status -b --porcelain`
  (原 rev-parse + status 两次 git 调用→1 次)。多会话叠加刷新时降 fork 峰值最明显。
- subagent 段:全局 total 走 /tmp 文件缓存(TTL 10s),多会话刷新共享同一次扫描,
  避免每次全量 glob projects 树;本会话 here 仍实时(只扫单目录)。"""
import sys, json, os, glob, time, subprocess

CLAUDE_CONFIG_DIR = os.environ.get("CLAUDE_CONFIG_DIR") or os.path.expanduser("~/.claude")
PROJECTS_ROOT = os.path.join(CLAUDE_CONFIG_DIR, "projects")

# 全局 total 缓存:跨会话一致且扫描最贵,故多会话刷新共享。here 本会话独立,仍实时算。
CACHE_PATH = "/tmp/cc-statusline-cache.json"
CACHE_TTL = 10

C_CLEAN  = "\033[38;5;78m"   # 绿色:干净分支
C_DIRTY  = "\033[38;5;214m"  # 橙色:有改动
C_MODEL  = "\033[38;5;245m"  # 灰色:模型名
C_AGENT  = "\033[38;5;176m"  # 淡紫:子agent计数
C_SEP    = "\033[38;5;240m"  # 暗灰:分隔符
C_CTX_OK = "\033[38;5;78m"   # 绿色:离压缩点还远
C_CTX_HI = "\033[38;5;221m"  # 黄色:达压缩点 90%(逼近自动压缩)
C_CTX_OVER = "\033[38;5;196m" # 红色:达/超压缩点(该压缩了)
C_DARK   = "\033[38;5;238m"  # 暗灰:进度条空格
RESET    = "\033[0m"
SEP      = f" {C_SEP}|{RESET} "

# 子agent运行判据:运行中(前台/后台)持续把工具调用追加进自己的 agent-*.jsonl,
# 文件在 RUNNING_WINDOW 秒内被改动即视为运行中;结束/崩溃后文件不再增长,自然归零。
# 90s 兼顾常见停顿(web 抓取、中等 bash)。可按需调整。
RUNNING_WINDOW = 90


def _git_root(cwd):
    """向上找最近含 .git 的目录;非 git 目录返回 None。用纯 stat 判断,
    避免在非 git 目录(如 /home/li)白 fork 一次 git rev-parse 才知道不是仓库。"""
    try:
        cur = os.path.abspath(cwd)
    except Exception:
        return None
    while True:
        if os.path.isdir(os.path.join(cur, ".git")):
            return cur
        parent = os.path.dirname(cur)
        if parent == cur:
            return None
        cur = parent


def git_segment(cwd):
    root = _git_root(cwd)
    if not root:
        return None
    try:
        # 单次调用同时拿分支名 + 脏状态(替代原 rev-parse + status --porcelain 两次)。
        st = subprocess.run(
            ["git", "-C", root, "status", "-b", "--porcelain"],
            capture_output=True, text=True, timeout=1.5,
        )
        if st.returncode != 0 or not st.stdout:
            return None
        # 首行形如 "## main" / "## main...origin/main [ahead 2]" / "## HEAD (no branch)"
        first = st.stdout.split("\n", 1)[0].strip()
        name = first[2:].strip() if first.startswith("##") else ""
        if "..." in name:
            name = name.split("...", 1)[0].strip()
        if not name or "no branch" in name:
            name = "HEAD"
        # 脏 = 除首行 ## 外还有任意改动行
        dirty = any(ln and not ln.startswith("##") for ln in st.stdout.splitlines()[1:])
        return f"{C_DIRTY}⎇ {name}*{RESET}" if dirty else f"{C_CLEAN}⎇ {name}{RESET}"
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


def _read_cache():
    try:
        with open(CACHE_PATH) as f:
            d = json.load(f)
        if time.time() - float(d.get("ts", 0)) <= CACHE_TTL:
            return d
    except Exception:
        pass
    return None


def _write_cache(d):
    # tmp 带 PID,避免多会话同写撞同一临时文件;os.replace 原子替换。
    try:
        tmp = f"{CACHE_PATH}.{os.getpid()}.tmp"
        with open(tmp, "w") as f:
            json.dump(d, f)
        os.replace(tmp, CACHE_PATH)
    except Exception:
        pass


def _cached_total(now):
    """全局运行中子agent总数:跨会话一致,走文件缓存;过期才全量扫 projects 树。"""
    c = _read_cache()
    if c is not None and "total" in c:
        try:
            return int(c["total"])
        except (TypeError, ValueError):
            pass
    total = 0
    try:
        for sdir in glob.glob(os.path.join(PROJECTS_ROOT, "*", "*", "subagents")):
            total += count_running(sdir, now)
    except Exception:
        pass
    _write_cache({"ts": now, "total": total})
    return total


def subagent_segment(data):
    """本会话运行中子agent数 / 全部会话运行中子agent总数,如 1/3。
    here 实时(只扫本会话单目录,便宜);total 走缓存(跨会话一致+扫描最贵)。"""
    now = time.time()
    here = 0
    tp = data.get("transcript_path")
    if tp:
        here = count_running(os.path.splitext(tp)[0] + "/subagents", now)
    total = _cached_total(now)
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
    """上下文占用百分比,分母=后端真实窗口(CLAUDE_CODE_AUTO_COMPACT_WINDOW),
    而非 CC 报的 context_window_size——经代理时常虚高(opus[1m] 报 1M,但后端
    glm-5.2 实为 256K)。压缩实走 真实窗口×PCT_OVERRIDE/100,故显示也用真实窗口
    做分母,数字才与压缩触发点对齐(到 override% 即该压缩)。未配真实窗口则退回
    CC 口径(此时数字会偏小,如本机 opus 经 CPA 走 glm-5.2 会虚低 ~4×)。"""
    pct = None
    cw = data.get("context_window")

    # CC 报的窗口(经代理常虚高):优先 context_window_size,否则按模型名兜底。
    real_window = None
    if isinstance(cw, dict):
        wsz = cw.get("context_window_size")
        if isinstance(wsz, (int, float)) and wsz > 0:
            real_window = wsz
    if real_window is None:
        m = data.get("model") or {}
        mid = str(m.get("id") or m.get("display_name") or "").lower()
        real_window = 1000000 if ("1m" in mid or "opus" in mid) else 200000

    # 后端真实窗口:压缩实际按此触发;未配则等于 real_window(退回 CC 口径)。
    auto_w = int(os.environ.get("CLAUDE_CODE_AUTO_COMPACT_WINDOW") or 0) or real_window
    auto_w = min(auto_w, real_window)   # 不能超过 CC 报的窗口
    override = int(os.environ.get("CLAUDE_AUTOCOMPACT_PCT_OVERRIDE") or 0) or 92

    # 路径 1:CC 自带 used_percentage,从 CC 口径换算到真实窗口口径。
    # CC 的 used_percentage = used/real_window;换成 used/auto_w 即放大 real_window/auto_w 倍。
    if isinstance(cw, dict):
        up = cw.get("used_percentage")
        if isinstance(up, (int, float)):
            pct = float(up) * real_window / auto_w

    # 路径 2:transcript 地面真相回退(直接用真实窗口做分母)。
    if pct is None:
        used = _transcript_context_used(data.get("transcript_path"))
        if used:
            pct = used * 100.0 / auto_w

    if pct is None:
        return None

    # 真实窗口口径下,触发点就是 override% 本身;其 90% = 黄色预警。
    trigger_pct = float(override)
    warn_pct = trigger_pct * 0.9

    col = C_CTX_OVER if pct >= trigger_pct else (C_CTX_HI if pct >= warn_pct else C_CTX_OK)
    filled = max(0, min(10, int(pct / 10 + 0.5)))
    empty = 10 - filled
    bar = col + "▰" * filled
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
