import asyncio
import json
import logging
from datetime import datetime
from typing import List, Dict, Optional
from sqlalchemy.orm import Session

from backend.config import settings
from backend.models.database import SessionLocal, HotTopic, HotTopicTrend, ScheduledTaskRun, ContentHistory
from backend.services.sensitive_filter import SensitiveFilter
from backend.services.image_generator import image_generator
from backend.agents import AgentTask

logger = logging.getLogger(__name__)


class ScheduledTaskService:
    """定时任务服务：每2小时自动抓取热点、生成文案、预测下一个热点"""

    def __init__(self):
        self._running = False
        self._task = None
        self.orchestrator = None  # 由 main.py 在启动后注入

    def set_orchestrator(self, orchestrator) -> None:
        self.orchestrator = orchestrator

    async def run_auto_generate(self):
        if self._running:
            logger.warning("定时任务已在运行，跳过")
            return

        if not self.orchestrator:
            logger.error("Orchestrator 未注入，跳过")
            return

        self._running = True

        run_log_id = self._create_run_log()
        if run_log_id is None:
            self._running = False
            return

        try:
            logger.info("[ScheduledTask] 开始执行")

            collector = self.orchestrator.get_agent("collector")
            douyin_task = AgentTask(instruction="请从 douyin 平台采集热点数据", context={"limit": 10})
            weibo_task = AgentTask(instruction="请从 weibo 平台采集热点数据", context={"limit": 10})

            douyin_result = await collector.run(douyin_task)
            weibo_result = await collector.run(weibo_task)

            all_topics = []
            if douyin_result.success and douyin_result.output:
                all_topics.extend(douyin_result.output)
            if weibo_result.success and weibo_result.output:
                all_topics.extend(weibo_result.output)

            self._save_topics_to_db(all_topics)

            topics_for_generate = sorted(all_topics, key=lambda x: x.get("heat_score", 0), reverse=True)[:5]

            generated_count, generated_summaries = await self._batch_generate_content(topics_for_generate)

            analyzer = self.orchestrator.get_agent("analyzer")
            prediction = await self._predict_with_agent(analyzer, topics_for_generate)
            prediction["generated_contents"] = generated_summaries

            self._finish_run_log(run_log_id, "success", len(all_topics),
                                 generated_count, prediction)

            logger.info(f"[ScheduledTask] 完成 - {len(all_topics)}条话题, {generated_count}组文案")

        except Exception as e:
            logger.error(f"定时任务失败: {str(e)}", exc_info=True)
            self._finish_run_log(run_log_id, "failed", 0, 0,
                                 {"error": str(e)[:500]})
        finally:
            self._running = False

    # ==================== 数据库短连接辅助 ====================

    def _create_run_log(self) -> Optional[int]:
        try:
            db = SessionLocal()
            run_log = ScheduledTaskRun(task_type="auto_generate", status="running", started_at=datetime.utcnow())
            db.add(run_log)
            db.commit()
            run_id = run_log.id
            db.close()
            return run_id
        except Exception as e:
            logger.error(f"创建运行记录失败: {str(e)}")
            return None

    def _save_topics_to_db(self, topics: List[Dict]) -> None:
        try:
            db = SessionLocal()
            db.query(HotTopic).filter(HotTopic.platform.in_(["douyin", "weibo"])).delete()
            for topic_data in topics:
                db.add(HotTopic(**topic_data))
            for topic_data in topics:
                db.add(HotTopicTrend(
                    title=topic_data.get("title", ""),
                    platform=topic_data.get("platform", ""),
                    heat_score=topic_data.get("heat_score", 0),
                    rank=topic_data.get("rank", 0),
                    tags=topic_data.get("tags", ""),
                    recorded_at=datetime.utcnow(),
                ))
            db.commit()
            db.close()
        except Exception as e:
            logger.error(f"保存热点失败: {str(e)}")
            raise

    def _finish_run_log(self, run_id: int, status: str,
                         topics_fetched: int, contents_generated: int,
                         prediction: dict) -> None:
        try:
            db = SessionLocal()
            run_log = db.query(ScheduledTaskRun).filter(ScheduledTaskRun.id == run_id).first()
            if run_log:
                run_log.status = status
                run_log.topics_fetched = topics_fetched
                run_log.contents_generated = contents_generated
                run_log.prediction = json.dumps(prediction, ensure_ascii=False)
                run_log.error_message = prediction.get("error") if status == "failed" else None
                run_log.finished_at = datetime.utcnow()
                db.commit()
            db.close()
        except Exception as e:
            logger.error(f"更新运行记录失败: {str(e)}")

    # ==================== 批量生成文案 ====================

    async def _batch_generate_content(self, topics: List[Dict]) -> tuple:
        """使用 WriterAgent 为所有热点生成文案。

        Returns:
            (count: int, summaries: list[dict]) — 数量和生成内容摘要
        """
        writer = self.orchestrator.get_agent("writer")
        semaphore = asyncio.Semaphore(3)  # 控制并发
        count = 0
        summaries = []

        async def generate_one(topic: Dict):
            nonlocal count
            async with semaphore:
                try:
                    title = topic.get("title", "")
                    desc = topic.get("description", "")
                    content = f"{title}\n{desc}" if desc else title

                    if len(content) < 5:
                        return

                    results = await writer.generate_for_platforms(content)
                    if not results:
                        return

                    # 敏感词过滤
                    filter_service = SensitiveFilter(settings.sensitive_words_file)
                    for platform in results:
                        filtered, _ = filter_service.filter(results[platform])
                        results[platform] = filtered

                    # 存入历史记录
                    db = SessionLocal()
                    try:
                        # 使用 ImagePromptAgent 将文案转为生动的画面描述
                        image_prompt_agent = self.orchestrator.get_agent("image_prompt")
                        if image_prompt_agent:
                            platform_contents = {
                                p: results.get(p, "")
                                for p in ["weibo", "douyin", "xiaohongshu", "wechat"]
                            }
                            visual_desc = await image_prompt_agent.generate_prompt(title, platform_contents)
                            content_for_image = visual_desc if visual_desc else desc
                        else:
                            # 降级：拼接文案
                            content_for_image = "\n".join(filter(None, [
                                results.get(p, "") for p in ["weibo", "douyin", "xiaohongshu"]
                            ])) or desc
                        image_url = image_generator.generate(title, content_for_image)

                        record = ContentHistory(
                            original_content=content,
                            xiaohongshu_content=results.get("xiaohongshu"),
                            douyin_content=results.get("douyin"),
                            wechat_content=results.get("wechat"),
                            weibo_content=results.get("weibo"),
                            image_url=image_url,
                            created_at=datetime.utcnow()
                        )
                        db.add(record)
                        db.commit()
                        count += 1
                    finally:
                        db.close()

                    # 收集摘要：标题 + 各平台完整文案
                    summaries.append({
                        "title": title[:50],
                        "image_url": image_url,
                        "platforms": list(results.keys()),
                        "previews": {
                            p: (results[p] or "")
                            for p in results
                        },
                    })

                except Exception as e:
                    logger.warning(f"生成失败 [{topic.get('title', '?')[:20]}]: {str(e)[:50]}")

        tasks = [generate_one(t) for t in topics]
        await asyncio.gather(*tasks)
        return count, summaries

    # ==================== 预测 ====================

    async def _predict_with_agent(self, analyzer, topics: List[Dict]) -> Dict:
        """使用 AnalyzerAgent 预测下一个热点。"""
        hot_titles = [t.get("title", "") for t in topics[:5] if t.get("title")]
        return await analyzer.predict_next_topic(hot_titles)

    # ==================== 查询运行状态 ====================

    def get_last_run(self, db: Session) -> Optional[Dict]:
        """获取最近一次运行记录"""
        record = db.query(ScheduledTaskRun).filter(
            ScheduledTaskRun.task_type == "auto_generate"
        ).order_by(ScheduledTaskRun.started_at.desc()).first()

        if not record:
            return None

        return {
            "id": record.id,
            "status": record.status,
            "topics_fetched": record.topics_fetched,
            "contents_generated": record.contents_generated,
            "prediction": json.loads(record.prediction) if record.prediction else None,
            "error_message": record.error_message,
            "started_at": record.started_at.isoformat() if record.started_at else None,
            "finished_at": record.finished_at.isoformat() if record.finished_at else None,
        }

    def get_run_history(self, db: Session, limit: int = 10) -> List[Dict]:
        """获取运行历史"""
        records = db.query(ScheduledTaskRun).filter(
            ScheduledTaskRun.task_type == "auto_generate"
        ).order_by(ScheduledTaskRun.started_at.desc()).limit(limit).all()

        return [
            {
                "id": r.id,
                "status": r.status,
                "topics_fetched": r.topics_fetched,
                "contents_generated": r.contents_generated,
                "prediction": json.loads(r.prediction) if r.prediction else None,
                "error_message": r.error_message,
                "started_at": r.started_at.isoformat() if r.started_at else None,
                "finished_at": r.finished_at.isoformat() if r.finished_at else None,
            }
            for r in records
        ]


# 全局单例
scheduled_task_service = ScheduledTaskService()
