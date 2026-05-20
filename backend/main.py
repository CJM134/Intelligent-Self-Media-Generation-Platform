from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from typing import List
import logging
import asyncio
from backend.config import settings
from backend.models.database import get_db, HotTopic, HotTopicTrend, ScheduledTaskRun
from backend.models.schemas import (
    ContentRequest, ContentResponse, HotTopicResponse,
    ViralPredictionRequest, ViralPredictionResponse,
    TopicTrendResponse, PlatformCompareResponse, CategoryStatResponse,
)
from backend.services.content_generator import ContentGenerator
from backend.services.sensitive_filter import SensitiveFilter
from backend.services.history_manager import HistoryManager
from backend.services.hot_topic_fetcher import HotTopicFetcher
from backend.services.hot_topic_analyzer import HotTopicAnalyzer
from backend.services.scheduled_tasks import scheduled_task_service
from backend.services.image_generator import image_generator, init_image_generator
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from backend.agents import OrchestratorAgent, AgentTask
from zhipuai import ZhipuAI
from backend.agents.trace_store import trace_store
# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

app = FastAPI(title=settings.api_title, version=settings.api_version)

# 启动时输出配置信息
@app.on_event("startup")
async def startup_event():
    logger.info("=" * 60)
    logger.info("应用启动中...")
    logger.info(f"应用名称: {settings.api_title}")
    logger.info(f"应用版本: {settings.api_version}")
    logger.info(f"调试模式: {settings.debug}")
    logger.info(f"数据库: {settings.database_url}")
    logger.info(f"智谱AI模型: {settings.zhipu_model}")
    logger.info(f"智谱AI Key: {'已配置' if settings.zhipu_api_key else '未配置'}")
    logger.info(f"天聚数行 Key: {'已配置' if settings.tianapi_key else '未配置'}")
    logger.info("=" * 60)

    # 初始化图像生成器
    try:
        init_image_generator(backend="jimeng")
    except Exception as e:
        logger.warning(f"图像生成器初始化失败: {str(e)}")

    # 初始化定时任务调度器，每2小时执行一次
    try:
        scheduler = AsyncIOScheduler()
        scheduler.add_job(
            scheduled_task_service.run_auto_generate,
            trigger="interval",
            hours=2,
            id="auto_generate_job",
            replace_existing=True,
            # 启动后延迟1分钟再首次执行，给系统足够时间完成初始化
            next_run_time=datetime.utcnow() + timedelta(minutes=1),
        )
        scheduler.start()
        logger.info("定时任务调度器已启动 - 每2小时自动抓取热点并生成文案")
    except Exception as e:
        logger.error(f"定时任务调度器启动失败: {str(e)}")

# 添加 CORS 中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


llm_client = ZhipuAI(api_key=settings.zhipu_api_key)
orchestrator = OrchestratorAgent.create_default(
    llm_client=llm_client,
    llm_model=settings.zhipu_model,
)

# 将 Orchestrator 注入定时任务服务，替换原有的硬编码 Service 调用
scheduled_task_service.set_orchestrator(orchestrator)

@app.get("/api/agent/trace")
async def get_agent_trace(agent_name: str = "", limit: int = 10):
      """获取 Agent 执行轨迹"""
      from backend.agents.trace_store import trace_store
      if agent_name:
          records = await trace_store.get(agent_name, limit)
      else:
          records = await trace_store.get_all(limit)
      return {"records": records}


@app.get("/health")
async def health_check():
    return {"status": "ok"}

