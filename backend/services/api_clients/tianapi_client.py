import requests
from typing import List, Dict, Optional
from datetime import datetime
import time
import logging

logger = logging.getLogger(__name__)


class TianAPIClient:
    """天聚数行API客户端"""

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://apis.tianapi.com"
        self.timeout = 10
        logger.info("天聚数行API客户端初始化完成")

    def get_weibo_hot(self, num: int = 10) -> List[Dict]:
        """
        获取微博热搜榜

        Args:
            num: 返回数量，默认10，最大20

        Returns:
            热搜列表
        """
        url = f"{self.base_url}/weibohot/index"
        params = {
            "key": self.api_key,
            "num": min(num, 10)
        }
        logger.info(f"请求微博热搜榜 - 数量: {min(num, 10)}")

        try:
            response = requests.get(url, params=params, timeout=self.timeout)
            response.raise_for_status()
            data = response.json()

            if data.get("code") == 200:
                hot_list = data.get("result", {}).get("list", [])
                logger.info(f"微博热搜API返回成功 - 获取到 {len(hot_list)} 条数据")
                return self._format_weibo_data(hot_list[:num])
            else:
                error_msg = data.get('msg', '未知错误')
                logger.error(f"微博热搜API返回错误: {error_msg}")
                raise Exception(f"API返回错误: {error_msg}")

        except requests.exceptions.RequestException as e:
            logger.error(f"微博热搜API请求异常: {str(e)}")
            raise Exception(f"微博热搜API调用失败: {str(e)}")

    def get_douyin_hot(self, num: int = 10, hot_type: int = 0) -> List[Dict]:
        """
        获取抖音热搜榜

        Args:
            num: 返回数量，默认20
            hot_type: 榜单类型 0-综合榜 1-娱乐榜 2-社会榜

        Returns:
            热搜列表
        """
        url = f"{self.base_url}/douyinhot/index"
        params = {
            "key": self.api_key,
            "type": hot_type
        }
        logger.info(f"请求抖音热搜榜 - 数量: {num}, 榜单类型: {hot_type}")

        try:
            response = requests.get(url, params=params, timeout=self.timeout)
            response.raise_for_status()
            data = response.json()

            if data.get("code") == 200:
                hot_list = data.get("result", {}).get("list", [])
                logger.info(f"抖音热搜API返回成功 - 获取到 {len(hot_list)} 条数据")
                return self._format_douyin_data(hot_list[:num])
            else:
                error_msg = data.get('msg', '未知错误')
                logger.error(f"抖音热搜API返回错误: {error_msg}")
                raise Exception(f"API返回错误: {error_msg}")

        except requests.exceptions.RequestException as e:
            logger.error(f"抖音热搜API请求异常: {str(e)}")
            raise Exception(f"抖音热搜API调用失败: {str(e)}")

    def _format_weibo_data(self, hot_list: List[Dict]) -> List[Dict]:
        """格式化微博热搜数据"""
        logger.info(f"格式化 {len(hot_list)} 条微博热搜数据")
        formatted_list = []
        for idx, item in enumerate(hot_list, 1):
            # 处理热度值（可能包含空格）
            hotwordnum = str(item.get("hotwordnum", "0")).strip()
            try:
                heat_score = float(hotwordnum)
            except ValueError:
                heat_score = 0.0

            hottag = item.get("hottag", "热")
            formatted_list.append({
                "platform": "weibo",
                "title": item.get("hotword", ""),
                "description": f"微博热搜 - {hottag if hottag else '热'}",
                "heat_score": heat_score,
                "rank": idx,
                "tags": f"微博,{hottag if hottag else '热搜'}",
                "url": f"https://s.weibo.com/weibo?q={item.get('hotword', '')}",
                "fetched_at": datetime.utcnow()
            })
        logger.info(f"微博数据格式化完成 - 共 {len(formatted_list)} 条")
        return formatted_list

    def _format_douyin_data(self, hot_list: List[Dict]) -> List[Dict]:
        """格式化抖音热搜数据"""
        logger.info(f"格式化 {len(hot_list)} 条抖音热搜数据")

        label_map = {0: "综合", 1: "娱乐", 2: "社会", 3: "热搜"}
        formatted_list = []
        for idx, item in enumerate(hot_list, 1):
            word = item.get("word", "")
            hotindex = item.get("hotindex", 0)
            label = label_map.get(item.get("label"), "热搜")

            formatted_list.append({
                "platform": "douyin",
                "title": word,
                "description": f"抖音{label} - 热度 {hotindex}",
                "heat_score": float(hotindex),
                "rank": idx,
                "tags": f"抖音,{label}",
                "url": "https://www.douyin.com/hot",
                "fetched_at": datetime.utcnow()
            })
        logger.info(f"抖音数据格式化完成 - 共 {len(formatted_list)} 条")
        return formatted_list