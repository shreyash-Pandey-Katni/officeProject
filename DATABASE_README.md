# SQLite Database Integration

## Overview
The browser automation testing framework now includes **SQLite database integration** for persistent storage of test results, history tracking, and organized screenshot management.

## What's New ✨

### 1. **Persistent Test Storage**
- All test runs are automatically saved to `test_automation.db`
- Track test history, success rates, and trends
- Never lose test results across sessions

### 2. **Organized Screenshot Storage**
Screenshots are now organized by date and test run:
```
screenshots/
└── 2025/
    └── 10/
        └── 17/
            └── test_1/
                ├── step_1_before.png
                ├── step_1_after.png
                ├── step_2_before.png
                ├── step_2_after.png
                └── ...
```

### 3. **Database Utilities**
New `db_utils.py` script for querying and managing test data.

## Quick Start 🚀

### Run Tests (Automatic Database Saving)
```bash
python replay_browser_activities.py
```
Test results are automatically saved to the database!

### View Statistics
```bash
python db_utils.py --stats
```
Shows:
- Total test runs
- Pass/fail rates
- Average duration
- Storage usage

### View Test History
```bash
# Show all recent tests
python db_utils.py --history

# Show history for specific test
python db_utils.py --history --test "Browser Activity Replay" --limit 5
```

### View Test Details
```bash
python db_utils.py --details 1
```
Shows detailed step-by-step information for test run ID 1.

### Find Flaky Tests
```bash
python db_utils.py --flaky --days 7
```
Identifies tests with inconsistent results.

### View Failed Tests
```bash
python db_utils.py --failed --days 7
```
Lists all failed tests from the last 7 days.

### Storage Information
```bash
python db_utils.py --storage
```
Shows database size, screenshot count, and total storage used.

### Cleanup Old Data
```bash
# Dry run first (no deletion)
python db_utils.py --cleanup 90 --dry-run

# Actually delete data older than 90 days
python db_utils.py --cleanup 90
```

## Database Schema 📊

### Tables

#### `test_runs`
Stores overall test execution information:
- `id`: Unique test run ID
- `test_name`: Name of the test
- `timestamp`: When the test ran
- `status`: pass/fail/running
- `duration`: Total execution time
- `browser`: Browser used (chrome)
- `viewport`: Viewport size
- `total_steps`: Total number of steps
- `passed_steps`: Number of successful steps
- `failed_steps`: Number of failed steps
- `error_message`: Error details if failed

#### `test_steps`
Stores individual step information:
- `id`: Unique step ID
- `test_run_id`: Parent test run
- `step_number`: Step number (1, 2, 3...)
- `action`: Action type (navigation, click, text_input)
- `success`: Whether step succeeded
- `error_message`: Error details if failed
- `method`: Method used (xpath, shadow_dom, etc.)
- `duration`: Step execution time
- `element_info`: Additional element data (JSON)

#### `screenshots`
Stores screenshot metadata:
- `id`: Unique screenshot ID
- `test_run_id`: Parent test run
- `step_number`: Associated step
- `type`: Screenshot type (before/after/failure)
- `file_path`: Relative path to file
- `file_size`: File size in bytes
- `captured_at`: Timestamp

## Example Output 📈

### Statistics
```
============================================================
TEST STATISTICS
============================================================
Total Test Runs: 10
Passed: 9 (90.0%)
Failed: 1
Unique Tests: 2
Total Steps Executed: 30
Average Duration: 42.5s
Min/Max Duration: 38.2s / 51.3s

============================================================
STORAGE STATISTICS
============================================================
Database Size: 0.12 MB
Screenshots: 60 files
Screenshots Size: 18.5 MB
Average Screenshot: 315.8 KB
Total Storage Used: 18.62 MB
============================================================
```

### Test History
```
================================================================================
TEST HISTORY
================================================================================

Showing last 3 test runs:

✅ ID: 3 | 2025-10-17 15:18:19
   Test: Browser Activity Replay
   Status: PASS | Duration: 45.8s | Steps: 3/3

✅ ID: 2 | 2025-10-17 14:38:47
   Test: Browser Activity Replay
   Status: PASS | Duration: 43.2s | Steps: 3/3

❌ ID: 1 | 2025-10-17 13:22:15
   Test: Browser Activity Replay
   Status: FAIL | Duration: 22.5s | Steps: 1/3
   Error: Element not found
================================================================================
```

### Flaky Tests
```
============================================================
FLAKY TESTS (Last 7 days)
============================================================

❌ Search Functionality Test
   Total Runs: 10
   Passes: 7 | Fails: 3
   Failure Rate: 30.0%
   Avg Duration: 41.23s

❌ Login Flow Test
   Total Runs: 8
   Passes: 6 | Fails: 2
   Failure Rate: 25.0%
   Avg Duration: 15.87s
============================================================
```

