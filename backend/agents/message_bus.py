from __future__ import annotations
import asyncio
import logging
import uuid
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class MessageType(str, Enum):
    """系统中所有 Agent 间消息类型的枚举。

    定义消息类型 = 定义 Agent 之间的「协议」。
    新增协作场景时，先在这里加一种消息类型。
    """
    # 数据采集类
    FETCH_HOT_TOPICS = "fetch_hot_topics"
    FETCH_COMPLETED = "fetch_completed"

    # 分析类
    ANALYZE_TOPIC = "analyze_topic"
    ANALYSIS_COMPLETED = "analysis_completed"
    PREDICT_VIRAL = "predict_viral"
    PREDICTION_COMPLETED = "prediction_completed"

    # 内容生成类
    GENERATE_CONTENT = "generate_content"
    CONTENT_GENERATED = "content_generated"

    # 质量审查类
    REVIEW_CONTENT = "review_content"
    REVIEW_COMPLETED = "review_completed"
    RETRY_GENERATION = "retry_generation"

    # 记忆管理类
    SAVE_MEMORY = "save_memory"
    QUERY_MEMORY = "query_memory"
    MEMORY_RESULT = "memory_result"

    # 调度与控制
    TASK_DELEGATE = "task_delegate"
    TASK_COMPLETED = "task_completed"
    TASK_FAILED = "task_failed"
    STATUS_UPDATE = "status_update"
    AGENT_ERROR = "agent_error"


class Message(BaseModel):
    """Agent 间通信的基本单位。"""
    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:8])
    msg_type: MessageType
    sender: str
    recipient: Optional[str] = None  # None = broadcast
    payload: Dict[str, Any] = Field(default_factory=dict)
    trace_id: str = ""  # 追踪一次完整的任务链
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat())


class MessageBus:
    """Agent 之间的消息总线（单例模式）。

    核心设计：
    - 发布/订阅模式：Agent 注册自己关心的消息类型
    - 点对点 + 广播：可发给指定 Agent，也可全广播
    - 异步：所有消息处理都是 async
    - 追踪：trace_id 串起一次完整任务的所有消息

    使用示例：
        bus = MessageBus()
        bus.register("writer", handle_writer_message)
        await bus.send("orchestrator", "writer", MessageType.GENERATE_CONTENT, {...})
    """

    _instance: Optional["MessageBus"] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        # subscriber: {agent_name: callback}
        self._subscribers: Dict[str, Callable] = {}
        # mailbox: {agent_name: [Message]}
        self._mailboxes: Dict[str, List[Message]] = {}
        # message history（用于调试和追踪）
        self._history: List[Message] = []
        self._lock = asyncio.Lock()
        logger.info("[MessageBus] 消息总线初始化完成")

    # ==================== 注册 ====================

    def register(self, agent_name: str, callback: Callable) -> None:
        """注册一个 Agent 到总线。Agent 停止时需注销。"""
        self._subscribers[agent_name] = callback
        self._mailboxes[agent_name] = []
        logger.info(f"[MessageBus] Agent [{agent_name}] 已注册")

    def unregister(self, agent_name: str) -> None:
        """从总线注销一个 Agent。"""
        self._subscribers.pop(agent_name, None)
        self._mailboxes.pop(agent_name, None)
        logger.info(f"[MessageBus] Agent [{agent_name}] 已注销")

    # ==================== 发送 ====================

    async def send(self, sender: str, recipient: str,
                   msg_type: MessageType,
                   payload: Dict[str, Any] = None,
                   trace_id: str = "") -> None:
        """点对点发送消息给指定 Agent。"""
        msg = Message(
            msg_type=msg_type,
            sender=sender,
            recipient=recipient,
            payload=payload or {},
            trace_id=trace_id,
        )
        async with self._lock:
            self._history.append(msg)
            # 放入目标 Agent 的邮箱
            if recipient in self._mailboxes:
                self._mailboxes[recipient].append(msg)
            else:
                logger.warning(f"[MessageBus] 目标 Agent [{recipient}] 未注册，消息丢弃")

        logger.debug(f"[MessageBus] {sender} → {recipient}: {msg_type.value}")

        # 如果目标在线，立即触发处理
        if recipient in self._subscribers:
            await self._subscribers[recipient](msg)

    async def broadcast(self, sender: str,
                        msg_type: MessageType,
                        payload: Dict[str, Any] = None,
                        trace_id: str = "") -> None:
        """广播消息给所有注册的 Agent。"""
        msg = Message(
            msg_type=msg_type,
            sender=sender,
            recipient=None,
            payload=payload or {},
            trace_id=trace_id,
        )
        async with self._lock:
            self._history.append(msg)

        logger.debug(f"[MessageBus] {sender} → *广播*: {msg_type.value}")

        # 通知所有在线 Agent
        for agent_name, callback in self._subscribers.items():
            if agent_name != sender:
                # 每个 Agent 收到自己的副本
                msg_copy = msg.model_copy()
                msg_copy.recipient = agent_name
                async with self._lock:
                    self._mailboxes[agent_name].append(msg_copy)
                await callback(msg_copy)

    # ==================== 接收 ====================

    async def wait_for_message(self, agent_name: str,
                                msg_type: Optional[MessageType] = None,
                                timeout: float = 30.0) -> Optional[Message]:
        """等待一条发给指定 Agent 的消息（阻塞，可用于 Agent 主动等回复）。"""
        start = datetime.utcnow()
        while (datetime.utcnow() - start).total_seconds() < timeout:
            async with self._lock:
                mailbox = self._mailboxes.get(agent_name, [])
                for i, msg in enumerate(mailbox):
                    if msg_type is None or msg.msg_type == msg_type:
                        return mailbox.pop(i)
            await asyncio.sleep(0.1)
        return None

    def get_history(self, limit: int = 50) -> List[Message]:
        """获取最近的消息历史（调试用）。"""
        return self._history[-limit:]

    def clear_mailbox(self, agent_name: str) -> None:
        """清空 Agent 的邮箱。"""
        if agent_name in self._mailboxes:
            self._mailboxes[agent_name] = []
