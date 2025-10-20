@echo off
REM Codacy CLI Integration Script (Windows)

SETLOCAL ENABLEEXTENSIONS

REM Set up paths first
SET "bin_name=codacy-cli-v2"

REM Determine OS-specific paths
SET "os_name=%OS%"
SET "arch=%PROCESSOR_ARCHITECTURE%"
IF "%arch%"=="AMD64" SET "arch=amd64"
IF "%arch%"=="x86" SET "arch=386"
IF "%arch%"=="ARM64" SET "arch=arm64"

IF "%CODACY_CLI_V2_TMP_FOLDER%"=="" (
    SET "CODACY_CLI_V2_TMP_FOLDER=%USERPROFILE%\.cache\codacy\codacy-cli-v2"
)

SET "version_file=%CODACY_CLI_V2_TMP_FOLDER%\version.yaml"

REM Function: get_version_from_yaml
REM (Batch does not support functions, so use inline logic)
IF EXIST "%version_file%" (
    FOR /F "tokens=2 delims=\"" %%A IN ('findstr "version:" "%version_file%"') DO (
        SET "version=%%A"
    )
)

REM Function: get_latest_version
REM (Use PowerShell to fetch latest release from GitHub)
IF NOT "%GH_TOKEN%"=="" (
    FOR /F "usebackq tokens=*" %%A IN (`powershell -Command "Invoke-WebRequest -Uri 'https://api.github.com/repos/codacy/codacy-cli-v2/releases/latest' -Headers @{Authorization='Bearer %GH_TOKEN%'} | Select-Object -ExpandProperty Content"`) DO SET "response=%%A"
) ELSE (
    FOR /F "usebackq tokens=*" %%A IN (`powershell -Command "Invoke-WebRequest -Uri 'https://api.github.com/repos/codacy/codacy-cli-v2/releases/latest' | Select-Object -ExpandProperty Content"`) DO SET "response=%%A"
)
REM Extract version from response
FOR /F "tokens=4 delims=\"" %%A IN ('echo %response% ^| findstr "tag_name"') DO SET "latest_version=%%A"

REM Output version info
ECHO Version from YAML: %version%
ECHO Latest version from GitHub: %latest_version%
ENDLOCAL
