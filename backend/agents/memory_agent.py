import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from backend.agents.base_agent import BaseAgent
from backend.agents.tool import Tool
from backend.agents.skill import Skill

logger = logging.getLogger(__name__)


# ==================== 工具函数 ====================


def _save_to_db(table: str, data: Dict) -> Dict:
    """保存数据到数据库。

    Args:
        table: 表名 (content_history / hot_topics / hot_topic_trends / scheduled_task_runs)
        data: 要保存的数据（字典格式）
    """
    try:
        from backend.models.database import SessionLocal, ContentHistory, HotTopic, HotTopicTrend, ScheduledTaskRun

        table_map = {
            "content_history": ContentHistory,
            "hot_topics": HotTopic,
            "hot_topic_trends": HotTopicTrend,
            "scheduled_task_runs": ScheduledTaskRun,
        }

        model_class = table_map.get(table)
        if not model_class:
            return {"success": False, "error": f"未知表名: {table}"}

        db = SessionLocal()
        try:
            record = model_class(**data)
            db.add(record)
            db.commit()
            return {"success": True, "id": record.id}
        finally:
            db.close()
    except Exception as e:
        logger.error(f"数据库保存失败: {str(e)}")
        return {"success": False, "error": str(e)}


def _query_db(table: str, limit: int = 20, order_by: str = "id",
               descending: bool = True) -> List[Dict]:
    """从数据库查询记录。

    Args:
        table: 表名
        limit: 返回数量
        order_by: 排序字段
        descending: 是否降序
    """
    try:
        from backend.models.database import SessionLocal, ContentHistory, HotTopic, HotTopicTrend, ScheduledTaskRun

        table_map = {
            "content_history": ContentHistory,
            "hot_topics": HotTopic,
            "hot_topic_trends": HotTopicTrend,
            "scheduled_task_runs": ScheduledTaskRun,
        }

        model_class = table_map.get(table)
        if not model_class:
            return []

        db = SessionLocal()
        try:
            query = db.query(model_class)
            sort_col = getattr(model_class, order_by, model_class.id)
            if descending:
                query = query.order_by(sort_col.desc())
            else:
                query = query.order_by(sort_col.asc())

            results = []
            for row in query.limit(limit).all():
                record = {}
                for col in row.__table__.columns:
                    value = getattr(row, col.name)
                    if isinstance(value, datetime):
                        value = value.isoformat()
                    record[col.name] = value
                results.append(record)
            return results
        finally:
            db.close()
    except Exception as e:
        logger.error(f"数据库查询失败: {str(e)}")
        return []


# ==================== MemoryAgent ====================


class MemoryAgent(BaseAgent):
    """记忆管理型 Agent。

    角色: "档案管理员" — 管理所有 Agent 的短期和长期记忆
    特质: 存储层，不主动做事，被其他 Agent 调用
    策略: 提供存储/检索接口，让其他 Agent 能持久化知识

    这个 Agent 展示了：
      「Memory Pattern」
      Agent 系统需要记忆来保持上下文连贯性。
      短期记忆 = 当前任务的工作上下文
      长期记忆 = 跨任务的知识和经验
    """

    def __init__(self, name: str = "memory"):
        tools = [
            Tool.from_function(_save_to_db),
            Tool.from_function(_query_db),
        ]
        super().__init__(
            name=name,
            role="记忆管理员，负责存储和检索各类数据。"
                 "你可以保存记录到数据库，也可以从数据库查询历史数据。",
            tools=tools,
            llm_client=None,  # 纯工具型
        )

        self.register_skills([
            Skill(
                name="data_persistence",
                description="将数据持久化存储到数据库，支持 content_history / hot_topics / hot_topic_trends / scheduled_task_runs 四张表",
                tool_names=["save_to_db"],
                success_criteria="数据成功写入数据库并返回记录 ID",
            ),
            Skill(
                name="data_retrieval",
                description="从数据库查询历史记录，支持指定表名、排序方式和返回数量",
                tool_names=["query_db"],
                success_criteria="返回指定数量的格式化记录，日期字段自动转为 ISO 格式",
            ),
            Skill(
                name="working_memory",
                description="在内存中维护短期工作记忆，支持跨 Agent 共享当前任务的上下文信息",
                tool_names=[],
                success_criteria="记忆读写正确，Agent 间共享无冲突",
            ),
        ])

        # 短期工作记忆（内存中，Agent 间共享）
        self._working_memory: Dict[str, Any] = {}

    def remember(self, key: str, value: Any) -> None:
        """保存到短期工作记忆。"""
        self._working_memory[key] = value

    def recall(self, key: str, default: Any = None) -> Any:
        """从短期工作记忆读取。"""
        return self._working_memory.get(key, default)

    def forget(self, key: str) -> None:
        """从短期工作记忆删除。"""
        self._working_memory.pop(key, None)

    def clear_working_memory(self) -> None:
        """清空短期工作记忆。"""
        self._working_memory.clear()

    def get_working_memory_summary(self) -> Dict[str, Any]:
        """获取工作记忆摘要。"""
        return dict(self._working_memory)
