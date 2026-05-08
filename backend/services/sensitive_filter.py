import os
from typing import Tuple, List
import logging

logger = logging.getLogger(__name__)


class SensitiveFilter:
    def __init__(self, words_file: str):
        self.sensitive_words = self._load_words(words_file)

    def _load_words(self, words_file: str) -> List[str]:
        if not os.path.exists(words_file):
            logger.warning(f"敏感词库文件不存在: {words_file}")
            return []
        with open(words_file, 'r', encoding='utf-8') as f:
            return [line.strip() for line in f if line.strip()]

    def filter(self, text: str) -> Tuple[str, List[str]]:
        detected = []
        filtered = text
        for word in self.sensitive_words:
            if word in text:
                detected.append(word)
                filtered = filtered.replace(word, "*" * len(word))
        if detected:
            logger.info(f"过滤到敏感词: {detected}")
        return filtered, detected

    def has_sensitive_words(self, text: str) -> bool:
        for word in self.sensitive_words:
            if word in text:
                return True
        return False
