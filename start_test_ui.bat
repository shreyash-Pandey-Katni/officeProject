@echo off
REM Quick Start Script for Test Generation UI (Windows)

ECHO 🚀 Starting Test Generation UI...
ECHO.

REM Activate virtual environment
IF EXIST .venv\Scripts\activate.bat (
    ECHO 🐍 Activating virtual environment (.venv)...
    CALL .venv\Scripts\activate.bat
    ECHO ✅ Virtual environment activated
) ELSE IF EXIST venv\Scripts\activate.bat (
    ECHO 🐍 Activating virtual environment (venv)...
    CALL venv\Scripts\activate.bat
    ECHO ✅ Virtual environment activated
) ELSE (
    ECHO ⚠️  No virtual environment found
    ECHO    Using system Python: python
)
ECHO.

REM Check if Ollama is running
ECHO 📡 Checking Ollama...
REM Windows does not have curl by default, so check with PowerShell
powershell -Command "try { $r = Invoke-WebRequest -Uri 'http://localhost:11434/api/tags' -UseBasicParsing } catch { exit 1 }"
IF %ERRORLEVEL% EQU 0 (
    ECHO ✅ Ollama is running
) ELSE (
    ECHO ❌ Ollama is not running!
    ECHO    Please start Ollama first:
    ECHO    ollama serve
    EXIT /B 1
)

REM Check if required model is available
ECHO.
ECHO 🤖 Checking Granite model...
powershell -Command "try { $r = Invoke-WebRequest -Uri 'http://localhost:11434/api/tags' -UseBasicParsing; if ($r.Content -match 'granite3.2-vision') { exit 0 } else { exit 1 } } catch { exit 1 }"
IF %ERRORLEVEL% EQU 0 (
    ECHO ✅ granite3.2-vision:latest is available
) ELSE (
    ECHO ⚠️  granite3.2-vision:latest not found
    ECHO    Pulling model (this may take a few minutes)...
    ollama pull granite3.2-vision:latest
)

REM Check Python dependencies
ECHO.
ECHO 📦 Checking Python dependencies...
python -c "import flask, selenium, werkzeug" 2>NUL
IF %ERRORLEVEL% NEQ 0 (
    ECHO ❌ Required dependencies not installed
    ECHO    Installing dependencies in virtual environment...
    pip install flask werkzeug selenium pillow imagehash requests
    ECHO ✅ Dependencies installed
)
ECHO ✅ All dependencies available

REM Create required directories
ECHO.
ECHO 📁 Creating directories...
IF NOT EXIST generated_tests mkdir generated_tests
IF NOT EXIST uploads mkdir uploads
ECHO ✅ Directories created
