# 新媒体运营 AI 助手

基于多 Agent 架构的智能内容生产系统，自动采集热点、生成多平台文案、配图，实现从选题到发布的全流程自动化。

## 核心能力

- **热点自动追踪** — 定时采集微博、抖音热搜，聚合去重，RRF 排序
- **多平台文案生成** — 一次 LLM 调用产出小红书、抖音、公众号、微博四平台文案，节省 75% 调用量
- **AI 配图生成** — 基于 火山引擎 Ark（豆包 Seedream 5.0）自动生成高清配图，支持 6 种视觉风格
- **文案转画面描述** — ImagePromptAgent 理解文案语义，生成精准的视觉描述词
- **数据分析与爆款预测** — 平台热度对比、趋势分析、高峰时段识别、AI 爆款潜力预测
- **敏感词过滤** — 自动检测并过滤敏感词
- **定时自动生产** — 每 2 小时自动完成采集 → 生成 → 配图全流程
- **批评家质量闭环** — CriticAgent 自动审查文案质量，低分触发重写

## 系统架构

### 多 Agent 编排模式

系统采用 **Orchestration Pattern（编排模式）**，由 OrchestratorAgent 统一调度 6 个子 Agent：

```
用户请求
    │
    ▼
OrchestratorAgent  ── 拆解任务、分派、汇总
    │
    ├── CollectorAgent   采集微博/抖音热点
    ├── AnalyzerAgent    趋势分析 & 爆款预测
    ├── WriterAgent      生成多平台文案（一次 LLM 调用）
    ├── CriticAgent      文案质量审查 & 改进建议
    ├── ImagePromptAgent 文案 → 画面描述（LLM 驱动）
    └── MemoryAgent      历史记忆管理
```

### 数据流

```
热点采集 → 趋势分析 → 文案生成 → 批评家审查 → 画面描述 → 图片生成 → 入库
```

### 调用链路

全部 Agent 通过直接 async 方法调用协作，不依赖外部消息队列。关键优化：

- **Batch LLM**: WriterAgent 一次调用生成 4 个平台文案，而非逐平台串行
- **Critic 闭环**: 一次审查全部文案，不达标一次性重写
- **ImagePromptAgent**: 用 LLM 理解文案语义生成画面描述，替代正则清洗

## 技术栈

| 层 | 技术 |
|--------|------|
| 后端框架 | FastAPI |
| LLM | 智谱 AI GLM-4-plus |
| 图片生成 | 火山引擎 Ark（豆包 Seedream 5.0） |
| 热点数据 | 天聚数行 API |
| 数据库 | SQLite + SQLAlchemy |
| 定时任务 | APScheduler |
| 前端 | Streamlit |
| 容器化 | Docker + Docker Compose |

## 项目结构

```
my-content-agent/
├── backend/
│   ├── main.py                # FastAPI 入口 & API 路由
│   ├── config.py              # 配置管理（Pydantic Settings）
│   ├── agents/                # 多 Agent 系统
│   │   ├── base_agent.py      # Agent 基类（ReAct 循环）
│   │   ├── orchestrator.py    # 编排者 Agent
│   │   ├── collector_agent.py # 热点采集 Agent
│   │   ├── writer_agent.py    # 文案生成 Agent
│   │   ├── analyzer_agent.py  # 数据分析 Agent
│   │   ├── critic_agent.py    # 批评家 Agent
│   │   ├── image_prompt_agent.py  # 画面描述 Agent
│   │   ├── memory_agent.py    # 记忆 Agent
│   │   ├── tool.py            # 工具类
│   │   ├── skill.py           # 技能类
│   │   └── message_bus.py     # 消息总线
│   ├── services/
│   │   ├── image_generator.py       # 图片生成（Jimeng API）
│   │   ├── scheduled_tasks.py       # 定时任务
│   │   ├── hot_topic_fetcher.py     # 热点抓取
│   │   ├── hot_topic_analyzer.py    # 热点分析
│   │   └── sensitive_filter.py      # 敏感词过滤
│   ├── models/
│   │   └── database.py       # 数据模型
│   ├── prompts/               # 各平台文案提示词模板
│   │   ├── xiaohongshu.txt
│   │   ├── douyin.txt
│   │   ├── wechat.txt
│   │   └── weibo.txt
│   └── data/
│       └── sensitive_words.txt
├── frontend/
│   └── app.py                # Streamlit 前端
├── docker/
├── docker-compose.yml
└── .env.example
```

## 快速开始

### 前置要求

- Python 3.11+
- 智谱 AI API Key（GLM-4-plus）
- 火山引擎 Ark API Key（图片生成）
- 天聚数行 API Key（热点数据）

### 本地启动

```bash
# 1. 配置环境变量
cp .env.example .env
# 编辑 .env，填入 API Key、Endpoint 等

# 2. 安装依赖
cd backend
pip install -r requirements.txt

# 3. 启动后端
python main.py
# API: http://localhost:8000
# 文档: http://localhost:8000/docs

# 4. 启动前端（新终端）
pip install streamlit requests
streamlit run frontend/app.py
# 前端: http://localhost:8501
```

### Docker 部署

```bash
docker-compose up -d
```

## 配置说明

编辑 `.env` 文件：

| 变量 | 说明 |
|------|------|
| `ZHIPU_API_KEY` | 智谱 AI API 密钥（GLM-4-plus） |
| `TIANAPI_KEY` | 天聚数行 API 密钥（热点数据） |
| `JIMENG_API_KEY` | 火山引擎 Ark API 密钥 |
| `JIMENG_API_BASE` | Ark API 地址 |
| `JIMENG_ENDPOINT` | Seedream 图片生成 Endpoint ID |
| `DATABASE_URL` | 数据库连接字符串 |
| `SENSITIVE_WORDS_FILE` | 敏感词库路径 |

## API 文档

### 文案生成

```bash
POST /api/generate-content
Content-Type: application/json

{ "content": "原始内容" }
```

### 基于热点生成

```bash
POST /api/generate-from-topic/{topic_id}
```

### 获取历史

```bash
GET /api/history?limit=10
```

### 热点数据

```bash
GET /api/topics                              # 当前热点列表
GET /api/analysis/trend?hours=24             # 趋势分析
GET /api/analysis/platform-compare           # 平台对比
GET /api/analysis/peak-hours                 # 高峰时段
GET /api/prediction/predict-next-topic       # 爆款预测
```

## Agent 系统详解

### ReAct 循环

每个 Agent 继承 `BaseAgent`，具备思考-行动-观察的 ReAct 循环能力。LLM 输出结构化指令，框架自动解析并执行工具调用。

### 技能系统

Agent 通过 `Skill` 注册能力，`_match_skill()` 根据任务描述自动匹配合适技能，动态注入 system prompt。

### 消息总线

保留 `MessageBus` 供 Agent 间异步通信，标记为保留能力，当前主流程使用直接方法调用。

## 提示词模板

平台文案模板位于 `backend/prompts/`，可根据需要修改：

- `xiaohongshu.txt` — 小红书：标题公式、种草结构、标签分层
- `douyin.txt` — 抖音：钩子开头、口语化脚本、互动引导
- `wechat.txt` — 公众号：标题公式、分层结构、排版规范
- `weibo.txt` — 微博：3 秒抓眼球、短句节奏、话题标签
