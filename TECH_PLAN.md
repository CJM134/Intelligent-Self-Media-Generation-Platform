# 新媒体运营 AI 助手 - 技术方案

## 项目概述

从**文案多平台转换**这一核心功能切入，逐步扩展到热点追踪、数据分析等功能。

---

## 第一阶段：MVP（2-3周）- 核心文案转换引擎

### 功能范围
- ✅ 一份素材 → 多平台文案生成（小红书、抖音、公众号、微博）
- ✅ 基础敏感词过滤
- ✅ 简单的 Web UI

### 技术栈

```
后端框架:     FastAPI (Python)
LLM:          Claude API (Sonnet 4.6)
前端:         Streamlit / React (简单版用 Streamlit)
数据库:       SQLite (本地) / PostgreSQL (云版)
部署:         Docker + 云服务 (AWS/阿里云)
```

### 核心架构

```
┌─────────────────────────────────────────────────────┐
│                   用户界面层                          │
│  (Streamlit Web / React SPA)                        │
└────────────────┬────────────────────────────────────┘
                 │
┌────────────────▼────────────────────────────────────┐
│              API 层 (FastAPI)                        │
│  ├─ /api/generate-content  (文案生成)               │
│  ├─ /api/filter-sensitive  (敏感词检测)             │
│  └─ /api/history           (历史记录)               │
└────────────────┬────────────────────────────────────┘
                 │
┌────────────────▼────────────────────────────────────┐
│            业务逻辑层 (Service)                      │
│  ├─ ContentGenerator       (文案生成服务)           │
│  ├─ SensitiveFilter        (敏感词过滤)             │
│  └─ HistoryManager         (历史管理)               │
└────────────────┬────────────────────────────────────┘
                 │
┌────────────────▼────────────────────────────────────┐
│            LLM 集成层                                │
│  ├─ Claude API Client                               │
│  ├─ Prompt Templates (平台特定模板)                 │
│  └─ Response Parser                                 │
└────────────────┬────────────────────────────────────┘
                 │
┌────────────────▼────────────────────────────────────┐
│            数据持久化层                              │
│  ├─ SQLite/PostgreSQL                               │
│  └─ 本地敏感词库                                    │
└─────────────────────────────────────────────────────┘
```

### 文件结构

```
my-content-agent/
├── backend/
│   ├── main.py                 # FastAPI 入口
│   ├── config.py               # 配置管理
│   ├── requirements.txt
│   ├── services/
│   │   ├── content_generator.py    # 文案生成核心
│   │   ├── sensitive_filter.py     # 敏感词过滤
│   │   └── history_manager.py      # 历史管理
│   ├── models/
│   │   ├── schemas.py          # Pydantic 数据模型
│   │   └── database.py         # ORM 模型
│   ├── prompts/
│   │   ├── xiaohongshu.txt     # 小红书文案模板
│   │   ├── douyin.txt          # 抖音文案模板
│   │   ├── wechat.txt          # 公众号文案模板
│   │   └── weibo.txt           # 微博文案模板
│   └── data/
│       └── sensitive_words.txt # 敏感词库
├── frontend/
│   ├── app.py                  # Streamlit 应用
│   └── pages/
│       ├── home.py
│       ├── history.py
│       └── settings.py
├── docker/
│   ├── Dockerfile
│   └── docker-compose.yml
└── README.md
```

### 核心代码框架

**1. 文案生成服务** (`services/content_generator.py`)

```python
class ContentGenerator:
    def __init__(self, api_key: str):
        self.client = Anthropic(api_key=api_key)
        self.platforms = ["xiaohongshu", "douyin", "wechat", "weibo"]
    
    async def generate(self, original_content: str) -> dict:
        """生成多平台文案"""
        results = {}
        for platform in self.platforms:
            prompt = self._load_prompt(platform)
            result = await self._call_claude(original_content, prompt)
            results[platform] = result
        return results
    
    def _load_prompt(self, platform: str) -> str:
        """加载平台特定的提示词"""
        # 从 prompts/ 目录加载
        pass
    
    async def _call_claude(self, content: str, prompt: str) -> str:
        """调用 Claude API"""
        pass
```

**2. 敏感词过滤** (`services/sensitive_filter.py`)

```python
class SensitiveFilter:
    def __init__(self, words_file: str):
        self.sensitive_words = self._load_words(words_file)
    
    def filter(self, text: str) -> tuple[str, list]:
        """过滤敏感词，返回过滤后文本和检测到的敏感词"""
        detected = []
        filtered = text
        for word in self.sensitive_words:
            if word in text:
                detected.append(word)
                filtered = filtered.replace(word, "*" * len(word))
        return filtered, detected
```

