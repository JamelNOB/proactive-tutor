#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ProActive-Tutor 交互式导师命令行终端 (CLI Tutor)
特点：
- 界面极简、高密度、零废话；
- 支持用户直接输入作答；
- 显示毫秒级决策耗时、状态栈指示灯：
  [主线推导中] vs [⚡原子微切片挂起中 (剩余20s)] vs [🎯瞬间回弹主线]；
- 提供模拟测试模式 (--simulate) 和真实交互模式。
"""

import sys
import os
import time
import argparse
from typing import Optional, List, Dict, Tuple

# Windows 控制台编码防护
if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

# 路径加载
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
if CURRENT_DIR not in sys.path:
    sys.path.insert(0, CURRENT_DIR)
sys.path.insert(0, r"C:\Users\JamelNOB\.gemini\antigravity\scratch\proactive-tutor")

try:
    from core.models import (
        InterventionLevel, FaultType, AtomicOperator,
        DiagnosisResult, InterventionAction, StackFrame, LessonStep
    )
except ImportError:
    from scenarios import (
        InterventionLevel, FaultType, AtomicOperator,
        DiagnosisResult, InterventionAction, LessonStep
    )

try:
    from core.scenarios import (
        Scenario, get_scenario, ALL_SCENARIOS,
        SCENARIO_SOFTMAX_ATTENTION_BACKPROP, SCENARIO_CUDA_BANK_CONFLICT
    )
except ImportError:
    from scenarios import (
        Scenario, get_scenario, ALL_SCENARIOS,
        SCENARIO_SOFTMAX_ATTENTION_BACKPROP, SCENARIO_CUDA_BANK_CONFLICT
    )


# =====================================================================
# 终端 ANSI 颜色与极简视觉渲染
# =====================================================================
class ANSI:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    CYAN = "\033[36m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    RED = "\033[31m"
    MAGENTA = "\033[35m"
    BLUE = "\033[34m"
    BG_BLUE = "\033[44m"
    BG_RED = "\033[41m"
    BG_YELLOW = "\033[43m"


# =====================================================================
# 教学推导决策评估器 (Evaluation & Pedagogy Decision Engine)
# =====================================================================
class TutorEngine:
    def __init__(self, scenario: Scenario):
        self.scenario = scenario
        self.current_step_idx = 0
        self.stack: List[StackFrame] = []
        self.active_slice: Optional[AtomicOperator] = None
        self.slice_start_time: float = 0.0

    def get_current_step(self) -> Optional[LessonStep]:
        if self.current_step_idx < len(self.scenario.steps):
            return self.scenario.steps[self.current_step_idx]
        return None

    def evaluate_input(self, user_ans: str) -> Tuple[InterventionAction, float]:
        """
        核心逆向归因与决策，返回动作与耗时(ms)
        """
        t0 = time.perf_counter()
        user_clean = user_ans.strip()
        step = self.get_current_step()

        # 1. 若处于原子微切片挂起状态
        if self.active_slice:
            elapsed = time.time() - self.slice_start_time
            # 校验原子题作答 (支持选项 A/B/C 或关键字)
            exp = self.active_slice.expected_answer.upper()
            user_choice = user_clean.upper()

            is_match = (
                user_choice == exp or 
                user_choice.startswith(exp) or
                (exp == "B" and ("e^{z_j}" in user_clean or "1" in user_clean or "错位" in user_clean))
            )

            if is_match:
                # 瞬间回弹主线
                bridge_speech = self.active_slice.snapback_bridge
                self.active_slice = None
                if self.stack:
                    self.stack.pop()
                dt_ms = (time.perf_counter() - t0) * 1000.0
                return InterventionAction(
                    level=InterventionLevel.L3_ATOMIC_SLICE,
                    speech_output=bridge_speech,
                    is_stack_pushed=False,
                    is_snapbacked=True
                ), dt_ms
            else:
                # 切片内二度纠正 (极简单句)
                dt_ms = (time.perf_counter() - t0) * 1000.0
                return InterventionAction(
                    level=InterventionLevel.L3_ATOMIC_SLICE,
                    speech_output=f"【算子纠偏】答案应为 {self.active_slice.expected_answer}。{self.active_slice.concept_summary}",
                    atomic_operator=self.active_slice,
                    is_stack_pushed=False,
                    is_snapbacked=False
                ), dt_ms

        if not step:
            dt_ms = (time.perf_counter() - t0) * 1000.0
            return InterventionAction(
                level=InterventionLevel.L0_SPOTLIGHT,
                speech_output="全部推导闭环完成！",
                is_snapbacked=False
            ), dt_ms

        # 2. 正常主线推导评估
        # 命中不变量判定 (精确/模糊包含)
        matched_invariants = [inv for inv in step.key_invariants if inv.lower() in user_clean.lower()]
        has_slip_or_doubt = any(kw in user_clean for kw in ["不会", "卡住", "求和项怎么求导", "不懂", "为什么", "不知道", "死锁", "忘了"])

        # 判定是否触发前置断裂并激活原子算子切片
        if step.prerequisite_operator and (has_slip_or_doubt or len(matched_invariants) == 0):
            # 挂起主线 -> 注入原子微切片
            self.active_slice = step.prerequisite_operator
            self.slice_start_time = time.time()
            frame = StackFrame(
                frame_id=f"frame_step_{step.step_id}",
                topic_name=self.scenario.scenario_id,
                current_step=step.step_id,
                step_description=step.prompt,
                suspended_at=time.time(),
                atomic_operator=self.active_slice,
                timeout_seconds=20
            )
            self.stack.append(frame)

            speech = (
                f"【微切片挂起】检测到底层前置算子未就绪：{self.active_slice.name}。\n"
                f"⚡ {self.active_slice.concept_summary}\n"
                f"👉 {self.active_slice.micro_probe_question}"
            )
            dt_ms = (time.perf_counter() - t0) * 1000.0
            return InterventionAction(
                level=InterventionLevel.L3_ATOMIC_SLICE,
                speech_output=speech,
                atomic_operator=self.active_slice,
                max_duration_seconds=20,
                is_stack_pushed=True,
                is_snapbacked=False
            ), dt_ms

        # 判定是否包含核心答案
        if len(matched_invariants) >= 1 or user_clean == "pass":
            # 本步通过，推进下一阶段
            self.current_step_idx += 1
            next_step = self.get_current_step()
            dt_ms = (time.perf_counter() - t0) * 1000.0
            if next_step:
                msg = f"✅ 本步闭合！标准对照: {step.standard_solution}\n\n👉 紧跟主线推进:"
            else:
                msg = f"🎉 完美推导完成！标准闭环: {step.standard_solution}"
            return InterventionAction(
                level=InterventionLevel.L0_SPOTLIGHT,
                speech_output=msg,
                is_snapbacked=False
            ), dt_ms

        # 弱匹配或表层混淆 -> L1 脚手架设问
        dt_ms = (time.perf_counter() - t0) * 1000.0
        return InterventionAction(
            level=InterventionLevel.L1_SOCRATIC_PROMPT,
            speech_output=f"【脚手架提示】注意这一步的核心不变量: {', '.join(step.key_invariants[:2])}。再试一次？",
            is_snapbacked=False
        ), dt_ms


# =====================================================================
# 状态指示灯与终端渲染
# =====================================================================
def render_status_bar(engine: TutorEngine):
    if engine.active_slice:
        elapsed = int(time.time() - engine.slice_start_time)
        remain = max(0, 20 - elapsed)
        indicator = f"{ANSI.BG_YELLOW}{ANSI.BOLD} ⚡ 原子微切片挂起中 (剩余{remain}s) {ANSI.RESET}"
    elif len(engine.stack) == 0:
        indicator = f"{ANSI.GREEN}{ANSI.BOLD} [主线推导中] {ANSI.RESET}"
    else:
        indicator = f"{ANSI.CYAN}{ANSI.BOLD} [🎯瞬间回弹主线] {ANSI.RESET}"

    step_info = f"进度: Step {min(engine.current_step_idx + 1, len(engine.scenario.steps))}/{len(engine.scenario.steps)}"
    print(f"\n{ANSI.DIM}--------------------------------------------------------------------------------{ANSI.RESET}")
    print(f"状态栈: {indicator} | {step_info} | 场景: {engine.scenario.title}")
    print(f"{ANSI.DIM}--------------------------------------------------------------------------------{ANSI.RESET}")


# =====================================================================
# CLI 运行主控
# =====================================================================
def run_tutor(scenario_key: str = "1", simulate: bool = False):
    scenario = get_scenario(scenario_key)
    if not scenario:
        print(f"{ANSI.RED}错误: 未找到场景 '{scenario_key}'。可选场景: 1 (Softmax), 2 (CUDA Bank Conflict){ANSI.RESET}")
        return

    engine = TutorEngine(scenario)

    print(f"\n{ANSI.BOLD}{ANSI.CYAN}================================================================================")
    print(f"   名师微创导学决策引擎 (ProActive-Tutor CLI)")
    print(f"   当前场景: [{scenario.category}] {scenario.title}")
    print(f"   模式: {'自动化模拟对练 (--simulate)' if simulate else '高密度真实交互'}")
    print(f"================================================================================{ANSI.RESET}\n")
    print(f"{ANSI.DIM}简介: {scenario.description}{ANSI.RESET}\n")

    # 预置模拟输入脚本 (用于 --simulate 模式)
    simulate_scripts = {
        "Softmax_Attention_Backprop": [
            ("商法则展开: (u'v - uv') / v^2，分子为 (∂e^{z_i}/∂z_j)·∑e^{z_k} - e^{z_i}·∂(∑e^{z_k})/∂z_j", "学生按标准商法则展开"),
            ("求和项怎么求导？为什么感觉求和项很大很难算，卡住了", "学生在前置微积分坍缩处发生认知断裂"),
            ("B", "学生在5秒原子切片中秒答 'B (e^{z_j})'"),
            ("代入坍缩项，i==j 时为 S_i(1-S_i)，i!=j 时为 -S_i*S_j", "回弹主线后完成对角/非对角最终推导")
        ],
        "CUDA_Shared_Memory_Bank_Conflict": [
            ("访问 sData[threadIdx.x][0] 时，所有 32 个线程全部落在 Bank 0，产生 32-way 满冲突，完全串行化", "学生准确指出 Bank 0 满冲突"),
            ("怎么改完全不知道，为什么换成二维还会死锁？", "学生在错位 Padding 算子处产生阻滞"),
            ("B", "学生在5秒切片中秒算 '(1*33)%32 = 1'，确认错位"),
            ("公式为 Bank ID = (k * 33) % 32 = k，32 个线程分散到 32 个独立 Bank，0 冲突", "回弹主线完成带宽满载证明")
        ]
    }

    sim_inputs = simulate_scripts.get(scenario.scenario_id, [])
    sim_idx = 0

    while True:
        step = engine.get_current_step()
        if not step and not engine.active_slice:
            render_status_bar(engine)
            print(f"\n{ANSI.GREEN}{ANSI.BOLD}🎓 恭喜！整个推导主线已完全闭环验证通过！{ANSI.RESET}\n")
            break

        render_status_bar(engine)

        if not engine.active_slice and step:
            print(f"\n{ANSI.BOLD}{ANSI.BLUE}【推导任务】{ANSI.RESET} {step.prompt}")

        # 获取作答
        if simulate:
            if sim_idx < len(sim_inputs):
                user_input, note = sim_inputs[sim_idx]
                sim_idx += 1
                time.sleep(0.6)  # 拟真演示停顿
                print(f"\n{ANSI.YELLOW}▶ [学生输入 ({note})]:{ANSI.RESET} {user_input}")
            else:
                user_input = "pass"
                print(f"\n{ANSI.YELLOW}▶ [学生输入]:{ANSI.RESET} pass")
        else:
            try:
                prompt_label = "⚡ [原子切片选项 A/B/C] >> " if engine.active_slice else "✍️  [你的推导/解答 (输入 q 退出)] >> "
                user_input = input(f"\n{ANSI.YELLOW}{prompt_label}{ANSI.RESET}")
            except (KeyboardInterrupt, EOFError):
                print(f"\n{ANSI.DIM}退出导师终端。{ANSI.RESET}")
                break

            if user_input.strip().lower() in ["q", "quit", "exit"]:
                print(f"{ANSI.DIM}已中止推导。{ANSI.RESET}")
                break

        # 引擎决策评估
        action, dt_ms = engine.evaluate_input(user_input)

        # 耗时与动作渲染
        dt_color = ANSI.GREEN if dt_ms < 5.0 else ANSI.YELLOW
        print(f"\n{ANSI.DIM}[决策耗时: {dt_color}{dt_ms:.2f}ms{ANSI.DIM} | 干预层级: {action.level.value}]{ANSI.RESET}")

        if action.is_snapbacked:
            print(f"{ANSI.CYAN}{ANSI.BOLD}[🎯瞬间回弹主线]{ANSI.RESET} {action.speech_output}")
        elif action.is_stack_pushed:
            print(f"{ANSI.MAGENTA}{ANSI.BOLD}{action.speech_output}{ANSI.RESET}")
        else:
            print(f"{ANSI.BOLD}{action.speech_output}{ANSI.RESET}")

        time.sleep(0.3)


# =====================================================================
# CLI 参数解析入口
# =====================================================================
def main():
    parser = argparse.ArgumentParser(
        description="ProActive-Tutor CLI: 名师微创导学极简交互终端",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "-s", "--scenario",
        default="1",
        choices=["1", "2", "softmax", "cuda"],
        help="选择推导场景: 1=Softmax反向传播推导(期末突击), 2=CUDA Bank Conflict错位(项目防穿帮)"
    )
    parser.add_argument(
        "--simulate",
        action="store_true",
        help="启用全自动模拟对练推演模式 (验证状态栈挂起与瞬间回弹完整闭环)"
    )

    args = parser.parse_args()
    run_tutor(scenario_key=args.scenario, simulate=args.simulate)


if __name__ == "__main__":
    main()