@app.post("/api/generate-content", response_model=ContentResponse)
async def generate_content(request: ContentRequest, db: Session = Depends(get_db)):
    logger.info(f"生成文案 - {len(request.content)}字")
    try:
        pipeline_result = await orchestrator.run_content_generation(content=request.content)

        if pipeline_result["status"] == "failed":
            raise Exception(pipeline_result.get("error", "Agent 管线执行失败"))

        results = {}
        for step in pipeline_result.get("steps", []):
            if step.get("step") == "生成文案" and step.get("success"):
                results = step.get("data", {})
                break

        if not results:
            results = pipeline_result.get("generated_content", {})

        filter_service = SensitiveFilter(settings.sensitive_words_file)
        sensitive_words_dict = {}
        for platform in results:
            filtered, detected = filter_service.filter(results[platform])
            results[platform] = filtered
            sensitive_words_dict[platform] = detected

        history_manager = HistoryManager(db)
        history_manager.save_record(request.content, results)

        # 生成配图
        image_url = image_generator.generate(request.content)
        if image_url:
            logger.info(f"配图生成成功 - {len(image_url)}字符URL")

        logger.info(f"文案完成 - {list(results.keys())}")
        return ContentResponse(results=results, sensitive_words=sensitive_words_dict, image_url=image_url, timestamp=datetime.utcnow())
    except Exception as e:
        logger.error(f"文案生成失败: {str(e)}", exc_info=True)
        raise

@app.get("/api/history")
async def get_history(limit: int = 10, db: Session = Depends(get_db)):
    try:
        history_manager = HistoryManager(db)
        records = history_manager.get_history(limit)
        return {"records": records}
    except Exception as e:
        logger.error(f"获取历史记录失败: {str(e)}")
        raise

@app.get("/api/history/{record_id}")
async def get_history_detail(record_id: int, db: Session = Depends(get_db)):
    try:
        history_manager = HistoryManager(db)
        record = history_manager.get_record_by_id(record_id)
        if not record:
            logger.warning(f"历史记录不存在 - ID: {record_id}")
        return record if record else {"error": "Record not found"}
    except Exception as e:
        logger.error(f"获取历史记录详情失败: {str(e)}")
        raise

@app.get("/api/hot-topics", response_model=List[HotTopicResponse])
async def get_hot_topics(platform: str = "all", limit: int = 20, db: Session = Depends(get_db)):
    try:
        query = db.query(HotTopic)
        if platform != "all":
            query = query.filter(HotTopic.platform == platform)
        return query.order_by(HotTopic.rank).limit(limit).all()
    except Exception as e:
        logger.error(f"获取热点失败: {str(e)}")
        raise

@app.post("/api/hot-topics/refresh")
async def refresh_hot_topics(platform: str = "all", db: Session = Depends(get_db)):
    logger.info(f"刷新热点 - 平台: {platform}")
    try:
        collector = orchestrator.get_agent("collector")
        result = await collector.run(AgentTask(instruction=f"请从 {platform} 平台采集热点数据", context={"limit": 20}))
        topics_data = result.output

        if platform == "all":
            db.query(HotTopic).delete()
        else:
            db.query(HotTopic).filter(HotTopic.platform == platform).delete()

        for topic_data in topics_data:
            db.add(HotTopic(**topic_data))
        db.commit()

        try:
            analyzer = HotTopicAnalyzer(db, zhipu_api_key=settings.zhipu_api_key, zhipu_model=settings.zhipu_model)
            analyzer.record_trend_snapshot()
        except Exception:
            pass

        logger.info(f"刷新完成 - {len(topics_data)} 条")
        return {"message": f"成功刷新 {len(topics_data)} 条热点", "count": len(topics_data)}
    except Exception as e:
        logger.error(f"刷新热点失败: {str(e)}", exc_info=True)
        db.rollback()
        raise

