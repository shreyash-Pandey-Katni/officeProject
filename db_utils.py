#!/usr/bin/env python3
"""
Database Utilities for Test Automation Framework
Query test history, statistics, and manage data
"""

import sys
import argparse
from test_database import TestDatabase, print_test_statistics, print_flaky_tests
from datetime import datetime
from pathlib import Path


def show_test_history(db: TestDatabase, test_name: str = None, limit: int = 10):
    """Show test execution history"""
    print("\n" + "="*80)
    print("TEST HISTORY")
    print("="*80)
    
    if test_name:
        history = db.get_test_history(test_name, limit)
        if not history:
            print(f"\n❌ No test runs found for '{test_name}'")
            return
        
        print(f"\nShowing last {len(history)} runs of '{test_name}':\n")
    else:
        history = db.get_recent_test_runs(limit)
        if not history:
            print("\n❌ No test runs found")
            return
        
        print(f"\nShowing last {len(history)} test runs:\n")
    
    for run in history:
        status_icon = "✅" if run['status'] == 'pass' else "❌"
        timestamp = run['timestamp']
        duration = run['duration'] or 0
        steps = f"{run['passed_steps']}/{run['total_steps']}" if run['total_steps'] else "N/A"
        
        print(f"{status_icon} ID: {run['id']} | {timestamp}")
        if test_name is None:
            print(f"   Test: {run['test_name']}")
        print(f"   Status: {run['status'].upper()} | Duration: {duration:.1f}s | Steps: {steps}")
        if run['error_message']:
            print(f"   Error: {run['error_message'][:100]}")
        print()
    
    print("="*80 + "\n")


def show_failed_tests(db: TestDatabase, days: int = 7):
    """Show failed tests from recent days"""
    failed = db.get_failed_tests(days)
    
    if not failed:
        print(f"\n✅ No failed tests in the last {days} days!")
        return
    
    print("\n" + "="*80)
    print(f"FAILED TESTS (Last {days} days)")
    print("="*80 + "\n")
    
    for test in failed:
        print(f"❌ {test['test_name']}")
        print(f"   ID: {test['id']} | {test['timestamp']}")
        print(f"   Duration: {test['duration']:.1f}s | Steps: {test['passed_steps']}/{test['total_steps']}")
        if test['error_message']:
            print(f"   Error: {test['error_message'][:100]}")
        print()
    
    print("="*80 + "\n")


def show_test_details(db: TestDatabase, test_run_id: int):
    """Show detailed information about a test run"""
    test_run = db.get_test_run(test_run_id)
    
    if not test_run:
        print(f"\n❌ Test run {test_run_id} not found")
        return
    
    steps = db.get_test_steps(test_run_id)
    
    print("\n" + "="*80)
    print(f"TEST RUN DETAILS - ID {test_run_id}")
    print("="*80)
    
    status_icon = "✅" if test_run['status'] == 'pass' else "❌"
    print(f"\n{status_icon} {test_run['test_name']}")
    print(f"Status: {test_run['status'].upper()}")
    print(f"Timestamp: {test_run['timestamp']}")
    print(f"Duration: {test_run['duration']:.1f}s")
    print(f"Browser: {test_run['browser']} | Viewport: {test_run['viewport']}")
    print(f"Steps: {test_run['passed_steps']} passed, {test_run['failed_steps']} failed, {test_run['total_steps']} total")
    
    if test_run['error_message']:
        print(f"\nError: {test_run['error_message']}")
    
    print("\n" + "-"*80)
    print("STEPS:")
    print("-"*80)
    
    for step in steps:
        step_icon = "✅" if step['success'] else "❌"
        print(f"\n{step_icon} Step {step['step_number']}: {step['action'].upper()}")
        print(f"   Method: {step['method'] or 'N/A'} | Duration: {step['duration']:.2f}s" if step['duration'] else f"   Method: {step['method'] or 'N/A'}")
        
        if not step['success'] and step['error_message']:
            print(f"   Error: {step['error_message']}")
        
        # Show screenshots if available
        for screenshot_type in ['before', 'after']:
            screenshot_path = db.get_screenshot_path(test_run_id, step['step_number'], screenshot_type)
            if screenshot_path and screenshot_path.exists():
                print(f"   Screenshot ({screenshot_type}): {screenshot_path}")
    
    print("\n" + "="*80 + "\n")


