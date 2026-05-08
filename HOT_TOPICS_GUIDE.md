# 热点跟踪功能使用指南

## 功能概述

热点跟踪功能可以帮助你从抖音、微博、小红书等平台获取当前热门话题，并基于这些热点快速生成适合各平台的营销文案。

## 主要特性

### 1. 多平台热点获取
- **抖音** 🎵：获取抖音平台的热门话题
- **微博** 📱：获取微博平台的热搜话题
- **小红书** 📕：获取小红书平台的热门内容

### 2. 热点信息展示
每条热点包含以下信息：
- 排名：热点在平台上的排名
- 标题：热点话题的标题
- 描述：热点的详细描述
- 标签：相关话题标签
- 热度值：话题的热度分数

### 3. 一键生成文案
点击任意热点的"生成文案"按钮，系统会自动：
- 基于热点内容生成适合各平台的文案
- 同时生成小红书、抖音、公众号、微博四个平台的版本
- 自动过滤敏感词
- 保存到历史记录

## 使用步骤

### 1. 启动应用

使用启动脚本：
```bash
# Windows
start.bat

# 或手动启动
# 终端1：启动后端
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload

# 终端2：启动前端
streamlit run frontend/app.py
```

### 2. 访问热点跟踪页面

1. 打开浏览器访问 `http://localhost:8501`
2. 点击顶部的 **"🔥 热点跟踪"** 标签页

### 3. 获取热点数据

1. 选择要查看的平台：
   - 全部平台
   - 抖音
   - 微博
   - 小红书

2. 点击 **"🔄 刷新热点"** 按钮获取最新热点数据

### 4. 生成文案

1. 浏览热点列表，找到感兴趣的话题
2. 点击该热点右侧的 **"生成文案"** 按钮
3. 等待几秒钟，系统会自动生成四个平台的文案
4. 生成的文案会显示在页面下方，可以直接复制使用

## API 接口说明

### 获取热点列表
```
GET /api/hot-topics?platform={platform}&limit={limit}
```
参数：
- `platform`: 平台名称（all/douyin/weibo/xiaohongshu）
- `limit`: 返回数量限制（默认20）

### 刷新热点数据
```
POST /api/hot-topics/refresh?platform={platform}
```
参数：
- `platform`: 要刷新的平台（all/douyin/weibo/xiaohongshu）

### 基于热点生成文案
```
POST /api/generate-from-topic?topic_id={topic_id}
```
参数：
- `topic_id`: 热点话题的ID

## 数据库结构

热点数据存储在 `hot_topics` 表中：
- `id`: 热点ID
- `platform`: 平台来源
- `title`: 热点标题
- `description`: 热点描述
- `heat_score`: 热度值
- `rank`: 排名
- `tags`: 话题标签
- `url`: 原始链接
- `fetched_at`: 抓取时间
- `created_at`: 创建时间

## 扩展说明

### 接入真实API

当前版本使用模拟数据。要接入真实的平台API，需要：

1. 修改 `backend/services/hot_topic_fetcher.py`
2. 在 `_fetch_platform_topics` 方法中添加真实API调用
3. 配置相应平台的API密钥

示例：
```python
def _fetch_platform_topics(self, platform: str, limit: int):
    if platform == "douyin":
        # 调用抖音开放平台API
        return self._fetch_douyin_api(limit)
    elif platform == "weibo":
        # 调用微博开放平台API
        return self._fetch_weibo_api(limit)
    # ...
```

### 定时刷新

可以添加定时任务自动刷新热点数据：
```python
# 使用 APScheduler 或 Celery
from apscheduler.schedulers.background import BackgroundScheduler

scheduler = BackgroundScheduler()
scheduler.add_job(refresh_hot_topics, 'interval', hours=1)
scheduler.start()
```

## 注意事项

1. **API限制**：接入真实API时注意调用频率限制
2. **数据更新**：建议每1-2小时刷新一次热点数据
3. **敏感词过滤**：生成的文案会自动过滤敏感词
4. **历史记录**：所有生成的文案都会保存到历史记录中

## 故障排查

### 热点列表为空
- 点击"刷新热点"按钮获取数据
- 检查后端服务是否正常运行

### 生成文案失败
- 检查智谱AI API密钥是否配置正确
- 确认账户有足够的API调用额度
- 查看后端日志获取详细错误信息

### 数据库错误
- 确保数据库文件有写入权限
- 运行数据库初始化脚本重建表结构

## 技术栈

- **后端**: FastAPI + SQLAlchemy
- **前端**: Streamlit
- **AI**: 智谱AI GLM-4-Plus
- **数据库**: SQLite

## 更新日志

### v0.2.0 (2026-05-03)
- ✨ 新增热点跟踪功能
- ✨ 支持多平台热点获取（抖音、微博、小红书）
- ✨ 支持基于热点一键生成文案
- ✨ 新增热点数据库表结构
- ✨ 新增热点相关API接口

### v0.1.0
- 基础文案生成功能
- 多平台文案转换
- 敏感词过滤
- 历史记录管理
