import json
import logging
import re
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session
from sqlalchemy import func

from backend.agents.base_agent import BaseAgent, AgentTask
from backend.agents.tool import Tool
from backend.agents.skill import Skill
from backend.models.database import HotTopic, HotTopicTrend

logger = logging.getLogger(__name__)


# ==================== 工具函数 ====================


def _get_db() -> Optional[Session]:
    """获取数据库会话（工具内部使用）。"""
    try:
        from backend.models.database import SessionLocal
        return SessionLocal()
    except Exception as e:
        logger.error(f"数据库连接失败: {str(e)}")
        return None


def calculate_trend(title: str, hours: int = 24) -> Dict:
    """计算某个话题的热度变化趋势。

    Args:
        title: 话题标题
        hours: 分析时间范围（小时）
    """
    db = _get_db()
    if not db:
        return {"error": "数据库不可用"}

    try:
        since = datetime.utcnow() - timedelta(hours=hours)
        records = db.query(HotTopicTrend).filter(
            HotTopicTrend.title == title,
            HotTopicTrend.recorded_at >= since
        ).order_by(HotTopicTrend.recorded_at.asc()).all()

        if not records:
            return {"title": title, "data_points": 0, "trend": "no_data"}

        scores = [r.heat_score for r in records]
        change = scores[-1] - scores[0]
        change_pct = ((scores[-1] - scores[0]) / scores[0] * 100) if scores[0] > 0 else 0

        return {
            "title": title,
            "data_points": len(records),
            "current_score": scores[-1],
            "peak_score": max(scores),
            "heat_change": round(change, 2),
            "heat_change_percent": round(change_pct, 2),
            "trend": "rising" if change > 0 else ("falling" if change < 0 else "stable"),
        }
    finally:
        db.close()


def classify_topic(title: str, description: str = "") -> Dict:
    """对话题进行分类。实际场景下应该调用 LLM，这里用简单关键词匹配。

    Args:
        title: 话题标题
        description: 话题描述
    """
    text = f"{title} {description}".lower()
    categories = {
        "科技": ["ai", "人工智能", "科技", "数码", "互联网", "软件", "硬件", "编程"],
        "娱乐": ["明星", "电影", "综艺", "音乐", "八卦", "偶像", "演唱会"],
        "社会": ["社会", "政策", "法律", "教育", "医疗", "民生", "新闻"],
        "财经": ["财经", "股票", "基金", "经济", "市场", "投资", "消费"],
        "体育": ["体育", "赛事", "运动", "篮球", "足球", "奥运", "电竞"],
        "生活": ["美食", "旅行", "健康", "家居", "穿搭", "护肤", "健身"],
    }

    matched = []
    for cat, keywords in categories.items():
        if any(kw in text for kw in keywords):
            matched.append(cat)

    return {
        "title": title,
        "categories": matched or ["其他"],
        "primary": matched[0] if matched else "其他",
    }


def get_platform_stats(platform: str = "") -> Dict:
    """获取指定平台的热点统计数据。

    Args:
        platform: 平台名（空字符串表示全部）
    """
    db = _get_db()
    if not db:
        return {"error": "数据库不可用"}

    try:
        query = db.query(
            HotTopic.platform,
            func.count(HotTopic.id).label("topic_count"),
            func.avg(HotTopic.heat_score).label("avg_heat"),
            func.max(HotTopic.heat_score).label("max_heat"),
        )
        if platform:
            query = query.filter(HotTopic.platform == platform)
        query = query.group_by(HotTopic.platform)

        results = []
        for row in query.all():
            results.append({
                "platform": row.platform,
                "topic_count": row.topic_count,
                "avg_heat": round(row.avg_heat or 0, 2),
                "max_heat": round(row.max_heat or 0, 2),
            })

        # 按话题数降序排列
        results.sort(key=lambda x: x["topic_count"], reverse=True)
        return {"platforms": results, "total": len(results)}
    finally:
        db.close()


