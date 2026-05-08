import json
import logging
import os
import re
from typing import Any, Dict, List, Optional

from backend.agents.base_agent import BaseAgent, AgentTask, AgentResult
from backend.agents.tool import Tool
from backend.agents.skill import Skill
from backend.agents.critic_agent import CriticAgent

logger = logging.getLogger(__name__)


# ==================== 工具函数 ====================


def load_platform_prompt(platform: str) -> str:
    """加载平台文案模板。"""
    base_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "prompts")
    prompt_file = os.path.join(base_dir, f"{platform}.txt")
    if os.path.exists(prompt_file):
        with open(prompt_file, 'r', encoding='utf-8') as f:
            return f.read()
    return f"请将以下内容改写为适合{platform}的文案"


# ==================== WriterAgent ====================


class WriterAgent(BaseAgent):
    """内容生成型 Agent。

    角色: "文案写手" — 根据输入生成适配各平台的营销文案
    特质: 强 LLM 依赖 + Critic 反馈闭环

    Optimized: 一次 LLM 调用生成所有平台文案，一次 Critic 审查全部。
    相比逐平台串行生成，LLM 调用量减少约 75%。
    """

    def __init__(self, name: str = "writer",
                 llm_client=None, llm_model: str = "glm-4-plus"):
        tools = [
            Tool.from_function(load_platform_prompt, name="load_platform_prompt"),
        ]
        super().__init__(
            name=name,
            role="新媒体文案写手，擅长为不同社交媒体平台创作适配的文案。"
                 "你熟悉小红书、抖音、公众号、微博等平台的风格特点。",
            tools=tools,
            llm_client=llm_client,
            llm_model=llm_model,
            max_steps=15,
        )

        self._critic: Optional["CriticAgent"] = None

        self.register_skills([
            Skill(
                name="multi_platform_generation",
                description="为同一份内容批量生成适配小红书、抖音、公众号、微博四个平台的文案，一次调用产出全部平台版本",
                tool_names=["load_platform_prompt"],
                success_criteria="返回包含全部4个平台文案的完整 JSON，每个平台的文案风格符合其平台特点",
            ),
            Skill(
                name="content_rewrite",
                description="根据 CriticAgent 的审稿意见，对已生成的文案进行针对性修改和优化，保留原有结构同时改进缺陷",
                tool_names=["load_platform_prompt"],
                success_criteria="修改后的文案评分不低于原始版本，审稿意见中提出的改进点全部得到解决",
            ),
            Skill(
                name="single_platform_generation",
                description="为单个指定平台生成文案（降级策略），逐平台通过 ReAct 循环完成，当批量生成失败时自动启用",
                tool_names=["load_platform_prompt"],
                success_criteria="生成的单个平台文案符合该平台风格要求",
            ),
        ])

    def set_critic(self, critic: "CriticAgent") -> None:
        """设置审稿 Agent。"""
        self._critic = critic

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
你的写作要求：
1. 先理解原始内容的核心信息
2. 为目标平台选择合适的风格
3. 直接按要求输出，不要额外说明

