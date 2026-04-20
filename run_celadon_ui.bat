@echo off
chcp 65001 > nul
setlocal enabledelayedexpansion

cd /d %~dp0

set "ENV_NAME=pixel_ai"
set "CONDA_BAT="
set "PROJECT_DIR=%CD%"

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

where conda >nul 2>nul
if %ERRORLEVEL%==0 (
    call conda activate %ENV_NAME%
) else (
    if exist "%USERPROFILE%\anaconda3\condabin\conda.bat" set "CONDA_BAT=%USERPROFILE%\anaconda3\condabin\conda.bat"
    if exist "%USERPROFILE%\miniconda3\condabin\conda.bat" set "CONDA_BAT=%USERPROFILE%\miniconda3\condabin\conda.bat"
    if defined CONDA_BAT (
        call "%CONDA_BAT%" activate %ENV_NAME%
    ) else (
        echo [ERROR] Conda not found. Please install Anaconda or Miniconda first.
        pause
        exit /b 1
    )
)

if not %ERRORLEVEL%==0 (
    echo [ERROR] Failed to activate conda env: %ENV_NAME%
    pause
    exit /b 1
)

echo ===============================================
echo   TakeChinaHome Celadon UI
echo ===============================================
echo [Workspace] %PROJECT_DIR%
echo [URL] http://127.0.0.1:7860
echo [UI Features]
echo   1. Upload vessel image
echo   2. Upload pattern image
echo   3. Select workflow: 6C or 6D
echo ===============================================

python app.py

set "EXIT_CODE=%ERRORLEVEL%"
if not "%EXIT_CODE%"=="0" (
    echo [ERROR] app.py exited with code: %EXIT_CODE%
    pause
    exit /b %EXIT_CODE%
)

echo [OK] Gradio UI closed normally.
pause
