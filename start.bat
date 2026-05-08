@echo off
chcp 65001 >nul
echo ====================================
echo    启动新媒体内容生成助手
echo ====================================
echo.

echo [1/3] 检查虚拟环境...
if not exist .venv (
    echo 错误: 虚拟环境不存在，请先运行 python -m venv .venv
    pause
    exit /b 1
)

echo [2/3] 启动后端服务...
start "Backend API" cmd /k "cd /d %~dp0 && .venv\Scripts\activate && python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload"

timeout /t 3 /nobreak >nul

echo [3/3] 启动前端界面...
start "Frontend UI" cmd /k "cd /d %~dp0 && .venv\Scripts\activate && streamlit run frontend/app.py"

echo.
echo ====================================
echo 服务启动完成！
echo 后端API: http://127.0.0.1:8000
echo 前端界面: http://localhost:8501
echo ====================================
echo.
echo 按任意键关闭此窗口...
pause >nul