每个平台的风格要点：
- 小红书：亲切真诚，像朋友分享，多用 emoji 和 #标签
- 抖音：短小精悍，开头要抓人，轻松有趣
- 公众号：结构清晰，有小标题，专业但不失亲切
- 微博：简洁有力，善用 #话题#，适合传播
"""

    # ==================== 批量生成入口（优化核心） ====================

    async def generate_for_platforms(self, content: str,
                                      platforms: List[str] = None) -> Dict[str, str]:
        """为多个平台生成文案（优化版：一次 LLM 调用生成全部平台）。

        Old: 每个平台走 ReAct 循环（think→tool→think→final），再逐平台 Critic
        New: 一次性生成所有平台文案，一次性 Critic 审查
        """
        if platforms is None:
            platforms = ["xiaohongshu", "douyin", "wechat", "weibo"]

        # 预加载所有平台模板（本地 I/O，无 LLM 开销）
        prompts = {p: load_platform_prompt(p) for p in platforms}

        # ====== 一次 LLM 调用，生成所有平台 ======
        results = await self._generate_all(content, prompts)
        if not results:
            logger.warning("[WriterAgent] 批量生成失败，降级到逐平台生成")
            return await self._generate_fallback(content, platforms, prompts)

        # ====== 一次 Critic 审查全部 ======
        if self._critic:
            results = await self._review_and_rewrite(content, results, prompts)

        return results

    # ==================== 核心优化：一次生成全部平台 ====================

    async def _generate_all(self, content: str,
                             platform_prompts: Dict[str, str]) -> Dict[str, str]:
        """一次 LLM 调用，为所有平台生成文案。"""
        platforms_desc = "\n\n".join([
            f"【{p}】\n要求：{prompt[:300]}"
            for p, prompt in platform_prompts.items()
        ])

        prompt = f"""请根据以下原始内容，为每个平台创作适配的文案。

        原始内容：
        {content}

        各平台要求：
        {platforms_desc}

        请直接以 JSON 格式返回，key 为平台名，value 为文案内容，不要包含其他说明：
        {{
            "xiaohongshu": "...",
            "douyin": "...",
            "wechat": "...",
            "weibo": "..."
        }}"""

        messages = [
            {"role": "system", "content": self.build_system_prompt()},
            {"role": "user", "content": prompt},
        ]

        try:
            response = self.llm_client.chat.completions.create(
                model=self.llm_model,
                messages=messages,
                temperature=0.7,
            )

            raw = response.choices[0].message.content
            return self._parse_json_response(raw, list(platform_prompts.keys()))
        except Exception as e:
            logger.error(f"[WriterAgent] 一次生成调用失败: {str(e)}")
            return {}

    def _parse_json_response(self, raw: str,
                              platforms: List[str]) -> Dict[str, str]:
        """从 LLM 输出中解析 JSON。"""
        # 尝试直接解析
        try:
            data = json.loads(raw)
            if isinstance(data, dict):
                return {p: data.get(p, "") for p in platforms}
        except json.JSONDecodeError:
            pass

        # 尝试从 markdown 代码块提取
        match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', raw)
        if match:
            try:
                data = json.loads(match.group(1))
                if isinstance(data, dict):
                    return {p: data.get(p, "") for p in platforms}
            except json.JSONDecodeError:
                pass

        # 按平台名分割（最坏情况降级）
        result = {}
        for p in platforms:
            # 找 "平台名": 后面的内容，直到下一个平台名或结尾
            pattern = rf'["\']?{p}["\']?\s*[:：]\s*["\'](.*?)["\']\s*[,}}]'
            match = re.search(pattern, raw, re.DOTALL)
            if match:
                result[p] = match.group(1).strip()
            else:
                result[p] = ""

        if any(result.values()):
            return result

        # 完全无法解析
        logger.error("[WriterAgent] 无法解析 LLM JSON 输出")
        return {}

    # ==================== 降级：逐平台生成 ====================

    async def _generate_fallback(self, content: str,
                                  platforms: List[str],
                                  prompts: Dict[str, str]) -> Dict[str, str]:
        """降级策略：逐平台通过 ReAct 循环生成（优化前的逻辑）。"""
        results = {}
        for platform in platforms:
            try:
                task = AgentTask(
                    instruction=f"请为【{platform}】平台生成文案。原始内容：\n\n{content}",
                    context={"platform": platform, "original_content": content},
                )
                result = await self._generate_single(task, prompts.get(platform, ""))
                if result:
                    results[platform] = result
                else:
                    results[platform] = f"生成失败: {content[:200]}"
            except Exception as e:
                logger.warning(f"[WriterAgent] {platform} 降级生成失败: {str(e)[:50]}")
                results[platform] = f"生成失败: {content[:200]}"
        return results

    async def _generate_single(self, task: AgentTask,
                                platform_prompt: str) -> str:
        """单个平台的 ReAct 生成。"""
        result = await self.run(task)
        return result.output or ""

    # ==================== 批量审查 + 重写 ====================

    async def _review_and_rewrite(self, content: str,
                                   results: Dict[str, str],
                                   prompts: Dict[str, str]) -> Dict[str, str]:
        """一次 Critic 审查 + 一次性重写。"""
        if not self._critic:
            return results

        # 构造审查请求：所有平台放一起
        review_prompt = "请审查以下多平台文案：\n\n"
        for platform, text in results.items():
            preview = text[:500] + ("..." if len(text) > 500 else "")
            review_prompt += f"--- {platform} ---\n{preview}\n\n"

        review = await self._critic.review(review_prompt, platform="all")

        if review.get("verdict") == "pass":
            logger.info(f"[WriterAgent] 所有平台通过审查 - 评分: {review.get('overall_score')}")
            return results

        improvements = review.get("improvements", [])
        if not improvements:
            logger.info(f"[WriterAgent] 无改进建议，通过 - 评分: {review.get('overall_score')}")
            return results

        feedback = "\n".join([f"- {imp}" for imp in improvements])
        logger.info(f"[WriterAgent] 收到审稿反馈，进行一次性修改")

        # 用一次 LLM 调用重写所有平台
        platforms_desc = "\n\n".join([
            f"【{p}】\n要求：{prompts.get(p, '')[:200]}"
            for p in results
        ])

        current_versions = "\n\n".join([
            f"--- {p} ---\n{results[p][:800]}"
            for p in results
        ])
        logger.info(f"当前版本：{current_versions}\n")
        rewrite_prompt = f"""请根据以下审稿意见，修改各平台文案。

        原始内容：{content}

        当前各平台版本：
        {current_versions}

        审稿意见：
        {feedback}

        请参照审稿意见逐条改进后，以 JSON 格式重新输出所有平台的文案：
        {{
            "xiaohongshu": "...",
            "douyin": "...",
            "wechat": "...",
            "weibo": "..."
        }}"""

        messages = [
            {"role": "system", "content": self.build_system_prompt()},
            {"role": "user", "content": rewrite_prompt},
        ]

        try:
            response = self.llm_client.chat.completions.create(
                model=self.llm_model,
                messages=messages,
                temperature=0.7,
            )
            rewritten = self._parse_json_response(
                response.choices[0].message.content,
                list(results.keys()),
            )
            if rewritten and any(rewritten.values()):
                logger.info(f"[WriterAgent] 重写完成")
                return rewritten
        except Exception as e:
            logger.warning(f"[WriterAgent] 重写失败，保留原版: {str(e)[:50]}")

        return results
