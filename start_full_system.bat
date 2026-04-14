@echo off
chcp 65001 > nul
setlocal enabledelayedexpansion

set "COMFY_ROOT=D:\PixelSmile\ComfyUI_windows_portable_nvidia\ComfyUI_windows_portable"
set "PROJECT_ROOT=D:\PixelSmile\LoRA"
set "OUTPUT_DIR=%PROJECT_ROOT%\outputs"
set "ENV_NAME=pixel_ai"

echo [1/2] 正在后台启动 ComfyUI 服务 (青瓷模式)...
start "Comfy-Backend-Celadon" /min "%COMFY_ROOT%\python_embeded\python.exe" -s "%COMFY_ROOT%\ComfyUI\main.py" ^
  --windows-standalone-build ^
  --lowvram ^
  --output-directory "%OUTPUT_DIR%"

echo [2/2] 正在准备【青瓷定制】前端界面...
timeout /t 8 /nobreak > nul

where conda >nul 2>nul
if %ERRORLEVEL%==0 (
    call conda activate %ENV_NAME%
) else (
    if exist "%USERPROFILE%\anaconda3\condabin\conda.bat" set "CONDA_BAT=%USERPROFILE%\anaconda3\condabin\conda.bat"
    if exist "%USERPROFILE%\miniconda3\condabin\conda.bat" set "CONDA_BAT=%USERPROFILE%\miniconda3\condabin\conda.bat"
    if defined CONDA_BAT (call "%CONDA_BAT%" activate %ENV_NAME%)
)

echo ===============================================
echo   🏺 TakeChinaHome - 青瓷 AI 工厂 (已关联 LoRA-2)
echo ===============================================
:: 传递参数给 Python
python app.py "图生图+LoRA (2).json"
pause