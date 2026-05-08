import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from backend.agents.base_agent import BaseAgent, AgentThought, AgentResult, AgentTask
from backend.agents.tool import Tool
from backend.agents.skill import Skill
from backend.services.hot_topic_fetcher import HotTopicFetcher

logger = logging.getLogger(__name__)


# ==================== 工具函数 ====================

def _create_fetcher(tianapi_key: Optional[str] = None):
    """创建热点抓取器。优先用真实 API，没有 key 就用 mock。"""
    return HotTopicFetcher(tianapi_key=tianapi_key, use_real_api=bool(tianapi_key))


def _fetch_weibo(key: str = "", limit: int = 10) -> List[Dict]:
    """抓取微博热搜榜。"""
    from backend.config import settings
    fetcher = _create_fetcher(settings.tianapi_key)
    return fetcher.fetch_hot_topics(platform="weibo", limit=limit)


def _fetch_douyin(key: str = "", limit: int = 10) -> List[Dict]:
    """抓取抖音热搜榜。"""
    from backend.config import settings
    fetcher = _create_fetcher(settings.tianapi_key)
    return fetcher.fetch_hot_topics(platform="douyin", limit=limit)


def _fetch_xiaohongshu(key: str = "", limit: int = 10) -> List[Dict]:
    """抓取小红书热搜榜（当前使用模拟数据）。"""
    from backend.config import settings
    fetcher = _create_fetcher(settings.tianapi_key)
    return fetcher.fetch_hot_topics(platform="xiaohongshu", limit=limit)


def _fetch_all(limit: int = 20) -> List[Dict]:
    """抓取所有平台的热点。"""
    from backend.config import settings
    fetcher = _create_fetcher(settings.tianapi_key)
    return fetcher.fetch_hot_topics(platform="all", limit=limit)


# ==================== CollectorAgent ====================


class CollectorAgent(BaseAgent):
    """数据采集型 Agent。

    角色: "情报员" — 从外部平台获取热点数据
    特质: 纯工具型，不需要 LLM 推理
    策略: 根据参数直接路由到对应平台，不经过 LLM 思考

    这个 Agent 展示了 Agent 设计中的一个重要概念：
      「Agent 不一定需要 LLM」
      判断标准是：这个 Agent 是否需要自己决定"做什么"？
      CollectorAgent 不需要，它的工作就是"执行采集"。
    """

    def __init__(self, name: str = "collector"):
        tools = [
            Tool.from_function(_fetch_weibo, name="fetch_weibo"),
            Tool.from_function(_fetch_douyin, name="fetch_douyin"),
            Tool.from_function(_fetch_xiaohongshu, name="fetch_xiaohongshu"),
            Tool.from_function(_fetch_all, name="fetch_all"),
        ]
        super().__init__(
            name=name,
            role="数据采集员，负责从各大社交媒体平台抓取热点话题。"
                 "你可以使用微博、抖音、小红书等多个平台的数据源。",
            tools=tools,
            llm_client=None,  # 不需要 LLM
        )
        self.register_skills([
            Skill(
                name="hot_topic_collection",
                description="从指定社交媒体平台抓取实时热点话题，支持微博、抖音、小红书等平台，可自定义返回数量",
                tool_names=["fetch_weibo", "fetch_douyin", "fetch_xiaohongshu", "fetch_all"],
                success_criteria="成功返回指定数量的热点话题，每条包含标题、热度、排名等核心信息",
            ),
            Skill(
                name="cross_platform_search",
                description="跨平台聚合搜索热点，一键获取所有平台的热点话题，用于全面了解当前舆论风向",
                tool_names=["fetch_all"],
                success_criteria="返回至少两个平台的热点数据，按热度排序",
            ),
        ])

    async def run(self, task: AgentTask) -> AgentResult:
        start_time = datetime.utcnow()
        messages = self._build_initial_messages(task)
        ##logger.info(f"解析消息：[{messages}] ")
        thought = self._simple_route(messages)
        ##logger.info(f"解析消息：[{messages}] ")

        try:
            output = await self._execute_tool(thought)
            result = AgentResult(
                task_id=task.id,
                success=True,
                output=output,
                skill_name=thought.skill_name,
            )
            logger.info(f"[{self.name}] 采集完成 - 获取 {len(output) if isinstance(output, list) else '?'} 条")
        except Exception as e:
            logger.error(f"[{self.name}] 采集失败: {str(e)}")
            result = AgentResult(
                task_id=task.id,
                success=False,
                error=str(e),
                skill_name=thought.skill_name if "thought" in dir() else None,
            )

        duration = (datetime.utcnow() - start_time).total_seconds() * 1000
        result.total_duration_ms = round(duration, 2)

        # 保存执行轨迹
        from backend.agents.trace_store import trace_store
        await trace_store.save(self.name, {
            "task_id": task.id,
            "instruction": task.instruction[:200],
            "skill_name": result.skill_name,
            "success": result.success,
            "error": result.error,
            "steps_count": 1,
            "total_duration_ms": result.total_duration_ms,
            "steps": [],
            "timestamp": datetime.utcnow().isoformat(),
        })

        return result

    def _simple_route(self, messages: List[Dict]) -> AgentThought:
        """没有 LLM 时的直接路由。

        优先匹配技能，再按关键词匹配平台。
        """
        instruction = ""
        for msg in reversed(messages):
            if msg["role"] == "user":
                instruction = msg.get("content", "")
                break

        platform = "all"
        if "weibo" in instruction or "微博" in instruction:
            platform = "weibo"
        elif "douyin" in instruction or "抖音" in instruction:
            platform = "douyin"
        elif "xiaohongshu" in instruction or "小红书" in instruction:
            platform = "xiaohongshu"

        limit = 10
        import re
        match = re.search(r'limit[=:]\s*(\d+)', instruction)
        if match:
            limit = int(match.group(1))

        skill_name = ""
        if platform == "all":
            matched = self.skills.get("cross_platform_search")
        else:
            matched = self.skills.get("hot_topic_collection")
        if matched:
            skill_name = matched.name

        return AgentThought(
            thought=f"使用技能 [{skill_name}] 采集平台: {platform}",
            action="use_tool",
            skill_name=skill_name or None,
            action_input={
                "tool_name": f"fetch_{platform}",
                "limit": limit,
            }
        )
