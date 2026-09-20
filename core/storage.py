"""
proactive-tutor SQLite Storage Layer (零依赖持久化存储实现)
"""

import sqlite3
import time
import json
from typing import Optional, List, Dict, Any, Tuple
import os
import sys

# 兼容导入模型定义
try:
    from core.models import StackFrame, AtomicOperator, FaultType
except ImportError:
    models_path = r"C:\Users\JamelNOB\.gemini\antigravity\scratch\proactive-tutor"
    if models_path not in sys.path:
        sys.path.insert(0, models_path)
    from core.models import StackFrame, AtomicOperator, FaultType


class TutorStorage:
    """
    基于纯标准库 sqlite3 的轻量级持久化存储引擎
    支持：
    1. sessions 表：存储会话 ID、当前场景、当前步骤索引、更新时间
    2. call_stack_frames 表：存储挂起的调用栈帧（frame_id, session_id, stack_order, topic_name, current_step, step_description, operator_id, suspended_at, timeout, operator_json）
    3. mastery_records 表：存储学生知识点掌握度历史与错因标签
    """

    def __init__(self, db_path: str = "tutor_state.db"):
        self.db_path = db_path
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        # 启用外键约束
        conn.execute("PRAGMA foreign_keys = ON;")
        return conn

    def _init_db(self) -> None:
        """初始化数据表结构"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            # 1. sessions 表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS sessions (
                    session_id TEXT PRIMARY KEY,
                    current_scenario TEXT NOT NULL,
                    current_step_index INTEGER NOT NULL DEFAULT 0,
                    updated_at REAL NOT NULL,
                    extra_state_json TEXT
                )
            """)

            # 2. call_stack_frames 表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS call_stack_frames (
                    frame_id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    stack_order INTEGER NOT NULL,
                    topic_name TEXT NOT NULL,
                    current_step INTEGER NOT NULL,
                    step_description TEXT,
                    operator_id TEXT,
                    suspended_at REAL NOT NULL,
                    timeout INTEGER NOT NULL DEFAULT 25,
                    operator_json TEXT,
                    FOREIGN KEY (session_id) REFERENCES sessions(session_id) ON DELETE CASCADE
                )
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_stack_session_order 
                ON call_stack_frames(session_id, stack_order)
            """)

            # 3. mastery_records 表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS mastery_records (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    concept_id TEXT NOT NULL,
                    mastery_score REAL NOT NULL,
                    fault_type TEXT,
                    attempt_count INTEGER NOT NULL DEFAULT 1,
                    last_observed_at REAL NOT NULL,
                    detail TEXT,
                    FOREIGN KEY (session_id) REFERENCES sessions(session_id) ON DELETE CASCADE
                )
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_mastery_session_concept 
                ON mastery_records(session_id, concept_id)
            """)
            conn.commit()

    def save_session_state(
        self,
        session_id: str,
        current_scenario: str,
        current_step_index: int,
        extra_state: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        保存/更新会话基础进度
        """
        now = time.time()
        extra_json = json.dumps(extra_state, ensure_ascii=False) if extra_state else None
        with self._get_connection() as conn:
            conn.execute("""
                INSERT INTO sessions (session_id, current_scenario, current_step_index, updated_at, extra_state_json)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(session_id) DO UPDATE SET
                    current_scenario = excluded.current_scenario,
                    current_step_index = excluded.current_step_index,
                    updated_at = excluded.updated_at,
                    extra_state_json = excluded.extra_state_json
            """, (session_id, current_scenario, current_step_index, now, extra_json))
            conn.commit()

    def load_session_state(self, session_id: str) -> Optional[Dict[str, Any]]:
        """
        加载指定会话的状态（包括基础进度与所有调用栈帧）
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM sessions WHERE session_id = ?", (session_id,))
            session_row = cursor.fetchone()
            if not session_row:
                return None

            cursor.execute("""
                SELECT * FROM call_stack_frames 
                WHERE session_id = ? 
                ORDER BY stack_order ASC
            """, (session_id,))
            frame_rows = cursor.fetchall()

            frames: List[StackFrame] = []
            for row in frame_rows:
                op = None
                if row["operator_json"]:
                    try:
                        op_dict = json.loads(row["operator_json"])
                        op = AtomicOperator(**op_dict)
                    except Exception:
                        pass
                
                frame = StackFrame(
                    frame_id=row["frame_id"],
                    topic_name=row["topic_name"],
                    current_step=row["current_step"],
                    step_description=row["step_description"] or "",
                    suspended_at=row["suspended_at"],
                    atomic_operator=op,
                    timeout_seconds=row["timeout"]
                )
                frames.append(frame)

            extra_state = None
            if session_row["extra_state_json"]:
                try:
                    extra_state = json.loads(session_row["extra_state_json"])
                except Exception:
                    pass

            return {
                "session_id": session_row["session_id"],
                "current_scenario": session_row["current_scenario"],
                "current_step_index": session_row["current_step_index"],
                "updated_at": session_row["updated_at"],
                "extra_state": extra_state,
                "call_stack": frames
            }

    def push_frame_to_db(self, session_id: str, frame: StackFrame) -> None:
        """
        向数据库中的指定会话调用栈压入新帧
        自动维护 stack_order 顺序
        """
        # 确保 session 存在（若不存在则自动用占位兜底创建）
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT 1 FROM sessions WHERE session_id = ?", (session_id,))
            if not cursor.fetchone():
                now = time.time()
                cursor.execute("""
                    INSERT INTO sessions (session_id, current_scenario, current_step_index, updated_at)
                    VALUES (?, 'UNKNOWN', 0, ?)
                """, (session_id, now))

            # 查询当前最大的 stack_order
            cursor.execute("""
                SELECT MAX(stack_order) AS max_order FROM call_stack_frames WHERE session_id = ?
            """, (session_id,))
            row = cursor.fetchone()
            current_max = row["max_order"] if (row and row["max_order"] is not None) else -1
            next_order = current_max + 1

            op_id = frame.atomic_operator.operator_id if frame.atomic_operator else None
            op_json = None
            if frame.atomic_operator:
                op_json = json.dumps({
                    "operator_id": frame.atomic_operator.operator_id,
                    "name": frame.atomic_operator.name,
                    "concept_summary": frame.atomic_operator.concept_summary,
                    "micro_probe_question": frame.atomic_operator.micro_probe_question,
                    "expected_answer": frame.atomic_operator.expected_answer,
                    "snapback_bridge": frame.atomic_operator.snapback_bridge,
                }, ensure_ascii=False)

            cursor.execute("""
                INSERT OR REPLACE INTO call_stack_frames (
                    frame_id, session_id, stack_order, topic_name, current_step,
                    step_description, operator_id, suspended_at, timeout, operator_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                frame.frame_id,
                session_id,
                next_order,
                frame.topic_name,
                frame.current_step,
                frame.step_description,
                op_id,
                frame.suspended_at if frame.suspended_at is not None else time.time(),
                frame.timeout_seconds,
                op_json
            ))
            conn.commit()

    def pop_frame_from_db(self, session_id: str) -> Optional[StackFrame]:
        """
        从数据库中的指定会话调用栈弹出栈顶帧（stack_order 最大的一项）
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM call_stack_frames 
                WHERE session_id = ? 
                ORDER BY stack_order DESC 
                LIMIT 1
            """, (session_id,))
            row = cursor.fetchone()
            if not row:
                return None

            frame_id = row["frame_id"]
            cursor.execute("DELETE FROM call_stack_frames WHERE frame_id = ?", (frame_id,))
            conn.commit()

            op = None
            if row["operator_json"]:
                try:
                    op_dict = json.loads(row["operator_json"])
                    op = AtomicOperator(**op_dict)
                except Exception:
                    pass

            return StackFrame(
                frame_id=row["frame_id"],
                topic_name=row["topic_name"],
                current_step=row["current_step"],
                step_description=row["step_description"] or "",
                suspended_at=row["suspended_at"],
                atomic_operator=op,
                timeout_seconds=row["timeout"]
            )

    def peek_frame_from_db(self, session_id: str) -> Optional[StackFrame]:
        """
        查看栈顶帧（不弹出）
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM call_stack_frames 
                WHERE session_id = ? 
                ORDER BY stack_order DESC 
                LIMIT 1
            """, (session_id,))
            row = cursor.fetchone()
            if not row:
                return None

            op = None
            if row["operator_json"]:
                try:
                    op_dict = json.loads(row["operator_json"])
                    op = AtomicOperator(**op_dict)
                except Exception:
                    pass

            return StackFrame(
                frame_id=row["frame_id"],
                topic_name=row["topic_name"],
                current_step=row["current_step"],
                step_description=row["step_description"] or "",
                suspended_at=row["suspended_at"],
                atomic_operator=op,
                timeout_seconds=row["timeout"]
            )

    def update_mastery(
        self,
        session_id: str,
        concept_id: str,
        mastery_score: float,
        fault_type: Optional[Any] = None,
        detail: str = ""
    ) -> None:
        """
        记录或更新学生知识点掌握度与错因标签
        """
        fault_str = fault_type.value if hasattr(fault_type, "value") else (str(fault_type) if fault_type else None)
        now = time.time()

        with self._get_connection() as conn:
            cursor = conn.cursor()
            # 确保 session 存在
            cursor.execute("SELECT 1 FROM sessions WHERE session_id = ?", (session_id,))
            if not cursor.fetchone():
                cursor.execute("""
                    INSERT INTO sessions (session_id, current_scenario, current_step_index, updated_at)
                    VALUES (?, 'UNKNOWN', 0, ?)
                """, (session_id, now))

            # 查询现有记录
            cursor.execute("""
                SELECT id, attempt_count FROM mastery_records 
                WHERE session_id = ? AND concept_id = ?
            """, (session_id, concept_id))
            existing = cursor.fetchone()

            if existing:
                new_attempts = existing["attempt_count"] + 1
                cursor.execute("""
                    UPDATE mastery_records SET
                        mastery_score = ?,
                        fault_type = ?,
                        attempt_count = ?,
                        last_observed_at = ?,
                        detail = ?
                    WHERE id = ?
                """, (mastery_score, fault_str, new_attempts, now, detail, existing["id"]))
            else:
                cursor.execute("""
                    INSERT INTO mastery_records (
                        session_id, concept_id, mastery_score, fault_type, attempt_count, last_observed_at, detail
                    ) VALUES (?, ?, ?, ?, 1, ?, ?)
                """, (session_id, concept_id, mastery_score, fault_str, now, detail))
            conn.commit()

    def get_mastery_records(self, session_id: str) -> List[Dict[str, Any]]:
        """
        获取指定会话的所有知识点掌握度记录
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT concept_id, mastery_score, fault_type, attempt_count, last_observed_at, detail
                FROM mastery_records
                WHERE session_id = ?
                ORDER BY last_observed_at DESC
            """, (session_id,))
            return [dict(row) for row in cursor.fetchall()]
