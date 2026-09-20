"""
ProActive-Tutor Standard Stdio MCP Server
=========================================
基于名师微创导学决策引擎的标准 Model Context Protocol (MCP) Stdio 服务端。
特性：
1. 零外部三方依赖（纯 Python 标准库：json, sys, os, time, uuid 等）。
2. 标准 MCP Stdio 协议生命周期（initialize, notifications/initialized, tools/list, tools/call, ping）。
3. 稳健错误处理与日志输出（所有 debug/info 日志严格输出至 stderr，确保 stdout 纯净输出 JSON-RPC 消息）。
4. 注册并实现 4 个核心教学工具：
   - tutor_init_session(topic_or_material: str)
   - tutor_evaluate_step(student_input: str)
   - tutor_answer_slice(choice: str)
   - tutor_get_stack_status()
"""

import sys
import os
import json
import time
import traceback
from typing import Dict, Any, Optional, List

# 路径自适应：确保优先导入 core 模块
CORE_PATHS = [
    r"C:\Users\JamelNOB\.gemini\antigravity\scratch\proactive-tutor",
    r"D:\edge-swarm\workspaces\worker"
]
for p in CORE_PATHS:
    if os.path.exists(p) and p not in sys.path:
        sys.path.insert(0, p)

try:
    from core.models import (
        InterventionLevel,
        FaultType,
        AtomicOperator,
        DiagnosisResult,
        InterventionAction,
        StackFrame,
        LessonStep,
    )
    from core.engine import (
        PedagogicalCallStack,
        RootCauseTracer,
        PedagogicalDecisionEngine,
    )
    from core.scenarios import (
        Scenario,
        get_scenario,
        ALL_SCENARIOS,
        SCENARIO_SOFTMAX_ATTENTION_BACKPROP,
        SCENARIO_CUDA_BANK_CONFLICT,
    )
except ImportError:
    # 本地工作区兼容兜底
    from engine import (
        PedagogicalCallStack,
        RootCauseTracer,
        PedagogicalDecisionEngine,
        LessonStep,
        AtomicOperator,
        FaultType,
        InterventionLevel,
        StackFrame,
    )
    try:
        from scenarios import Scenario, get_scenario, ALL_SCENARIOS
    except ImportError:
        ALL_SCENARIOS = {}
        def get_scenario(key: str):
            return None


def log_stderr(message: str) -> None:
    """所有诊断日志输出到 stderr，绝不污染 stdout 的 json-rpc 报文"""
    sys.stderr.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] [MCP-Tutor] {message}\n")
    sys.stderr.flush()


