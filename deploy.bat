@echo off
chcp 65001 >nul

echo ==================================
echo   Docker部署脚本
echo ==================================
echo.

REM 检查Docker是否运行
docker info >nul 2>&1
if errorlevel 1 (
    echo 错误: Docker未运行，请先启动Docker Desktop
    pause
    exit /b 1
)

echo [1/4] 停止现有容器...
docker-compose down

echo.
echo [2/4] 构建Docker镜像...
docker-compose build

echo.
echo [3/4] 启动服务...
docker-compose up -d

echo.
echo [4/4] 等待服务启动...
timeout /t 5 /nobreak >nul

echo.
echo ==================================
echo   部署完成！
echo ==================================
echo.
echo 服务访问地址：
echo   前端界面: http://localhost:8501
echo   后端API:  http://localhost:8000
echo   API文档:  http://localhost:8000/docs
echo.
echo 查看日志：
echo   docker-compose logs -f
echo.
echo 停止服务：
echo   docker-compose down
echo.
pause