@app.post("/api/generate-from-topic")
async def generate_from_topic(topic_id: int, db: Session = Depends(get_db)):
    logger.info(f"生成文案 - 热点ID: {topic_id}")
    try:
        topic = db.query(HotTopic).filter(HotTopic.id == topic_id).first()
        if not topic:
            return {"error": "热点不存在"}

        content = f"{topic.title}\n{topic.description or ''}"
        pipeline_result = await orchestrator.run_content_generation(content=content)
        if pipeline_result["status"] == "failed":
            raise Exception(pipeline_result.get("error", "Agent 管线执行失败"))

        results = {}
        for step in pipeline_result.get("steps", []):
            if step.get("step") == "生成文案" and step.get("success"):
                results = step.get("data", {})
                break
        if not results:
            results = pipeline_result.get("generated_content", {})

        filter_service = SensitiveFilter(settings.sensitive_words_file)
        sensitive_words_dict = {}
        for platform in results:
            filtered, detected = filter_service.filter(results[platform])
            results[platform] = filtered
            sensitive_words_dict[platform] = detected

        history_manager = HistoryManager(db)
        history_manager.save_record(content, results)

        # 使用 ImagePromptAgent 将文案转为生动的画面描述
        image_prompt_agent = orchestrator.get_agent("image_prompt")
        if image_prompt_agent:
            platform_contents = {
                p: results.get(p, "")
                for p in ["weibo", "douyin", "xiaohongshu", "wechat"]
            }
            visual_desc = await image_prompt_agent.generate_prompt(topic.title, platform_contents)
            content_for_image = visual_desc if visual_desc else topic.description or ""
        else:
            # 降级：拼接文案
            content_for_image = "\n".join(filter(None, [
                results.get(p, "") for p in ["weibo", "douyin", "xiaohongshu"]
            ])) or topic.description or ""
        image_url = image_generator.generate(topic.title, content_for_image)
        if image_url:
            logger.info(f"配图生成成功")

        logger.info(f"文案完成 - {list(results.keys())}")
        return ContentResponse(results=results, sensitive_words=sensitive_words_dict, image_url=image_url, timestamp=datetime.utcnow())
    except Exception as e:
        logger.error(f"基于热点生成文案失败: {str(e)}", exc_info=True)
        raise

# ==================== 热点分析与爆款预测 ====================

@app.get("/api/analysis/trend", response_model=List[TopicTrendResponse])
async def get_topic_trends(hours: int = 24, limit: int = 10, db: Session = Depends(get_db)):
    try:
        analyzer = HotTopicAnalyzer(db, zhipu_api_key=settings.zhipu_api_key, zhipu_model=settings.zhipu_model)
        trending = analyzer.get_trending_topics(hours=hours, limit=limit)
        results = []
        for t in trending:
            trend = analyzer.get_trend(t["title"], t["platform"], hours=hours)
            if trend:
                results.append(trend)
        return results
    except Exception as e:
        logger.error(f"获取话题趋势失败: {str(e)}")
        raise

@app.get("/api/analysis/platform-compare", response_model=List[PlatformCompareResponse])
async def get_platform_compare(db: Session = Depends(get_db)):
    try:
        analyzer = HotTopicAnalyzer(db, zhipu_api_key=settings.zhipu_api_key, zhipu_model=settings.zhipu_model)
        return analyzer.get_platform_compare()
    except Exception as e:
        logger.error(f"获取平台对比失败: {str(e)}")
        raise

@app.get("/api/analysis/category-stats", response_model=List[CategoryStatResponse])
async def get_category_stats(db: Session = Depends(get_db)):
    try:
        analyzer = HotTopicAnalyzer(db, zhipu_api_key=settings.zhipu_api_key, zhipu_model=settings.zhipu_model)
        return analyzer.get_category_stats()
    except Exception as e:
        logger.error(f"获取分类统计失败: {str(e)}")
        raise

@app.get("/api/analysis/peak-hours")
async def get_peak_hours(db: Session = Depends(get_db)):
    try:
        analyzer = HotTopicAnalyzer(db, zhipu_api_key=settings.zhipu_api_key, zhipu_model=settings.zhipu_model)
        return analyzer.get_peak_hour_analysis()
    except Exception as e:
        logger.error(f"获取高峰时段分析失败: {str(e)}")
        raise

