import logging
from zhipuai import ZhipuAI
from typing import Dict
import os

logger = logging.getLogger(__name__)


class ContentGenerator:
    def __init__(self, api_key: str, model: str = "glm-4-plus"):
        logger.info("初始化文案生成器...")
        # 初始化智谱AI客户端
        self.client = ZhipuAI(api_key=api_key)
        # 支持的平台列表
        self.platforms = ["xiaohongshu", "douyin", "wechat", "weibo"]
        # 模型名称
        self.model = model
        # 获取当前文件所在目录
        self.base_dir = os.path.dirname(os.path.abspath(__file__))
        logger.info(f"文案生成器初始化完成 - 模型: {model}, 平台: {', '.join(self.platforms)}")

    def generate(self, original_content: str) -> Dict[str, str]:
        logger.info(f"开始生成多平台文案 - 原始内容长度: {len(original_content)} 字符")
        results = {}
        for platform in self.platforms:
            logger.info(f"正在为 [{platform}] 平台生成文案...")
            prompt = self._load_prompt(platform)
            result = self._call_ai(original_content, prompt)
            results[platform] = result
            logger.info(f"[{platform}] 文案生成完成 - 长度: {len(result)} 字符")
        logger.info(f"所有平台文案生成完毕 - 共 {len(results)} 个平台")
        return results

    def _load_prompt(self, platform: str) -> str:
        prompt_file = os.path.join(self.base_dir, "..", "prompts", f"{platform}.txt")
        if os.path.exists(prompt_file):
            with open(prompt_file, 'r', encoding='utf-8') as f:
                content = f.read()
            logger.info(f"已加载 [{platform}] 平台提示词模板 - 长度: {len(content)} 字符")
            return content
        logger.warning(f"[{platform}] 提示词模板文件不存在，使用默认提示词")
        return f"请将以下内容改写为适合{platform}的文案"

    def _call_ai(self, content: str, prompt: str) -> str:
        logger.info(f"调用智谱AI API - 模型: {self.model}")
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "user",
                        "content": f"{prompt}\n\n原始内容：\n{content}"
                    }
                ]
            )
            result = response.choices[0].message.content
            logger.info(f"智谱AI API调用成功 - 返回长度: {len(result)} 字符")
            return result
        except Exception as e:
            logger.error(f"智谱AI API调用失败: {str(e)}")
            raise ValueError(
                f"智谱AI API调用失败：{str(e)}\n"
                "请检查API key是否正确，账户是否有足够额度。"
            )
