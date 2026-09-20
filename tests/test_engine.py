"""
Unit and Adversarial Test Suite for ProActive-Tutor Core Engine
涵盖四级最小干预策略、调用栈完整性、超时熔断与对抗测试
"""

import sys
import os
import time
import pytest

# 加入工程根目录
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

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


@pytest.fixture
def mock_atomic_operator():
    return AtomicOperator(
        operator_id="op_denom_sum",
        name="分母求导求和坍缩算子",
        concept_summary="对分母求和项偏导时只有目标项非零，坍缩为单项",
        micro_probe_question="d/dz_2 [e^z1 + e^z2 + e^z3] 等于什么？",
        expected_answer="e^z2",
        snapback_bridge="求和号已坍缩为 e^z2，现在代回原题分子！"
    )


@pytest.fixture
def mock_lesson_step(mock_atomic_operator):
    return LessonStep(
        step_id=1,
        prompt="应用商法则写出 ∂S_i/∂z_j 展开式",
        standard_solution="∂S_i/∂z_j = [ (∂e^{z_i}/∂z_j)·(∑_k e^{z_k}) - e^{z_i}·(∂(∑_k e^{z_k})/∂z_j) ] / (∑_k e^{z_k})^2",
        key_invariants=["商法则", "分母平方"],
        common_faults={
            "chain_rule_lost": FaultType.SURFACE_CONFUSION,
            "denominator_linear": FaultType.WRONG_HEURISTIC,
            "cant_do_sum_derivative": FaultType.PREREQUISITE_BROKEN,
        },
        prerequisite_operator=mock_atomic_operator
    )


class TestPedagogicalCallStack:
    """教学调用栈测试套件"""

    def test_call_stack_push_pop_integrity(self):
        stack = PedagogicalCallStack(default_timeout_seconds=25)
        assert stack.is_empty()

        frame1 = StackFrame(frame_id="f1", topic_name="Softmax", current_step=1, step_description="Step 1")
        frame2 = StackFrame(frame_id="f2", topic_name="Softmax", current_step=2, step_description="Step 2")

        stack.push(frame1)
        assert not stack.is_empty()
        assert stack.peek().frame_id == "f1"

        stack.push(frame2)
        assert stack.peek().frame_id == "f2"

        popped2 = stack.pop()
        assert popped2.frame_id == "f2"
        popped1 = stack.pop()
        assert popped1.frame_id == "f1"
        assert stack.is_empty()

    def test_call_stack_timeout_forced_snapback(self):
        stack = PedagogicalCallStack(default_timeout_seconds=1)
        old_frame = StackFrame(
            frame_id="f_timeout",
            topic_name="Softmax",
            current_step=1,
            step_description="Stuck step",
            suspended_at=time.time() - 5.0,  # 挂起已超过5秒
            timeout_seconds=1
        )
        stack.push(old_frame)

        # 检查超时应触发强制回弹弹出
        timed_out = stack.check_timeout()
        assert len(timed_out) == 1
        assert timed_out[0].frame_id == "f_timeout"
        assert stack.is_empty()


class TestDecisionPolicyEngine:
    """决策引擎策略分级与对抗测试"""

    def test_l0_spotlight(self, mock_lesson_step):
        engine = PedagogicalDecisionEngine()
        # 模拟仅有微小符号/格式笔误输入 (例如仅漏掉一个下标)
        action = engine.decide_action(mock_lesson_step, "∂S_i/∂z_j = [ (∂e^{z_i}/∂z_j)·(∑_k e^{z_k}) - e^{z_i}·(∂(∑_k e^{z_k})/∂z_j) ] / (∑_k e^{z_k})")
        # 漏了分母平方 -> 属于细节锚定
        assert action.level in [InterventionLevel.L0_SPOTLIGHT, InterventionLevel.L1_SOCRATIC_PROMPT]
        assert len(action.speech_output) <= 50  # 严禁废话

    def test_l1_socratic_prompt(self, mock_lesson_step):
        engine = PedagogicalDecisionEngine()
        # 表面混淆：提到了 chain_rule_lost 相关特征
        action = engine.decide_action(mock_lesson_step, "chain_rule_lost: 我把分子分母直接分别求导了")
        assert action.level in [InterventionLevel.L1_SOCRATIC_PROMPT, InterventionLevel.L2_COUNTER_EXAMPLE]
        assert len(action.speech_output) <= 60

    def test_l2_counter_example(self, mock_lesson_step):
        engine = PedagogicalDecisionEngine()
        # 伪直觉：denominator_linear
        action = engine.decide_action(mock_lesson_step, "denominator_linear: 分母求和的导数难道不就是所有导数的和直接消掉吗")
        assert action.level == InterventionLevel.L2_COUNTER_EXAMPLE

    def test_l3_atomic_slice_and_snapback(self, mock_lesson_step):
        engine = PedagogicalDecisionEngine()
        # 底层断裂：完全不知道求和项导数怎么求
        action = engine.decide_action(mock_lesson_step, "cant_do_sum_derivative: 我完全不知道这个求和符号∑怎么对单一zj求偏导")
        assert action.level == InterventionLevel.L3_ATOMIC_SLICE
        assert action.is_stack_pushed is True
        assert not engine.call_stack.is_empty()
        assert "d/dz_2" in action.speech_output or "原子测试" in action.speech_output

        # 学生在切片中做对 -> 瞬间回弹
        snapback_action = engine.process_atomic_response("e^z2")
        assert snapback_action.is_snapbacked is True
        assert engine.call_stack.is_empty()

    def test_student_gibberish_or_empty_input(self, mock_lesson_step):
        engine = PedagogicalDecisionEngine()
        # 乱码或空输入
        action = engine.decide_action(mock_lesson_step, "???")
        assert action.level is not None
        assert len(action.speech_output) > 0
        # 乱码不能导致系统崩溃
        action_empty = engine.decide_action(mock_lesson_step, "")
        assert action_empty.level is not None
