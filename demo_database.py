#!/usr/bin/env python3
"""
Database Demo Script
Demonstrates database features with example queries
"""

from test_database import TestDatabase
import os


def demo_database():
    """Demonstrate database features"""
    
    print("\n" + "="*80)
    print("DATABASE INTEGRATION DEMO")
    print("="*80 + "\n")
    
    # Initialize database
    db = TestDatabase()
    
    # 1. Show current statistics
    print("📊 CURRENT STATISTICS:")
    print("-" * 80)
    stats = db.get_test_statistics()
    print(f"Total Test Runs: {stats.get('total_runs', 0) or 0}")
    print(f"Success Rate: {stats.get('pass_rate', 0) or 0}%")
    print(f"Average Duration: {stats.get('avg_duration') or 0:.2f}s")
    print(f"Total Steps Executed: {stats.get('total_steps_executed', 0) or 0}")
    
    # 2. Show recent test runs
    print("\n\n📋 RECENT TEST RUNS:")
    print("-" * 80)
    recent = db.get_recent_test_runs(limit=5)
    if recent:
        for run in recent:
            status_icon = "✅" if run['status'] == 'pass' else "❌"
            print(f"{status_icon} Test ID {run['id']}: {run['test_name']}")
            print(f"   {run['timestamp']} | {run['duration']:.1f}s | Steps: {run['passed_steps']}/{run['total_steps']}")
    else:
        print("No test runs found. Run 'python replay_browser_activities.py' first!")
    
    # 3. Show storage information
    print("\n\n💾 STORAGE INFORMATION:")
    print("-" * 80)
    storage = db.get_storage_stats()
    print(f"Database Size: {storage['database_size_mb']} MB")
    print(f"Total Screenshots: {storage['total_screenshots']} files")
    print(f"Screenshots Size: {storage['screenshots_size_mb']} MB")
    print(f"Total Storage: {storage['total_size_mb']} MB")
    
    # 4. Show screenshot organization
    print("\n\n📸 SCREENSHOT ORGANIZATION:")
    print("-" * 80)
    screenshot_dir = db.screenshot_dir
    if screenshot_dir.exists():
        # Count organized screenshots
        organized_count = 0
        for root, dirs, files in os.walk(screenshot_dir):
            if 'test_' in root:
                organized_count += len([f for f in files if f.endswith('.png')])
        
        print(f"Screenshot directory: {screenshot_dir}")
        print(f"Organized screenshots: {organized_count} files")
        print(f"Organization: screenshots/YYYY/MM/DD/test_ID/step_N_type.png")
    
    # 5. Show example queries
    print("\n\n🔍 EXAMPLE QUERIES:")
    print("-" * 80)
    
    # Get test history for a specific test
    history = db.get_test_history("Browser Activity Replay", limit=3)
    if history:
        print(f"\nLast 3 runs of 'Browser Activity Replay':")
        for run in history:
            status_icon = "✅" if run['status'] == 'pass' else "❌"
            print(f"  {status_icon} {run['timestamp']} | {run['duration']:.1f}s")
    
    # Check for flaky tests
    flaky = db.get_flaky_tests(days=30)
    if flaky:
        print(f"\nFlaky tests found (last 30 days):")
        for test in flaky:
            print(f"  ⚠️  {test['test_name']}: {test['failure_rate']}% failure rate ({test['fails']}/{test['total_runs']} runs)")
    else:
        print("\n✅ No flaky tests detected!")
    
    # Show specific test details
    if recent:
        test_id = recent[0]['id']
        print(f"\n\nDetails for Test Run #{test_id}:")
        steps = db.get_test_steps(test_id)
        for step in steps:
            status_icon = "✅" if step['success'] else "❌"
            print(f"  {status_icon} Step {step['step_number']}: {step['action']} ({step['method']}) - {step['duration']:.2f}s" if step['duration'] else f"  {status_icon} Step {step['step_number']}: {step['action']} ({step['method']})")
    
    # 6. Show available utilities
    print("\n\n🛠️  AVAILABLE UTILITIES:")
    print("-" * 80)
    print("View statistics:      python db_utils.py --stats")
    print("View history:         python db_utils.py --history")
    print("View test details:    python db_utils.py --details <ID>")
    print("Find flaky tests:     python db_utils.py --flaky")
    print("View failed tests:    python db_utils.py --failed")
    print("Storage info:         python db_utils.py --storage")
    print("Cleanup old data:     python db_utils.py --cleanup 90")
    
    # 7. Show Python API examples
    print("\n\n💻 PYTHON API EXAMPLES:")
    print("-" * 80)
    print("""
# Import database
from test_database import TestDatabase

# Create instance
db = TestDatabase()

# Query methods
stats = db.get_test_statistics()          # Overall stats
history = db.get_test_history("Test")    # Test history
flaky = db.get_flaky_tests(days=7)       # Flaky tests
failed = db.get_failed_tests(days=7)     # Failed tests
run = db.get_test_run(test_id)           # Specific test
steps = db.get_test_steps(test_id)       # Test steps
storage = db.get_storage_stats()         # Storage info

# Cleanup
deleted = db.cleanup_old_data(days=90)   # Remove old data

db.close()
    """)
    
    # 8. Show migration benefits
    print("\n\n🎯 BENEFITS OF DATABASE INTEGRATION:")
    print("-" * 80)
    print("✅ Persistent test history across sessions")
    print("✅ Track test trends and success rates")
    print("✅ Identify flaky and failing tests quickly")
    print("✅ Organized screenshot storage by date")
    print("✅ Automatic cleanup of old data")
    print("✅ Easy querying with Python API or CLI tools")
    print("✅ Team collaboration (share database file)")
    print("✅ Export data for reporting and analytics")
    
    # 9. Next steps
    print("\n\n🚀 NEXT STEPS:")
    print("-" * 80)
    print("1. Run tests: python replay_browser_activities.py")
    print("2. Check stats: python db_utils.py --stats")
    print("3. View history: python db_utils.py --history")
    print("4. Setup cleanup: Add to cron/scheduler for automatic maintenance")
    print("5. Explore advanced features in DATABASE_AND_STORAGE_COMPARISON.md")
    
    print("\n" + "="*80 + "\n")
    
    db.close()


if __name__ == "__main__":
    demo_database()
