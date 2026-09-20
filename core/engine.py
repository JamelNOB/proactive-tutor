"""
ProActive-Tutor Core Pedagogical Engine
名师微创导学决策引擎核心实现
"""

import sys
import os
import time
import uuid
from typing import Optional, List, Dict, Any, Tuple
from dataclasses import asdict

# 兼容加载核心数据模型
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
except ImportError:
    # 动态支持跨路径或本地导入
    models_path = r"C:\Users\JamelNOB\.gemini\antigravity\scratch\proactive-tutor"
    if models_path not in sys.path:
        sys.path.insert(0, models_path)
    from core.models import (
        InterventionLevel,
        FaultType,
        AtomicOperator,
        DiagnosisResult,
        InterventionAction,
        StackFrame,
        LessonStep,
    )


class PedagogicalCallStack:
    """
    教学状态栈：支持上下文挂起、瞬间回弹、超时强制熔断与快照
    """

    def __init__(self, default_timeout_seconds: int = 25):
        self._stack: List[StackFrame] = []
        self.default_timeout_seconds = default_timeout_seconds

    def push(self, frame: StackFrame) -> None:
        """压入挂起的主线教学上下文"""
        if frame.suspended_at is None:
            frame.suspended_at = time.time()
        self._stack.append(frame)

    def pop(self) -> Optional[StackFrame]:
        """弹出最近挂起的教学上下文"""
        if not self._stack:
            return None
        return self._stack.pop()

    def peek(self) -> Optional[StackFrame]:
        """查看栈顶教学上下文（不弹出）"""
        if not self._stack:
            return None
        return self._stack[-1]

    def is_empty(self) -> bool:
        """检查调用栈是否为空"""
        return len(self._stack) == 0

    def clear(self) -> None:
        """清空调用栈"""
        self._stack.clear()

    def check_timeout(self, max_seconds: Optional[int] = None) -> List[StackFrame]:
        """
        超时检查与强制熔断回弹。
        如果栈顶帧挂起时间超过 max_seconds，则触发强制清空回弹，避免学生在支线卡死。
        返回超时的帧列表。
        """
        limit = max_seconds if max_seconds is not None else self.default_timeout_seconds
        now = time.time()
        timed_out_frames = []

        while self._stack:
            top = self._stack[-1]
            elapsed = now - top.suspended_at
            frame_limit = top.timeout_seconds if top.timeout_seconds else limit
            if elapsed >= frame_limit:
                timed_out_frames.append(self._stack.pop())
            else:
                break

        return timed_out_frames

    def get_snapshot(self) -> List[Dict[str, Any]]:
        """获取当前教学调用栈的深层快照"""
        snapshot = []
        for frame in self._stack:
            snapshot.append({
                "frame_id": frame.frame_id,
                "topic_name": frame.topic_name,
                "current_step": frame.current_step,
                "step_description": frame.step_description,
                "suspended_at": frame.suspended_at,
                "timeout_seconds": frame.timeout_seconds,
                "has_operator": frame.atomic_operator is not None,
                "operator_id": frame.atomic_operator.operator_id if frame.atomic_operator else None
            })
        return snapshot

    def __len__(self) -> int:
        return len(self._stack)