def get_trending_topics(hours: int = 24, limit: int = 10) -> List[Dict]:
    """获取热度上升最快的话题。

    Args:
        hours: 时间范围（小时）
        limit: 返回数量
    """
    db = _get_db()
    if not db:
        return []

    try:
        since = datetime.utcnow() - timedelta(hours=hours)

        # 取每个话题最新的记录和最旧的记录，比较热度变化
        subquery = db.query(
            HotTopicTrend.title,
            HotTopicTrend.platform,
            func.max(HotTopicTrend.recorded_at).label("max_time"),
            func.min(HotTopicTrend.recorded_at).label("min_time"),
        ).filter(
            HotTopicTrend.recorded_at >= since
        ).group_by(
            HotTopicTrend.title, HotTopicTrend.platform
        ).subquery()

        # 获取最新和最旧的热度值
        results = []
        for row in db.query(subquery).all():
            latest = db.query(HotTopicTrend).filter(
                HotTopicTrend.title == row.title,
                HotTopicTrend.platform == row.platform,
                HotTopicTrend.recorded_at == row.max_time,
            ).first()
            earliest = db.query(HotTopicTrend).filter(
                HotTopicTrend.title == row.title,
                HotTopicTrend.platform == row.platform,
                HotTopicTrend.recorded_at == row.min_time,
            ).first()

            if latest and earliest and earliest.heat_score > 0:
                change_pct = ((latest.heat_score - earliest.heat_score) / earliest.heat_score) * 100
                results.append({
                    "title": row.title,
                    "platform": row.platform,
                    "current_heat": latest.heat_score,
                    "change_percent": round(change_pct, 2),
                })

        results.sort(key=lambda x: x["change_percent"], reverse=True)
        return results[:limit]
    finally:
        db.close()


# ==================== AnalyzerAgent ====================


