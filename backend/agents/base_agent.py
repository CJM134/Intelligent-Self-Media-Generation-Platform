from __future__ import annotations
import json
import logging
import uuid
from abc import ABC, abstractmethod
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple

from pydantic import BaseModel, Field

from backend.agents.tool import Tool
from backend.agents.skill import Skill
from backend.agents.message_bus import MessageBus, Message, MessageType

logger = logging.getLogger(__name__)


# ==================== 数据模型 ====================


class AgentThought(BaseModel):
    """Agent 一步思考的结果。

    这就是 ReAct 模式中的「Thought」：
    - thought: 推理过程（LLM 输出的思考文本）
    - action: 决定下一步做什么（use_tool / final_answer / wait_message）
    - action_input: 执行动作所需的参数
    - output: 如果是 final_answer，这里放最终输出
    """
    thought: str = Field(description="推理过程")
    action: str = Field(description="动作类型：use_tool | final_answer | wait_message")
    action_input: Dict[str, Any] = Field(default_factory=dict, description="动作参数")
    skill_name: Optional[str] = Field(default=None, description="当前使用的技能名称")
    output: Optional[str] = Field(default=None, description="最终答案（action=final_answer 时使用）")


class AgentTask(BaseModel):
    """Agent 接收到的任务。"""
    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    instruction: str = Field(description="任务指令")
    context: Dict[str, Any] = Field(default_factory=dict, description="额外上下文")
    trace_id: str = ""
    created_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())


class AgentStep(BaseModel):
    """Agent 执行的一步记录（用于追踪和调试）。"""
    thought: str
    action: str
    action_input: Dict[str, Any]
    skill_name: Optional[str] = None
    result: Optional[Any] = None
    error: Optional[str] = None
    duration_ms: Optional[float] = None


class AgentResult(BaseModel):
    """Agent 执行结果。"""
    task_id: str
    success: bool = False
    output: Optional[Any] = None
    error: Optional[str] = None
    skill_name: Optional[str] = None
    steps: List[AgentStep] = Field(default_factory=list)
    total_duration_ms: float = 0.0


# ==================== BaseAgent ====================


