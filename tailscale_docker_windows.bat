@echo off
REM Windows: Tailscale Docker konteynerini baslatir (Docker Desktop acik olmali)
setlocal
cd /d "%~dp0"
set "CFGDIR=%ProgramData%\Optimuslock"
set "CFG=%CFGDIR%\tailscale.env"
if not exist "%CFGDIR%" mkdir "%CFGDIR%"
if not exist "%CFG%" (
  copy ".env.example" "%CFG%" >nul
  echo %CFG% olusturuldu. TS_AUTHKEY ve TS_HOSTNAME degerlerini duzenleyip tekrar calistirin.
  notepad "%CFG%"
  exit /b
)
docker compose -f docker-compose.windows.yml --env-file "%CFG%" up -d
docker exec optimuslock-tailscale tailscale status
pause
