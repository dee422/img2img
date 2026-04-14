@echo off
chcp 65001 > nul
setlocal enabledelayedexpansion

:: ===========================================================
:: TakeChinaHome - 青瓷 AI 私人定制系统启动脚本
:: ===========================================================

cd /d %~dp0

:: 基础配置
set "ENV_NAME=pixel_ai"
set "CONDA_BAT="
set "PROJECT_DIR=%CD%"

:: 磁盘保护逻辑：重定向缓存与临时文件到项目所在盘符 (D:)
set "LOCAL_TMP=%PROJECT_DIR%\.tmp"
set "LOCAL_CACHE=%PROJECT_DIR%\.cache"

if not exist "%LOCAL_TMP%" mkdir "%LOCAL_TMP%"
if not exist "%LOCAL_CACHE%" mkdir "%LOCAL_CACHE%"
if not exist "%LOCAL_CACHE%\torch" mkdir "%LOCAL_CACHE%\torch"
if not exist "%LOCAL_CACHE%\huggingface" mkdir "%LOCAL_CACHE%\huggingface"
if not exist "%LOCAL_CACHE%\pip" mkdir "%LOCAL_CACHE%\pip"

set "TEMP=%LOCAL_TMP%"
set "TMP=%LOCAL_TMP%"
set "TORCH_HOME=%LOCAL_CACHE%\torch"
set "HF_HOME=%LOCAL_CACHE%\huggingface"
set "PIP_CACHE_DIR=%LOCAL_CACHE%\pip"

:: 检查并激活 Conda 环境
where conda >nul 2>nul
if %ERRORLEVEL%==0 (
    call conda activate %ENV_NAME%
) else (
    if exist "%USERPROFILE%\anaconda3\condabin\conda.bat" set "CONDA_BAT=%USERPROFILE%\anaconda3\condabin\conda.bat"
    if exist "%USERPROFILE%\miniconda3\condabin\conda.bat" set "CONDA_BAT=%USERPROFILE%\miniconda3\condabin\conda.bat"
    if defined CONDA_BAT (
        call "%CONDA_BAT%" activate %ENV_NAME%
    ) else (
        echo [错误] 未找到 Conda。请先安装 Anaconda 或 Miniconda。
        pause
        exit /b 1
    )
)

if not %ERRORLEVEL%==0 (
    echo [错误] 激活 Conda 环境失败: %ENV_NAME%
    pause
    exit /b 1
)

echo ===============================================
echo   TakeChinaHome 青瓷 AI 工厂启动中...
echo ===============================================
echo [系统状态] 显卡: NVIDIA RTX 3070 8GB
echo [工作目录] %PROJECT_DIR%
echo [服务地址] http://127.0.0.1:7860
echo ===============================================

:: 启动 Gradio 界面
python app.py

set "EXIT_CODE=%ERRORLEVEL%"
if not "%EXIT_CODE%"=="0" (
    echo [错误] app.py 异常退出，错误代码: %EXIT_CODE%。
    pause
    exit /b %EXIT_CODE%
)

echo [OK] Gradio 程序已正常关闭。
pause