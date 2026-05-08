from pydantic import BaseModel
from datetime import datetime
from typing import Optional, Dict, List

class ContentRequest(BaseModel):
    # 用户输入的原始内容
    content: str
    # 可选的行业标签
    industry: Optional[str] = None

class ContentResponse(BaseModel):
    # 生成的多平台文案结果
    results: Dict[str, str]
    # 检测到的敏感词
    sensitive_words: Dict[str, list]
    # AI 配图 URL
    image_url: Optional[str] = None
    # 生成时间戳
    timestamp: datetime

class HistoryRecord(BaseModel):
    # 历史记录 ID
    id: int
    # 原始内容
    original_content: str
    # 生成结果
    generated_content: Dict[str, str]
    # 创建时间
    created_at: datetime

class HotTopicResponse(BaseModel):
    # 热点 ID
    id: int
    # 平台来源
    platform: str
    # 热点标题
    title: str
    # 热点描述
    description: Optional[str]
    # 热度值
    heat_score: Optional[float]
    # 排名
    rank: Optional[int]
    # 话题标签
    tags: Optional[str]
    # 原始链接
    url: Optional[str]
    # 抓取时间
    fetched_at: datetime

    class Config:
        from_attributes = True


# ---- 热点分析与爆款预测 ----

class TrendPoint(BaseModel):
    """趋势数据点"""
    recorded_at: datetime
    heat_score: float
    rank: Optional[int] = None

class TopicTrendResponse(BaseModel):
    """话题趋势响应"""
    title: str
    platform: str
    tags: Optional[str] = None
    trend_data: List[TrendPoint]
    heat_change: float          # 热度变化量
    heat_change_percent: float  # 热度变化百分比
    peak_score: float           # 最高热度
    current_score: float        # 当前热度

class PlatformCompareResponse(BaseModel):
    """平台对比响应"""
    platform: str
    topic_count: int
    avg_heat: float
    total_heat: float
    max_heat: float

class CategoryStatResponse(BaseModel):
    """分类统计响应"""
    category: str
    topic_count: int
    avg_heat: float
    platforms: List[str]

class ViralPredictionRequest(BaseModel):
    """爆款预测请求"""
    title: str
    content: str = ""
    platform: str = "all"

class ViralPredictionResponse(BaseModel):
    """爆款预测响应"""
    title: str
    platform: str
    viral_score: int           # 爆款潜力分 0-100
    confidence: str            # high / medium / low
    peak_hour: Optional[int]   # 建议发布时间
    suggested_platform: str    # 建议首发平台
    reasons: List[str]         # 评分理由
    suggestions: List[str]     # 优化建议