def cleanup_old_data(db: TestDatabase, days: int = 90, dry_run: bool = False):
    """Clean up old test data"""
    print("\n" + "="*80)
    print(f"CLEANUP - Data older than {days} days")
    print("="*80 + "\n")
    
    if dry_run:
        print("🔍 DRY RUN MODE - No data will be deleted\n")
        
        # Count what would be deleted
        from test_database import TestDatabase as DB
        temp_db = DB()
        cursor = temp_db.conn.cursor()
        cursor.execute('''
            SELECT COUNT(*) FROM test_runs
            WHERE timestamp < datetime('now', '-' || ? || ' days')
        ''', (days,))
        count = cursor.fetchone()[0]
        temp_db.close()
        
        print(f"Would delete {count} test runs and associated data")
    else:
        print("⚠️  DELETING OLD DATA...\n")
        deleted = db.cleanup_old_data(days)
        print(f"✅ Deleted {deleted} test runs and associated screenshots")
    
    print("\n" + "="*80 + "\n")


def show_storage_stats(db: TestDatabase):
    """Show storage statistics"""
    stats = db.get_storage_stats()
    
    print("\n" + "="*80)
    print("STORAGE STATISTICS")
    print("="*80)
    print(f"\nDatabase Size: {stats['database_size_mb']} MB")
    print(f"Screenshots: {stats['total_screenshots']} files")
    print(f"Screenshots Total Size: {stats['screenshots_size_mb']} MB")
    print(f"Average Screenshot Size: {stats['avg_screenshot_size_kb']} KB")
    print(f"\nTotal Storage Used: {stats['total_size_mb']} MB")
    print("="*80 + "\n")


def main():
    parser = argparse.ArgumentParser(
        description="Database utilities for test automation framework",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Show overall statistics
  python db_utils.py --stats
  
  # Show test history
  python db_utils.py --history
  python db_utils.py --history --test "Browser Activity Replay" --limit 5
  
  # Show flaky tests
  python db_utils.py --flaky --days 7
  
  # Show failed tests
  python db_utils.py --failed --days 7
  
  # Show test run details
  python db_utils.py --details 123
  
  # Storage information
  python db_utils.py --storage
  
  # Cleanup old data (dry run first!)
  python db_utils.py --cleanup 90 --dry-run
  python db_utils.py --cleanup 90
        """
    )
    
    parser.add_argument('--stats', action='store_true', help='Show test statistics')
    parser.add_argument('--history', action='store_true', help='Show test history')
    parser.add_argument('--test', type=str, help='Filter by test name')
    parser.add_argument('--limit', type=int, default=10, help='Limit number of results (default: 10)')
    parser.add_argument('--flaky', action='store_true', help='Show flaky tests')
    parser.add_argument('--failed', action='store_true', help='Show failed tests')
    parser.add_argument('--days', type=int, default=7, help='Number of days to look back (default: 7)')
    parser.add_argument('--details', type=int, metavar='TEST_RUN_ID', help='Show detailed info for test run')
    parser.add_argument('--storage', action='store_true', help='Show storage statistics')
    parser.add_argument('--cleanup', type=int, metavar='DAYS', help='Cleanup data older than DAYS')
    parser.add_argument('--dry-run', action='store_true', help='Dry run for cleanup (no deletion)')
    
    args = parser.parse_args()
    
    # If no arguments, show stats by default
    if len(sys.argv) == 1:
        args.stats = True
    
    # Initialize database
    db = TestDatabase()
    
    try:
        if args.stats:
            print_test_statistics()
        
        if args.history:
            show_test_history(db, args.test, args.limit)
        
        if args.flaky:
            print_flaky_tests(args.days)
        
        if args.failed:
            show_failed_tests(db, args.days)
        
        if args.details:
            show_test_details(db, args.details)
        
        if args.storage:
            show_storage_stats(db)
        
        if args.cleanup is not None:
            cleanup_old_data(db, args.cleanup, args.dry_run)
    
    finally:
        db.close()


if __name__ == "__main__":
    main()
