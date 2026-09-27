@echo off
chcp 65001 >nul
cd /d "%~dp0"

rem System python (portable version removed). Show version + full path for clarity.
set PY=
python -c "import ezdxf, shapely, fastapi, uvicorn" >nul 2>nul
if not errorlevel 1 set PY=python
if not defined PY set PY=python

set PINFO=
for /f "delims=" %%v in ('%PY% -c "import sys;print(sys.version.split()[0]+' '+sys.executable)"') do set PINFO=%%v
echo Interpreter: %PY%  (%PINFO%)

start "" /b cmd /c "timeout /t 2 /nobreak >nul & start http://127.0.0.1:8000"
%PY% serve.py
pause