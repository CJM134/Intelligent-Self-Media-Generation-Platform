from typing import Dict, List, Any, Optional
import asyncio


class TraceStore:
    """Agent 执行轨迹存储（内存）。"""

    def __init__(self, max_per_agent: int = 100):
        self._traces: Dict[str, List[Dict]] = {}
        self._max = max_per_agent
        self._lock = asyncio.Lock()

    async def save(self, agent_name: str, trace: Dict) -> None:
        """保存一条 Agent 执行记录"""
        async with self._lock:
            if agent_name not in self._traces:
                self._traces[agent_name] = []
            self._traces[agent_name].append(trace)
            # 超出上限，删最旧的
            if len(self._traces[agent_name]) > self._max:
                self._traces[agent_name].pop(0)

    async def get(self, agent_name: str, limit: int = 10) -> List[Dict]:
        """获取指定 Agent 的最近 N 条记录"""
        async with self._lock:
            records = self._traces.get(agent_name, [])
            return records[-limit:]

    async def get_all(self, limit: int = 10) -> List[Dict]:
        """获取所有 Agent 的最近记录（包含 agent_name 字段）"""
        async with self._lock:
            all_records = []
            for name, records in self._traces.items():
                for r in records[-limit:]:
                    all_records.append({"agent_name": name, **r})
            # 按时间倒序
            all_records.sort(key=lambda x: x.get("task_id", ""), reverse=True)
            return all_records[:limit]

    async def clear(self, agent_name: Optional[str] = None) -> None:
        """清空，不传 agent_name 则清空全部"""
        async with self._lock:
            if agent_name:
                self._traces.pop(agent_name, None)
            else:
                self._traces.clear()


# 全局单例
trace_store = TraceStore()
