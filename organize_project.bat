@echo off
REM Project Organization Script (Windows)
REM Organizes files into logical folder structure

ECHO 🗂️  Organizing Project Files...
ECHO =================================

REM Create directory structure
ECHO 📁 Creating directory structure...
IF NOT EXIST docs\guides mkdir docs\guides
IF NOT EXIST docs\summaries mkdir docs\summaries
IF NOT EXIST docs\references mkdir docs\references
IF NOT EXIST core\executors mkdir core\executors
IF NOT EXIST core\locators mkdir core\locators
IF NOT EXIST core\analyzers mkdir core\analyzers
IF NOT EXIST core\database mkdir core\database
IF NOT EXIST ui\static mkdir ui\static
IF NOT EXIST ui\templates mkdir ui\templates
IF NOT EXIST tests\test_cases mkdir tests\test_cases
IF NOT EXIST tests\recordings mkdir tests\recordings
IF NOT EXIST tests\screenshots mkdir tests\screenshots
IF NOT EXIST scripts mkdir scripts
IF NOT EXIST cache mkdir cache
IF NOT EXIST backups\recordings mkdir backups\recordings
IF NOT EXIST backups\screenshots mkdir backups\screenshots
IF NOT EXIST backups\phase3 mkdir backups\phase3
ECHO ✅ Directory structure created
ECHO.

REM Move Documentation Files
ECHO 📚 Organizing documentation...
IF EXIST DATABASE_AND_STORAGE_COMPARISON.md move /Y DATABASE_AND_STORAGE_COMPARISON.md docs\summaries\
IF EXIST DATABASE_README.md move /Y DATABASE_README.md docs\guides\
IF EXIST ENHANCED_FEATURES_GUIDE.md move /Y ENHANCED_FEATURES_GUIDE.md docs\guides\
IF EXIST EXECUTOR_SHADOW_DOM_IMPLEMENTATION.md move /Y EXECUTOR_SHADOW_DOM_IMPLEMENTATION.md docs\summaries\
IF EXIST FEATURE_SUMMARY.md move /Y FEATURE_SUMMARY.md docs\summaries\
IF EXIST FUTURE_IMPROVEMENTS_AND_VLM_OPPORTUNITIES.md move /Y FUTURE_IMPROVEMENTS_AND_VLM_OPPORTUNITIES.md docs\references\
IF EXIST HTML_EXTRACTION_IMPLEMENTATION.md move /Y HTML_EXTRACTION_IMPLEMENTATION.md docs\summaries\
IF EXIST IMPLEMENTATION_SUMMARY.md move /Y IMPLEMENTATION_SUMMARY.md docs\summaries\
IF EXIST IMPLEMENTATION_SUMMARY.txt move /Y IMPLEMENTATION_SUMMARY.txt docs\summaries\
IF EXIST INTEGRATION_SUMMARY.md move /Y INTEGRATION_SUMMARY.md docs\summaries\
IF EXIST NEW_FEATURES_GUIDE.txt move /Y NEW_FEATURES_GUIDE.txt docs\guides\
IF EXIST PHASE2_IMPLEMENTATION_SUMMARY.md move /Y PHASE2_IMPLEMENTATION_SUMMARY.md docs\summaries\
IF EXIST PHASE2_OLLAMA_GUIDE.md move /Y PHASE2_OLLAMA_GUIDE.md docs\guides\
IF EXIST PHASE2_VLM_INTEGRATION_GUIDE.md move /Y PHASE2_VLM_INTEGRATION_GUIDE.md docs\guides\
IF EXIST PHASE3_COMPLETION_SUMMARY.md move /Y PHASE3_COMPLETION_SUMMARY.md docs\summaries\
IF EXIST PHASE3_GUIDE.md move /Y PHASE3_GUIDE.md docs\guides\
IF EXIST PHASE3_QUICK_REFERENCE.md move /Y PHASE3_QUICK_REFERENCE.md docs\references\
IF EXIST PHASE3_STATUS_REPORT.md move /Y PHASE3_STATUS_REPORT.md docs\summaries\
IF EXIST PHASE4_STATUS_REPORT.md move /Y PHASE4_STATUS_REPORT.md docs\summaries\
IF EXIST QUICK_REFERENCE.txt move /Y QUICK_REFERENCE.txt docs\references\
IF EXIST RECORDING_MANAGEMENT.md move /Y RECORDING_MANAGEMENT.md docs\guides\
IF EXIST REPLAY_FAILURE_ANALYSIS.md move /Y REPLAY_FAILURE_ANALYSIS.md docs\guides\
IF EXIST SQLITE_IMPLEMENTATION_SUMMARY.md move /Y SQLITE_IMPLEMENTATION_SUMMARY.md docs\summaries\
IF EXIST TEST_EDITOR_FEATURE_SUMMARY.md move /Y TEST_EDITOR_FEATURE_SUMMARY.md docs\summaries\
IF EXIST TEST_EDITOR_GUIDE.md move /Y TEST_EDITOR_GUIDE.md docs\guides\
ECHO ✅ Documentation organized
