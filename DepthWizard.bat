@echo off
rem DepthWizard: start the app and open it in its own window (Edge / Chrome app mode, else the default browser).
rem Run Install.bat once first. To stop the app, close the minimised "DepthWizard server" window.
setlocal
cd /d "%~dp0SynRS3D"
if not exist ".venv\Scripts\python.exe" (
  echo DepthWizard is not installed yet: run Install.bat first.
  pause
  exit /b 1
)
set URL=http://127.0.0.1:8000
powershell -NoProfile -Command "try { Invoke-WebRequest -UseBasicParsing -TimeoutSec 2 %URL%/api/scenes | Out-Null; exit 0 } catch { exit 1 }"
if errorlevel 1 start "DepthWizard server" /min ".venv\Scripts\python.exe" app.py
echo Starting DepthWizard...
powershell -NoProfile -Command "for ($i = 0; $i -lt 180; $i++) { try { Invoke-WebRequest -UseBasicParsing -TimeoutSec 2 %URL%/api/scenes | Out-Null; exit 0 } catch { Start-Sleep 1 } }; exit 1"
if errorlevel 1 (
  echo The server did not start: see the "DepthWizard server" window for the error.
  pause
  exit /b 1
)
set EDGE=%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe
if not exist "%EDGE%" set EDGE=%ProgramFiles%\Microsoft\Edge\Application\msedge.exe
set CHROME=%ProgramFiles%\Google\Chrome\Application\chrome.exe
if exist "%EDGE%" (start "" "%EDGE%" --app=%URL%) else if exist "%CHROME%" (start "" "%CHROME%" --app=%URL%) else (start "" %URL%)
