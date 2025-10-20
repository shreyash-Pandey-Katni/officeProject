#!/bin/bash

# Project Organization Script
# Organizes files into logical folder structure

echo "🗂️  Organizing Project Files..."
echo "================================"

cd "$(dirname "$0")"

# Create directory structure
echo "📁 Creating directory structure..."
mkdir -p docs/guides
mkdir -p docs/summaries
mkdir -p docs/references
mkdir -p core/executors
mkdir -p core/locators
mkdir -p core/analyzers
mkdir -p core/database
mkdir -p ui/static
mkdir -p ui/templates
mkdir -p tests/test_cases
mkdir -p tests/recordings
mkdir -p tests/screenshots
mkdir -p scripts
mkdir -p cache
mkdir -p backups/recordings
mkdir -p backups/screenshots
mkdir -p backups/phase3

echo "✅ Directory structure created"
echo ""

# Move Documentation Files
echo "📚 Organizing documentation..."
mv -n DATABASE_AND_STORAGE_COMPARISON.md docs/summaries/ 2>/dev/null
mv -n DATABASE_README.md docs/guides/ 2>/dev/null
mv -n ENHANCED_FEATURES_GUIDE.md docs/guides/ 2>/dev/null
mv -n EXECUTOR_SHADOW_DOM_IMPLEMENTATION.md docs/summaries/ 2>/dev/null
mv -n FEATURE_SUMMARY.md docs/summaries/ 2>/dev/null
mv -n FUTURE_IMPROVEMENTS_AND_VLM_OPPORTUNITIES.md docs/references/ 2>/dev/null
mv -n HTML_EXTRACTION_IMPLEMENTATION.md docs/summaries/ 2>/dev/null
mv -n IMPLEMENTATION_SUMMARY.md docs/summaries/ 2>/dev/null
mv -n IMPLEMENTATION_SUMMARY.txt docs/summaries/ 2>/dev/null
mv -n INTEGRATION_SUMMARY.md docs/summaries/ 2>/dev/null
mv -n NEW_FEATURES_GUIDE.txt docs/guides/ 2>/dev/null
mv -n PHASE2_IMPLEMENTATION_SUMMARY.md docs/summaries/ 2>/dev/null
mv -n PHASE2_OLLAMA_GUIDE.md docs/guides/ 2>/dev/null
mv -n PHASE2_VLM_INTEGRATION_GUIDE.md docs/guides/ 2>/dev/null
mv -n PHASE3_COMPLETION_SUMMARY.md docs/summaries/ 2>/dev/null
mv -n PHASE3_GUIDE.md docs/guides/ 2>/dev/null
mv -n PHASE3_QUICK_REFERENCE.md docs/references/ 2>/dev/null
mv -n PHASE3_STATUS_REPORT.md docs/summaries/ 2>/dev/null
mv -n PHASE4_STATUS_REPORT.md docs/summaries/ 2>/dev/null
mv -n QUICK_REFERENCE.txt docs/references/ 2>/dev/null
mv -n RECORDING_MANAGEMENT.md docs/guides/ 2>/dev/null
mv -n REPLAY_FAILURE_ANALYSIS.md docs/guides/ 2>/dev/null
mv -n SQLITE_IMPLEMENTATION_SUMMARY.md docs/summaries/ 2>/dev/null
mv -n TEST_EDITOR_FEATURE_SUMMARY.md docs/summaries/ 2>/dev/null
mv -n TEST_EDITOR_GUIDE.md docs/guides/ 2>/dev/null
mv -n TEST_EXECUTION_FEATURE.md docs/summaries/ 2>/dev/null
mv -n TEST_EXECUTION_FIX.md docs/summaries/ 2>/dev/null
mv -n TEST_GENERATION_UI_GUIDE.md docs/guides/ 2>/dev/null
mv -n USAGE_GUIDE.md docs/guides/ 2>/dev/null

echo "✅ Documentation organized"
echo ""

# Move Core Executors
echo "⚙️  Organizing core executors..."
mv -n activity_executor.py core/executors/ 2>/dev/null
mv -n replay_browser_activities.py core/executors/ 2>/dev/null
mv -n parallel_test_executor.py core/executors/ 2>/dev/null

echo "✅ Executors organized"
echo ""

# Move Locators and Finders
echo "🔍 Organizing locators and finders..."
mv -n element_locator.py core/locators/ 2>/dev/null
mv -n element_finder.py core/locators/ 2>/dev/null
mv -n vlm_element_finder.py core/locators/ 2>/dev/null

echo "✅ Locators organized"
echo ""