class ProActiveTutorMCPServer:
    """名师微创导学 MCP 服务端上下文管理"""

    def __init__(self):
        self.engine = PedagogicalDecisionEngine(default_timeout_seconds=25, max_stack_depth=2)
        self.current_scenario: Optional[Any] = None
        self.current_step_index: int = 0
        self.mastery_profile: Dict[str, Any] = {
            "completed_steps": [],
            "identified_faults": [],
            "repaired_operators": [],
            "total_attempts": 0,
            "session_start_time": time.time(),
        }

    def init_session(self, topic_or_material: str) -> Dict[str, Any]:
        """初始化新课程主线推导"""
        clean_key = topic_or_material.strip()
        sc = get_scenario(clean_key)
        if not sc:
            # 智能模糊匹配预设场景
            key_lower = clean_key.lower()
            if any(k in key_lower for k in ["softmax", "attention", "期末", "反向传播", "backprop", "1"]):
                sc = ALL_SCENARIOS.get("1") or ALL_SCENARIOS.get("softmax")
            elif any(k in key_lower for k in ["cuda", "bank", "shared", "共享内存", "防穿帮", "2"]):
                sc = ALL_SCENARIOS.get("2") or ALL_SCENARIOS.get("cuda")

        if not sc:
            # 动态由输入素材生成自适应单步推导主线
            sc = Scenario(
                scenario_id="dynamic_session",
                title=f"自适应推导：{clean_key[:30]}",
                category="通用探针",
                description=clean_key,
                steps=[
                    LessonStep(
                        step_id=1,
                        prompt=f"【主线第 1 步】请根据学习目标《{clean_key[:50]}》，给出第一阶段核心不变量推导或实现。",
                        standard_solution="正确的不变量表达式与边界推导",
                        key_invariants=["不变量", "守恒", "基底"],
                        common_faults={"笔误": FaultType.SLIP},
                        prerequisite_operator=None
                    )
                ],
                atomic_operators={}
            )

        self.current_scenario = sc
        self.current_step_index = 0
        self.engine.call_stack.clear()
        self.mastery_profile = {
            "scenario_id": sc.scenario_id,
            "scenario_title": sc.title,
            "category": getattr(sc, "category", "名师微创导学"),
            "completed_steps": [],
            "identified_faults": [],
            "repaired_operators": [],
            "total_attempts": 0,
            "session_start_time": time.time(),
        }

        first_step = sc.steps[0]
        self.engine.current_step = first_step

        return {
            "status": "initialized",
            "scenario_title": sc.title,
            "category": getattr(sc, "category", ""),
            "total_steps": len(sc.steps),
            "current_step_id": first_step.step_id,
            "prompt": first_step.prompt,
            "key_invariants": first_step.key_invariants,
            "speech": f"课程已加载：《{sc.title}》。执掌节拍器，主线推进开始！\n{first_step.prompt}"
        }

    def evaluate_step(self, student_input: str) -> Dict[str, Any]:
        """核心逆向归因与决策动作"""
        if not self.current_scenario:
            return {
                "error": "未初始化教学推导会话，请先调用 tutor_init_session 初始化课程。"
            }

        steps = self.current_scenario.steps
        if self.current_step_index >= len(steps):
            return {
                "status": "session_completed",
                "speech": "🎉 恭喜！本专题全部推导步骤已圆满通关，核心底层断点均已闭环！",
                "call_stack_status": "EMPTY",
                "mastery_profile": self.mastery_profile
            }

        curr_step = steps[self.current_step_index]
        self.mastery_profile["total_attempts"] += 1

        action: InterventionAction = self.engine.decide_action(curr_step, student_input)

        response_data: Dict[str, Any] = {
            "level": action.level.value,
            "speech_output": action.speech_output,
            "max_duration_seconds": action.max_duration_seconds,
            "is_stack_pushed": action.is_stack_pushed,
            "is_snapbacked": action.is_snapbacked,
            "target_token": action.target_token,
            "current_step": curr_step.step_id,
            "total_steps": len(steps)
        }

        # 记录归因特征
        if action.level != InterventionLevel.L0_SPOTLIGHT or action.is_stack_pushed:
            self.mastery_profile["identified_faults"].append({
                "step_id": curr_step.step_id,
                "input": student_input,
                "level": action.level.value,
                "token": action.target_token,
                "timestamp": time.time()
            })

        # 判断推导是否正确/通过当前步
        clean_input = student_input.strip().lower()
        std_input = curr_step.standard_solution.strip().lower()
        has_all_invariants = all(inv.lower() in clean_input for inv in curr_step.key_invariants)
        is_exact_or_close = (clean_input in std_input or std_input in clean_input) and len(clean_input) >= 5

        # 若未挂起栈，且学生给出了正确解（包含核心不变量或匹配标准解）
        if (has_all_invariants or is_exact_or_close) and not action.is_stack_pushed and not action.is_snapbacked:
            self.mastery_profile["completed_steps"].append(curr_step.step_id)
            self.current_step_index += 1
            if self.current_step_index < len(steps):
                next_step = steps[self.current_step_index]
                self.engine.current_step = next_step
                response_data["status"] = "step_passed"
                response_data["level"] = "L0_SPOTLIGHT"
                response_data["speech_output"] = f"✅ 推导精准无误！\n\n下一节点目标已下发：\n{next_step.prompt}"
                response_data["next_step_id"] = next_step.step_id
                response_data["next_prompt"] = next_step.prompt
            else:
                response_data["status"] = "session_completed"
                response_data["speech_output"] = "🎯 漂亮！整套推导主线全部通关，底层数学与硬件物理映射完全闭环！"
        else:
            response_data["status"] = "under_intervention"

        return response_data

    def answer_slice(self, choice: str) -> Dict[str, Any]:
        """20秒微切片作答校验并秒级回弹"""
        if not self.current_scenario:
            return {
                "error": "未初始化教学会话。"
            }

        if self.engine.call_stack.is_empty():
            return {
                "status": "no_slice_active",
                "speech": "当前主线未挂起任何微切片，请直接在主线进行推导！",
                "stack_depth": 0
            }

        current_frame = self.engine.call_stack.peek()
        op_id = current_frame.atomic_operator.operator_id if current_frame and current_frame.atomic_operator else None

        action = self.engine.process_atomic_response(choice)

        if op_id:
            self.mastery_profile["repaired_operators"].append({
                "operator_id": op_id,
                "student_choice": choice,
                "timestamp": time.time()
            })

        # 回弹后提示当前主线位置
        steps = self.current_scenario.steps
        curr_step = steps[self.current_step_index] if self.current_step_index < len(steps) else None

        return {
            "status": "slice_evaluated",
            "is_snapbacked": action.is_snapbacked,
            "speech_output": action.speech_output,
            "current_stack_depth": len(self.engine.call_stack),
            "resume_main_step": curr_step.step_id if curr_step else None,
            "resume_prompt": curr_step.prompt if curr_step else None
        }

    def get_stack_status(self) -> Dict[str, Any]:
        """查看当前物理调用栈与掌握度画像"""
        snapshot = self.engine.call_stack.get_snapshot()
        return {
            "stack_depth": len(self.engine.call_stack),
            "call_stack_frames": snapshot,
            "current_scenario": self.current_scenario.title if self.current_scenario else None,
            "current_step_index": self.current_step_index + 1 if self.current_scenario else 0,
            "mastery_profile": self.mastery_profile,
            "is_suspended_in_slice": not self.engine.call_stack.is_empty()
        }


