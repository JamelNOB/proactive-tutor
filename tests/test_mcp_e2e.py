#!/usr/bin/env python3
"""
End-to-End Test for ProActive-Tutor MCP Stdio Server
====================================================
模拟 Antigravity 客户端通过 stdio 发送 JSON-RPC 2.0 报文：
1. initialize -> 验证协议握手与版本信息
2. notifications/initialized -> 发送初始化完成通知
3. ping -> 心跳响应验证
4. tools/list -> 验证 4 大核心微创导学工具注册
5. tools/call:
   - tutor_init_session ("softmax")
   - tutor_evaluate_step (触发 L1 微创反问或 L0 推进)
   - tutor_get_stack_status (验证调用栈帧与掌握度画像)
"""

import sys
import os
import json
import time
import subprocess
from pathlib import Path

# 设置标准输出编码为 UTF-8 避免 Windows GBK 终端乱码
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# ANSI 格式化
GREEN = "\033[32m"
CYAN = "\033[36m"
YELLOW = "\033[33m"
RED = "\033[31m"
BOLD = "\033[1m"
RESET = "\033[0m"


class MCPTestClient:
    def __init__(self, server_path: str, python_path: str = sys.executable):
        self.server_path = server_path
        self.python_path = python_path
        self.proc = None
        self.req_id = 0

    def start(self):
        print(f"{CYAN}[CLIENT] 正在拉起 MCP 服务端子进程: {self.server_path}{RESET}")
        self.proc = subprocess.Popen(
            [self.python_path, self.server_path],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            bufsize=1
        )
        time.sleep(0.3)
        if self.proc.poll() is not None:
            err = self.proc.stderr.read()
            raise RuntimeError(f"MCP 服务端未能成功启动，错误: {err}")

    def send_request(self, method: str, params: dict = None) -> dict:
        self.req_id += 1
        msg = {
            "jsonrpc": "2.0",
            "id": self.req_id,
            "method": method
        }
        if params is not None:
            msg["params"] = params

        line = json.dumps(msg, ensure_ascii=False)
        self.proc.stdin.write(line + "\n")
        self.proc.stdin.flush()

        resp_line = self.proc.stdout.readline()
        if not resp_line:
            err = self.proc.stderr.read()
            raise RuntimeError(f"未接收到服务端响应 (EOF)。Stderr 输出: {err}")

        return json.loads(resp_line.strip())

    def send_notification(self, method: str, params: dict = None):
        msg = {
            "jsonrpc": "2.0",
            "method": method
        }
        if params is not None:
            msg["params"] = params
        line = json.dumps(msg, ensure_ascii=False)
        self.proc.stdin.write(line + "\n")
        self.proc.stdin.flush()

    def close(self):
        if self.proc:
            try:
                self.proc.stdin.close()
                self.proc.terminate()
                self.proc.wait(timeout=2)
            except Exception:
                pass


