"""
Scenarios Library for ProActive-Tutor (名师微创导学决策引擎 - 双黄金推导场景库)
场景一（期末突击）：Softmax_Attention_Backprop（包含分母求导求和坍缩原子算子）
场景二（项目防穿帮）：CUDA_Shared_Memory_Bank_Conflict（包含 32-way Bank 错位 Padding 原子算子）
"""

import sys
import os
from typing import Dict, List, Optional
from dataclasses import dataclass, field

# 允许直接引用 core.models 或同目录模块
sys.path.insert(0, r"C:\Users\JamelNOB\.gemini\antigravity\scratch\proactive-tutor")
try:
    from core.models import LessonStep, AtomicOperator, FaultType, InterventionLevel, DiagnosisResult, InterventionAction
except ImportError:
    # 容错降级定义
    from enum import Enum
    class InterventionLevel(str, Enum):
        L0_SPOTLIGHT = "L0_SPOTLIGHT"
        L1_SOCRATIC_PROMPT = "L1_SOCRATIC_PROMPT"
        L2_COUNTER_EXAMPLE = "L2_COUNTER_EXAMPLE"
        L3_ATOMIC_SLICE = "L3_ATOMIC_SLICE"
    class FaultType(str, Enum):
        SLIP = "SLIP"
        SURFACE_CONFUSION = "SURFACE_CONFUSION"
        WRONG_HEURISTIC = "WRONG_HEURISTIC"
        PREREQUISITE_BROKEN = "PREREQUISITE_BROKEN"
    @dataclass
    class AtomicOperator:
        operator_id: str
        name: str
        concept_summary: str
        micro_probe_question: str
        expected_answer: str
        snapback_bridge: str
    @dataclass
    class LessonStep:
        step_id: int
        prompt: str
        standard_solution: str
        key_invariants: List[str]
        common_faults: Dict[str, FaultType] = field(default_factory=dict)
        prerequisite_operator: Optional[AtomicOperator] = None


@dataclass
class Scenario:
    scenario_id: str
    title: str
    category: str  # "期末突击" / "项目防穿帮"
    description: str
    steps: List[LessonStep]
    atomic_operators: Dict[str, AtomicOperator]


# =====================================================================
# 原子算子 1: 分母求导求和坍缩算子 (Denominator Sum Collapse Operator)
# =====================================================================
OP_DENOM_SUM_COLLAPSE = AtomicOperator(
    operator_id="OP_DENOM_SUM_COLLAPSE",
    name="分母求导求和坍缩算子",
    concept_summary="对分母求和项 ∑_k e^{z_k} 关于单个变量 z_j 求偏导时，求和符号中只有 k=j 的那一项导数非零，其余项导数为零，求和符号直接坍缩为单项 e^{z_j}。",
    micro_probe_question="【5秒原子测试】d/dz_j [ e^{z_1} + e^{z_2} + ... + e^{z_K} ] 的结果是？(输入: A. ∑_k e^{z_k}  B. e^{z_j}  C. 0)",
    expected_answer="B",
    snapback_bridge="🎯 求和号已坍缩为 e^{z_j}。现在带回商法则分母的导数项，写出完整 ∂S_i/∂z_j 表达式！"
)

# =====================================================================
# 原子算子 2: 32-way Bank 错位 Padding 算子 (Bank Stride Padding Operator)
# =====================================================================
OP_BANK_STRIDE_PADDING = AtomicOperator(
    operator_id="OP_BANK_STRIDE_PADDING",
    name="32-way Bank 错位 Padding 算子",
    concept_summary="Shared Memory 划分为 32 个 4-byte 宽度的 Bank。二维数组 [32][32] 列访问时 32 线程必全中 Bank 0 产生 32 路满冲突。通过声明 [32][33]（Padding +1），每行步长由 32 变为 33，使第 r 行第 c 列映射为 (r*33 + c) % 32 = (r + c) % 32，对角错位化解全部冲突。",
    micro_probe_question="【5秒原子测试】若声明为 float sData[32][33]，第 1 行第 0 列元素 sData[1][0] 的 Bank 编号 (1*33+0)%32 是几号 Bank？(输入: A. 0  B. 1  C. 32)",
    expected_answer="B",
    snapback_bridge="🎯 Bank 编号已从 0 错位推移到 1，32 个线程完美打散到 32 个独立 Bank。立刻落盘修改核函数声明！"
)