**3. FastAPI 路由** (`main.py`)

```python
@app.post("/api/generate-content")
async def generate_content(request: ContentRequest):
    """生成多平台文案"""
    generator = ContentGenerator(api_key=CLAUDE_API_KEY)
    results = await generator.generate(request.content)
    
    # 过滤敏感词
    filter_service = SensitiveFilter("data/sensitive_words.txt")
    for platform in results:
        results[platform], _ = filter_service.filter(results[platform])
    
    return results
```

---

## 第二阶段：热点追踪（第 3-4 周）

### 新增功能
- 微博热榜 / 知乎热榜 API 集成
- 行业选题库
- 热点匹配推荐

### 新增文件

```
backend/
├── services/
│   ├── hotspot_tracker.py      # 热点追踪
│   └── topic_recommender.py    # 选题推荐
├── integrations/
│   ├── weibo_api.py            # 微博 API
│   ├── zhihu_api.py            # 知乎 API
│   └── baidu_index.py          # 百度指数
└── data/
    └── industry_topics.json    # 行业选题库
```

### 核心逻辑

```python
class HotspotTracker:
    async def get_trending_topics(self) -> list:
        """获取实时热点"""
        weibo_trends = await self.weibo_api.get_trends()
        zhihu_trends = await self.zhihu_api.get_trends()
        return self._merge_and_rank(weibo_trends, zhihu_trends)
    
    async def recommend_topics(self, industry: str) -> list:
        """推荐行业相关选题"""
        pass
```

---

## 第三阶段：数据分析（第 5-6 周）

### 新增功能
- 账号数据导入（Excel/CSV）
- 爆款内容分析
- 创作方向建议

### 新增文件

```
backend/
├── services/
│   ├── data_analyzer.py        # 数据分析
│   └── trend_analyzer.py       # 趋势分析
└── ml/
    └── content_classifier.py   # 内容分类模型
```

---

## 扩展性设计原则

### 1. 插件化平台支持

```python
# 易于添加新平台
class PlatformAdapter(ABC):
    @abstractmethod
    def get_prompt_template(self) -> str:
        pass
    
    @abstractmethod
    def validate_content(self, content: str) -> bool:
        pass

class XiaohongshuAdapter(PlatformAdapter):
    pass

class DouyinAdapter(PlatformAdapter):
    pass
```

### 2. 配置驱动

```yaml
# config.yaml
platforms:
  xiaohongshu:
    max_length: 2000
    hashtag_limit: 30
    emoji_allowed: true
  douyin:
    max_length: 150
    hashtag_limit: 5
    emoji_allowed: false
```

### 3. 模块化 LLM 调用

```python
class LLMProvider(ABC):
    @abstractmethod
    async def generate(self, prompt: str) -> str:
        pass

class ClaudeProvider(LLMProvider):
    pass

class GPTProvider(LLMProvider):  # 未来支持
    pass
```

### 4. 事件驱动架构

```python
# 便于添加新的处理流程
class ContentGeneratedEvent:
    content: str
    platform: str
    timestamp: datetime

@event_bus.on(ContentGeneratedEvent)
async def on_content_generated(event):
    # 自动保存、分析、发送通知等
    pass
```

---

## 部署方案

### 本地开发

```bash
# 使用 Docker Compose
docker-compose up -d

# 访问
http://localhost:8000/docs      # API 文档
http://localhost:8501           # Streamlit UI
```

### 云部署

```
AWS:
├─ EC2 (后端)
├─ RDS (数据库)
├─ S3 (文件存储)
└─ CloudFront (CDN)

或

阿里云:
├─ ECS (后端)
├─ RDS (数据库)
├─ OSS (文件存储)
└─ CDN
```

---

## 成本估算（月度）

| 项目 | 成本 | 说明 |
|------|------|------|
| Claude API | $50-200 | 按使用量计费 |
| 云服务器 | $20-50 | 小型 EC2/ECS |
| 数据库 | $10-30 | RDS 最小配置 |
| 存储 | $5-10 | S3/OSS |
| **总计** | **$85-290** | 可根据用户量扩展 |

---

## 下一步行动

1. **确认 MVP 范围** - 是否只做文案转换？
2. **选择前端框架** - Streamlit（快速）vs React（专业）
3. **API 密钥准备** - Claude API key
4. **敏感词库** - 使用开源库还是自建？

