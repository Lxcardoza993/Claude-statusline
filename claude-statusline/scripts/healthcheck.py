#!/usr/bin/env python3
"""Claude Code config healthcheck。
- 默认(手动 / /claude-statusline:healthcheck):全检含 binary grep,人类报告,exit 0/1。
- --hook(SessionStart 调用):只跑快检(跳过 binary grep),输出 JSON,不 block;
  全过 suppressOutput,有回退则 additionalContext 注入警告让模型提示修复。

可移植:走 $CLAUDE_CONFIG_DIR(默认 ~/.claude)。"""
import json, glob, os, subprocess, sys, shutil

BASE = os.environ.get("CLAUDE_CONFIG_DIR") or os.path.expanduser("~/.claude")
PROFILES_DIR = os.path.join(BASE, "profiles")
SETTINGS = os.path.join(BASE, "settings.json")
STATUSLINE = os.path.join(BASE, "statusline.py")

HOOK_MODE = "--hook" in sys.argv

PASS = "\033[38;5;78m✅\033[0m"
FAIL = "\033[38;5;196m❌\033[0m"


def run_checks(fast_only=False):
    """返回 [(ok, msg, detail), ...]。fast_only 跳过 binary grep(开 session 太慢)。"""
    results = []
    def check(ok, msg, detail=""):
        results.append((ok, msg, detail))
        return ok

    # 1. CC 二进制 + 版本
    cc_bin, cc_ver = None, "?"
    try:
        p = shutil.which("claude")
        if p:
            cc_bin = os.path.realpath(p)
            cc_ver = (subprocess.run(["claude", "--version"], capture_output=True,
                                     text=True, timeout=5).stdout.strip() or "?")
    except Exception:
        pass
    check(bool(cc_bin), f"CC binary found ({cc_ver})", cc_bin or "claude not on PATH")

    # 2. 二进制是否仍识别自动压缩 env var(慢,fast_only 跳过)
    if not fast_only and cc_bin and os.path.exists(cc_bin):
        for var in ["CLAUDE_AUTOCOMPACT_PCT_OVERRIDE", "CLAUDE_CODE_AUTO_COMPACT_WINDOW"]:
            try:
                r = subprocess.run(["grep", "-a", "-c", var, cc_bin],
                                   capture_output=True, text=True, timeout=20)
                n = int(r.stdout.strip()) if r.returncode == 0 else 0
            except Exception:
                n = -1
            check(n > 0, f"binary recognizes {var}",
                  f"{n} hits" if n >= 0 else "grep failed")
    elif fast_only:
        check(True, "binary env-var grep (skipped in hook mode)", "run /claude-statusline:healthcheck for full check")

    # 3. statusline.py 存在且能跑(输出含 ctx)
    sl_exists = os.path.exists(STATUSLINE)
    check(sl_exists, "statusline.py exists", STATUSLINE)
    if sl_exists:
        try:
            mock = json.dumps({"transcript_path": "", "cwd": BASE,
                               "model": {"display_name": "X", "id": "x"},
                               "context_window": {"used_percentage": 12,
                                                  "context_window_size": 200000}})
            r = subprocess.run(["python3", STATUSLINE], input=mock,
                               capture_output=True, text=True, timeout=5)
            check("ctx" in r.stdout, "statusline.py runs + emits ctx", r.stdout.strip()[:60])
        except Exception as e:
            check(False, "statusline.py run failed", str(e))

    # 4. settings.json
    try:
        s = json.load(open(SETTINGS)); env = s.get("env", {})
        check(env.get("CLAUDE_AUTOCOMPACT_PCT_OVERRIDE") == "50",
              "settings PCT_OVERRIDE=50", env.get("CLAUDE_AUTOCOMPACT_PCT_OVERRIDE"))
        check(env.get("CLAUDE_CODE_AUTO_COMPACT_WINDOW") == "300000",
              "settings WINDOW=300000", env.get("CLAUDE_CODE_AUTO_COMPACT_WINDOW"))
        check(s.get("autoCompactEnabled") is True,
              "settings autoCompactEnabled=true", s.get("autoCompactEnabled"))
        sl = s.get("statusLine", {})
        check(str(sl.get("command", "")).endswith("statusline.py"),
              "settings statusLine wired", sl.get("command"))
    except Exception as e:
        check(False, "settings.json read failed", str(e))

    # 5. cc-switch profiles(若有)
    profiles = sorted(glob.glob(os.path.join(PROFILES_DIR, "**", "*.json"), recursive=True))
    if profiles:
        for p in profiles:
            try:
                d = json.load(open(p)); env = d.get("env", {}); sl = d.get("statusLine", {})
                rel = os.path.relpath(p, BASE)
                ok = (env.get("CLAUDE_AUTOCOMPACT_PCT_OVERRIDE") == "50"
                      and env.get("CLAUDE_CODE_AUTO_COMPACT_WINDOW") == "300000"
                      and str(sl.get("command", "")).endswith("statusline.py"))
                check(ok, f"profile {rel}",
                      "PCT/WINDOW/statusLine " + ("OK" if ok else "MISSING"))
            except Exception as e:
                check(False, f"profile {os.path.relpath(p, BASE)} read failed", str(e))
    else:
        check(True, "no cc-switch profiles (settings.json only)", "skipped")

    return results


def main():
    results = run_checks(fast_only=HOOK_MODE)
    fails = [r for r in results if not r[0]]

    if HOOK_MODE:
        # SessionStart:不 block,全过静默,有回退注入警告
        if not fails:
            print(json.dumps({"suppressOutput": True}))
        else:
            lines = [f"  ❌ {m}" + (f" [{d}]" if d else "") for _, m, d in fails]
            msg = ("[claude-statusline] 健康检查发现回退(可能是 CC 更新或 profile 切换所致):\n"
                   + "\n".join(lines)
                   + "\n\n运行 /claude-statusline:install 重新接线修复。")
            print(json.dumps({
                "hookSpecificOutput": {
                    "hookEventName": "SessionStart",
                    "additionalContext": msg,
                }
            }))
        sys.exit(0)  # SessionStart 永不 block

    # 人类模式
    print("\n=== Claude Code config healthcheck ===\n")
    for ok, m, d in results:
        print(f"  {PASS if ok else FAIL} {m}" + (f"  [{d}]" if d else ""))
    print(f"\n{len(results)-len(fails)}/{len(results)} passed, {len(fails)} failed")
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
