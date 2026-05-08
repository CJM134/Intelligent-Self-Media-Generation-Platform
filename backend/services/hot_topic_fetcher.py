from typing import List, Dict, Optional
from datetime import datetime
import random
import logging
from backend.services.api_clients.tianapi_client import TianAPIClient

# 配置日志
logger = logging.getLogger(__name__)

class HotTopicFetcher:
    """热点话题抓取服务"""

    def __init__(self, tianapi_key: Optional[str] = None, use_real_api: bool = True):
        """
        初始化热点抓取服务

        Args:
            tianapi_key: 天聚数行API密钥
            use_real_api: 是否使用真实API（False则使用模拟数据）
        """
        self.platforms = ["douyin", "weibo", "xiaohongshu"]
        self.use_real_api = use_real_api and tianapi_key is not None

        if self.use_real_api:
            logger.info("使用真实API模式")
            self.api_client = TianAPIClient(tianapi_key)
        else:
            logger.info("使用模拟数据模式")
            self.api_client = None

    def fetch_hot_topics(self, platform: str = "all", limit: int = 20) -> List[Dict]:
        """
        获取热点话题

        Args:
            platform: 平台名称，支持 douyin, weibo, xiaohongshu, all
            limit: 返回数量限制

        Returns:
            热点话题列表
        """
        if platform == "all":
            topics = []
            for p in self.platforms:
                topics.extend(self._fetch_platform_topics(p, limit // len(self.platforms)))
            return topics[:limit]
        else:
            return self._fetch_platform_topics(platform, limit)

    def _fetch_platform_topics(self, platform: str, limit: int) -> List[Dict]:
        """
        从指定平台获取热点话题
        优先使用真实API，失败时降级到模拟数据
        """
        if self.use_real_api and self.api_client:
            try:
                logger.info(f"尝试从 {platform} 平台获取真实热点数据...")
                if platform == "weibo":
                    result = self.api_client.get_weibo_hot(num=limit)
                    logger.info(f"成功从微博API获取 {len(result)} 条热点")
                    return result
                elif platform == "douyin":
                    result = self.api_client.get_douyin_hot(num=limit)
                    logger.info(f"成功从抖音API获取 {len(result)} 条热点")
                    return result
                elif platform == "xiaohongshu":
                    logger.info("小红书暂时使用模拟数据")
                    return self._generate_mock_topics(platform, limit)
            except Exception as e:
                logger.warning(f"真实API调用失败，降级到模拟数据: {str(e)}")
                return self._generate_mock_topics(platform, limit)
        else:
            logger.info(f"使用模拟数据获取 {platform} 热点")
            return self._generate_mock_topics(platform, limit)

    def _generate_mock_topics(self, platform: str, count: int) -> List[Dict]:
        """生成模拟热点数据"""

        # 不同平台的热点话题模板
        topic_templates = {
            "douyin": [
                "AI技术如何改变我们的生活",
                "春季穿搭指南",
                "健康饮食新趋势",
                "职场新人必备技能",
                "旅行攻略分享",
                "美妆护肤心得",
                "数码产品测评",
                "家居收纳技巧"
            ],
            "weibo": [
                "热门电影讨论",
                "明星动态追踪",
                "社会热点事件",
                "科技新闻速递",
                "体育赛事直播",
                "美食探店推荐",
                "读书分享会",
                "音乐新歌推荐"
            ],
            "xiaohongshu": [
                "好物种草清单",
                "护肤品测评",
                "穿搭灵感分享",
                "美食制作教程",
                "旅行vlog",
                "学习方法分享",
                "家居装修案例",
                "健身打卡记录"
            ]
        }

        templates = topic_templates.get(platform, topic_templates["douyin"])
        topics = []

        for i in range(min(count, len(templates))):
            topic = {
                "platform": platform,
                "title": templates[i],
                "description": f"这是关于{templates[i]}的热点话题，正在{platform}平台热议中",
                "heat_score": round(random.uniform(50000, 1000000), 2),
                "rank": i + 1,
                "tags": self._generate_tags(templates[i]),
                "url": f"https://{platform}.com/topic/{i+1}",
                "fetched_at": datetime.utcnow()
            }
            topics.append(topic)

        return topics

    def _generate_tags(self, title: str) -> str:
        """根据标题生成相关标签"""
        tag_map = {
            "AI": ["人工智能", "科技", "未来"],
            "穿搭": ["时尚", "搭配", "服装"],
            "饮食": ["美食", "健康", "营养"],
            "职场": ["工作", "技能", "成长"],
            "旅行": ["旅游", "攻略", "风景"],
            "美妆": ["化妆", "护肤", "美容"],
            "数码": ["科技", "测评", "电子产品"],
            "家居": ["装修", "收纳", "生活"],
            "电影": ["影视", "娱乐", "观影"],
            "明星": ["娱乐", "八卦", "粉丝"],
            "体育": ["运动", "赛事", "健身"],
            "读书": ["阅读", "书籍", "知识"],
            "音乐": ["歌曲", "娱乐", "艺术"]
        }

        tags = []
        for keyword, tag_list in tag_map.items():
            if keyword in title:
                tags.extend(tag_list[:2])

        return ",".join(tags) if tags else "热门,推荐"