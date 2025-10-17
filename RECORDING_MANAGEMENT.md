# Recording Management - Quick Reference

## Clear Last Recording and Start Fresh

### Option 1: Using the Recording Manager (Recommended) ✅

```bash
# Clear current recording (creates automatic backup)
python manage_recordings.py clear

# Start new recording
python main.py
```

**What it does:**
- ✅ Automatically backs up your current recording before clearing
- ✅ Clears `activity_log.json`
- ✅ Ready for fresh recording

---

### Option 2: Manual Method

```bash
# Backup current recording (optional but recommended)
cp activity_log.json activity_log_backup.json

# Clear the recording
echo "[]" > activity_log.json

# Start new recording
python main.py
```

---

### Option 3: Delete Everything

```bash
# Remove recording and screenshots
rm activity_log.json
rm -rf screenshots/

# Start new recording
python main.py
```

---

## Common Commands

### 📄 View Current Recording Info
```bash
python manage_recordings.py info
```
Shows:
- Number of activities
- Activity types (clicks, inputs, etc.)
- File size and date
- Whether enhanced locators are present
- Screenshot count

### 💾 Backup Current Recording
```bash
python manage_recordings.py backup my_test_name
```
Saves to: `recording_backups/my_test_name_TIMESTAMP.json`

### 🔄 Restore a Backup
```bash
python manage_recordings.py restore my_test_name
```
Restores recording and screenshots (if available)

### 📋 List All Backups
```bash
python manage_recordings.py list
```
Shows all available backups with dates and sizes

---

## Workflow Examples

### Example 1: Test Different Scenarios

```bash
# Record first scenario
python main.py
# ... interact with website ...
# Press Ctrl+C when done

# Backup first scenario
python manage_recordings.py backup login_flow

# Clear and record second scenario
python manage_recordings.py clear
python main.py
# ... interact with website ...
# Press Ctrl+C when done

# Backup second scenario
python manage_recordings.py backup checkout_flow

# List all recordings
python manage_recordings.py list
```

### Example 2: Quick Re-record

```bash
# Made a mistake during recording?
python manage_recordings.py clear  # Auto-backs up
python main.py                     # Start fresh
```

### Example 3: Switch Between Tests

```bash
# Switch to login test
python manage_recordings.py restore login_flow
python replay_browser_activities.py

# Switch to checkout test
python manage_recordings.py restore checkout_flow
python replay_browser_activities.py
```

---

## File Locations

```
project/
├── activity_log.json              # Current recording
├── screenshots/                   # Current screenshots
├── recording_backups/             # Backup recordings
│   ├── login_flow_20251017_143022.json
│   ├── checkout_flow_20251017_150134.json
│   └── auto_backup_20251017_153045.json
└── screenshot_backups/            # Backup screenshots
    ├── login_flow_20251017_143022/
    └── checkout_flow_20251017_150134/
```

---

## Tips

### ⚡ Quick Clear
```bash
# Create alias for quick clearing
alias clear-recording="python manage_recordings.py clear"
clear-recording
```

### 🔍 Check Before Recording
```bash
# Always check if there's existing data
python manage_recordings.py info

# If you see activities, decide:
# 1. Backup: python manage_recordings.py backup <name>
# 2. Clear: python manage_recordings.py clear
# 3. Keep: just start replaying
```

### 🛡️ Safety
The `clear` command ALWAYS creates an automatic backup:
```
⚠️  Current recording has 15 activities
Are you sure you want to clear it? (yes/no): yes
📦 Creating automatic backup: auto_backup_20251017_143022
✅ Recording cleared! Ready for new recording.
   Backup saved to: recording_backups/auto_backup_20251017_143022.json
```

### 📊 Verify Recording
```bash
# After recording, check it's valid
python manage_recordings.py info

# You should see:
#   ✅ Enhanced locators captured (Phase 1)
#   ✅ VLM descriptions included
```

---

## Troubleshooting

### "No recording to clear"
✅ This is fine! Just start recording:
```bash
python main.py
```

### "Recording is empty"
Check if you recorded any activities:
```bash
python manage_recordings.py info
```

### Want to keep screenshots
Backups automatically include screenshots:
```bash
python manage_recordings.py backup with_screenshots
```

### Manual JSON editing needed
```bash
# Open in editor
code activity_log.json

# Or use jq for pretty printing
cat activity_log.json | jq '.'
```

---

## Advanced

### Merge Multiple Recordings

```python
import json

# Load multiple recordings
with open('recording_backups/test1.json') as f:
    rec1 = json.load(f)

with open('recording_backups/test2.json') as f:
    rec2 = json.load(f)

# Merge
merged = rec1 + rec2

# Save
with open('activity_log.json', 'w') as f:
    json.dump(merged, f, indent=2)
```

### Filter Activities

```python
import json

with open('activity_log.json') as f:
    activities = json.load(f)

# Keep only clicks
clicks_only = [a for a in activities if a['action'] == 'click']

with open('activity_log.json', 'w') as f:
    json.dump(clicks_only, f, indent=2)
```

---

## Summary

**To clear and start fresh:**
```bash
python manage_recordings.py clear
python main.py
```

**To manage multiple tests:**
```bash
# Backup each test with a meaningful name
python manage_recordings.py backup test_name

# Switch between tests anytime
python manage_recordings.py restore test_name
```

**Need help?**
```bash
python manage_recordings.py
```

🎉 Happy Testing!