## Features 🎯

### Automatic Integration
- **Zero configuration** - Works out of the box
- **Automatic saving** - All test runs are saved
- **Organized storage** - Screenshots in date-based folders
- **Metadata tracking** - Complete test execution details

### Query Capabilities
- **Test history** - View past test executions
- **Statistics** - Track success rates and trends
- **Flaky test detection** - Find unreliable tests
- **Failed test tracking** - Quickly find failures
- **Step-by-step details** - Complete execution breakdown

### Maintenance
- **Auto-cleanup** - Remove old test data
- **Storage tracking** - Monitor disk usage
- **Dry run mode** - Preview cleanup before deleting

## Benefits 🌟

1. **Never Lose Data** - All test results are preserved
2. **Track Trends** - See how tests perform over time
3. **Find Problems** - Identify flaky and failing tests
4. **Save Disk Space** - Automatic cleanup of old data
5. **Easy Queries** - Simple CLI tools for data access
6. **Team Collaboration** - Share test history (commit the .db file)

## Storage Impact 💾

### Small Project (100 tests)
- Database: ~1 MB
- Screenshots: ~30-50 MB (with cleanup)
- **Total: ~31-51 MB**

### Medium Project (1000 tests)
- Database: ~10 MB
- Screenshots: ~100-200 MB (with 90-day cleanup)
- **Total: ~110-210 MB**

### Best Practices
- Run cleanup regularly: `python db_utils.py --cleanup 90`
- Keep database file in version control (small size)
- Exclude screenshots/ from git (add to .gitignore)

## Migration from Old System ⚡

### What Changed?
- **Before**: Loose screenshot files, no history
- **After**: Organized screenshots + database tracking

### Backward Compatible
- Old screenshots remain in `screenshots/` (not deleted)
- New screenshots go to organized folders
- Both systems work side-by-side

### Cleanup Old Screenshots
```bash
# Remove old unorganized screenshots (keep new organized ones)
rm screenshots/screenshot_*.png
rm screenshots/step_*.png
```

## Advanced Usage 🔧

### Python API
```python
from test_database import TestDatabase

# Initialize database
db = TestDatabase()

# Query test history
history = db.get_test_history("My Test", limit=10)

# Get statistics
stats = db.get_test_statistics()

# Find flaky tests
flaky = db.get_flaky_tests(days=7)

# Get specific test run
test_run = db.get_test_run(test_run_id=1)
steps = db.get_test_steps(test_run_id=1)

# Cleanup
deleted = db.cleanup_old_data(days=90)

db.close()
```

### Custom Queries
```python
import sqlite3

conn = sqlite3.connect('test_automation.db')
cursor = conn.cursor()

# Find slowest tests
cursor.execute('''
    SELECT test_name, AVG(duration) as avg_duration
    FROM test_runs
    GROUP BY test_name
    ORDER BY avg_duration DESC
    LIMIT 5
''')

for row in cursor.fetchall():
    print(f"{row[0]}: {row[1]:.2f}s")

conn.close()
```

## Troubleshooting 🔧

### Database locked error
**Cause**: Multiple processes accessing database simultaneously  
**Solution**: Close other processes or wait for them to finish

### Screenshots not appearing
**Cause**: File was moved or deleted  
**Solution**: Screenshot paths are relative, ensure working directory is correct

### Database too large
**Cause**: Too many old test runs  
**Solution**: Run cleanup: `python db_utils.py --cleanup 30`

## Future Enhancements 🚀

See `DATABASE_AND_STORAGE_COMPARISON.md` for:
- PostgreSQL migration path (team collaboration)
- AWS S3 integration (cloud storage)
- Advanced analytics
- Real-time dashboards
- CI/CD integration

## Files Created 📁

1. **`test_database.py`** - Database module (544 lines)
2. **`db_utils.py`** - Command-line utilities (237 lines)
3. **`test_automation.db`** - SQLite database (auto-created)
4. **`DATABASE_AND_STORAGE_COMPARISON.md`** - Comprehensive guide (38 KB)
5. **`DATABASE_README.md`** - This file

## Commands Reference 📝

```bash
# Statistics
python db_utils.py --stats

# History
python db_utils.py --history
python db_utils.py --history --test "Test Name" --limit 5

# Flaky tests
python db_utils.py --flaky --days 7

# Failed tests
python db_utils.py --failed --days 7

# Test details
python db_utils.py --details <TEST_RUN_ID>

# Storage
python db_utils.py --storage

# Cleanup
python db_utils.py --cleanup 90 --dry-run
python db_utils.py --cleanup 90
```

---

**Ready to use!** The database integration is fully functional and automatically saves all test results. 🎉