# =====================================================================
# MCP 标准协议定义与分发
# =====================================================================

MCP_TOOLS = [
    {
        "name": "tutor_init_session",
        "description": "初始化新课程主线推导。加载核心场景（如 Softmax 雅可比偏导、CUDA 共享内存 Bank Conflict）或基于材料构建推导主线。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "topic_or_material": {
                    "type": "string",
                    "description": "教学推导主题、场景关键词（如 'softmax', 'cuda', '1', '2'）或知识点材料。"
                }
            },
            "required": ["topic_or_material"]
        }
    },
    {
        "name": "tutor_evaluate_step",
        "description": "核心逆向归因与决策动作。接收学生当前步骤的推导输入，定位根因断点，触发 L0~L3 最小充分干预。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "student_input": {
                    "type": "string",
                    "description": "学生在当前主线步骤提交的推导过程、数学公式或代码。"
                }
            },
            "required": ["student_input"]
        }
    },
    {
        "name": "tutor_answer_slice",
        "description": "20秒微切片作答校验并秒级回弹。接收学生对原子探针设问的选择或简答，修补前置断裂后瞬间回弹主线。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "choice": {
                    "type": "string",
                    "description": "学生对 5秒探针问题的选项或答案（如 'A', 'B', 'e^{z_j}' 等）。"
                }
            },
            "required": ["choice"]
        }
    },
    {
        "name": "tutor_get_stack_status",
        "description": "查看当前教学物理调用栈与学生掌握度画像。实时透视栈帧挂起状态、前置算子及历史诊断记录。",
        "inputSchema": {
            "type": "object",
            "properties": {}
        }
    }
]


def serve():
    """MCP Stdio 主通信循环"""
    server = ProActiveTutorMCPServer()
    log_stderr("ProActive-Tutor MCP Stdio Server started successfully.")

    # 针对 Windows 环境下控制台编码保证 UTF-8
    try:
        sys.stdin.reconfigure(encoding='utf-8')
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

    while True:
        try:
            line = sys.stdin.readline()
            if not line:
                log_stderr("Stdin EOF reached. Server terminating.")
                break

            line_str = line.strip()
            if not line_str:
                continue

            try:
                request = json.loads(line_str)
            except Exception as e:
                log_stderr(f"Invalid JSON received: {e}")
                continue

            req_id = request.get("id")
            method = request.get("method")
            params = request.get("params", {})

            # 处理通知（无需响应 id）
            if method == "notifications/initialized":
                log_stderr("Client notified initialized.")
                continue

            response = None

            if method == "initialize":
                response = {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {
                        "protocolVersion": "2024-11-05",
                        "capabilities": {
                            "tools": {
                                "listChanged": False
                            }
                        },
                        "serverInfo": {
                            "name": "proactive-tutor-mcp",
                            "version": "1.0.0"
                        }
                    }
                }

            elif method == "ping":
                response = {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {}
                }

            elif method == "tools/list":
                response = {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {
                        "tools": MCP_TOOLS
                    }
                }

            elif method == "tools/call":
                tool_name = params.get("name")
                arguments = params.get("arguments", {})

                try:
                    if tool_name == "tutor_init_session":
                        topic = arguments.get("topic_or_material", "")
                        tool_res = server.init_session(topic)
                    elif tool_name == "tutor_evaluate_step":
                        student_input = arguments.get("student_input", "")
                        tool_res = server.evaluate_step(student_input)
                    elif tool_name == "tutor_answer_slice":
                        choice = arguments.get("choice", "")
                        tool_res = server.answer_slice(choice)
                    elif tool_name == "tutor_get_stack_status":
                        tool_res = server.get_stack_status()
                    else:
                        raise ValueError(f"Unknown tool: {tool_name}")

                    content_text = json.dumps(tool_res, ensure_ascii=False, indent=2)
                    response = {
                        "jsonrpc": "2.0",
                        "id": req_id,
                        "result": {
                            "content": [
                                {
                                    "type": "text",
                                    "text": content_text
                                }
                            ],
                            "isError": False
                        }
                    }
                except Exception as call_err:
                    log_stderr(f"Error executing tool {tool_name}: {traceback.format_exc()}")
                    response = {
                        "jsonrpc": "2.0",
                        "id": req_id,
                        "result": {
                            "content": [
                                {
                                    "type": "text",
                                    "text": f"Tool Execution Error: {str(call_err)}"
                                }
                            ],
                            "isError": True
                        }
                    }

            else:
                if req_id is not None:
                    response = {
                        "jsonrpc": "2.0",
                        "id": req_id,
                        "error": {
                            "code": -32601,
                            "message": f"Method not found: {method}"
                        }
                    }

            if response is not None:
                sys.stdout.write(json.dumps(response, ensure_ascii=False) + "\n")
                sys.stdout.flush()

        except Exception as loop_err:
            log_stderr(f"Fatal loop exception: {traceback.format_exc()}")


if __name__ == "__main__":
    serve()
