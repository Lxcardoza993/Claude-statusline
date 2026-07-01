#!/usr/bin/env python3
"""把 Claude Code 自定义配置接线进本机:拷 statusline.py 到 ~/.claude/,
写 statusLine 字段 + 自动压缩 env var + autoCompactEnabled 进 settings.json,
若有 cc-switch profiles 则一并铺全部(防切换抹掉)。幂等,带 .bak 备份。

可移植:走 $CLAUDE_CONFIG_DIR(默认 ~/.claude),不硬编码用户家目录。
用法:
  python3 install.py            # 拷贝 statusline.py(默认,适合分发)
  python3 install.py --symlink  # 软链 statusline.py(开发用,改仓库文件实时生效)
"""
import json, shutil, os, glob, sys, time

BASE = os.environ.get("CLAUDE_CONFIG_DIR") or os.path.expanduser("~/.claude")
PROFILES_DIR = os.path.join(BASE, "profiles")
SETTINGS = os.path.join(BASE, "settings.json")
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
STATUSLINE_SRC = os.path.join(SCRIPT_DIR, "statusline.py")
STATUSLINE_DST = os.path.join(BASE, "statusline.py")

SYMLINK = "--symlink" in sys.argv

STATUSLINE_CMD = f"python3 {STATUSLINE_DST}"

ENV_VARS = {
    "CLAUDE_AUTOCOMPACT_PCT_OVERRIDE": "50",      # 50% 触发自动压缩
    "CLAUDE_CODE_AUTO_COMPACT_WINDOW": "300000",  # token 窗口
}


def backup_once(path):
    """首次编辑前把原文件存到 <path>.bak(幂等:已存在 .bak 不覆盖)。"""
    bak = path + ".bak"
    if os.path.exists(path) and not os.path.exists(bak):
        try:
            shutil.copy2(path, bak)
        except Exception:
            pass


def wire(path):
    """把 statusLine + env + autoCompactEnabled 写进一个 settings/profile JSON。"""
    backup_once(path)
    with open(path) as fh:
        d = json.load(fh)
    env = d.setdefault("env", {})
    for k, v in ENV_VARS.items():
        env[k] = v
    d["statusLine"] = {"type": "command", "command": STATUSLINE_CMD}
    d["autoCompactEnabled"] = True
    with open(path, "w") as fh:
        json.dump(d, fh, indent=2, ensure_ascii=False)
        fh.write("\n")


def main():
    if not os.path.exists(STATUSLINE_SRC):
        print(f"❌ statusline.py not found next to install.py: {STATUSLINE_SRC}")
        sys.exit(1)

    os.makedirs(BASE, exist_ok=True)

    # 1. 部署 statusline.py
    if SYMLINK:
        if os.path.islink(STATUSLINE_DST) or os.path.exists(STATUSLINE_DST):
            os.remove(STATUSLINE_DST)
        os.symlink(STATUSLINE_SRC, STATUSLINE_DST)
        print(f"🔗 symlinked {STATUSLINE_DST} -> {STATUSLINE_SRC}")
    else:
        shutil.copy2(STATUSLINE_SRC, STATUSLINE_DST)
        print(f"📄 copied statusline.py -> {STATUSLINE_DST}")

    # 2. 收集要接线的文件:settings.json + 全部 cc-switch profile(若有)
    targets = []
    profiles = sorted(glob.glob(os.path.join(PROFILES_DIR, "**", "*.json"), recursive=True))
    if profiles:
        targets.extend(profiles)
        print(f"📂 cc-switch detected: {len(profiles)} profiles")
    if os.path.exists(SETTINGS):
        targets.append(SETTINGS)
    else:
        # 全新安装:建一份最小 settings.json
        with open(SETTINGS, "w") as fh:
            json.dump({}, fh)
        targets.append(SETTINGS)
        print(f"📝 created minimal {SETTINGS}")

    # 去重(settings.json 可能已在 profiles glob 里——不会,profiles 在 profiles/ 子目录)
    seen = set(); uniq = []
    for t in targets:
        if t not in seen:
            seen.add(t); uniq.append(t)

    print(f"\nWiring statusLine + env + autoCompactEnabled into {len(uniq)} file(s):")
    for t in uniq:
        rel = os.path.relpath(t, BASE)
        try:
            wire(t)
            print(f"  ✅ {rel}")
        except Exception as e:
            print(f"  ❌ {rel}: {e}")

    print(f"\nDone. statusLine command: {STATUSLINE_CMD}")
    print("Restart Claude Code for env vars to load into the running process.")
    print("Run healthcheck.py to verify.")


if __name__ == "__main__":
    main()
