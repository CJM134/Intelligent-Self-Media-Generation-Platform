from sqlalchemy import create_engine, Column, Integer, String, DateTime, Text, Float, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime
from backend.config import settings

# 创建数据库引擎
engine = create_engine(settings.database_url, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class ContentHistory(Base):
    # 内容历史记录表
    __tablename__ = "content_history"

    # 记录 ID
    id = Column(Integer, primary_key=True, index=True)
    # 原始内容
    original_content = Column(Text, nullable=False)
    # 小红书文案
    xiaohongshu_content = Column(Text)
    # 抖音文案
    douyin_content = Column(Text)
    # 公众号文案
    wechat_content = Column(Text)
    # 微博文案
    weibo_content = Column(Text)
    # AI 配图 URL（CogView 生成的图片）
    image_url = Column(String(1000), nullable=True)
    # 创建时间
    created_at = Column(DateTime, default=datetime.utcnow)

class HotTopic(Base):
    # 热点话题表
    __tablename__ = "hot_topics"

    # 热点 ID
    id = Column(Integer, primary_key=True, index=True)
    # 平台来源（douyin, weibo, xiaohongshu等）
    platform = Column(String(50), nullable=False)
    # 热点标题
    title = Column(String(500), nullable=False)
    # 热点描述
    description = Column(Text)
    # 热度值
    heat_score = Column(Float)
    # 排名
    rank = Column(Integer)
    # 话题标签
    tags = Column(String(500))
    # 原始链接
    url = Column(String(1000))
    # 抓取时间
    fetched_at = Column(DateTime, default=datetime.utcnow)
    # 创建时间
    created_at = Column(DateTime, default=datetime.utcnow)

class HotTopicTrend(Base):
    # 热点热度趋势表
    __tablename__ = "hot_topic_trends"

    id = Column(Integer, primary_key=True, index=True)
    # 关联热点标题（用标题去重）
    title = Column(String(500), nullable=False)
    # 平台来源
    platform = Column(String(50), nullable=False)
    # 热度值
    heat_score = Column(Float, default=0)
    # 排名
    rank = Column(Integer)
    # 话题标签
    tags = Column(String(500))
    # 记录时间（每个时间点的热度快照）
    recorded_at = Column(DateTime, default=datetime.utcnow)

class ScheduledTaskRun(Base):
    # 定时任务运行记录表
    __tablename__ = "scheduled_task_runs"

    id = Column(Integer, primary_key=True, index=True)
    # 任务类型：auto_generate / next_topic_predict
    task_type = Column(String(50), nullable=False, default="auto_generate")
    # 运行状态：running / success / failed
    status = Column(String(20), nullable=False, default="running")
    # 抓取话题数
    topics_fetched = Column(Integer, default=0)
    # 生成文案数
    contents_generated = Column(Integer, default=0)
    # 预测的下一个热点（JSON字符串）
    prediction = Column(Text, nullable=True)
    # 错误信息
    error_message = Column(Text, nullable=True)
    # 开始/结束时间
    started_at = Column(DateTime, default=datetime.utcnow)
    finished_at = Column(DateTime, nullable=True)

# 创建所有表
Base.metadata.create_all(bind=engine)

# 兼容旧数据库：新增字段时自动加列（SQLite 不支持 ALTER 的 IF NOT EXISTS）


def _migrate_schema():
    """增量迁移：添加旧表缺少的列。"""
    try:
        from sqlalchemy import inspect as sa_inspect, text as sa_text
        inspector = sa_inspect(engine)
        columns = [c["name"] for c in inspector.get_columns("content_history")]
        if "image_url" not in columns:
            with engine.connect() as conn:
                conn.execute(sa_text("ALTER TABLE content_history ADD COLUMN image_url VARCHAR(1000)"))
                conn.commit()
            logging.getLogger(__name__).info("数据库迁移: content_history 添加 image_url 列")
    except Exception:
        pass  # 表不存在或其他忽略


_migrate_schema()

def get_db():
    # 获取数据库会话
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
