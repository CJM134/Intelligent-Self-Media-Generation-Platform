from __future__ import annotations
import inspect
import logging
from typing import Any, Callable, Dict, Optional, get_type_hints

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class Tool(BaseModel):
    """工具是 Agent 能力的原子单元。

    每个工具包含三要素：
    - name: 工具名（Agent 通过这个名字调用它）
    - description: 用自然语言描述「什么时候用、怎么用」（LLM 通过这个决定是否使用）
    - parameters: JSON Schema 格式的参数描述
    - func: 实际执行的 Python 函数
    """
    name: str = Field(description="工具名称，Agent 通过此名称调用")
    description: str = Field(description="工具描述，LLM 据此决定何时使用")
    parameters: Dict[str, Any] = Field(
        default_factory=dict,
        description="参数 JSON Schema"
    )
    func: Callable = Field(exclude=True, description="实际执行的函数")

    class Config:
        arbitrary_types_allowed = True

    @classmethod
    def from_function(cls,
                      fn: Callable,
                      name: Optional[str] = None,
                      description: Optional[str] = None) -> "Tool":
        """从普通 Python 函数自动生成 Tool。

        自动提取函数名、docstring 和参数类型信息，免去手动写 Schema。
        """
        tool_name = name or fn.__name__
        tool_desc = description or fn.__doc__ or "无描述"

        # 从函数签名自动推断参数 schema
        sig = inspect.signature(fn)
        hints = get_type_hints(fn)
        properties = {}
        required = []

        for param_name, param in sig.parameters.items():
            if param_name == "self" or param_name == "cls":
                continue

            param_type = hints.get(param_name, str)
            # 简化类型映射
            type_map = {
                str: {"type": "string"},
                int: {"type": "integer"},
                float: {"type": "number"},
                bool: {"type": "boolean"},
                dict: {"type": "object"},
                list: {"type": "array"},
            }
            schema = type_map.get(param_type, {"type": "string"})

            if param.default is inspect.Parameter.empty:
                required.append(param_name)
            else:
                schema["default"] = param.default

            properties[param_name] = schema

        parameters = {
            "type": "object",
            "properties": properties,
        }
        if required:
            parameters["required"] = required

        return cls(
            name=tool_name,
            description=tool_desc,
            parameters=parameters,
            func=fn,
        )

    async def execute(self, **kwargs) -> Any:
        """执行工具函数。支持同步和异步函数。"""
        logger.info(f"[Tool] 执行 {self.name} - 参数: {kwargs}")
        try:
            if inspect.iscoroutinefunction(self.func):
                result = await self.func(**kwargs)
            else:
                result = self.func(**kwargs)
            logger.info(f"[Tool] {self.name} 执行成功")
            return result
        except Exception as e:
            logger.error(f"[Tool] {self.name} 执行失败: {str(e)}")
            raise

    def to_llm_description(self) -> Dict[str, Any]:
        """转成 OpenAI Function Calling 格式的描述，用于 LLM 函数调用。"""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            }
        }