class AnalyzerAgent(BaseAgent):
    """分析预测型 Agent。

    角色: "分析师" — 从数据中发现模式和趋势
    特质: 强 LLM 推理 + 数据工具
    策略:
      1. 接收数据
      2. 调用数据工具计算指标
      3. LLM 分析结果，给出洞察
      4. 综合输出分析报告

    这个 Agent 展示了：
      「ReAct + Tool Use 模式」
      Agent 结合 LLM 推理和工具执行，做数据驱动的分析决策。
    """

    def __init__(self, name: str = "analyzer",
                 llm_client=None, llm_model: str = "glm-4-plus"):
        tools = [
            Tool.from_function(calculate_trend),
            Tool.from_function(classify_topic),
            Tool.from_function(get_platform_stats),
            Tool.from_function(get_trending_topics),
        ]
        super().__init__(
            name=name,
            role="热点分析师，擅长从数据中发现趋势和模式。"
                 "你会使用数据工具计算指标，然后基于数据给出专业分析。",
            tools=tools,
            llm_client=llm_client,
            llm_model=llm_model,
            max_steps=15,
        )

        self.register_skills([
            Skill(
                name="trend_analysis",
                description="分析指定话题在过去一段时间内的热度变化趋势，计算升降幅度和变化率，判断话题是上升/下降/平稳",
                tool_names=["calculate_trend", "get_trending_topics"],
                success_criteria="返回趋势方向、变化幅度百分比、数据点数量等量化指标",
            ),
            Skill(
                name="topic_classification",
                description="对热点话题进行自动分类（科技/娱乐/社会/财经/体育/生活），支持按分类维度统计和分析",
                tool_names=["classify_topic"],
                success_criteria="准确识别话题所属分类，支持多分类标注",
            ),
            Skill(
                name="viral_prediction",
                description="基于当前热点数据和历史趋势，预测下一个可能爆火的话题方向，给出置信度和理由",
                tool_names=["calculate_trend", "get_trending_topics", "get_platform_stats"],
                success_criteria="输出预测话题名称、置信度评分、相关标签、建议首发平台及推理理由",
            ),
            Skill(
                name="platform_statistics",
                description="统计各平台的热点数量、平均热度、最高热度等指标，支持跨平台横向对比",
                tool_names=["get_platform_stats"],
                success_criteria="输出每个平台的话题数、平均热度和最高热度，按热度排序",
            ),
        ])

    def build_system_prompt(self, matched_skill=None) -> str:
        skills_desc = "\n".join([
            f"  * {s.name}: {s.description}"
            for s in self.skills.values()
        ])

        tools_desc = "\n".join([
            f"  - {t.name}: {t.description}"
            for t in self.tool_list
        ])
        skill_hint = ""
        if matched_skill:
            skill_hint = f"\n当前任务最适合使用技能【{matched_skill.name}】来。\n"

        return f"""你是 {self.name}，你的角色是：{self.role}

        你掌握以下核心技能：
        {skills_desc}
        {skill_hint}
        你可以使用以下工具分析数据：
        {tools_desc}

        工作流程：
        1. 先调用工具获取数据
        2. 基于数据分析结果
        3. 给出有洞察的分析报告

        分析报告格式：
        {{
            "summary": "总体分析结论",
            "key_findings": ["发现1", "发现2", "发现3"],
            "trends": [
                {{"topic": "话题名", "direction": "up/down/stable", "change": "变化描述"}}
            ],
            "recommendations": ["建议1", "建议2"]
        }}
        """

    async def analyze_topics(self, platform: str = "all",
                              hours: int = 24) -> Dict[str, Any]:
        """对外便捷方法：分析热点趋势。"""
        task = AgentTask(
            instruction=f"分析{platform if platform != 'all' else '各'}平台过去{hours}小时的热点趋势",
            context={"platform": platform, "hours": hours},
        )
        result = await self.run(task)

        if result.success and result.output:
            try:
                return json.loads(result.output)
            except (json.JSONDecodeError, TypeError):
                return {"raw_output": result.output}
        return {"error": result.error or "分析失败"}

    async def predict_viral(self, title: str, content: str = "",
                             platform: str = "all") -> Dict[str, Any]:
        """对外便捷方法：预测爆款潜力。"""
        task = AgentTask(
            instruction=f"预测以下内容的爆款潜力\n标题：{title}\n内容：{content or '无'}\n目标平台：{platform or '不限'}",
            context={"title": title, "content": content, "platform": platform},
        )
        result = await self.run(task)

        if result.success and result.output:
            try:
                return json.loads(result.output)
            except (json.JSONDecodeError, TypeError):
                return {"raw_output": result.output, "title": title}
        return {"error": result.error or "预测失败", "title": title}

    async def predict_next_topic(self, hot_titles: List[str]) -> Dict[str, Any]:
        """预测下一个爆火话题（直接调用 LLM，不走 ReAct 循环）。"""
        if not hot_titles:
            return {"topic": "暂无数据", "confidence": 0, "reason": "热点数据为空"}

        prompt = f"""基于以下当前热点话题，预测下一个可能爆火的话题方向。

        当前热点：
        {chr(10).join(f'- {t}' for t in hot_titles)}

        请直接返回 JSON，不要包含其他说明：
        {{
            "topic": "预测的下一个热点话题",
            "confidence": 0-100的数字,
            "hot_tags": ["相关标签1", "相关标签2"],
            "hot_platform": "最可能爆火的平台",
            "rising_topics": ["上升话题1", "上升话题2", "上升话题3"],
            "reasons": ["理由1", "理由2", "理由3"]
        }}"""

        try:
            response = self.llm_client.chat.completions.create(
                model=self.llm_model,
                messages=[
                    {"role": "system", "content": "你是一个热点趋势分析师。请基于给定热点，预测下一个爆火方向。"},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.7,
            )
            raw = response.choices[0].message.content
            # 尝试解析 JSON
            try:
                return json.loads(raw)
            except json.JSONDecodeError:
                import re
                match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', raw)
                if match:
                    return json.loads(match.group(1))
            return {"topic": hot_titles[0], "confidence": 50, "reason": "AI 输出格式错误"}
        except Exception as e:
            logger.error(f"预测失败: {str(e)}")
            return {"topic": hot_titles[0], "confidence": 30, "reason": f"AI 调用失败: {str(e)[:50]}"}
