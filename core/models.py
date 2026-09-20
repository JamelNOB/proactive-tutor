"""
Core Data Models for ProActive-Tutor (名师微创导学决策引擎)
"""

from enum import Enum
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field
import time


class InterventionLevel(str, Enum):
    """最小充分干预层级"""
    L0_SPOTLIGHT = "L0_SPOTLIGHT"              # 聚光灯锚定 (≤ 3秒, 仅指引视线，不给知识)
    L1_SOCRATIC_PROMPT = "L1_SOCRATIC_PROMPT"  # 脚手架设问 (≤ 8秒, 提问已知不变量)
    L2_COUNTER_EXAMPLE = "L2_COUNTER_EXAMPLE"  # 极限反例冲击 (≤ 10秒, 极值击碎伪规律)
    L3_ATOMIC_SLICE = "L3_ATOMIC_SLICE"        # 原子微切片 (≤ 20秒, 挂起主线->注入单步算子->回弹)


class FaultType(str, Enum):
    """诊断错误根因类型"""
    SLIP = "SLIP"                              # 纯笔误/下标抄错
    SURFACE_CONFUSION = "SURFACE_CONFUSION"    # 局部推导符号或桥梁概念模糊
    WRONG_HEURISTIC = "WRONG_HEURISTIC"        # 抱有错误的伪经验/伪守恒直觉
    PREREQUISITE_BROKEN = "PREREQUISITE_BROKEN"# 底层前置关联知识断裂


@dataclass
class AtomicOperator:
    """原子算子定义"""
    operator_id: str
    name: str
    concept_summary: str          # 极简规则(1句话)
    micro_probe_question: str     # 5秒切片设问
    expected_answer: str          # 预期脱口而出的答案
    snapback_bridge: str          # 瞬间回弹到主线的接驳语


@dataclass
class DiagnosisResult:
    """逆向归因诊断结果"""
    fault_type: FaultType
    divergence_point: str         # 首个偏离断点
    confidence: float             # 归因置信度 (0.0 ~ 1.0)
    associated_operator: Optional[AtomicOperator] = None
    detail: str = ""


@dataclass
class InterventionAction:
    """决策引擎输出的教学动作"""
    level: InterventionLevel
    speech_output: str            # 名师对学生说的话 (极度克制，无废话)
    target_token: Optional[str] = None
    atomic_operator: Optional[AtomicOperator] = None
    max_duration_seconds: int = 20
    is_stack_pushed: bool = False
    is_snapbacked: bool = False


@dataclass
class StackFrame:
    """教学调用栈帧"""
    frame_id: str
    topic_name: str
    current_step: int
    step_description: str
    suspended_at: float = field(default_factory=time.time)
    atomic_operator: Optional[AtomicOperator] = None
    timeout_seconds: int = 25


@dataclass
class LessonStep:
    """课程主线单步推导目标"""
    step_id: int
    prompt: str                   # 老师布置的当前步骤任务
    standard_solution: str        # 标准推导结果/代码
    key_invariants: List[str]     # 这一步的核心不变量
    common_faults: Dict[str, FaultType] = field(default_factory=dict)
    prerequisite_operator: Optional[AtomicOperator] = None
