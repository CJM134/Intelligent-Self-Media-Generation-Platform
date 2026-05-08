from sqlalchemy.orm import Session
from backend.models.database import ContentHistory
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class HistoryManager:
    def __init__(self, db: Session):
        self.db = db

    def save_record(self, original_content: str, results: dict,
                     image_url: str = None) -> ContentHistory:
        record = ContentHistory(
            original_content=original_content,
            xiaohongshu_content=results.get("xiaohongshu"),
            douyin_content=results.get("douyin"),
            wechat_content=results.get("wechat"),
            weibo_content=results.get("weibo"),
            image_url=image_url,
            created_at=datetime.utcnow()
        )
        self.db.add(record)
        self.db.commit()
        self.db.refresh(record)
        return record

    def get_history(self, limit: int = 10) -> list:
        return self.db.query(ContentHistory).order_by(
            ContentHistory.created_at.desc()
        ).limit(limit).all()

    def get_record_by_id(self, record_id: int) -> ContentHistory:
        return self.db.query(ContentHistory).filter(
            ContentHistory.id == record_id
        ).first()

    def delete_record(self, record_id: int) -> bool:
        record = self.get_record_by_id(record_id)
        if record:
            self.db.delete(record)
            self.db.commit()
            return True
        return False
