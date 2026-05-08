# Docker部署指南

**部署日期**: 2026-05-04  
**Docker版本**: 推荐使用 Docker 20.10+ 和 Docker Compose 2.0+

---

## 📋 部署概述

本项目使用Docker Compose进行容器化部署，包含两个服务：
- **backend**: FastAPI后端服务（端口8000）
- **frontend**: Streamlit前端服务（端口8501）

---

## 🔧 部署前准备

### 1. 安装Docker

**Windows**:
- 下载并安装 [Docker Desktop for Windows](https://www.docker.com/products/docker-desktop)
- 启动Docker Desktop

**Linux**:
```bash
# Ubuntu/Debian
sudo apt-get update
sudo apt-get install docker.io docker-compose

# CentOS/RHEL
sudo yum install docker docker-compose
```

**macOS**:
- 下载并安装 [Docker Desktop for Mac](https://www.docker.com/products/docker-desktop)

### 2. 验证安装

```bash
docker --version
docker-compose --version
```

### 3. 配置环境变量

确保 `.env` 文件包含以下配置：

```env
# 智谱AI API密钥
ZHIPU_API_KEY=your_zhipu_api_key

# 天聚数行API密钥
TIANAPI_KEY=your_tianapi_key

# 数据库配置
DATABASE_URL=sqlite:///./content_agent.db

# 应用配置
DEBUG=False
```

---

## 🚀 快速开始

### 方法1：使用Docker Compose（推荐）

```bash
# 1. 进入项目目录
cd D:/AgentProject/MyFirthAgent

# 2. 构建镜像
docker-compose build

# 3. 启动服务
docker-compose up -d

# 4. 查看日志
docker-compose logs -f

# 5. 停止服务
docker-compose down
```

### 方法2：手动构建和运行

```bash
# 构建后端镜像
docker build -f docker/Dockerfile -t content-agent-backend .

# 构建前端镜像
docker build -f docker/Dockerfile.frontend -t content-agent-frontend .

# 运行后端容器
docker run -d \
  --name backend \
  -p 8000:8000 \
  -e ZHIPU_API_KEY=your_key \
  -e TIANAPI_KEY=your_key \
  -v $(pwd)/data:/app/data \
  content-agent-backend

# 运行前端容器
docker run -d \
  --name frontend \
  -p 8501:8501 \
  -e API_URL=http://backend:8000 \
  --link backend \
  content-agent-frontend
```

---

## 📁 项目结构

```
MyFirthAgent/
├── docker/
│   ├── Dockerfile              # 后端Dockerfile
│   └── Dockerfile.frontend     # 前端Dockerfile
├── docker-compose.yml          # Docker Compose配置
├── backend/
│   ├── requirements.txt        # Python依赖
│   ├── main.py                 # FastAPI应用
│   ├── config.py               # 配置文件
│   ├── models/                 # 数据模型
│   └── services/               # 业务服务
├── frontend/
│   └── app.py                  # Streamlit应用
├── data/                       # 数据目录
└── .env                        # 环境变量
```

---

## 🔍 服务访问

启动成功后，可以通过以下地址访问：

- **前端界面**: http://localhost:8501
- **后端API**: http://localhost:8000
- **API文档**: http://localhost:8000/docs
- **健康检查**: http://localhost:8000/health

---

## 📊 Docker Compose配置说明

### 服务配置

```yaml
services:
  backend:
    build:
      context: .
      dockerfile: docker/Dockerfile
    ports:
      - "8000:8000"
    environment:
      - ZHIPU_API_KEY=${ZHIPU_API_KEY}
      - TIANAPI_KEY=${TIANAPI_KEY}
      - DATABASE_URL=sqlite:///./content_agent.db
    volumes:
      - ./backend:/app/backend
      - ./data:/app/data
      - db_data:/app

  frontend:
    build:
      context: .
      dockerfile: docker/Dockerfile.frontend
    ports:
      - "8501:8501"
    environment:
      - API_URL=http://backend:8000
    depends_on:
      - backend
```

### 数据持久化

使用Docker Volume持久化数据库：

```yaml
volumes:
  db_data:
```

---

## 🛠️ 常用命令

### 查看服务状态

```bash
docker-compose ps
```

### 查看日志

```bash
# 查看所有服务日志
docker-compose logs -f

# 查看后端日志
docker-compose logs -f backend

# 查看前端日志
docker-compose logs -f frontend
```

### 重启服务

```bash
# 重启所有服务
docker-compose restart

# 重启单个服务
docker-compose restart backend
```

### 进入容器

```bash
# 进入后端容器
docker-compose exec backend bash

# 进入前端容器
docker-compose exec frontend bash
```

### 清理资源

```bash
# 停止并删除容器
docker-compose down

# 停止并删除容器、网络、卷
docker-compose down -v

# 删除所有镜像
docker-compose down --rmi all
```

---

## 🔧 故障排查

### 问题1：容器启动失败

**检查日志**：
```bash
docker-compose logs backend
docker-compose logs frontend
```

**常见原因**：
- 端口被占用（8000或8501）
- 环境变量未配置
- 依赖安装失败

**解决方案**：
```bash
# 检查端口占用
netstat -ano | findstr :8000
netstat -ano | findstr :8501

# 重新构建镜像
docker-compose build --no-cache

# 重新启动
docker-compose up -d
```

### 问题2：API调用失败

**检查后端服务**：
```bash
curl http://localhost:8000/health
```

**检查环境变量**：
```bash
docker-compose exec backend env | grep API_KEY
```

### 问题3：数据库文件丢失

**检查数据卷**：
```bash
docker volume ls
docker volume inspect myfirthagent_db_data
```

**备份数据库**：
```bash
docker cp backend:/app/content_agent.db ./backup.db
```

### 问题4：前端无法连接后端

**检查网络**：
```bash
docker network ls
docker network inspect myfirthagent_default
```

**检查API_URL配置**：
```bash
docker-compose exec frontend env | grep API_URL
```

---

## 🔐 安全建议

### 1. 环境变量管理

不要将 `.env` 文件提交到Git：

```bash
# .gitignore
.env
*.db
```

### 2. 生产环境配置

```yaml
# docker-compose.prod.yml
services:
  backend:
    restart: always
    environment:
      - DEBUG=False
    command: uvicorn backend.main:app --host 0.0.0.0 --port 8000 --workers 4
```

### 3. 使用Secrets

```yaml
services:
  backend:
    secrets:
      - zhipu_api_key
      - tianapi_key

secrets:
  zhipu_api_key:
    file: ./secrets/zhipu_key.txt
  tianapi_key:
    file: ./secrets/tianapi_key.txt
```

---

## 📈 性能优化

### 1. 多阶段构建

```dockerfile
# 构建阶段
FROM python:3.11-slim as builder
WORKDIR /app
COPY requirements.txt .
RUN pip install --user -r requirements.txt

# 运行阶段
FROM python:3.11-slim
WORKDIR /app
COPY --from=builder /root/.local /root/.local
COPY . .
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0"]
```

### 2. 使用缓存

```bash
# 使用BuildKit加速构建
DOCKER_BUILDKIT=1 docker-compose build
```

### 3. 资源限制

```yaml
services:
  backend:
    deploy:
      resources:
        limits:
          cpus: '1'
          memory: 1G
        reservations:
          cpus: '0.5'
          memory: 512M
```

---

## 🌐 生产部署

### 使用Nginx反向代理

```nginx
server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://localhost:8501;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }

    location /api {
        proxy_pass http://localhost:8000;
    }
}
```

### 使用Docker Swarm

```bash
# 初始化Swarm
docker swarm init

# 部署服务
docker stack deploy -c docker-compose.yml content-agent

# 查看服务
docker service ls
```

### 使用Kubernetes

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: content-agent-backend
spec:
  replicas: 3
  selector:
    matchLabels:
      app: backend
  template:
    metadata:
      labels:
        app: backend
    spec:
      containers:
      - name: backend
        image: content-agent-backend:latest
        ports:
        - containerPort: 8000
```

---

## 📝 维护建议

### 定期备份

```bash
# 备份脚本
#!/bin/bash
DATE=$(date +%Y%m%d_%H%M%S)
docker cp backend:/app/content_agent.db ./backups/db_$DATE.db
```

### 日志轮转

```yaml
services:
  backend:
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"
```

### 监控

```bash
# 使用docker stats监控资源使用
docker stats

# 使用Prometheus + Grafana监控
docker-compose -f docker-compose.monitoring.yml up -d
```

---

## 🆘 获取帮助

- **项目文档**: 查看项目根目录下的README.md
- **API文档**: http://localhost:8000/docs
- **Docker文档**: https://docs.docker.com/
- **Docker Compose文档**: https://docs.docker.com/compose/

---

## ✅ 部署检查清单

- [ ] Docker和Docker Compose已安装
- [ ] .env文件已配置
- [ ] 端口8000和8501未被占用
- [ ] 镜像构建成功
- [ ] 容器启动成功
- [ ] 前端可以访问（http://localhost:8501）
- [ ] 后端API正常（http://localhost:8000/health）
- [ ] 热点刷新功能正常
- [ ] 文案生成功能正常
- [ ] 数据持久化正常

---

**部署完成后，访问 http://localhost:8501 开始使用！** 🎉
