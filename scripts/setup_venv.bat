@echo off
REM Virtual Environment Setup Script for Test Generation Project (Windows)

ECHO 🔧 Setting up Virtual Environment...
ECHO.

REM Check if virtual environment already exists
IF EXIST venv\Scripts\activate.bat (
    ECHO ⚠️  Virtual environment already exists at .\venv
    SET /P REPLY="Do you want to recreate it? (y/n): "
    IF /I "%REPLY%"=="Y" (
        ECHO 🗑️  Removing old virtual environment...
        rmdir /S /Q venv
    ) ELSE (
        ECHO ✅ Using existing virtual environment
        CALL venv\Scripts\activate.bat
        ECHO ✅ Virtual environment activated!
        ECHO.
        ECHO Python: python
        python --version
        EXIT /B 0
    )
)

REM Create virtual environment
ECHO 📦 Creating virtual environment...
python -m venv venv
IF %ERRORLEVEL% NEQ 0 (
    ECHO ❌ Failed to create virtual environment
    ECHO    Make sure Python is installed and available in PATH
    EXIT /B 1
)
ECHO ✅ Virtual environment created
ECHO.

REM Activate virtual environment
ECHO 🚀 Activating virtual environment...
CALL venv\Scripts\activate.bat
ECHO ✅ Virtual environment activated!
ECHO.
ECHO Python location: python
python --version
ECHO.

REM Upgrade pip
ECHO ⬆️  Upgrading pip...
python -m pip install --upgrade pip >NUL 2>&1

REM Install core dependencies
ECHO 📦 Installing core dependencies...
pip install selenium flask werkzeug requests pillow imagehash >NUL 2>&1
IF %ERRORLEVEL% NEQ 0 (
    ECHO ❌ Failed to install dependencies
    EXIT /B 1
)
ECHO ✅ Dependencies installed
