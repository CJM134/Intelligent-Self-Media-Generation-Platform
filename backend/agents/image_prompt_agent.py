import logging
from typing import Dict

from backend.agents.base_agent import BaseAgent
from backend.agents.skill import Skill

logger = logging.getLogger(__name__)


class ImagePromptAgent(BaseAgent):
    """文案转画面描述 Agent。

    角色: "视觉描述专家" — 理解文案内容，生成生动的画面描述供 AI 绘图
    核心能力: 分析多平台文案，提取视觉要素，输出纯画面描述

    与 ImageGenerator 的分工:
      - 本 Agent 负责「画什么」— 主体、场景、动作、氛围
      - ImageGenerator 负责「怎么画」— 风格、构图、光线、色彩参数
    """

    def __init__(self, name: str = "image_prompt",
                 llm_client=None, llm_model: str = "glm-4-plus"):
        super().__init__(
            name=name,
            role="视觉描述专家，擅长从文案中提取核心视觉要素，生成生动的画面描述",
            tools=[],
            llm_client=llm_client,
            llm_model=llm_model,
            max_steps=2,
        )

        self.register_skills([
            Skill(
                name="visual_description_generation",
                description="根据话题标题和多平台文案，提取核心视觉要素，生成 100-200 字的画面描述",
                tool_names=[],
                success_criteria="输出为 100-200 字的生动中文画面描述，不包含营销话术和技术参数",
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
你的工作要求：
1. 深入理解文案内容，提取核心视觉要素
2. 只描述画面本身（主体、场景、动作、氛围）
3. 不要包含营销话术、#标签、@用户、互动引导语
4. 不要包含技术参数（风格、构图、光线、色彩——这些由下游系统自动添加）
5. 输出 100-200 字的中文画面描述
6. 直接返回描述文字，不要额外说明
"""

    async def generate_prompt(self, title: str,
                               platform_contents: Dict[str, str]) -> str:
        """根据标题和各平台文案，生成生动的画面描述。

        Args:
            title: 热点标题
            platform_contents: 各平台文案 dict，key 为平台名，value 为文案

        Returns:
            纯文本画面描述（100-200 字），失败返回空字符串
        """
        if not platform_contents:
            return ""

        parts = [f"【{p}】{c}" for p, c in platform_contents.items() if c]
        if not parts:
            return ""
        all_content = "\n\n".join(parts)

        prompt = f"""根据以下话题标题和各平台文案，生成一段生动的画面描述（100-200字），用于 AI 绘图。

标题：{title}

各平台文案：
{all_content}

要求：
1. 深入理解文案内容，提取核心视觉要素：主体、场景、动作、氛围
2. 用生动形象的中文描述画面，100-200字
3. 只描述画面本身，不要包含营销话术、标签、互动引导
4. 不要包含技术参数（风格、构图、光线等——这些由下游系统自动添加）
5. 直接返回描述文字，不要加引号或其他格式"""

        messages = [
            {"role": "system", "content": self.build_system_prompt()},
            {"role": "user", "content": prompt},
        ]

        try:
            response = self.llm_client.chat.completions.create(
                model=self.llm_model,
                messages=messages,
                temperature=0.8,
            )
            result = response.choices[0].message.content.strip()
            logger.info(f"[ImagePromptAgent] 生成画面描述成功 - len={len(result)}")
            return result[:500]
        except Exception as e:
            logger.error(f"[ImagePromptAgent] LLM 调用失败: {str(e)}")
            return ""
