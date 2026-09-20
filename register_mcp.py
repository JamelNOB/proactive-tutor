#!/usr/bin/env python3
"""
Register proactive-tutor MCP Server into Antigravity Config
=============================================================
支持在 ~/.gemini/config/mcp_config.json 中安全注入或反注册 proactive-tutor MCP 服务。
"""

import sys
import os
import json
import argparse
from pathlib import Path

# 设置标准输出编码为 UTF-8 避免 Windows 终端乱码
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# ANSI 颜色定义
COLOR_RESET = "\033[0m"
COLOR_BOLD = "\033[1m"
COLOR_GREEN = "\033[32m"
COLOR_CYAN = "\033[36m"
COLOR_YELLOW = "\033[33m"
COLOR_RED = "\033[31m"

def print_info(msg: str):
    print(f"{COLOR_CYAN}[INFO]{COLOR_RESET} {msg}")

def print_success(msg: str):
    print(f"{COLOR_GREEN}{COLOR_BOLD}[SUCCESS]{COLOR_RESET} {msg}")

def print_warn(msg: str):
    print(f"{COLOR_YELLOW}[WARN]{COLOR_RESET} {msg}")

def print_error(msg: str):
    print(f"{COLOR_RED}{COLOR_BOLD}[ERROR]{COLOR_RESET} {msg}")


def get_default_paths():
    user_home = Path.home()
    mcp_config_path = user_home / ".gemini" / "config" / "mcp_config.json"
    
    server_script = user_home / ".gemini" / "antigravity" / "scratch" / "proactive-tutor" / "mcp_server.py"
    python_exe = Path(sys.executable).resolve()
    
    return mcp_config_path, server_script, python_exe


def load_mcp_config(config_path: Path) -> dict:
    if not config_path.exists():
        print_warn(f"配置文件不存在，将新建: {config_path}")
        return {"mcpServers": {}}
    
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            content = f.read().strip()
            if not content:
                return {"mcpServers": {}}
            data = json.loads(content)
            if not isinstance(data, dict):
                return {"mcpServers": {}}
            if "mcpServers" not in data:
                data["mcpServers"] = {}
            return data
    except Exception as e:
        print_warn(f"读取或解析 JSON 失败: {e}，将初始化标准空配置。")
        return {"mcpServers": {}}


def save_mcp_config(config_path: Path, data: dict):
    config_path.parent.mkdir(parents=True, exist_ok=True)
    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")


def register(config_path: Path, server_script: Path, python_exe: Path):
    print_info(f"目标配置文件: {COLOR_BOLD}{config_path}{COLOR_RESET}")
    print_info(f"检测到 Python 解释器: {COLOR_BOLD}{python_exe}{COLOR_RESET}")
    print_info(f"MCP 服务端脚本路径: {COLOR_BOLD}{server_script}{COLOR_RESET}")

    if not server_script.exists():
        print_warn(f"警告：服务端脚本尚未在 {server_script} 就绪！")

    config = load_mcp_config(config_path)
    servers = config.setdefault("mcpServers", {})

    service_name = "proactive-tutor"
    server_entry = {
        "command": str(python_exe),
        "args": [
            str(server_script.resolve())
        ],
        "env": {
            "PYTHONUNBUFFERED": "1"
        }
    }

    already_exists = service_name in servers
    servers[service_name] = server_entry
    config["mcpServers"] = servers

    save_mcp_config(config_path, config)

    action_word = "已更新覆盖" if already_exists else "已成功注册"
    print_success(f"服务 [{service_name}] {action_word} 到 Antigravity MCP 统一配置！")
    print_info("当前配置项预览:")
    print(f"{COLOR_CYAN}{json.dumps({service_name: server_entry}, ensure_ascii=False, indent=2)}{COLOR_RESET}")


def unregister(config_path: Path):
    print_info(f"正在从 {config_path} 移除 proactive-tutor 服务配置...")
    config = load_mcp_config(config_path)
    servers = config.get("mcpServers", {})

    service_name = "proactive-tutor"
    if service_name in servers:
        del servers[service_name]
        save_mcp_config(config_path, config)
        print_success(f"服务 [{service_name}] 已从配置文件中安全移除！")
    else:
        print_warn(f"未找到服务 [{service_name}]，无需移除。")


def main():
    parser = argparse.ArgumentParser(description="Antigravity ProActive-Tutor MCP 自动化注册/反注册管理工具")
    parser.add_argument("--unregister", action="store_true", help="反注册并移除 proactive-tutor 服务配置")
    parser.add_argument("--config", type=str, default=None, help="自定义 mcp_config.json 路径")
    parser.add_argument("--script", type=str, default=None, help="自定义 mcp_server.py 脚本路径")
    parser.add_argument("--python", type=str, default=None, help="自定义 python 解释器绝对路径")

    args = parser.parse_args()

    default_config, default_script, default_python = get_default_paths()

    config_path = Path(args.config).resolve() if args.config else default_config
    server_script = Path(args.script).resolve() if args.script else default_script
    python_exe = Path(args.python).resolve() if args.python else default_python

    if args.unregister:
        unregister(config_path)
    else:
        register(config_path, server_script, python_exe)


if __name__ == "__main__":
    main()
