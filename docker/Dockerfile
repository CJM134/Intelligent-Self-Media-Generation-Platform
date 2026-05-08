FROM python:3.11-slim

WORKDIR /app

# 复制依赖文件
COPY backend/requirements.txt .

# 安装依赖
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install apscheduler==3.10.4

# 复制应用代码
COPY backend/ ./backend/
COPY data/ ./data/

# 创建数据库目录
RUN mkdir -p /app/data

# 暴露端口
EXPOSE 8000

# 启动应用
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