class BaseAgent(ABC):
    """所有 Agent 的基类。

    Agent ≠ Service 的关键区别：
      Service: 被别人调用，做固定的事
      Agent:  自己思考决定做什么，有自主性

    核心循环（ReAct）：
      run(task):
        while 没完成:
          think()     → "我现在该做什么？"（调用 LLM 推理）
          act()       → 执行工具或等消息
          observe()   → 看结果，更新上下文
        return final_answer

    Agent 的三个核心属性：
      name:        唯一标识
      role:        角色描述（对 LLM 的 system prompt）
      tools:       可用的工具集
    """

    def __init__(self,
                 name: str,
                 role: str,
                 tools: Optional[List[Tool]] = None,
                 llm_client: Optional[Any] = None,
                 llm_model: str = "glm-4-plus",
                 max_steps: int = 10):
        self.name = name
        self.role = role
        self.tools = {t.name: t for t in (tools or [])}
        self.tool_list = tools or []
        self.skills: Dict[str, Skill] = {}  # name → Skill
        self.llm_client = llm_client
        self.llm_model = llm_model
        self.max_steps = max_steps

        # 消息总线
        self.bus = MessageBus()
        self._steps: List[AgentStep] = []

        logger.info(f"[{self.name}] 初始化完成 - {len(self.tools)} 工具 - {llm_model}")

    # ==================== 注册工具 ====================

    def register_tool(self, tool: Tool) -> None:
        """注册一个工具。"""
        self.tools[tool.name] = tool
        self.tool_list.append(tool)
        logger.info(f"[{self.name}] 注册工具: {tool.name}")

    def register_tools(self, tools: List[Tool]) -> None:
        """批量注册工具。"""
        for tool in tools:
            self.register_tool(tool)

    # ==================== 技能管理 ====================

    def register_skill(self, skill: Skill) -> None:
        """注册一个技能。"""
        self.skills[skill.name] = skill
        logger.info(f"[{self.name}] 注册技能: {skill.name}")

    def register_skills(self, skills: List[Skill]) -> None:
        """批量注册技能。"""
        for skill in skills:
            self.register_skill(skill)

    def get_skill(self, name: str) -> Optional[Skill]:
        """按名称获取技能。"""
        return self.skills.get(name)

    def list_skills(self) -> List[Dict[str, Any]]:
        """列出所有已注册技能（含详细信息）。"""
        return [
            {
                "name": s.name,
                "description": s.description,
                "tool_names": s.tool_names,
                "success_criteria": s.success_criteria,
            }
            for s in self.skills.values()
        ]

    # ==================== 技能匹配与执行 ====================

    def _match_skill(self, instruction: str) -> Optional[Skill]:
        """根据任务指令匹配最合适的技能。

        遍历所有注册的技能，检查指令是否命中技能的描述关键字。
        子类可以重写这个方法来提供更精确的匹配逻辑。
        """
        if not self.skills:
            return None
        for skill in self.skills.values():
            desc_keywords = set(skill.description.replace("，", " ").replace("。", " ").split())
            inst_lower = instruction.lower()
            # 至少命中 2 个关键字或技能名直接出现在指令中
            if skill.name.lower() in inst_lower:
                return skill
            matched = sum(1 for kw in desc_keywords if kw in inst_lower and len(kw) > 1)
            if matched >= 2:
                return skill
        return None

    async def execute_skill(self, skill_name: str, **kwargs) -> Any:
        """按技能名直接执行（绕过 ReAct 循环，适用于已知技能）。

        Args:
            skill_name: 技能名称
            **kwargs: 传递给工具的参数

        Returns:
            工具执行结果

        Raises:
            ValueError: 技能不存在
        """
        skill = self.skills.get(skill_name)
        if not skill:
            raise ValueError(f"技能 [{skill_name}] 未注册。可用技能: {list(self.skills.keys())}")

        if not skill.tool_names:
            # 纯 LLM 技能（如 Critic），走 ReAct
            return await self.run(AgentTask(
                instruction=kwargs.get("instruction", f"请使用技能 {skill_name}"),
                context=kwargs,
            ))

        # 调用技能的默认工具
        tool_name = skill.tool_names[0]
        tool = self.tools.get(tool_name)
        if not tool:
            raise ValueError(f"技能 [{skill_name}] 所需的工具 [{tool_name}] 未注册")

        logger.info(f"[{self.name}] 执行技能: {skill_name} → 工具: {tool_name}")
        return await tool.execute(**kwargs)

    # ==================== 核心 ReAct 循环 ====================

    async def run(self, task: AgentTask) -> AgentResult:
        """Agent 的主入口：执行 ReAct 循环直到得到最终答案或出错。

        流程：
        1. 构造初始 messages（system_prompt + task）
        2. 循环：
           a. think()  → LLM 推理，决定下一步
           b. 如果是 final_answer → 结束，返回结果
           c. 如果是 use_tool    → 执行工具，观察结果
           d. 如果是 wait_message → 等别的 Agent 发消息
        3. 记录所有步骤到 AgentResult
        """
        logger.info(f"[{self.name}] ====== 开始执行 ======")

        start_time = datetime.utcnow()
        self._steps = []

        # 匹配技能：根据指令找到最合适的技能
        matched_skill = self._match_skill(task.instruction)
        if matched_skill:
            logger.info(f"[{self.name}] 匹配技能: {matched_skill.name}")

        # 构造对话上下文（技能信息注入 system prompt）
        messages = self._build_initial_messages(task, matched_skill)

        result = AgentResult(task_id=task.id, skill_name=matched_skill.name if matched_skill else None)

        try:
            for step_idx in range(self.max_steps):
                logger.info(f"[{self.name}] Step {step_idx + 1}/{self.max_steps}")

                # ====== THINK ======
                thought = await self._think(messages)
                step_record = AgentStep(
                    thought=thought.thought,
                    action=thought.action,
                    action_input=thought.action_input,
                )

                # ====== 情况 1: 最终答案 ======
                if thought.action == "final_answer":
                    step_record.result = thought.output
                    self._steps.append(step_record)
                    result.success = True
                    result.output = thought.output
                    break

                # ====== 情况 2: 使用工具 ======
                elif thought.action == "use_tool":
                    tool_result = await self._execute_tool(thought)
                    step_record.result = tool_result
                    self._steps.append(step_record)

                    # 把观察结果放回消息列表
                    messages.append({
                        "role": "user",
                        "content": f"工具 [{thought.action_input.get('tool_name', '?')}] 返回结果:\n{json.dumps(tool_result, ensure_ascii=False, default=str)[:2000]}"
                    })

                # ====== 情况 3: 等待消息 ======
                elif thought.action == "wait_message":
                    step_record.result = "等待其他 Agent 消息..."
                    self._steps.append(step_record)
                    # 阻塞等待消息
                    msg = await self._wait_for_message()
                    if msg:
                        messages.append({
                            "role": "user",
                            "content": f"收到来自 [{msg.sender}] 的消息 ({msg.msg_type.value}):\n{json.dumps(msg.payload, ensure_ascii=False, default=str)[:2000]}"
                        })
                    else:
                        messages.append({
                            "role": "user",
                            "content": "等待超时，未收到任何消息"
                        })

                # ====== 情况 4: 未知动作 ======
                else:
                    error_msg = f"未知动作: {thought.action}"
                    step_record.error = error_msg
                    self._steps.append(step_record)
                    result.success = False
                    result.error = error_msg
                    break

            else:
                # 到达 max_steps 仍未结束
                result.success = False
                result.error = f"达到最大步数限制 ({self.max_steps})"

        except Exception as e:
            logger.error(f"[{self.name}] 执行出错: {str(e)}", exc_info=True)
            result.success = False
            result.error = str(e)

        # 计算耗时
        duration = (datetime.utcnow() - start_time).total_seconds() * 1000
        result.total_duration_ms = round(duration, 2)
        result.steps = self._steps

        status = "成功" if result.success else "失败"
        logger.info(f"[{self.name}] ====== 任务{status} ====== "
                     f"- 步数: {len(self._steps)} - 耗时: {result.total_duration_ms}ms")
        
        ##存入TraceStore
        from backend.agents.trace_store import TraceStore
        trace_store = TraceStore()
        ##先封装
        trace={
            "task_id": task.id,
            "instruction": task.instruction[:200],
            "skill_name": result.skill_name,
            "success": result.success,
            "error": result.error,
            "steps_count": len(result.steps),
            "total_duration_ms": result.total_duration_ms,
            "steps": [s.model_dump() for s in result.steps],
            "timestamp": datetime.utcnow().isoformat(),
        }            
        trace_store.save(self.name, trace)
        
        return result

    # ==================== 核心抽象方法 ====================

    def build_system_prompt(self, matched_skill: Optional[Skill] = None) -> str:
        """构建 Agent 的 system prompt。

        Agent 通过这个 prompt 理解：
        - 自己的角色
        - 掌握哪些技能
        - 可用哪些工具
        - 能做什么不能做什么

        Args:
            matched_skill: 当前任务匹配到的技能（如果有），用于生成更精准的 prompt
        """
        # 按技能组织工具
        if self.skills:
            skills_desc_lines = []
            for s in self.skills.values():
                skill_tools = [f"      - {tn}: {self.tools[tn].description}"
                               for tn in s.tool_names if tn in self.tools]
                skill_block = f"  * {s.name}: {s.description}"
                if skill_tools:
                    skill_block += "\n    所需工具:\n" + "\n".join(skill_tools)
                skills_desc_lines.append(skill_block)
            skills_desc = "\n".join(skills_desc_lines)
        else:
            skills_desc = "  (当前没有注册特定技能)"

        # 未归入技能的剩余工具
        all_skilled_tools = set(tn for s in self.skills.values() for tn in s.tool_names)
        extra_tools = [t for t in self.tool_list if t.name not in all_skilled_tools]
        extra_tools_desc = "\n".join([
            f"  - {t.name}: {t.description}"
            for t in extra_tools
        ]) if extra_tools else ""

        # 如果命中了特定技能，增加提示
        skill_hint = ""
        if matched_skill:
            skill_tools_hint = "、".join(matched_skill.tool_names) if matched_skill.tool_names else "无需工具"
            skill_hint = f"\n当前任务最适合使用技能【{matched_skill.name}】来完成，相关工具: {skill_tools_hint}\n"

        prompt = f"""你是 {self.name}，你的角色是：{self.role}

        你掌握以下核心技能：
        {skills_desc}
        {extra_tools_desc}
        {skill_hint}
        请严格按照以下格式思考每一步：

        思考过程：<你的推理>
        动作：use_tool | final_answer | wait_message
        动作参数：<JSON 格式的工具参数>
        最终输出：<如果是 final_answer，这里放答案>

        注意：
        - use_tool: 当你需要调用工具获取信息或执行操作时
        - final_answer: 当你已经完成任务，准备好输出最终结果时
        - wait_message: 当你需要等待其他 Agent 发送消息时
        - 不要编造工具名称，只能使用上面列出的工具
        """
        return prompt

    # ==================== 内部方法 ====================

    def _build_initial_messages(self, task: AgentTask,
                                 matched_skill: Optional[Skill] = None) -> List[Dict]:
        """构造初始对话消息。"""
        return [
            {"role": "system", "content": self.build_system_prompt(matched_skill)},
            {"role": "user", "content": f"任务：{task.instruction}\n\n上下文信息：{json.dumps(task.context, ensure_ascii=False, default=str)}"}
        ]

    async def _think(self, messages: List[Dict]) -> AgentThought:
        """LLM 推理：给定对话上下文，决定下一步做什么。

        子类可以重写这个方法来实现不同的推理策略：
        - CollectorAgent: 不需要 LLM，直接返回 use_tool
        - CriticAgent: 不需要工具，直接返回 final_answer
        - WriterAgent: 需要 LLM + Critic 的反思循环
        """
        if not self.llm_client:
            # 没有 LLM 的 Agent（如 CollectorAgent），由子类实现简单路由
            return self._simple_route(messages)

        return await self._llm_think(messages)

    async def _llm_think(self, messages: List[Dict]) -> AgentThought:
        """默认的 LLM 推理实现。"""
        try:
            response = self.llm_client.chat.completions.create(
                model=self.llm_model,
                messages=messages,
                temperature=0.7,
            )
            content = response.choices[0].message.content
            return self._parse_thought(content)
        except Exception as e:
            logger.error(f"[{self.name}] LLM 推理失败: {str(e)}")
            return AgentThought(
                thought=f"LLM 调用失败: {str(e)}",
                action="final_answer",
                action_input={},
                output=f"LLM 推理出错: {str(e)}"
            )

    def _parse_thought(self, content: str) -> AgentThought:
        """从 LLM 输出文本中解析出 AgentThought。"""
        lines = content.strip().split("\n")

        thought = ""
        action = "final_answer"
        action_input = {}
        output = content  # 默认把全部输出当 final_answer

        for i, line in enumerate(lines):
            if line.startswith("思考过程：") or line.startswith("思考："):
                thought = line.split("：", 1)[1] if "：" in line else line
            elif line.startswith("动作："):
                action_str = line.split("：", 1)[1] if "：" in line else ""
                action_str = action_str.strip().lower()
                if action_str in ("use_tool", "final_answer", "wait_message"):
                    action = action_str
            elif line.startswith("动作参数：") or line.startswith("参数："):
                param_str = line.split("：", 1)[1] if "：" in line else "{}"
                try:
                    action_input = json.loads(param_str)
                except json.JSONDecodeError:
                    action_input = {"raw": param_str}
            elif line.startswith("最终输出：") or line.startswith("答案："):
                output = line.split("：", 1)[1] if "：" in line else ""

        # 如果解析出的 action_input 里有 tool_name，放到顶层
        if "tool_name" in action_input:
            pass  # 已经是标准格式

        return AgentThought(
            thought=thought or f"执行动作: {action}",
            action=action,
            action_input=action_input,
            output=output if action == "final_answer" else None,
        )

    async def _execute_tool(self, thought: AgentThought) -> Any:
        """执行工具并返回结果。

        支持两种工具调用格式：
        1. action_input = {"tool_name": "...", ...args}
        2. action_input = {...} (直接传参，由 Agent 自行决定调用哪个工具)
        """
        tool_name = thought.action_input.get("tool_name")
        tool_args = {k: v for k, v in thought.action_input.items() if k != "tool_name"}

        if not tool_name:
            # 没指定 tool_name → 尝试用第一个工具
            if self.tool_list:
                tool_name = self.tool_list[0].name
                tool_args = thought.action_input
            else:
                raise ValueError("没有指定工具名，且 Agent 没有注册任何工具")

        if tool_name not in self.tools:
            raise ValueError(f"工具 [{tool_name}] 未注册。可用工具: {list(self.tools.keys())}")

        tool = self.tools[tool_name]
        step_start = datetime.utcnow()

        try:
            result = await tool.execute(**tool_args)
            duration = (datetime.utcnow() - step_start).total_seconds() * 1000
            logger.info(f"[{self.name}] 工具 [{tool.name}] 完成 - 耗时: {duration:.0f}ms")
            return result
        except Exception as e:
            logger.error(f"[{self.name}] 工具 [{tool.name}] 失败: {str(e)}")
            raise

    async def _wait_for_message(self, timeout: float = 60.0) -> Optional[Message]:
        """等待其他 Agent 发来的消息。"""
        logger.info(f"[{self.name}] 等待消息...")
        return await self.bus.wait_for_message(self.name, timeout=timeout)

    def _simple_route(self, messages: List[Dict]) -> AgentThought:
        """没有 LLM 时用的简单路由（子类可重写）。"""
        return AgentThought(
            thought="没有 LLM 客户端，直接执行第一个工具",
            action="use_tool",
            action_input={"tool_name": self.tool_list[0].name if self.tool_list else ""},
        )

    def to_json(self) -> Dict[str, Any]:
        """Agent 的元信息。"""
        return {
            "name": self.name,
            "role": self.role,
            "skills": list(self.skills.keys()),
            "skill_details": self.list_skills(),
            "tools": [t.name for t in self.tool_list],
            "model": self.llm_model,
            "max_steps": self.max_steps,
        }