# Move Analyzers
echo "🔬 Organizing analyzers..."
mv -n intelligent_failure_analyzer.py core/analyzers/ 2>/dev/null
mv -n content_verifier.py core/analyzers/ 2>/dev/null
mv -n visual_regression_detector.py core/analyzers/ 2>/dev/null
mv -n assertions.py core/analyzers/ 2>/dev/null

echo "✅ Analyzers organized"
echo ""

# Move Database Files
echo "💾 Organizing database files..."
mv -n test_database.py core/database/ 2>/dev/null
mv -n db_utils.py core/database/ 2>/dev/null
mv -n demo_database.py core/database/ 2>/dev/null

echo "✅ Database files organized"
echo ""

# Move UI Files
echo "🎨 Organizing UI files..."
mv -n test_generation_ui.py ui/ 2>/dev/null
mv -n natural_language_test_creator.py ui/ 2>/dev/null
mv -n screenshot_test_generator.py ui/ 2>/dev/null
mv -n manage_recordings.py ui/ 2>/dev/null

# Move static and templates if they exist as directories
if [ -d "static" ] && [ ! -d "ui/static" ]; then
    mv static/* ui/static/ 2>/dev/null
    rmdir static 2>/dev/null
fi

if [ -d "templates" ] && [ ! -d "ui/templates" ]; then
    mv templates/* ui/templates/ 2>/dev/null
    rmdir templates 2>/dev/null
fi

echo "✅ UI files organized"
echo ""

# Move Test Files
echo "🧪 Organizing test files..."
mv -n test_new_actions.json tests/test_cases/ 2>/dev/null
mv -n example_generated_test.json tests/test_cases/ 2>/dev/null

# Move generated tests
if [ -d "generated_tests" ]; then
    mv generated_tests/* tests/test_cases/ 2>/dev/null
    rmdir generated_tests 2>/dev/null
fi

echo "✅ Test files organized"
echo ""

# Move Screenshot Directories
echo "📸 Organizing screenshots..."
if [ -d "screenshots" ]; then
    mv screenshots/* tests/screenshots/ 2>/dev/null
    rmdir screenshots 2>/dev/null
fi

if [ -d "replay_screenshots" ]; then
    mv replay_screenshots/* tests/screenshots/ 2>/dev/null
    rmdir replay_screenshots 2>/dev/null
fi

if [ -d "test_screenshots" ]; then
    mv test_screenshots/* tests/screenshots/ 2>/dev/null
    rmdir test_screenshots 2>/dev/null
fi

echo "✅ Screenshots organized"
echo ""

# Move Backup Directories
echo "💼 Organizing backups..."
if [ -d "recording_backups" ]; then
    mv recording_backups/* backups/recordings/ 2>/dev/null
    rmdir recording_backups 2>/dev/null
fi

if [ -d "screenshot_backups" ]; then
    mv screenshot_backups/* backups/screenshots/ 2>/dev/null
    rmdir screenshot_backups 2>/dev/null
fi

if [ -d "phase3_backups" ]; then
    mv phase3_backups/* backups/phase3/ 2>/dev/null
    rmdir phase3_backups 2>/dev/null
fi

echo "✅ Backups organized"
echo ""

# Move Cache
echo "🗄️  Organizing cache..."
mv -n vlm_response_cache.py cache/ 2>/dev/null

if [ -d ".demo_vlm_cache" ]; then
    mv .demo_vlm_cache cache/ 2>/dev/null
fi

echo "✅ Cache organized"
echo ""

# Move Scripts
echo "📜 Organizing scripts..."
mv -n setup_venv.sh scripts/ 2>/dev/null
mv -n start_test_ui.sh scripts/ 2>/dev/null
mv -n debug_loading.py scripts/ 2>/dev/null
mv -n demo_enhanced_features.py scripts/ 2>/dev/null

echo "✅ Scripts organized"
echo ""

# Move Results
echo "📊 Organizing results..."
if [ -d "parallel_test_results" ]; then
    mv parallel_test_results tests/ 2>/dev/null
fi

echo "✅ Results organized"
echo ""

# Keep at root level
echo "📌 Files kept at root level:"
echo "   - README.md (project readme)"
echo "   - main.py (main entry point)"
echo "   - llm_helpers.py (shared helpers)"
echo "   - test_automation.db (database)"
echo "   - requirements.txt (dependencies)"
echo "   - package.json (node dependencies)"
echo "   - .gitignore (git config)"
echo ""

echo "================================"
echo "✅ Project Organization Complete!"
echo "================================"
echo ""
echo "📂 New Structure:"
echo "   docs/              - All documentation"
echo "   core/              - Core modules (executors, locators, analyzers, database)"
echo "   ui/                - UI files (Flask app, generators, managers)"
echo "   tests/             - Test files and results"
echo "   scripts/           - Utility scripts"
echo "   cache/             - Cache files"
echo "   backups/           - Backup directories"
echo ""