# =====================================================================
# 场景一（期末突击）：Softmax_Attention_Backprop
# =====================================================================
SCENARIO_SOFTMAX_ATTENTION_BACKPROP = Scenario(
    scenario_id="Softmax_Attention_Backprop",
    title="Softmax Attention 梯度反向传播严密手推",
    category="期末突击",
    description="推导注意力机制的核心：Softmax 雅可比矩阵的严密偏导。直击学生最易卡壳的商法则求导与分母求和坍缩断裂。",
    atomic_operators={
        "OP_DENOM_SUM_COLLAPSE": OP_DENOM_SUM_COLLAPSE
    },
    steps=[
        LessonStep(
            step_id=1,
            prompt="【目标 1/3】设 S_i = e^{z_i} / ∑_{k=1}^K e^{z_k}。应用微积分商法则 (u/v)' = (u'v - uv') / v^2，写出 ∂S_i / ∂z_j 的展开分子第一项与第二项关系。",
            standard_solution="∂S_i/∂z_j = [ (∂e^{z_i}/∂z_j)·(∑_k e^{z_k}) - e^{z_i}·(∂(∑_k e^{z_k})/∂z_j) ] / (∑_k e^{z_k})^2",
            key_invariants=["商法则", "分母平方", "u'v - uv'"],
            common_faults={
                "chain_rule_lost": FaultType.SURFACE_CONFUSION,
                "slip_index": FaultType.SLIP
            },
            prerequisite_operator=None
        ),
        LessonStep(
            step_id=2,
            prompt="【目标 2/3 (关键断裂点)】计算商法则分子第二项中的关键导数：∂(∑_{k=1}^K e^{z_k}) / ∂z_j。求和号对其中单一自变量 z_j 求导后等于什么？",
            standard_solution="e^{z_j}",
            key_invariants=["e^{z_j}", "坍缩", "求和消失", "独立求导"],
            common_faults={
                "sum_remains": FaultType.PREREQUISITE_BROKEN,
                "zero_heuristic": FaultType.WRONG_HEURISTIC,
                "slip_k": FaultType.SLIP
            },
            prerequisite_operator=OP_DENOM_SUM_COLLAPSE
        ),
        LessonStep(
            step_id=3,
            prompt="【目标 3/3】代入坍缩结果并化简，分别给出 i == j (对角线) 与 i != j (非对角线) 时 ∂S_i/∂z_j 关于 S 的精简公式。",
            standard_solution="i==j: S_i(1 - S_i); i!=j: -S_i * S_j (合并写作 S_i(δ_ij - S_j))",
            key_invariants=["S_i(1-S_i)", "-S_i*S_j", "克罗内克δ", "雅可比矩阵"],
            common_faults={
                "sign_error": FaultType.SLIP,
                "missing_sj": FaultType.SURFACE_CONFUSION
            },
            prerequisite_operator=None
        )
    ]
)


# =====================================================================
# 场景二（项目防穿帮）：CUDA_Shared_Memory_Bank_Conflict
# =====================================================================
SCENARIO_CUDA_BANK_CONFLICT = Scenario(
    scenario_id="CUDA_Shared_Memory_Bank_Conflict",
    title="CUDA 共享内存 32-way Bank Conflict 根因透视与错位优化",
    category="项目防穿帮",
    description="深入 GPU 底层内存体系结构，解决二维矩阵转置与跨步长访问时的 32 路满冲突，手撕 Padding 规避算法。",
    atomic_operators={
        "OP_BANK_STRIDE_PADDING": OP_BANK_STRIDE_PADDING
    },
    steps=[
        LessonStep(
            step_id=1,
            prompt="【目标 1/3】在 CUDA Kernel 中声明了 `__shared__ float sData[32][32];`。Warp 中 32 个线程执行 `sData[threadIdx.x][0]` 读取同一列时，这 32 个地址映射到硬件 Shared Memory 的哪些 Bank？冲突度是几路？",
            standard_solution="全部映射到 Bank 0，产生 32-way (32路满) Bank Conflict，硬件执行被迫串行化为 32 个内存事务。",
            key_invariants=["Bank 0", "32-way", "串行化", "满冲突"],
            common_faults={
                "no_conflict_heuristic": FaultType.WRONG_HEURISTIC,
                "bank_number_slip": FaultType.SLIP
            },
            prerequisite_operator=None
        ),
        LessonStep(
            step_id=2,
            prompt="【目标 2/3 (关键断裂点)】为消除此冲突，最经典的零开销声明改法是什么？请给出改动后的数组声明代码，并说明核心物理思想。",
            standard_solution="__shared__ float sData[32][33]; 物理思想：每行增加 1 个元素的 Padding 错位填充，使每行的起始 Bank 错开 1 位。",
            key_invariants=["33", "Padding", "错位", "[32][33]"],
            common_faults={
                "pad_wrong_dim": FaultType.SURFACE_CONFUSION,
                "unaware_stride": FaultType.PREREQUISITE_BROKEN
            },
            prerequisite_operator=OP_BANK_STRIDE_PADDING
        ),
        LessonStep(
            step_id=3,
            prompt="【目标 3/3】改用 `sData[32][33]` 后，Warp 中线程 k 读取 `sData[k][0]` 时，其元素对应的 Bank 编号计算公式是什么？32 个线程的访问模式是否完全无冲突？",
            standard_solution="Bank ID = (k * 33 + 0) % 32 = k % 32 = k。线程 0~31 分别访问 Bank 0~31，实现 0 Bank Conflict 满带宽并行访问！",
            key_invariants=["k % 32", "无冲突", "Bank k", "满带宽"],
            common_faults={
                "modulo_math_error": FaultType.SLIP
            },
            prerequisite_operator=None
        )
    ]
)


ALL_SCENARIOS: Dict[str, Scenario] = {
    "1": SCENARIO_SOFTMAX_ATTENTION_BACKPROP,
    "2": SCENARIO_CUDA_BANK_CONFLICT,
    "softmax": SCENARIO_SOFTMAX_ATTENTION_BACKPROP,
    "cuda": SCENARIO_CUDA_BANK_CONFLICT,
    "Softmax_Attention_Backprop": SCENARIO_SOFTMAX_ATTENTION_BACKPROP,
    "CUDA_Shared_Memory_Bank_Conflict": SCENARIO_CUDA_BANK_CONFLICT,
}


def get_scenario(key: str) -> Optional[Scenario]:
    """获取指定场景"""
    return ALL_SCENARIOS.get(str(key).strip())
