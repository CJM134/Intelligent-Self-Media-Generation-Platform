import logging
from typing import Optional

import httpx

logger = logging.getLogger(__name__)


class ImageGenerator:
    """AI 配图生成器。

    支持后端：
      - jimeng: 火山引擎 Ark（豆包 Seedream），同步返回图片 URL
      - cogview: 智谱 AI CogView（兼容保留）

    配置来源：
      1. `__init__` 传参（优先级高，适合测试覆盖）
      2. `.env` 文件（`ImageGenerator` 内部直接读取，省去 main.py 传递）
    """

    def __init__(self, backend: str = "jimeng",
                 api_key: Optional[str] = None,
                 api_base: Optional[str] = None,
                 endpoint: Optional[str] = None,
                 save_dir: str = "data/images"):
        self._backend = backend
        self._save_dir = save_dir
        self._client = None

        # 优先用传参，fallback 到 .env 配置
        try:
            from backend.config import settings as _cfg
            self._api_key = api_key or _cfg.jimeng_api_key or None
            self._api_base = api_base or _cfg.jimeng_api_base or "https://ark.cn-beijing.volces.com"
            self._endpoint = endpoint or _cfg.jimeng_endpoint or None
        except Exception:
            self._api_key = api_key
            self._api_base = api_base or "https://ark.cn-beijing.volces.com"
            self._endpoint = endpoint

        _key_status = "已配置" if self._api_key else "未配置"
        _ep_status = self._endpoint or "未配置"
        logger.info(f"[ImageGenerator] 初始化 - backend={backend} | "
                     f"API Key={_key_status} | Endpoint={_ep_status}")

    def generate(self, title: str, content: str = "",
                 style: str = "写实摄影") -> Optional[str]:
        """为话题生成配图。"""
        image_prompt = self._build_prompt(title, content, style)

        logger.info(f"[ImageGenerator] generate() 调用 - title={title[:20]}, "
                     f"style={style}, backend={self._backend}, "
                     f"has_key={bool(self._api_key)}, has_endpoint={bool(self._endpoint)}")

        if self._backend == "jimeng":
            if not self._api_key:
                logger.error("[ImageGenerator] 生成失败: API Key 未配置，请检查 .env 中的 JIMENG_API_KEY")
                return None
            if not self._endpoint:
                logger.error("[ImageGenerator] 生成失败: Endpoint 未配置，请检查 .env 中的 JIMENG_ENDPOINT")
                return None
            result = self._call_jimeng(image_prompt, title)
            if result:
                logger.info(f"[ImageGenerator] 生成成功 - {title[:20]}")
            else:
                logger.warning(f"[ImageGenerator] 生成失败（返回 None）- {title[:20]}")
            return result

        if self._client:
            return self._call_cogview(image_prompt, title)

        logger.warning("[ImageGenerator] 未配置任何后端，跳过图片生成")
        return None

    def _build_prompt(self, title: str, content: str, style: str) -> str:
        """构建详细的绘图 prompt，包含主体、场景、构图、光线、氛围描述。

        content 应为来自 ImagePromptAgent 的干净视觉描述文本。
        """
        text = f"{title}。{content}" if content else title

        # 根据不同风格调整描述侧重点
        style_descriptions = {
            "写实摄影": "写实摄影风格，真实自然的光影质感，细节丰富，景深适中",
            "插画": "插画风格，色彩明快，线条柔美，梦幻氛围",
            "3D渲染": "3D渲染风格，立体感强，光影质感细腻，材质真实",
            "水彩": "水彩画风格，色彩晕染自然，画面清新淡雅，留白得当",
            "油画": "油画风格，笔触明显，色彩浓郁厚重，质感强烈",
            "国风": "国风手绘风格，水墨意境，留白考究，古典雅致",
        }
        style_desc = style_descriptions.get(style, f"{style}风格")

        return (
            f"{style_desc}。"
            f"画面主体：{text}"
            f"。构图：主体突出，画面干净，留白舒适。"
            f"光线：柔和自然，层次分明。"
            f"色彩：整体色调和谐统一，符合{style}风格特点。"
            f"额外要求：绝对不要出现任何文字、水印、Logo，"
            f"整体风格适合新媒体平台发布的高清配图。"
        )

    # ==================== 火山引擎 Ark（豆包 Seedream） ====================

    def _call_jimeng(self, prompt: str, title: str) -> Optional[str]:
        """调用火山引擎 Ark 图片生成 API（同步返回）。"""
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self._endpoint,
            "prompt": prompt,
            "size": "1920x1920",
            "n": 1,
        }
        # Seedream 5.0 最低要求 1920x1920（约 370 万像素）
        # 如需更高质量可开启 hd 模式

        api_url = f"{self._api_base}/api/v3/images/generations"
        logger.info(f"[ImageGenerator] 请求详情: endpoint={self._endpoint}, "
                     f"url={api_url}, prompt_len={len(prompt)}")
        logger.info(f"[ImageGenerator] 实际发送的 prompt: {prompt}")

        try:
            with httpx.Client(timeout=120) as client:
                logger.info(f"[ImageGenerator] 发送请求 - {title[:20]}")
                resp = client.post(api_url, headers=headers, json=payload)
                logger.info(f"[ImageGenerator] 响应状态码: {resp.status_code}")

                if resp.status_code == 401:
                    logger.error(f"[ImageGenerator] 认证失败: API Key 无效或被拒绝")
                    return None
                if resp.status_code == 402:
                    logger.error(f"[ImageGenerator] 余额不足: 账户需要充值")
                    return None
                if resp.status_code == 429:
                    logger.error(f"[ImageGenerator] 请求超限: 触发频率限制")
                    return None
                if resp.status_code == 400:
                    err_body = resp.json()
                    err_code = err_body.get("error", {}).get("code", "")
                    err_msg = err_body.get("error", {}).get("message", "")
                    if "SensitiveContent" in err_code:
                        logger.warning(f"[ImageGenerator] 内容被安全审核拦截，已跳过 "
                                       f"(适用于不含敏感词的内容) - {title[:20]}")
                        return None
                    logger.warning(f"[ImageGenerator] 请求被拒: code={err_code}, message={err_msg} - {title[:20]}")
                    return None

                resp.raise_for_status()
                data = resp.json()

                images = data.get("data", [])
                if images:
                    url = images[0].get("url", "")
                    if url:
                        logger.info(f"[ImageGenerator] 生成成功 - {title[:20]}, url_len={len(url)}")
                        return url

                logger.warning(f"[ImageGenerator] API 返回成功但无图片 URL: {data.get('model', '?')}")
                return None

        except httpx.HTTPStatusError as e:
            logger.error(f"[ImageGenerator] HTTP {e.response.status_code}: {e.response.text[:300]}")
            return None
        except httpx.RequestError as e:
            logger.error(f"[ImageGenerator] 网络请求失败: {str(e)}")
            return None
        except Exception as e:
            logger.error(f"[ImageGenerator] 未知异常: {str(e)[:200]}")
            return None

    # ==================== CogView（同步模式，旧） ====================

    def _call_cogview(self, prompt: str, title: str) -> Optional[str]:
        """调用智谱 AI CogView 生成图片。"""
        try:
            response = self._client.images.generations(
                model="cogview-3-plus",
                prompt=prompt,
            )
            if hasattr(response, "data") and response.data:
                for item in response.data:
                    url = getattr(item, "url", None)
                    if url:
                        logger.info(f"[ImageGenerator] CogView 生成成功 - {title[:20]}")
                        return url
            logger.warning(f"[ImageGenerator] CogView 返回无有效 URL")
            return None
        except Exception as e:
            logger.error(f"[ImageGenerator] CogView 调用失败: {str(e)[:100]}")
            return None


# ==================== 全局单例 & 初始化 ====================

image_generator = ImageGenerator(
    backend="jimeng",
    api_key=None,  # 启动时通过 init_image_generator 配置
)


def init_image_generator(backend: str = "jimeng",
                          api_key: Optional[str] = None,
                          api_base: Optional[str] = None,
                          endpoint: Optional[str] = None,
                          zhipu_client=None) -> ImageGenerator:
    """配置全局 ImageGenerator（已自动读取 .env，此函数仅用于覆盖默认值）。"""
    if api_key:
        image_generator._api_key = api_key
    if api_base:
        image_generator._api_base = api_base
    if endpoint:
        image_generator._endpoint = endpoint
    if zhipu_client:
        image_generator._client = zhipu_client
    image_generator._backend = backend

    logger.info(f"[ImageGenerator] 更新配置 - backend={backend} | "
                 f"API Key={'已配置' if image_generator._api_key else '未配置'} | "
                 f"Endpoint={image_generator._endpoint or '未配置'}")
    return image_generator