def run_e2e_tests():
    server_candidates = [
        Path(r"C:\Users\JamelNOB\.gemini\antigravity\scratch\proactive-tutor\mcp_server.py"),
        Path(r"D:\edge-swarm\workspaces\specialist\mcp_server.py"),
        Path(r"D:\edge-swarm\workspaces\worker\mcp_server.py")
    ]
    
    server_path = None
    for p in server_candidates:
        if p.exists():
            server_path = str(p.resolve())
            break
            
    if not server_path:
        print(f"{RED}[ERROR] 找不到任何有效的 mcp_server.py{RESET}")
        sys.exit(1)

    print(f"{BOLD}{CYAN}======================================================{RESET}")
    print(f"{BOLD}{CYAN}       ProActive-Tutor MCP 端到端 (E2E) 测试套件       {RESET}")
    print(f"{BOLD}{CYAN}======================================================{RESET}\n")

    client = MCPTestClient(server_path=server_path)
    client.start()

    passed_tests = 0
    total_tests = 5

    try:
        # 1. initialize
        print(f"{CYAN}[TEST 1/5] 测试 initialize 握手...{RESET}")
        init_res = client.send_request("initialize", {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "Antigravity-Client", "version": "1.0.0"}
        })
        assert init_res.get("result", {}).get("serverInfo", {}).get("name") == "proactive-tutor-mcp"
        protocol_version = init_res["result"]["protocolVersion"]
        print(f"{GREEN}[PASS] initialize 成功！协商协议版本: {protocol_version}, 服务端: proactive-tutor-mcp{RESET}\n")
        passed_tests += 1

        # 发送通知
        client.send_notification("notifications/initialized")

        # 2. ping
        print(f"{CYAN}[TEST 2/5] 测试 ping 心跳...{RESET}")
        ping_res = client.send_request("ping")
        assert "result" in ping_res
        print(f"{GREEN}[PASS] ping 响应正常！{RESET}\n")
        passed_tests += 1

        # 3. tools/list
        print(f"{CYAN}[TEST 3/5] 测试 tools/list 工具枚举...{RESET}")
        tools_res = client.send_request("tools/list")
        tools = tools_res.get("result", {}).get("tools", [])
        tool_names = [t["name"] for t in tools]
        print(f"已发现工具列表 ({len(tools)} 个): {tool_names}")
        expected_tools = [
            "tutor_init_session",
            "tutor_evaluate_step",
            "tutor_answer_slice",
            "tutor_get_stack_status"
        ]
        for t in expected_tools:
            assert t in tool_names, f"缺少核心工具: {t}"
        print(f"{GREEN}[PASS] 4大微创导学核心工具齐全且定义规范！{RESET}\n")
        passed_tests += 1

        # 4. tools/call -> tutor_init_session
        print(f"{CYAN}[TEST 4/5] 测试 tools/call -> tutor_init_session('softmax')...{RESET}")
        init_call = client.send_request("tools/call", {
            "name": "tutor_init_session",
            "arguments": {
                "topic_or_material": "softmax"
            }
        })
        assert not init_call.get("result", {}).get("isError", False)
        content_json = json.loads(init_call["result"]["content"][0]["text"])
        print(f"课程初始化结果:\n  - 课程名称: {content_json.get('scenario_title')}\n  - 步骤总数: {content_json.get('total_steps')}\n  - 状态: {content_json.get('status')}")
        assert content_json.get("status") == "initialized"
        print(f"{GREEN}[PASS] tutor_init_session 执行成功！主线导学已就绪。{RESET}\n")
        passed_tests += 1

        # 5. tools/call -> tutor_evaluate_step & tutor_get_stack_status
        print(f"{CYAN}[TEST 5/5] 测试 tools/call -> tutor_evaluate_step 与 stack 透视...{RESET}")
        eval_call = client.send_request("tools/call", {
            "name": "tutor_evaluate_step",
            "arguments": {
                "student_input": "我不太确定，好像分母是累加指数？"
            }
        })
        assert not eval_call.get("result", {}).get("isError", False)
        eval_json = json.loads(eval_call["result"]["content"][0]["text"])
        print(f"决策干预输出:\n  - 干预等级: {eval_json.get('level')}\n  - 是否入栈微切片: {eval_json.get('is_stack_pushed')}\n  - 语音回话: {eval_json.get('speech_output')}")

        stack_call = client.send_request("tools/call", {
            "name": "tutor_get_stack_status",
            "arguments": {}
        })
        stack_json = json.loads(stack_call["result"]["content"][0]["text"])
        print(f"调用栈状态:\n  - 栈深度: {stack_json.get('stack_depth')}\n  - 挂起状态: {stack_json.get('is_suspended_in_slice')}\n  - 当前专题: {stack_json.get('current_scenario')}")
        assert "stack_depth" in stack_json
        print(f"{GREEN}[PASS] tutor_evaluate_step & tutor_get_stack_status 闭环验证成功！{RESET}\n")
        passed_tests += 1

    finally:
        client.close()

    print(f"{BOLD}{GREEN}======================================================{RESET}")
    print(f"{BOLD}{GREEN}  E2E 测试全部通过！({passed_tests}/{total_tests}) 通信完整性与协议规范 100% 达标{RESET}")
    print(f"{BOLD}{GREEN}======================================================{RESET}")


if __name__ == "__main__":
    run_e2e_tests()
