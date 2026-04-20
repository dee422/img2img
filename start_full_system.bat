@echo off
chcp 65001 > nul
setlocal enabledelayedexpansion

set "COMFY_ROOT=D:\PixelSmile\ComfyUI_windows_portable_nvidia\ComfyUI_windows_portable"
set "PROJECT_ROOT=D:\PixelSmile\LoRA"
set "OUTPUT_DIR=%PROJECT_ROOT%\outputs"
set "ENV_NAME=pixel_ai"

echo [1/2] Starting ComfyUI backend...
start "Comfy-Backend-Celadon" /min "%COMFY_ROOT%\python_embeded\python.exe" -s "%COMFY_ROOT%\ComfyUI\main.py" ^
  --windows-standalone-build ^
  --lowvram ^
  --output-directory "%OUTPUT_DIR%"

echo [2/2] Preparing TakeChinaHome UI...
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
echo   TakeChinaHome - Celadon Workflow UI
echo ===============================================
echo Upload vessel image + pattern image in UI
echo Workflow options: 6C (fit) / 6D (fit + light relief)
echo ===============================================

python app.py
pause
