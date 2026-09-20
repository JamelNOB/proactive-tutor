"""
ProActive-Tutor Storage Layer & Recovery Test Suite
验证在会话关闭、模拟崩溃重启后，调用栈帧与教学进度 100% 完整复原。
"""

import os
import sys
import tempfile
import time
import pytest

# 兼容加载核心数据模型与存储层
try:
    from core.models import StackFrame, AtomicOperator, FaultType
except ImportError:
    models_path = r"C:\Users\JamelNOB\.gemini\antigravity\scratch\proactive-tutor"
    if models_path not in sys.path:
        sys.path.insert(0, models_path)
    from core.models import StackFrame, AtomicOperator, FaultType

try:
    from core.storage import TutorStorage
except ImportError:
    from storage import TutorStorage


class TestStorageAndRecovery:
    """测试套件：验证 SQLite 持久化与崩溃/关闭恢复能力"""

    def setup_method(self):
        # 使用临时文件测试真实 SQLite 文件持久化行为
        self.temp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.db_path = self.temp_db.name
        self.temp_db.close()
        self.storage = TutorStorage(db_path=self.db_path)

    def teardown_method(self):
        if os.path.exists(self.db_path):
            try:
                os.remove(self.db_path)
            except Exception:
                pass

    def test_session_state_save_and_load(self):
        """测试基础 Session 进度的保存与加载"""
        session_id = "sess_test_001"
        self.storage.save_session_state(
            session_id=session_id,
            current_scenario="GRADUATION_DEFENSE_LLM",
            current_step_index=2,
            extra_state={"current_model": "llama-3-8b", "temperature": 0.2}
        )

        loaded = self.storage.load_session_state(session_id)
        assert loaded is not None
        assert loaded["session_id"] == session_id
        assert loaded["current_scenario"] == "GRADUATION_DEFENSE_LLM"
        assert loaded["current_step_index"] == 2
        assert loaded["extra_state"]["current_model"] == "llama-3-8b"
        assert loaded["call_stack"] == []

    def test_call_stack_push_pop_order(self):
        """测试调用栈帧的严格 LIFO (后进先出) 顺序及完整元数据"""
        session_id = "sess_stack_002"
        self.storage.save_session_state(session_id, "FINAL_EXAM_CALCULUS", 1)

        op1 = AtomicOperator(
            operator_id="OP_CHAIN_RULE",
            name="复合函数链式法则",
            concept_summary="外层导数乘以内层导数",
            micro_probe_question="(sin(x^2))' 的内层导数是多少？",
            expected_answer="2x",
            snapback_bridge="内层导数是 2x，直接代入原积分！"
        )
        frame1 = StackFrame(
            frame_id="frame_001",
            topic_name="Chain_Rule_Check",
            current_step=1,
            step_description="验证求导展开式",
            suspended_at=1000.0,
            atomic_operator=op1,
            timeout_seconds=20
        )

        op2 = AtomicOperator(
            operator_id="OP_POWER_RULE",
            name="幂函数求导",
            concept_summary="x^n 导数为 n*x^(n-1)",
            micro_probe_question="x^2 的导数是多少？",
            expected_answer="2x",
            snapback_bridge="正确，带入原式！"
        )
        frame2 = StackFrame(
            frame_id="frame_002",
            topic_name="Power_Rule_Check",
            current_step=1,
            step_description="验证多项式导数",
            suspended_at=1005.0,
            atomic_operator=op2,
            timeout_seconds=15
        )

        # 依次压入栈帧 1 与 2
        self.storage.push_frame_to_db(session_id, frame1)
        self.storage.push_frame_to_db(session_id, frame2)

        # peek 验证栈顶为 frame2
        peeked = self.storage.peek_frame_from_db(session_id)
        assert peeked is not None
        assert peeked.frame_id == "frame_002"
        assert peeked.atomic_operator.operator_id == "OP_POWER_RULE"

        # pop 弹出 frame2
        popped2 = self.storage.pop_frame_from_db(session_id)
        assert popped2 is not None
        assert popped2.frame_id == "frame_002"
        assert popped2.atomic_operator.operator_id == "OP_POWER_RULE"
        assert popped2.step_description == "验证多项式导数"

        # pop 弹出 frame1
        popped1 = self.storage.pop_frame_from_db(session_id)
        assert popped1 is not None
        assert popped1.frame_id == "frame_001"
        assert popped1.atomic_operator.operator_id == "OP_CHAIN_RULE"

        # 再次 pop 应该为空
        assert self.storage.pop_frame_from_db(session_id) is None

    def test_crash_recovery_100_percent(self):
        """
        核心考点：模拟系统崩溃/强行终止
        通过完全销毁当前 Storage 实例，重建新实例连到同一个 SQLite 文件，
        验证调用栈、知识点掌握度与步骤进度 100% 完整复原无损。
        """
        session_id = "sess_crash_003"
        self.storage.save_session_state(
            session_id=session_id,
            current_scenario="PROJECT_DEFENSE_KV_CACHE",
            current_step_index=3,
            extra_state={"user_level": "advanced", "interrupt_count": 2}
        )

        op = AtomicOperator(
            operator_id="OP_PAGED_ATTENTION",
            name="PagedAttention核心机制",
            concept_summary="将连续的 KV Cache 离散存储为虚拟分页",
            micro_probe_question="vLLM 是如何解决显存碎片的？",
            expected_answer="分页管理",
            snapback_bridge="正因虚拟内存分页，碎片率降至4%以下，继续看推导！"
        )
        original_frame = StackFrame(
            frame_id="frame_crash_01",
            topic_name="KV_Cache_Slicing",
            current_step=3,
            step_description="推导显存占用公式",
            suspended_at=time.time() - 5.0,
            atomic_operator=op,
            timeout_seconds=30
        )
        self.storage.push_frame_to_db(session_id, original_frame)

        # 记录掌握度
        self.storage.update_mastery(
            session_id=session_id,
            concept_id="KV_CACHE_MEM_CALC",
            mastery_score=0.45,
            fault_type=FaultType.PREREQUISITE_BROKEN,
            detail="忽略了 Batch Size 对 KV 缓存线性倍增的影响"
        )

        # --- 模拟崩溃与离线：销毁实例 ---
        del self.storage

        # --- 模拟系统重启：创建全新的 Storage 实例挂载数据库 ---
        restarted_storage = TutorStorage(db_path=self.db_path)
        recovered_state = restarted_storage.load_session_state(session_id)

        # 1. 验证会话元数据与进度 100% 复原
        assert recovered_state is not None
        assert recovered_state["session_id"] == session_id
        assert recovered_state["current_scenario"] == "PROJECT_DEFENSE_KV_CACHE"
        assert recovered_state["current_step_index"] == 3
        assert recovered_state["extra_state"]["user_level"] == "advanced"

        # 2. 验证调用栈帧 100% 复原（包含嵌套 AtomicOperator 字段）
        stack = recovered_state["call_stack"]
        assert len(stack) == 1
        rec_frame = stack[0]
        assert rec_frame.frame_id == "frame_crash_01"
        assert rec_frame.topic_name == "KV_Cache_Slicing"
        assert rec_frame.current_step == 3
        assert rec_frame.step_description == "推导显存占用公式"
        assert rec_frame.timeout_seconds == 30
        assert rec_frame.suspended_at == pytest.approx(original_frame.suspended_at, rel=1e-3)

        assert rec_frame.atomic_operator is not None
        assert rec_frame.atomic_operator.operator_id == "OP_PAGED_ATTENTION"
        assert rec_frame.atomic_operator.name == "PagedAttention核心机制"
        assert rec_frame.atomic_operator.micro_probe_question == "vLLM 是如何解决显存碎片的？"
        assert rec_frame.atomic_operator.expected_answer == "分页管理"
        assert rec_frame.atomic_operator.snapback_bridge == "正因虚拟内存分页，碎片率降至4%以下，继续看推导！"

        # 3. 验证掌握度历史数据完整复原
        mastery_list = restarted_storage.get_mastery_records(session_id)
        assert len(mastery_list) == 1
        rec_mastery = mastery_list[0]
        assert rec_mastery["concept_id"] == "KV_CACHE_MEM_CALC"
        assert rec_mastery["mastery_score"] == pytest.approx(0.45, rel=1e-3)
        assert rec_mastery["fault_type"] == "PREREQUISITE_BROKEN"
        assert rec_mastery["attempt_count"] == 1
        assert "Batch Size" in rec_mastery["detail"]

        # 4. 验证重启后依然能无缝弹出栈顶
        popped_after_restart = restarted_storage.pop_frame_from_db(session_id)
        assert popped_after_restart is not None
        assert popped_after_restart.frame_id == "frame_crash_01"
        assert restarted_storage.pop_frame_from_db(session_id) is None

    def test_mastery_records_update_and_accumulation(self):
        """测试掌握度多次学习记录的累计更新"""
        session_id = "sess_mastery_004"
        self.storage.update_mastery(
            session_id=session_id,
            concept_id="ATTENTION_FORMULA",
            mastery_score=0.3,
            fault_type=FaultType.SLIP,
            detail="缺少根号dk"
        )
        records = self.storage.get_mastery_records(session_id)
        assert len(records) == 1
        assert records[0]["attempt_count"] == 1
        assert records[0]["mastery_score"] == 0.3

        # 再次尝试提升掌握度
        self.storage.update_mastery(
            session_id=session_id,
            concept_id="ATTENTION_FORMULA",
            mastery_score=0.95,
            fault_type=None,
            detail="完整推导出标准 Softmax 缩放点积"
        )
        records_after = self.storage.get_mastery_records(session_id)
        assert len(records_after) == 1
        assert records_after[0]["attempt_count"] == 2
        assert records_after[0]["mastery_score"] == 0.95
        assert records_after[0]["fault_type"] is None
        assert "完整推导出" in records_after[0]["detail"]


if __name__ == "__main__":
    pytest.main(["-v", __file__])
