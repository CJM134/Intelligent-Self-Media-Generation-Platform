import logging
from typing import Optional

logger = logging.getLogger(__name__)


class ImageGenerator:
    """AI 配图生成器。

    使用智谱 AI CogView 模型为文案生成配图。
    支持真实 API 调用和本地 mock 两种模式。
    """

    def __init__(self, zhipu_client=None, save_dir: str = "data/images"):
        self._client = zhipu_client
        self._save_dir = save_dir

    def generate(self, title: str, content: str = "",
                 style: str = "写实摄影") -> Optional[str]:
        """为话题生成配图。

        Args:
            title: 话题标题
            content: 话题内容/描述
            style: 图片风格（写实摄影 / 插画 / 3D渲染 / 水彩等）

        Returns:
            图片 URL（远程 URL 或本地路径），生成失败返回 None
        """
        image_prompt = self._build_prompt(title, content, style)

        if self._client:
            return self._call_api(image_prompt, title)

        logger.info("[ImageGenerator] 无 API 客户端，使用占位图")
        return None

    def _build_prompt(self, title: str, content: str, style: str) -> str:
        """构建给 AI 绘图模型的 prompt。"""
        text = f"{title}。{content}" if content else title
        return (
            f"{style}风格。{text}"
            f"。画面干净，构图专业，适合作为新媒体内容的配图，无文字。"
        )

    def _call_api(self, prompt: str, title: str) -> Optional[str]:
        """调用智谱 AI CogView 生成图片。

        ZhipuAI SDK 2.x 图片生成 API：
            client.images.generations(model="cogview-3-plus", prompt="...")

        返回格式：ImagesResponded(data=[ImageField(url="...")])
        """
        try:
            response = self._client.images.generations(
                model="cogview-3-plus",
                prompt=prompt,
            )
            # 智谱AI 返回格式：data 是列表，每项有 url 字段
            if hasattr(response, "data") and response.data:
                for item in response.data:
                    url = getattr(item, "url", None)
                    if url:
                        logger.info(f"[ImageGenerator] 生成成功 - {title[:20]}")
                        return url

            logger.warning(f"[ImageGenerator] 返回数据无有效 URL: {response}")
            return None

        except Exception as e:
            logger.error(f"[ImageGenerator] API 调用失败: {str(e)[:100]}")
            return None


# 全局单例（由 main.py 在启动时配置）
image_generator = ImageGenerator()


def init_image_generator(zhipu_client=None):
    """配置全局 ImageGenerator（更新引用而非替换，保证已有 import 生效）。"""
    image_generator._client = zhipu_client
    status = "已配置" if zhipu_client else "未配置"
    logger.info(f"[ImageGenerator] 初始化完成 - API: {status}")
    return image_generator
