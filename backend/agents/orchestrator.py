from __future__ import annotations
import json
import logging
import uuid
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from backend.agents.base_agent import BaseAgent, AgentResult, AgentTask
from backend.agents.skill import Skill
from backend.agents.collector_agent import CollectorAgent
from backend.agents.writer_agent import WriterAgent
from backend.agents.analyzer_agent import AnalyzerAgent
from backend.agents.critic_agent import CriticAgent
from backend.agents.memory_agent import MemoryAgent
from backend.agents.image_prompt_agent import ImagePromptAgent
from backend.agents.message_bus import MessageBus, MessageType

logger = logging.getLogger(__name__)


class PipelineStatus(str, Enum):
    IDLE = "idle"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"


class OrchestratorAgent(BaseAgent):
    """总协调者 Agent — 多 Agent 系统的"大脑"。

    角色: "项目经理" — 不亲自干活，但知道谁适合干什么，以及怎么串联
    核心能力:
      1. 任务拆解：把用户请求拆成子任务
      2. Agent 选择：为每个子任务找到合适的 Agent
      3. 状态追踪：跟踪整个管线的执行状态
      4. 异常恢复：子任务失败时重新分配或降级

    这个 Agent 展示了 Agent 系统中最重要的模式：
      「Orchestration Pattern（编排模式）」
      多个 Agent 不是杂乱地互相调用，而是由一个协调者统一调度。
      这是多 Agent 系统和"多个 Service 互相调用"的本质区别。
    """

    def __init__(self, name: str = "orchestrator",
                 llm_client=None, llm_model: str = "glm-4-plus"):
        # Orchestrator 不需要外部工具，它的"工具"是其他 Agent
        super().__init__(
            name=name,
            role="项目协调者，你负责拆解任务、分派给合适的专家、汇总结果。"
                 "你不直接执行具体工作，而是管理整个工作流。",
            tools=[],
            llm_client=llm_client,
            llm_model=llm_model,
            max_steps=30,
        )

        # 注册的子 Agent
        self._agents: Dict[str, BaseAgent] = {}

        self.register_skills([
            Skill(
                name="pipeline_orchestration",
                description="编排多 Agent 协作管线：拆解用户请求为子任务，按序分配给合适的 Agent 执行，汇总各步骤结果",
                tool_names=[],
                success_criteria="管线完整执行所有步骤，各 Agent 返回预期结果，发生异常时有降级策略",
            ),
            Skill(
                name="agent_discovery",
                description="根据任务类型自动发现并选择合适的 Agent，支持按名称查询和按能力匹配两种方式",
                tool_names=[],
                success_criteria="能返回系统中所有已注册 Agent 及其技能列表",
            ),
            Skill(
                name="error_recovery",
                description="当管子任务失败时自动执行降级策略：重新分配 Agent、跳过非关键步骤、或返回部分结果而非完全失败",
                tool_names=[],
                success_criteria="单步失败不影响已完成的步骤，返回详细的失败原因和部分结果",
            ),
        ])

        # 当前管线状态
        self._pipeline_status = PipelineStatus.IDLE
        self._pipeline_id = ""
        self._pipeline_log: List[Dict] = []

    # ==================== Agent 注册 ====================

    def register_agent(self, name: str, agent: BaseAgent) -> None:
        """注册一个子 Agent。"""
        self._agents[name] = agent
        logger.info(f"[Orchestrator] 注册子 Agent: {name} ({type(agent).__name__})")

    def get_agent(self, name: str) -> Optional[BaseAgent]:
        return self._agents.get(name)

    def list_all_skills(self) -> Dict[str, List[Dict[str, Any]]]:
        """汇总所有已注册 Agent 的核心技能。"""
        return {
            name: agent.list_skills()
            for name, agent in self._agents.items()
        }

    @property
    def available_agents(self) -> List[str]:
        return list(self._agents.keys())

    async def run_hot_topic_pipeline(self) -> Dict[str, Any]:
        self._pipeline_id = uuid.uuid4().hex[:12]
        self._pipeline_status = PipelineStatus.RUNNING
        self._pipeline_log = []
        trace_id = self._pipeline_id

        logger.info(f"[Orchestrator] 开始管线 [{trace_id}]")

        pipeline_result = {
            "pipeline_id": trace_id,
            "status": "running",
            "steps": [],
            "started_at": datetime.utcnow().isoformat(),
        }

        # ====== Step 1: 采集热点 ======
        step1_result = await self._run_step(
            step_name="采集热点",
            agent_name="collector",
            instruction="请从微博、抖音、小红书平台各采集10条热点话题",
            context={"limit": 10},
            trace_id=trace_id,
        )
        pipeline_result["steps"].append(step1_result)
        if not step1_result["success"]:
            return self._pipeline_failed(pipeline_result, "热点采集失败")

        # ====== Step 2: 分析趋势 ======
        step2_result = await self._run_step(
            step_name="分析趋势",
            agent_name="analyzer",
            instruction="分析当前热点趋势，找出热度上升最快的方向",
            context={"hours": 24},
            trace_id=trace_id,
        )
        pipeline_result["steps"].append(step2_result)

        # ====== Step 3: 生成文案 ======
        # 从上一步采集的热点中取第一条，生成文案
        hot_topics = step1_result.get("data", [])
        if hot_topics:
            first_topic = hot_topics[0]
            content_for_writer = f"{first_topic.get('title', '')}\n{first_topic.get('description', '')}"

            step3_result = await self._run_step(
                step_name="生成文案",
                agent_name="writer",
                instruction=f"请为以下热点话题生成各平台文案：\n{content_for_writer}",
                context={"topic": first_topic, "platforms": ["xiaohongshu", "douyin", "wechat", "weibo"]},
                trace_id=trace_id,
            )
            pipeline_result["steps"].append(step3_result)

        # ====== Step 4: 结果汇总 ======
        pipeline_result["status"] = PipelineStatus.SUCCESS
        pipeline_result["finished_at"] = datetime.utcnow().isoformat()

        self._pipeline_status = PipelineStatus.SUCCESS

        logger.info(f"[Orchestrator] ====== 管线完成 [{trace_id}] ======")

        return self._summarize_pipeline(pipeline_result)

    async def run_content_generation(self, content: str,
                                      platforms: List[str] = None) -> Dict[str, Any]:
        """生成管线：直接根据内容生成各平台文案。"""
        self._pipeline_id = uuid.uuid4().hex[:12]
        self._pipeline_status = PipelineStatus.RUNNING
        trace_id = self._pipeline_id

        if platforms is None:
            platforms = ["xiaohongshu", "douyin", "wechat", "weibo"]

        pipeline_result = {
            "pipeline_id": trace_id,
            "status": "running",
            "steps": [],
            "started_at": datetime.utcnow().isoformat(),
        }

        # 直接调用 WriterAgent
        writer = self._agents.get("writer")
        if not writer:
            return self._pipeline_failed(pipeline_result, "WriterAgent 未注册")

        if hasattr(writer, "generate_for_platforms"):
            results = await writer.generate_for_platforms(content, platforms)
            pipeline_result["steps"].append({
                "step": "生成文案",
                "success": True,
                "data": results,
            })
        else:
            step_result = await self._run_step(
                step_name="生成文案",
                agent_name="writer",
                instruction=f"请为以下内容生成各平台文案：\n{content}",
                context={"platforms": platforms},
                trace_id=trace_id,
            )
            pipeline_result["steps"].append(step_result)

        pipeline_result["status"] = PipelineStatus.SUCCESS
        pipeline_result["finished_at"] = datetime.utcnow().isoformat()
        self._pipeline_status = PipelineStatus.SUCCESS

        return self._summarize_pipeline(pipeline_result)

    async def run_analysis(self, topic: str) -> Dict[str, Any]:
        """分析管线：对某个话题进行深度分析。"""
        self._pipeline_id = uuid.uuid4().hex[:12]
        trace_id = self._pipeline_id

        pipeline_result = {
            "pipeline_id": trace_id,
            "status": "running",
            "steps": [],
            "started_at": datetime.utcnow().isoformat(),
        }

        step_result = await self._run_step(
            step_name="深度分析",
            agent_name="analyzer",
            instruction=f"对话题进行深度分析：{topic}",
            context={"topic": topic},
            trace_id=trace_id,
        )
        pipeline_result["steps"].append(step_result)
        pipeline_result["status"] = PipelineStatus.SUCCESS
        pipeline_result["finished_at"] = datetime.utcnow().isoformat()

        return self._summarize_pipeline(pipeline_result)

    # ==================== 内部方法 ====================

    async def _run_step(self, step_name: str, agent_name: str,
                         instruction: str, context: Dict[str, Any],
                         trace_id: str) -> Dict[str, Any]:
        """执行一个子任务步骤。"""
        agent = self._agents.get(agent_name)
        if not agent:
            return {
                "step": step_name,
                "success": False,
                "error": f"Agent [{agent_name}] 未注册",
            }

        logger.info(f"[Orchestrator] → {step_name}")

        task = AgentTask(
            instruction=instruction,
            context=context,
            trace_id=trace_id,
        )

        try:
            result: AgentResult = await agent.run(task)

            step_record = {
                "step": step_name,
                "agent": agent_name,
                "success": result.success,
                "duration_ms": result.total_duration_ms,
                "steps_count": len(result.steps),
            }

            if result.success:
                step_record["data"] = result.output
                logger.info(f"[Orchestrator] ✅ {step_name} 完成 - {result.total_duration_ms}ms")
            else:
                step_record["error"] = result.error
                logger.warning(f"[Orchestrator] ❌ {step_name} 失败: {result.error[:100]}")

            return step_record

        except Exception as e:
            logger.error(f"[Orchestrator] {step_name} 异常: {str(e)}")
            return {"step": step_name, "success": False, "error": str(e)}

    def _pipeline_failed(self, pipeline_result, reason):
        pipeline_result["status"] = PipelineStatus.FAILED
        pipeline_result["error"] = reason
        pipeline_result["finished_at"] = datetime.utcnow().isoformat()
        self._pipeline_status = PipelineStatus.FAILED
        logger.error(f"[Orchestrator] 管线失败: {reason}")
        return pipeline_result

    def _summarize_pipeline(self, pipeline_result: Dict[str, Any]) -> Dict[str, Any]:
        """汇总管线执行结果。"""
        steps = pipeline_result.get("steps", [])
        success_count = sum(1 for s in steps if s.get("success"))
        total_count = len(steps)

        pipeline_result["summary"] = {
            "total_steps": total_count,
            "successful_steps": success_count,
            "failed_steps": total_count - success_count,
        }

        # 从结果中提取关键数据
        generated_content = None
        for step in steps:
            if step.get("step") == "生成文案" and step.get("success"):
                generated_content = step.get("data")

        if generated_content:
            pipeline_result["generated_content"] = generated_content

        return pipeline_result

    # ==================== 管线状态 ====================

    def get_pipeline_status(self) -> Dict[str, Any]:
        """获取当前管线状态。"""
        return {
            "status": self._pipeline_status,
            "pipeline_id": self._pipeline_id,
            "agents": self.available_agents,
        }

    @property
    def is_running(self) -> bool:
        return self._pipeline_status == PipelineStatus.RUNNING

    # ==================== 快速搭建方法 ====================

    @classmethod
    def create_default(cls, llm_client=None,
                       llm_model: str = "glm-4-plus") -> "OrchestratorAgent":
        """创建带默认子 Agent 的 Orchestrator。

        这是最快捷的启动方式 — 一行代码创建完整的 Agent 系统。
        """
        orchestrator = cls(llm_client=llm_client, llm_model=llm_model)

        # 创建并注册所有子 Agent
        collector = CollectorAgent()
        orchestrator.register_agent("collector", collector)

        analyzer = AnalyzerAgent(llm_client=llm_client, llm_model=llm_model)
        orchestrator.register_agent("analyzer", analyzer)

        writer = WriterAgent(llm_client=llm_client, llm_model=llm_model)
        critic = CriticAgent(llm_client=llm_client, llm_model=llm_model)
        writer.set_critic(critic)
        orchestrator.register_agent("writer", writer)
        orchestrator.register_agent("critic", critic)

        image_prompt = ImagePromptAgent(llm_client=llm_client, llm_model=llm_model)
        orchestrator.register_agent("image_prompt", image_prompt)

        memory = MemoryAgent()
        orchestrator.register_agent("memory", memory)

        logger.info("[Orchestrator] 默认 Agent 系统搭建完成 - "
                    f"已注册 {len(orchestrator._agents)} 个 Agent")

        return orchestrator
