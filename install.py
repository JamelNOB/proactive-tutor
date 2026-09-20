#!/usr/bin/env python3
"""
ProActive-Tutor 一键安装脚本 (One-Click Installer for Antigravity & MCP)
========================================================================
功能：
1. 自动将 SKILL.md 安装到 Antigravity 技能库 (~/.gemini/config/skills/proactive-tutor/SKILL.md)；
2. 自动将 MCP Server 注册到 Antigravity 统一配置 (~/.gemini/config/mcp_config.json)；
3. 执行健康检查，验证 stdio JSON-RPC 通信与 SQLite 数据库就绪状态。
"""

import sys
import os
import shutil
import subprocess
from pathlib import Path

# UTF-8 编码防护
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

CYAN = "\033[36m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
BOLD = "\033[1m"
RESET = "\033[0m"

def main():
    print(f"\n{BOLD}{CYAN}======================================================{RESET}")
    print(f"{BOLD}{CYAN}     ProActive-Tutor (名师微创导学) 一键安装程序      {RESET}")
    print(f"{BOLD}{CYAN}======================================================{RESET}\n")

    repo_dir = Path(__file__).resolve().parent
    user_home = Path.home()
    
    # 1. 安装 Antigravity Skill
    skill_src = repo_dir / "SKILL.md"
    skill_dest_dir = user_home / ".gemini" / "config" / "skills" / "proactive-tutor"
    skill_dest_file = skill_dest_dir / "SKILL.md"

    if skill_src.exists():
        skill_dest_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(skill_src, skill_dest_file)
        print(f"{GREEN}[✓] 成功安装 Antigravity Skill 技能规范:{RESET}")
        print(f"    -> {skill_dest_file}")
    else:
        print(f"{YELLOW}[!] 警告: 未在当前目录找到 SKILL.md，跳过 Skill 安装{RESET}")

    # 2. 注册 MCP Server
    register_script = repo_dir / "register_mcp.py"
    if register_script.exists():
        print(f"\n{CYAN}[*] 正在执行 MCP 服务端自动注册...{RESET}")
        ret = subprocess.run([sys.executable, str(register_script)], cwd=str(repo_dir))
        if ret.returncode == 0:
            print(f"{GREEN}[✓] MCP 服务端已成功挂载到 ~/.gemini/config/mcp_config.json！{RESET}")
        else:
            print(f"{YELLOW}[!] MCP 注册返回非零状态码: {ret.returncode}{RESET}")
    else:
        print(f"{YELLOW}[!] 警告: 未找到 register_mcp.py{RESET}")

    # 3. 运行端到端测试自检
    test_e2e_script = repo_dir / "tests" / "test_mcp_e2e.py"
    if test_e2e_script.exists():
        print(f"\n{CYAN}[*] 正在执行本地服务与通信自检测试...{RESET}")
        ret_test = subprocess.run([sys.executable, str(test_e2e_script)], cwd=str(repo_dir))
        if ret_test.returncode == 0:
            print(f"\n{GREEN}{BOLD}🎉 全部安装就绪！恭喜！{RESET}")
        else:
            print(f"\n{YELLOW}[!] 自检测试有警告，但配置已完成写入。{RESET}")

    print(f"\n{BOLD}💡 如何在 Antigravity 中立刻使用：{RESET}")
    print(f"1. 直接在任意对话框输入: {CYAN}/proactive-tutor{RESET}")
    print(f"2. 或直接说自然语言: {CYAN}“带我复习计算机网络”{RESET} 或 {CYAN}“带我推导 Softmax 反向传播”{RESET}")
    print(f"AI 将自动调用本地 MCP 工具并进入确定性名师带教模式！\n")

if __name__ == "__main__":
    main()
