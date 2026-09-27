@echo off
setlocal
cd /d "%~dp0"
set IMG=greenplan:1.0

docker image inspect %IMG% >nul 2>nul
if errorlevel 1 (
  if exist greenplan_docker.tar (
    echo Loading image from greenplan_docker.tar ...
    docker load -i greenplan_docker.tar
  ) else (
    echo Building image (internet needed once) ...
    docker build -t %IMG% .
  )
)

start "" /b cmd /c "timeout /t 2 /nobreak >nul & start http://127.0.0.1:8000"
docker run --rm -p 8000:8000 -e GREENPLAN_HOST=0.0.0.0 -v "%~dp0out:/app/out" %IMG%
pause