# 🚀 新媒体运营 AI 助手

一个智能的多平台文案生成工具，帮助内容创作者快速生成适配不同社交媒体平台的文案。

## ✨ 功能特性

- **多平台文案生成** - 一份素材自动生成小红书、抖音、公众号、微博文案
- **热点追踪** - 实时抓取微博、抖音、小红书等多平台热搜榜单
- **数据分析与爆款预测** - 平台对比、趋势分析、高峰时段分析、爆款潜力 AI 预测
- **敏感词过滤** - 自动检测并过滤敏感词
- **历史记录管理** - 保存所有生成的文案记录
- **定时任务** - 每 2 小时自动抓取热点并生成文案
- **Web UI** - 简洁易用的 Streamlit 前端界面
- **RESTful API** - 完整的 API 接口支持集成

## 🛠️ 技术栈

- **后端**: FastAPI + SQLAlchemy
- **前端**: Streamlit
- **LLM**: Claude API (Sonnet 4.6)
- **数据库**: SQLite
- **容器化**: Docker + Docker Compose

## 📦 项目结构

```
my-content-agent/
├── backend/                    # 后端代码
│   ├── main.py                # FastAPI 入口
│   ├── config.py              # 配置管理
│   ├── agents/                # AI Agent 层
│   │   ├── collector_agent.py # 热点采集 Agent
│   │   └── analyzer_agent.py  # 数据分析 Agent
│   ├── services/              # 业务逻辑
│   │   ├── hot_topic_fetcher.py    # 热点话题抓取
│   │   ├── hot_topic_analyzer.py   # 热点数据分析
│   │   ├── scheduled_tasks.py      # 定时任务
│   │   └── api_clients/            # 外部 API 客户端
│   ├── models/                # 数据模型
│   ├── prompts/               # 提示词模板
│   └── data/                  # 数据文件
├── frontend/                  # 前端代码
│   └── app.py                # Streamlit 应用
├── docker/                    # Docker 配置
├── docker-compose.yml         # 容器编排
└── README.md                  # 项目文档
```

## 🚀 快速开始

### 前置要求

- Python 3.11+
- Claude API Key
- Docker & Docker Compose (可选)

### 本地开发

1. **克隆项目**
```bash
git clone <repo-url>
cd my-content-agent
```

2. **配置环境变量**
```bash
cp .env.example .env
# 编辑 .env 文件，填入 CLAUDE_API_KEY
```

3. **安装依赖**
```bash
cd backend
pip install -r requirements.txt
```

4. **启动后端**
```bash
cd backend
python main.py
```

5. **启动前端** (新终端)
```bash
pip install streamlit requests
streamlit run frontend/app.py
```

### Docker 部署

```bash
docker-compose up -d
```

访问：
- 前端: http://localhost:8501
- API: http://localhost:8000
- API 文档: http://localhost:8000/docs

## 📖 API 文档

### 生成文案

```bash
POST /api/generate-content
Content-Type: application/json

{
  "content": "原始文案内容",
  "industry": "行业标签（可选）"
}
```

### 获取历史记录

```bash
GET /api/history?limit=10
```

## 🔧 配置说明

编辑 `.env` 文件配置：

- `CLAUDE_API_KEY` - Claude API 密钥
- `DATABASE_URL` - 数据库连接字符串
- `SENSITIVE_WORDS_FILE` - 敏感词库路径

## 📝 提示词模板

平台特定的提示词模板位于 `backend/prompts/` 目录：

- `xiaohongshu.txt` - 小红书文案模板
- `douyin.txt` - 抖音文案模板
- `wechat.txt` - 公众号文案模板
- `weibo.txt` - 微博文案模板

可根据需要修改模板以优化生成效果。

## 🛡️ 敏感词库

敏感词库位于 `backend/data/sensitive_words.txt`，每行一个敏感词。


## 📄 许可证

MIT License

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！