@app.post("/api/prediction/predict", response_model=ViralPredictionResponse)
async def predict_viral(request: ViralPredictionRequest, db: Session = Depends(get_db)):
    logger.info(f"爆款预测 - {request.title[:20]}")
    try:
        prediction = await orchestrator.get_agent("analyzer").predict_viral(
            title=request.title, content=request.content, platform=request.platform,
        )
        return ViralPredictionResponse(
            title=request.title, platform=request.platform,
            viral_score=prediction.get("viral_score", 50),
            confidence=prediction.get("confidence", "low"),
            peak_hour=prediction.get("peak_hour", 20),
            suggested_platform=prediction.get("suggested_platform", "weibo"),
            reasons=prediction.get("reasons", []),
            suggestions=prediction.get("suggestions", []),
        )
    except Exception as e:
        logger.error(f"爆款预测失败: {str(e)}")
        raise

@app.post("/api/prediction/batch-predict", response_model=List[ViralPredictionResponse])
async def batch_predict(topics: List[ViralPredictionRequest], db: Session = Depends(get_db)):
    logger.info(f"批量预测 - {len(topics)} 条")
    try:
        results = []
        analyzer = orchestrator.get_agent("analyzer")
        for idx, topic in enumerate(topics, 1):
            prediction = await analyzer.predict_viral(
                title=topic.title, content=topic.content, platform=topic.platform,
            )
            results.append(ViralPredictionResponse(
                title=topic.title, platform=topic.platform,
                viral_score=prediction.get("viral_score", 50),
                confidence=prediction.get("confidence", "low"),
                peak_hour=prediction.get("peak_hour", 20),
                suggested_platform=prediction.get("suggested_platform", "weibo"),
                reasons=prediction.get("reasons", []),
                suggestions=prediction.get("suggestions", []),
            ))
        return results
    except Exception as e:
        logger.error(f"批量预测失败: {str(e)}")
        raise


# ==================== Agent 技能查询 ====================


@app.get("/api/agents/skills")
async def get_all_agent_skills():
    """获取所有 Agent 的核心技能。"""
    skills = orchestrator.list_all_skills()
    return {
        "agents": [
            {
                "name": name,
                "role": getattr(orchestrator.get_agent(name), "role", ""),
                "skills": agent_skills,
            }
            for name, agent_skills in skills.items()
        ]
    }


@app.get("/api/agents/info")
async def get_all_agent_info():
    """获取所有 Agent 的元信息（含技能和工具）。"""
    return {
        "agents": [
            orchestrator.get_agent(name).to_json()
            for name in orchestrator.available_agents
        ]
    }


# ==================== 配图生成 ====================


@app.post("/api/generate-image")
async def generate_image(title: str, content: str = "", style: str = "写实摄影"):
    """为内容生成 AI 配图。"""
    try:
        image_url = image_generator.generate(title, content, style)
        if image_url:
            return {"image_url": image_url, "success": True}
        return {"error": "配图生成失败", "success": False}
    except Exception as e:
        logger.error(f"配图生成失败: {str(e)}")
        return {"error": str(e), "success": False}


# ==================== 定时任务监控 ====================

@app.get("/api/scheduled-task/status")
async def get_scheduled_task_status(db: Session = Depends(get_db)):
    """获取定时任务状态"""
    last_run = scheduled_task_service.get_last_run(db)
    return {
        "is_running": scheduled_task_service._running,
        "last_run": last_run
    }


@app.get("/api/scheduled-task/history")
async def get_scheduled_task_history(limit: int = 10,
                                      db: Session = Depends(get_db)):
    """获取定时任务运行历史"""
    return scheduled_task_service.get_run_history(db, limit=limit)


@app.post("/api/scheduled-task/trigger")
async def trigger_scheduled_task():
    """手动触发定时任务"""
    if scheduled_task_service._running:
        return {"message": "任务正在运行中，请等待完成", "status": "already_running"}
    asyncio.create_task(scheduled_task_service.run_auto_generate())
    return {"message": "任务已触发", "status": "started"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8001)
