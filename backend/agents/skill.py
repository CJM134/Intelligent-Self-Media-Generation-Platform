from __future__ import annotations
import logging
from typing import Any, Dict, List, Optional, Callable

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class Skill(BaseModel):
    """技能是 Agent 能力的「命名单元」。

    相比 Tool（原子操作），Skill 是更高层次的抽象：
    - 一个 Skill 可能包含多个 Tool
    - 一个 Skill 有 Prompt 模板，指导 LLM 如何完成这个任务
    - 一个 Skill 有成功标准，用于 Critic 评估

    类比：
      Tool  = 一把螺丝刀
      Skill = 会修水管（需要扳手、生料带、水管胶多个工具）
    """
    name: str = Field(description="技能名称，唯一标识")
    description: str = Field(description="技能描述——用一句话说清「这个技能能干什么」")
    tool_names: List[str] = Field(
        default_factory=list,
        description="该技能所需的工具名列表（引用 Agent 已注册的工具）"
    )
    prompt_template: str = Field(
        default="",
        description="技能专用 prompt 模板，指导 LLM 如何使用这个技能完成任务"
    )
    success_criteria: str = Field(
        default="",
        description="成功标准——什么样的输出算是「这个技能用好了」"
    )

    class Config:
        frozen = True

    def to_llm_description(self) -> str:
        """转成 LLM 可读的技能描述文本。"""
        desc = f"【{self.name}】{self.description}"
        if self.tool_names:
            desc += f"\n  所需工具: {', '.join(self.tool_names)}"
        return desc
