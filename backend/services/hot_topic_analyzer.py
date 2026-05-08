import json
import logging
import re
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from sqlalchemy.orm import Session
from sqlalchemy import func
from zhipuai import ZhipuAI
from backend.models.database import HotTopic, HotTopicTrend
from backend.models.schemas import (
    TopicTrendResponse, TrendPoint, PlatformCompareResponse,
    CategoryStatResponse, ViralPredictionResponse
)

logger = logging.getLogger(__name__)


class HotTopicAnalyzer:
    """热点话题分析与爆款预测服务"""

    # 热度等级阈值
    VIRAL_THRESHOLD = 5000000    # 500万以上算爆款
    HIGH_THRESHOLD = 1000000     # 100万以上算高热
    MEDIUM_THRESHOLD = 100000    # 10万以上算中等

    # 各平台高峰时段（经验值）
    PLATFORM_PEAK_HOURS = {
        "douyin": [12, 19, 20, 21],        # 午休+晚高峰
        "weibo": [10, 11, 21, 22],          # 上午+睡前
        "xiaohongshu": [8, 12, 20, 21],     # 早通勤+午休+晚间
    }

    def __init__(self, db: Session, zhipu_api_key: Optional[str] = None,
                 zhipu_model: str = "glm-4-plus"):
        self.db = db
        self.zhipu_api_key = zhipu_api_key
        self.zhipu_model = zhipu_model
        self._ai_client = ZhipuAI(api_key=zhipu_api_key) if zhipu_api_key else None

    # ==================== 趋势记录 ====================

    def record_trend_snapshot(self) -> int:
        """记录当前所有热点的热度快照到趋势表"""
        topics = self.db.query(HotTopic).all()
        count = 0
        for topic in topics:
            trend = HotTopicTrend(
                title=topic.title,
                platform=topic.platform,
                heat_score=topic.heat_score or 0,
                rank=topic.rank,
                tags=topic.tags,
                recorded_at=datetime.utcnow()
            )
            self.db.add(trend)
            count += 1
        self.db.commit()
        logger.info(f"记录 {count} 条热度趋势快照")
        return count

    # ==================== 趋势分析 ====================

    def get_trend(self, title: str, platform: str = "",
                  hours: int = 24) -> Optional[TopicTrendResponse]:
        """获取某个话题的热度趋势"""
        query = self.db.query(HotTopicTrend).filter(
            HotTopicTrend.title == title
        )
        if platform:
            query = query.filter(HotTopicTrend.platform == platform)

        since = datetime.utcnow() - timedelta(hours=hours)
        records = query.filter(
            HotTopicTrend.recorded_at >= since
        ).order_by(HotTopicTrend.recorded_at.asc()).all()

        if not records:
            return None

        trend_data = [
            TrendPoint(
                recorded_at=r.recorded_at,
                heat_score=r.heat_score,
                rank=r.rank
            ) for r in records
        ]

        scores = [r.heat_score for r in records]
        current = scores[-1]
        first = scores[0]
        change = current - first
        change_percent = ((current - first) / first * 100) if first > 0 else 0

        return TopicTrendResponse(
            title=title,
            platform=records[0].platform,
            tags=records[0].tags,
            trend_data=trend_data,
            heat_change=round(change, 2),
            heat_change_percent=round(change_percent, 2),
            peak_score=max(scores),
            current_score=current
        )

    def get_trending_topics(self, hours: int = 24, limit: int = 10) -> List[Dict]:
        """获取热度上升最快的话题"""
        since = datetime.utcnow() - timedelta(hours=hours)

        # 取每个话题最新的记录
        subquery = self.db.query(
            HotTopicTrend.title,
            HotTopicTrend.platform,
            func.max(HotTopicTrend.recorded_at).label("max_time")
        ).filter(
            HotTopicTrend.recorded_at >= since
        ).group_by(
            HotTopicTrend.title, HotTopicTrend.platform
        ).subquery()

        latest = self.db.query(HotTopicTrend).join(
            subquery,
            (HotTopicTrend.title == subquery.c.title) &
            (HotTopicTrend.platform == subquery.c.platform) &
            (HotTopicTrend.recorded_at == subquery.c.max_time)
        ).all()

        # 取当前在 HotTopic 表中的最高热度
        results = []
        for record in latest:
            current_topic = self.db.query(HotTopic).filter(
                HotTopic.title == record.title,
                HotTopic.platform == record.platform
            ).first()

            if current_topic:
                results.append({
                    "title": record.title,
                    "platform": record.platform,
                    "current_heat": current_topic.heat_score or 0,
                    "tags": record.tags,
                    "rank": current_topic.rank,
                })

        results.sort(key=lambda x: x["current_heat"], reverse=True)
        return results[:limit]

    # ==================== 平台对比 ====================

    def get_platform_compare(self) -> List[PlatformCompareResponse]:
        """对比各平台热点数据"""
        stats = self.db.query(
            HotTopic.platform,
            func.count(HotTopic.id).label("topic_count"),
            func.avg(HotTopic.heat_score).label("avg_heat"),
            func.sum(HotTopic.heat_score).label("total_heat"),
            func.max(HotTopic.heat_score).label("max_heat")
        ).group_by(HotTopic.platform).all()

        return [
            PlatformCompareResponse(
                platform=row.platform,
                topic_count=row.topic_count,
                avg_heat=round(row.avg_heat or 0, 2),
                total_heat=round(row.total_heat or 0, 2),
                max_heat=round(row.max_heat or 0, 2)
            )
            for row in stats
        ]

    # ==================== 分类统计 ====================

    def get_category_stats(self) -> List[CategoryStatResponse]:
        """按标签分类统计热点"""
        all_topics = self.db.query(HotTopic).all()
        category_map: Dict[str, Dict] = {}
        for topic in all_topics:
            if not topic.tags:
                continue
            for tag in topic.tags.split(","):
                tag = tag.strip()
                if not tag:
                    continue
                if tag not in category_map:
                    category_map[tag] = {
                        "count": 0,
                        "total_heat": 0.0,
                        "platforms": set()
                    }
                category_map[tag]["count"] += 1
                category_map[tag]["total_heat"] += topic.heat_score or 0
                category_map[tag]["platforms"].add(topic.platform)

        results = []
        for category, data in category_map.items():
            results.append(CategoryStatResponse(
                category=category,
                topic_count=data["count"],
                avg_heat=round(data["total_heat"] / data["count"], 2),
                platforms=sorted(data["platforms"])
            ))

        results.sort(key=lambda x: x.topic_count, reverse=True)
        return results

    # ==================== 高峰时段分析 ====================

    def get_peak_hour_analysis(self) -> Dict[str, Dict]:
        """分析各平台热点高峰时段（基于现有数据）"""
        result = {}
        for platform, peak_hours in self.PLATFORM_PEAK_HOURS.items():
            topics = self.db.query(HotTopic).filter(
                HotTopic.platform == platform
            ).count()

            result[platform] = {
                "topic_count": topics,
                "suggested_hours": peak_hours,
                "best_hour": max(set(peak_hours), key=peak_hours.count),
            }
        return result

    # ==================== 爆款特征提取 ====================

    def _get_viral_topics(self, limit: int = 20) -> List[Dict]:
        """提取当前爆款话题特征"""
        hot_topics = self.db.query(HotTopic).filter(
            HotTopic.heat_score >= self.HIGH_THRESHOLD
        ).order_by(HotTopic.heat_score.desc()).limit(limit).all()

        return [
            {
                "title": t.title,
                "platform": t.platform,
                "heat_score": t.heat_score,
                "tags": t.tags,
                "rank": t.rank,
            }
            for t in hot_topics
        ]

    def _estimate_peak_hour(self, platform: str) -> int:
        """根据平台推荐最佳发布时间"""
        hours = self.PLATFORM_PEAK_HOURS.get(platform, [12, 20])
        return max(set(hours), key=hours.count)

    def _suggest_platform(self, title: str, content: str) -> str:
        """根据内容特征推荐首发平台"""
        title_lower = title.lower()
        content_lower = content.lower()

        # 简单规则匹配
        douyin_keywords = ["舞蹈", "音乐", "搞笑", "挑战", "美食", "旅行", "vlog",
                          "化妆", "穿搭", "测评", "开箱"]
        weibo_keywords = ["新闻", "热点", "明星", "电影", "电视剧", "体育", "社会",
                         "政治", "国际", "科技"]
        xhs_keywords = ["护肤", "好物", "种草", "探店", "穿搭", "家居", "收纳",
                       "教程", "食谱", "健身"]

        for kw in douyin_keywords:
            if kw in title_lower or kw in content_lower:
                return "douyin"
        for kw in xhs_keywords:
            if kw in title_lower or kw in content_lower:
                return "xiaohongshu"
        return "weibo"

    def _predict_viral_score(self, viral_topics: List[Dict],
                              title: str, content: str, platform: str) -> Dict:
        """基于现有热点数据估算爆款潜力分"""
        score = 50  # 基础分
        reasons = []
        suggestions = []

        title_len = len(title)
        has_content = bool(content.strip())

        # 1. 标题长度评分
        if 10 <= title_len <= 30:
            score += 15
            reasons.append("标题长度适中(10-30字)，容易吸引点击")
        elif 5 <= title_len < 10:
            score += 5
            suggestions.append("建议适当加长标题至10-30字，增加信息量")
        elif title_len > 30:
            score -= 5
            suggestions.append("标题偏长(超过30字)，建议精简")
        else:
            score -= 10
            suggestions.append("标题太短，建议扩展至10-30字")

        # 2. 内容完整性评分
        if has_content and len(content) > 50:
            score += 10
            reasons.append("内容完整，信息量充足")
        elif has_content:
            score += 5
            suggestions.append("内容偏短，建议补充更多细节")
        else:
            score -= 5
            suggestions.append("建议补充详细内容，提高传播价值")

        # 3. 与爆款话题的特征匹配
        viral_titles = [t["title"] for t in viral_topics[:10]]
        viral_tags = set()
        for t in viral_topics:
            if t.get("tags"):
                viral_tags.update(t["tags"].split(","))

        title_words = set(title)
        match_count = sum(1 for vt in viral_titles if any(
            w in vt for w in title if len(w) > 1
        ))

        if match_count >= 3:
            score += 10
            reasons.append(f"标题关键词与{match_count}个爆款话题匹配")
        elif match_count >= 1:
            score += 5
            reasons.append("标题有爆款话题相关关键词")

        # 4. 平台匹配度
        suggested = self._suggest_platform(title, content)
        if platform == "all" or platform == suggested:
            score += 10
            reasons.append(f"推荐首发平台: {suggested}，与内容类型匹配度高")
        else:
            score += 5
            suggestions.append(f"建议考虑在 {suggested} 平台首发")

        # 5. 标签丰富度
        if viral_tags:
            matched_tags = [t for t in viral_tags if t in title or t in content]
            if matched_tags:
                score += 5
                reasons.append(f"使用了爆款标签: {', '.join(list(matched_tags)[:3])}")

        # 6. 热度等级对照
        if viral_topics:
            avg_heat = sum(t["heat_score"] for t in viral_topics) / len(viral_topics)
            if avg_heat > self.VIRAL_THRESHOLD:
                reasons.append(f"当前爆款话题平均热度 {int(avg_heat):,}，市场活跃度高")

        # 归一化到 0-100
        score = max(0, min(100, score))

        # 置信度
        if len(viral_topics) >= 10:
            confidence = "high"
        elif len(viral_topics) >= 5:
            confidence = "medium"
        else:
            confidence = "low"

        return {
            "score": score,
            "suggested_platform": suggested,
            "peak_hour": self._estimate_peak_hour(suggested),
            "confidence": confidence,
            "reasons": reasons,
            "suggestions": suggestions,
        }

    # ==================== AI 分析 ====================

    def _call_ai(self, prompt: str) -> Optional[str]:
        """调用智谱AI进行文本分析"""
        if not self._ai_client:
            return None
        try:
            response = self._ai_client.chat.completions.create(
                model=self.zhipu_model,
                messages=[{"role": "user", "content": prompt}]
            )
            return response.choices[0].message.content
        except Exception as e:
            logger.warning(f"AI分析调用失败: {str(e)}")
            return None

    def _ai_predict_viral_score(self, title: str, content: str,
                                 platform: str) -> Optional[Dict]:
        """使用AI预测爆款潜力"""
        viral_topics = self._get_viral_topics(limit=10)
        hot_context = "\n".join([
            f"- [{t['platform']}] {t['title']} (热度:{t['heat_score']}, 标签:{t['tags']})"
            for t in viral_topics
        ]) if viral_topics else "暂无热点数据"

        prompt = f"""你是一个社交媒体爆款分析专家。请基于当前热点数据，分析以下内容的爆款潜力。

        当前热点话题：
        {hot_context}

        待分析内容：
        标题：{title}
        内容：{content or '无详细内容'}
        目标平台：{platform}

        请从以下几个方面分析：
        1. 爆款潜力评分（0-100）
        2. 评分理由（2-3条）
        3. 改进建议（1-2条）
        4. 推荐首发平台
        5. 最佳发布时间（小时，0-23）
        6. 置信度（high/medium/low）

        请严格按照以下JSON格式返回结果，不要包含其他内容：
        {{
            "score": 75,
            "confidence": "medium",
            "suggested_platform": "douyin",
            "peak_hour": 20,
            "reasons": ["理由1", "理由2"],
            "suggestions": ["建议1"]
        }}"""

        result = self._call_ai(prompt)
        if not result:
            return None

        try:
            parsed = json.loads(result)
            return parsed
        except json.JSONDecodeError:
            match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', result)
            if match:
                try:
                    return json.loads(match.group(1))
                except json.JSONDecodeError:
                    pass
            logger.warning("AI返回格式无法解析为JSON")
            return None

    # ==================== 爆款预测（对外接口） ====================

    def predict_viral(self, title: str, content: str = "",
                      platform: str = "all") -> ViralPredictionResponse:
        """预测内容爆款潜力（AI优先，规则回退）"""
        logger.info(f"爆款预测 - 标题: {title[:30]}..., 平台: {platform}")

        # 尝试AI预测
        ai_result = self._ai_predict_viral_score(title, content, platform)
        if ai_result:
            logger.info(f"AI爆款预测完成 - 得分: {ai_result.get('score')}")
            return ViralPredictionResponse(
                title=title,
                platform=platform,
                viral_score=ai_result.get("score", 50),
                confidence=ai_result.get("confidence", "medium"),
                peak_hour=ai_result.get("peak_hour", 20),
                suggested_platform=ai_result.get("suggested_platform", "weibo"),
                reasons=ai_result.get("reasons", []),
                suggestions=ai_result.get("suggestions", []),
            )

        # AI失败，回退到规则预测
        logger.info("AI预测不可用，使用规则预测")
        viral_topics = self._get_viral_topics()
        result = self._predict_viral_score(
            viral_topics, title, content, platform
        )

        logger.info(
            f"规则爆款预测完成 - 得分: {result['score']}, "
            f"置信度: {result['confidence']}, "
            f"建议平台: {result['suggested_platform']}"
        )

        return ViralPredictionResponse(
            title=title,
            platform=platform,
            viral_score=result["score"],
            confidence=result["confidence"],
            peak_hour=result["peak_hour"],
            suggested_platform=result["suggested_platform"],
            reasons=result["reasons"],
            suggestions=result["suggestions"],
        )

    def batch_predict(self, topics: List[Dict]) -> List[ViralPredictionResponse]:
        """批量预测多条内容的爆款潜力（AI优先，规则回退）"""
        viral_topics = self._get_viral_topics()
        results = []

        for topic in topics:
            title = topic.get("title", "")
            content = topic.get("content", "")
            platform = topic.get("platform", "all")

            # 尝试AI预测
            ai_result = self._ai_predict_viral_score(title, content, platform)
            if ai_result:
                results.append(ViralPredictionResponse(
                    title=title,
                    platform=platform,
                    viral_score=ai_result.get("score", 50),
                    confidence=ai_result.get("confidence", "medium"),
                    peak_hour=ai_result.get("peak_hour", 20),
                    suggested_platform=ai_result.get("suggested_platform", "weibo"),
                    reasons=ai_result.get("reasons", []),
                    suggestions=ai_result.get("suggestions", []),
                ))
            else:
                result = self._predict_viral_score(
                    viral_topics, title, content, platform
                )
                results.append(ViralPredictionResponse(
                    title=title,
                    platform=platform,
                    viral_score=result["score"],
                    confidence=result["confidence"],
                    peak_hour=result["peak_hour"],
                    suggested_platform=result["suggested_platform"],
                    reasons=result["reasons"],
                    suggestions=result["suggestions"],
                ))

        return results
