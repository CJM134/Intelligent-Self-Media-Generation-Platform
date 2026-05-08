import json
import logging
from typing import Any, Dict, List, Optional

from backend.agents.base_agent import BaseAgent, AgentThought, AgentTask, AgentResult
from backend.agents.tool import Tool
from backend.agents.skill import Skill

logger = logging.getLogger(__name__)


# ==================== CriticAgent ====================


class CriticAgent(BaseAgent):
    """质量审查型 Agent。

    角色: "质检员" — 专门审查其他 Agent 的输出质量
    特质: 纯 LLM 评估，不执行任何外部工具
    策略: 收到内容 → LLM 逐维度评分 → 返回改进建议

    这个 Agent 展示了：
      「Reflection Pattern（反思模式）」
      Agent 系统不仅要能做事，还要能评估自己做得好不好。
      CriticAgent 就是系统的"自我审视"能力。
    """

    def __init__(self, name: str = "critic",
                 llm_client=None, llm_model: str = "glm-4-plus"):
        super().__init__(
            name=name,
            role="内容质量审查员。你严格、客观，能从多个维度评估文案质量。",
            tools=[],  # CriticAgent 不需要工具
            llm_client=llm_client,
            llm_model=llm_model,
            max_steps=2,  # Critic 一步就够了
        )

        self.register_skills([
            Skill(
                name="quality_review",
                description="从5个维度（标题吸引力/平台适配度/内容信息量/互动引导力/情感共鸣）对文案进行1-10分评估，输出综合评分和 verdict（pass/minor_fixes/rewrite）",
                tool_names=[],
                success_criteria="输出包含各维度评分、综合评分、优点和改进建议的完整 JSON 评估报告",
            ),
            Skill(
                name="rewrite_guidance",
                description="针对未通过的文案，输出具体的、可操作的修改建议，每项建议指向文案中的具体问题",
                tool_names=[],
                success_criteria="改进建议具体到某句话或某个表达，而非泛泛而谈",
            ),
        ])

    def build_system_prompt(self, matched_skill=None) -> str:
        skills_desc = "\n".join([
            f"  * {s.name}: {s.description}"
            for s in self.skills.values()
        ])
        skill_hint = ""
        if matched_skill:
            skill_hint = f"\n当前任务最适合使用技能【{matched_skill.name}】来完成。\n"

        return f"""你是 {self.name}，你的角色是：{self.role}

        你掌握以下核心技能：
        {skills_desc}
        {skill_hint}
        你的工作流程：
        1. 收到文案内容
        2. 从以下维度评分（每项 1-10）：
        - 标题吸引力：是否引人注目，有点击欲望
        - 平台适配度：是否符合该平台的风格和用户习惯
        - 内容信息量：是否有实质内容，不是空话
        - 互动引导力：是否引导读者点赞/评论/转发
        - 情感共鸣：是否能引起读者情感共鸣
        3. 给出综合评分和具体的改进建议

        请严格按照以下 JSON 格式返回结果，不要包含其他内容：
        {{
            "overall_score": 7.5,
            "dimensions": [
                {{"name": "标题吸引力", "score": 8, "comment": "..."}},
                {{"name": "平台适配度", "score": 7, "comment": "..."}},
                {{"name": "内容信息量", "score": 6, "comment": "..."}},
                {{"name": "互动引导力", "score": 8, "comment": "..."}},
                {{"name": "情感共鸣", "score": 7, "comment": "..."}}
            ],
            "strengths": ["优点1", "优点2"],
            "improvements": ["改进1", "改进2"],
            "verdict": "pass | minor_fixes | rewrite"
        }}

        评分标准：
        - overall_score >= 7.0 → verdict: "pass"（通过）
        - overall_score >= 5.0 → verdict: "minor_fixes"（小改）
        - overall_score < 5.0  → verdict: "rewrite"（重写）
        """

    async def review(self, content: str, platform: str = "",
                     title: str = "") -> Dict[str, Any]:
        """对外提供的便捷审查方法（不走完整 ReAct 循环）。"""
        task = AgentTask(
            instruction=f"请审查以下{'【' + platform + '】' if platform else ''}文案{'《' + title + '》' if title else ''}：\n\n{content}",
        )
        result = await self.run(task)
        if result.success and result.output:
            try:
                return json.loads(result.output)
            except json.JSONDecodeError:
                try:
                    # 尝试从 markdown 代码块中提取
                    import re
                    match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', result.output)
                    if match:
                        return json.loads(match.group(1))
                except (json.JSONDecodeError, AttributeError):
                    pass
        return {
            "overall_score": 5.0,
            "dimensions": [],
            "strengths": [],
            "improvements": ["审查失败，未能生成有效评估"],
            "verdict": "rewrite",
        }