class RootCauseTracer:
    """
    逆向差分归因器：比对学生输入与标准解法，定位偏离断点并诊断根因
    """

    @staticmethod
    def trace(lesson_step: LessonStep, student_input: str) -> DiagnosisResult:
        student_clean = student_input.strip()
        standard_clean = lesson_step.standard_solution.strip()

        # 1. 检查预设的已知错误模式 (Common Faults)
        for fault_pattern, fault_type in lesson_step.common_faults.items():
            if fault_pattern.lower() in student_clean.lower() or student_clean.lower() == fault_pattern.lower():
                operator = lesson_step.prerequisite_operator if fault_type == FaultType.PREREQUISITE_BROKEN else None
                return DiagnosisResult(
                    fault_type=fault_type,
                    divergence_point=fault_pattern,
                    confidence=0.95,
                    associated_operator=operator,
                    detail=f"命中预设认知特征: '{fault_pattern}' -> {fault_type.value}"
                )

        # 2. 检查字符级 / 符号级差分（判断是否为 SLIP 笔误）
        diff_info = RootCauseTracer._diff_tokens(standard_clean, student_clean)
        divergence_point, similarity = diff_info

        # 如果高度相似且只是个别字符/下标微差，判定为 SLIP
        if similarity >= 0.80:
            return DiagnosisResult(
                fault_type=FaultType.SLIP,
                divergence_point=divergence_point or "局部字符/下标差异",
                confidence=0.88,
                associated_operator=None,
                detail=f"高相似度({similarity:.2f})局部符号微差，判定为轻度笔误/手滑"
            )

        # 3. 检查核心不变量是否缺失或冲突
        missing_invariants = [inv for inv in lesson_step.key_invariants if inv.lower() not in student_clean.lower()]
        if missing_invariants:
            # 如果存在关联的前置算子且缺失关键不变量，判定为前置断裂
            if lesson_step.prerequisite_operator is not None:
                return DiagnosisResult(
                    fault_type=FaultType.PREREQUISITE_BROKEN,
                    divergence_point=missing_invariants[0],
                    confidence=0.92,
                    associated_operator=lesson_step.prerequisite_operator,
                    detail=f"核心不变量缺失: '{missing_invariants[0]}', 触发前置算子微创修复"
                )
            # 否则视作伪经验或概念混淆
            if len(missing_invariants) == len(lesson_step.key_invariants):
                return DiagnosisResult(
                    fault_type=FaultType.WRONG_HEURISTIC,
                    divergence_point=missing_invariants[0],
                    confidence=0.85,
                    associated_operator=None,
                    detail="全部核心不变量违背，存在伪守恒/直觉偏见"
                )
            return DiagnosisResult(
                fault_type=FaultType.SURFACE_CONFUSION,
                divergence_point=missing_invariants[0],
                confidence=0.78,
                associated_operator=None,
                detail="部分核心不变量未体现，局部推导桥梁模糊"
            )

        # 默认归因：表面混淆
        return DiagnosisResult(
            fault_type=FaultType.SURFACE_CONFUSION,
            divergence_point=divergence_point or "推导表述模糊",
            confidence=0.70,
            associated_operator=lesson_step.prerequisite_operator,
            detail="标准解法与学生推导在局部符号或逻辑表达上存在差异"
        )

    @staticmethod
    def _diff_tokens(standard: str, student: str) -> Tuple[str, float]:
        """简易归一化相似度与偏离锚点比对"""
        if not standard or not student:
            return "", 0.0

        std_tokens = standard.replace(" ", "")
        stu_tokens = student.replace(" ", "")

        # 首个偏离字符/子串定位
        divergence = ""
        min_len = min(len(std_tokens), len(stu_tokens))
        for i in range(min_len):
            if std_tokens[i] != stu_tokens[i]:
                divergence = f"期望 '{std_tokens[i]}' 实为 '{stu_tokens[i]}'"
                break

        # 计算简易 Levenshtein 相似度比例
        match_count = sum(1 for a, b in zip(std_tokens, stu_tokens) if a == b)
        max_len = max(len(std_tokens), len(stu_tokens))
        similarity = match_count / max_len if max_len > 0 else 1.0

        return divergence, similarity


class PedagogicalDecisionEngine:
    """
    名师微创导学决策引擎
    控制最小充分干预层级 (L0~L3)、挂起/回弹生命周期以及高能极简对话
    """

    def __init__(self, default_timeout_seconds: int = 25, max_stack_depth: int = 2):
        self.call_stack = PedagogicalCallStack(default_timeout_seconds=default_timeout_seconds)
        self.tracer = RootCauseTracer()
        self.current_step: Optional[LessonStep] = None
        self.max_stack_depth = max_stack_depth

    def decide_action(self, step: LessonStep, student_input: str) -> InterventionAction:
        """
        主线步骤中，接收学生输入并决策干预动作
        """
        self.current_step = step

        # 1. 检查是否存在超时未解决的栈帧
        timed_out = self.call_stack.check_timeout()
        if timed_out:
            # 熔断强回弹
            return InterventionAction(
                level=InterventionLevel.L0_SPOTLIGHT,
                speech_output=f"时间到。我们直接回到主线第 {step.step_id} 步：聚焦核心不变量。",
                target_token=step.key_invariants[0] if step.key_invariants else None,
                max_duration_seconds=5,
                is_snapbacked=True
            )

        # 2. 诊断归因
        diagnosis = self.tracer.trace(step, student_input)

        # 3. 按干预层级精准映射与决策
        if diagnosis.fault_type == FaultType.SLIP:
            # L0: 聚光灯锚定 (≤ 3秒)
            return InterventionAction(
                level=InterventionLevel.L0_SPOTLIGHT,
                speech_output=f"看这里：{diagnosis.divergence_point}，注意正负号与下标。",
                target_token=diagnosis.divergence_point,
                max_duration_seconds=3,
                is_stack_pushed=False,
                is_snapbacked=False
            )

        elif diagnosis.fault_type == FaultType.SURFACE_CONFUSION:
            # L1: 脚手架设问 (≤ 8秒)
            inv = step.key_invariants[0] if step.key_invariants else "当前约束"
            return InterventionAction(
                level=InterventionLevel.L1_SOCRATIC_PROMPT,
                speech_output=f"在这一步展开时，{inv} 必须满足什么守恒条件？",
                target_token=inv,
                max_duration_seconds=8,
                is_stack_pushed=False,
                is_snapbacked=False
            )

        elif diagnosis.fault_type == FaultType.WRONG_HEURISTIC:
            # L2: 极限反例冲击 (≤ 10秒)
            return InterventionAction(
                level=InterventionLevel.L2_COUNTER_EXAMPLE,
                speech_output="如果取极限状态或令参数为 0，你的推导还会成立吗？",
                target_token=diagnosis.divergence_point,
                max_duration_seconds=10,
                is_stack_pushed=False,
                is_snapbacked=False
            )

        elif diagnosis.fault_type == FaultType.PREREQUISITE_BROKEN:
            # L3: 原子微切片 (≤ 20秒)
            # 检查栈深度，防止死循环下沉（最多允许 max_stack_depth 层深度的前置切片）
            if len(self.call_stack) >= self.max_stack_depth:
                # 达到最大嵌套深度，强制熔断清空栈并直接给出结论锚定
                self.call_stack.clear() if hasattr(self.call_stack, 'clear') else [self.call_stack.pop() for _ in range(len(self.call_stack))]
                return InterventionAction(
                    level=InterventionLevel.L0_SPOTLIGHT,
                    speech_output="已达最大前置探针深度。直接给出核心结论，强制回到主线推导！",
                    target_token=diagnosis.divergence_point,
                    max_duration_seconds=5,
                    is_stack_pushed=False,
                    is_snapbacked=True
                )

            # 挂起当前主线步骤到栈
            operator = diagnosis.associated_operator or step.prerequisite_operator
            frame = StackFrame(
                frame_id=f"frame_{step.step_id}_{uuid.uuid4().hex[:6]}",
                topic_name=f"Step_{step.step_id}_Prereq_Fix",
                current_step=step.step_id,
                step_description=step.prompt,
                suspended_at=time.time(),
                atomic_operator=operator,
                timeout_seconds=25
            )
            self.call_stack.push(frame)

            probe_q = operator.micro_probe_question if operator else "这个前置算子的定义是什么？"
            return InterventionAction(
                level=InterventionLevel.L3_ATOMIC_SLICE,
                speech_output=f"暂停一下。回答我：{probe_q}",
                target_token=diagnosis.divergence_point,
                atomic_operator=operator,
                max_duration_seconds=20,
                is_stack_pushed=True,
                is_snapbacked=False
            )

        # 默认安全降级
        return InterventionAction(
            level=InterventionLevel.L0_SPOTLIGHT,
            speech_output="核对当前这步目标。",
            max_duration_seconds=3
        )

    def process_atomic_response(self, user_input: str) -> InterventionAction:
        """
        在 L3 原子微切片支线中，处理学生的快速回答
        """
        if self.call_stack.is_empty():
            # 栈空说明已在主线
            return InterventionAction(
                level=InterventionLevel.L0_SPOTLIGHT,
                speech_output="主线继续，请继续推导。",
                max_duration_seconds=3
            )

        current_frame = self.call_stack.peek()
        operator = current_frame.atomic_operator

        # 超时熔断
        if time.time() - current_frame.suspended_at >= current_frame.timeout_seconds:
            self.call_stack.pop()
            return InterventionAction(
                level=InterventionLevel.L0_SPOTLIGHT,
                speech_output="切片超时。直接记住结论，立刻回弹主线。",
                max_duration_seconds=5,
                is_snapbacked=True
            )

        expected = operator.expected_answer.strip().lower() if operator else ""
        user_ans = user_input.strip().lower()

        # 命中期望答案：瞬间回弹主线
        is_correct = (expected in user_ans) or (user_ans in expected) or (expected == "")

        if is_correct:
            # 弹出栈帧，瞬间回弹
            popped_frame = self.call_stack.pop()
            bridge = operator.snapback_bridge if operator else "很好，带入主线继续！"
            return InterventionAction(
                level=InterventionLevel.L0_SPOTLIGHT,
                speech_output=f"对！{bridge}",
                target_token=operator.operator_id if operator else None,
                atomic_operator=operator,
                max_duration_seconds=5,
                is_stack_pushed=False,
                is_snapbacked=True
            )
        else:
            # 切片内单次纠正（直接给出极简不变量并回弹）
            self.call_stack.pop()
            summary = operator.concept_summary if operator else "明确核心定义"
            return InterventionAction(
                level=InterventionLevel.L0_SPOTLIGHT,
                speech_output=f"不准确。记住：{summary}。立刻回到主线！",
                target_token=operator.operator_id if operator else None,
                atomic_operator=operator,
                max_duration_seconds=5,
                is_stack_pushed=False,
                is_snapbacked=True
            )
