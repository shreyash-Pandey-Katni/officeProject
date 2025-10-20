"""
SQLite Database for Browser Automation Testing Framework
Stores test runs, test steps, and screenshot metadata
"""

import sqlite3
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Optional, Tuple, Any
import json


class TestDatabase:
    """SQLite database for storing test execution data and screenshots"""
    
    def __init__(self, db_path: str = 'test_automation.db', screenshot_dir: str = 'screenshots'):
        """
        Initialize database connection and create tables
        
        Args:
            db_path: Path to SQLite database file
            screenshot_dir: Directory for storing screenshots
        """
        self.db_path = db_path
        self.screenshot_dir = Path(screenshot_dir)
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row  # Access columns by name
        self.create_tables()
        self.screenshot_dir.mkdir(exist_ok=True)
    
    def create_tables(self):
        """Create database tables if they don't exist"""
        cursor = self.conn.cursor()
        
        # Test runs table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS test_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                test_name TEXT NOT NULL,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                status TEXT NOT NULL,
                duration REAL,
                error_message TEXT,
                browser TEXT DEFAULT 'chrome',
                viewport TEXT DEFAULT '1920x1080',
                total_steps INTEGER DEFAULT 0,
                passed_steps INTEGER DEFAULT 0,
                failed_steps INTEGER DEFAULT 0
            )
        ''')
        
        # Test steps table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS test_steps (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                test_run_id INTEGER NOT NULL,
                step_number INTEGER NOT NULL,
                action TEXT NOT NULL,
                success BOOLEAN NOT NULL,
                error_message TEXT,
                method TEXT,
                duration REAL,
                element_info TEXT,
                FOREIGN KEY (test_run_id) REFERENCES test_runs(id) ON DELETE CASCADE
            )
        ''')
        
        # Screenshots table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS screenshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                test_run_id INTEGER NOT NULL,
                step_number INTEGER NOT NULL,
                type TEXT NOT NULL,
                file_path TEXT NOT NULL,
                file_size INTEGER,
                captured_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (test_run_id) REFERENCES test_runs(id) ON DELETE CASCADE
            )
        ''')
        
        # Create indexes for better query performance
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_test_runs_timestamp ON test_runs(timestamp)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_test_runs_status ON test_runs(status)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_test_runs_name ON test_runs(test_name)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_test_steps_run ON test_steps(test_run_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_screenshots_run ON screenshots(test_run_id)')
        
        self.conn.commit()
    
    def save_test_run(self, test_name: str, status: str = 'running', duration: float = 0, 
                      error: Optional[str] = None, browser: str = 'chrome', 
                      viewport: str = '1920x1080') -> int:
        """
        Save a test run record
        
        Args:
            test_name: Name of the test
            status: Test status ('running', 'pass', 'fail')
            duration: Test duration in seconds
            error: Error message if failed
            browser: Browser used
            viewport: Viewport size
            
        Returns:
            ID of the created test run
        """
        cursor = self.conn.cursor()
        cursor.execute('''
            INSERT INTO test_runs (test_name, status, duration, error_message, browser, viewport)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (test_name, status, duration, error, browser, viewport))
        self.conn.commit()
        return cursor.lastrowid
    
    def update_test_run(self, test_run_id: int, status: str, duration: float, 
                       total_steps: int = 0, passed_steps: int = 0, 
                       failed_steps: int = 0, error: Optional[str] = None):
        """
        Update test run with final results
        
        Args:
            test_run_id: Test run ID to update
            status: Final status
            duration: Total duration
            total_steps: Total number of steps
            passed_steps: Number of passed steps
            failed_steps: Number of failed steps
            error: Error message if any
        """
        cursor = self.conn.cursor()
        cursor.execute('''
            UPDATE test_runs 
            SET status = ?, duration = ?, total_steps = ?, passed_steps = ?, 
                failed_steps = ?, error_message = ?
            WHERE id = ?
        ''', (status, duration, total_steps, passed_steps, failed_steps, error, test_run_id))
        self.conn.commit()
    
    def save_test_step(self, test_run_id: int, step_number: int, action: str, 
                       success: bool, error: Optional[str] = None, method: Optional[str] = None,
                       duration: float = 0, element_info: Optional[Dict] = None) -> int:
        """
        Save a test step record
        
        Args:
            test_run_id: Parent test run ID
            step_number: Step number (1-indexed)
            action: Action type (navigation, click, text_input, etc.)
            success: Whether step succeeded
            error: Error message if failed
            method: Method used to find element
            duration: Step duration
            element_info: Additional element information
            
        Returns:
            ID of the created test step
        """
        cursor = self.conn.cursor()
        element_json = json.dumps(element_info) if element_info else None
        cursor.execute('''
            INSERT INTO test_steps (test_run_id, step_number, action, success, 
                                   error_message, method, duration, element_info)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (test_run_id, step_number, action, success, error, method, duration, element_json))
        self.conn.commit()
        return cursor.lastrowid
    
    def save_screenshot(self, test_run_id: int, step_number: int, 
                       screenshot_type: str, source_path: str) -> Optional[int]:
        """
        Save screenshot metadata and organize file
        
        Args:
            test_run_id: Parent test run ID
            step_number: Step number
            screenshot_type: Type of screenshot ('before', 'after', 'failure')
            source_path: Current path of screenshot file
            
        Returns:
            ID of the created screenshot record, or None if file doesn't exist
        """
        if not os.path.exists(source_path):
            return None
        
        # Create organized directory structure: screenshots/YYYY/MM/DD/test_ID/
        date_path = datetime.now().strftime('%Y/%m/%d')
        dest_dir = self.screenshot_dir / date_path / f'test_{test_run_id}'
        dest_dir.mkdir(parents=True, exist_ok=True)
        
        # Move screenshot to organized location
        filename = f'step_{step_number}_{screenshot_type}.png'
        dest_path = dest_dir / filename
        
        # Move file
        os.rename(source_path, dest_path)
        file_size = dest_path.stat().st_size
        
        # Save metadata to database
        cursor = self.conn.cursor()
        relative_path = str(dest_path.relative_to(self.screenshot_dir))
        cursor.execute('''
            INSERT INTO screenshots (test_run_id, step_number, type, file_path, file_size)
            VALUES (?, ?, ?, ?, ?)
        ''', (test_run_id, step_number, screenshot_type, relative_path, file_size))
        self.conn.commit()
        return cursor.lastrowid
    
    def get_screenshot_path(self, test_run_id: int, step_number: int, 
                           screenshot_type: str) -> Optional[Path]:
        """
        Get full path to a screenshot
        
        Args:
            test_run_id: Test run ID
            step_number: Step number
            screenshot_type: Screenshot type
            
        Returns:
            Full path to screenshot file, or None if not found
        """
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT file_path FROM screenshots
            WHERE test_run_id = ? AND step_number = ? AND type = ?
        ''', (test_run_id, step_number, screenshot_type))
        row = cursor.fetchone()
        if row:
            return self.screenshot_dir / row['file_path']
        return None
    
    def get_test_run(self, test_run_id: int) -> Optional[Dict]:
        """
        Get test run details
        
        Args:
            test_run_id: Test run ID
            
        Returns:
            Dictionary with test run details, or None if not found
        """
        cursor = self.conn.cursor()
        cursor.execute('SELECT * FROM test_runs WHERE id = ?', (test_run_id,))
        row = cursor.fetchone()
        return dict(row) if row else None
    
    def get_test_steps(self, test_run_id: int) -> List[Dict]:
        """
        Get all steps for a test run
        
        Args:
            test_run_id: Test run ID
            
        Returns:
            List of step dictionaries
        """
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT * FROM test_steps 
            WHERE test_run_id = ? 
            ORDER BY step_number
        ''', (test_run_id,))
        return [dict(row) for row in cursor.fetchall()]
    
    def get_test_history(self, test_name: str, limit: int = 10) -> List[Dict]:
        """
        Get recent runs of a specific test
        
        Args:
            test_name: Name of the test
            limit: Maximum number of results
            
        Returns:
            List of test run dictionaries
        """
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT id, timestamp, status, duration, error_message, 
                   total_steps, passed_steps, failed_steps
            FROM test_runs
            WHERE test_name = ?
            ORDER BY timestamp DESC
            LIMIT ?
        ''', (test_name, limit))
        return [dict(row) for row in cursor.fetchall()]
    
    def get_flaky_tests(self, days: int = 7, min_runs: int = 5) -> List[Dict]:
        """
        Find tests with inconsistent results (flaky tests)
        
        Args:
            days: Number of days to look back
            min_runs: Minimum number of runs to consider
            
        Returns:
            List of flaky test dictionaries with statistics
        """
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT 
                test_name,
                COUNT(*) as total_runs,
                SUM(CASE WHEN status='pass' THEN 1 ELSE 0 END) as passes,
                SUM(CASE WHEN status='fail' THEN 1 ELSE 0 END) as fails,
                ROUND(SUM(CASE WHEN status='fail' THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 2) as failure_rate,
                AVG(duration) as avg_duration
            FROM test_runs
            WHERE timestamp > datetime('now', '-' || ? || ' days')
            GROUP BY test_name
            HAVING COUNT(*) >= ?
                AND passes > 0 
                AND fails > 0
            ORDER BY failure_rate DESC
        ''', (days, min_runs))
        return [dict(row) for row in cursor.fetchall()]
    
    def get_test_statistics(self) -> Dict:
        """
        Get overall test statistics
        
        Returns:
            Dictionary with overall statistics
        """
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT 
                COUNT(*) as total_runs,
                SUM(CASE WHEN status='pass' THEN 1 ELSE 0 END) as passes,
                SUM(CASE WHEN status='fail' THEN 1 ELSE 0 END) as fails,
                ROUND(SUM(CASE WHEN status='pass' THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 2) as pass_rate,
                AVG(duration) as avg_duration,
                MIN(duration) as min_duration,
                MAX(duration) as max_duration,
                COUNT(DISTINCT test_name) as unique_tests,
                SUM(total_steps) as total_steps_executed
            FROM test_runs
        ''')
        row = cursor.fetchone()
        return dict(row) if row else {}
    
    def get_recent_test_runs(self, limit: int = 20) -> List[Dict]:
        """
        Get most recent test runs
        
        Args:
            limit: Maximum number of results
            
        Returns:
            List of test run dictionaries
        """
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT * FROM test_runs
            ORDER BY timestamp DESC
            LIMIT ?
        ''', (limit,))
        return [dict(row) for row in cursor.fetchall()]
    
    def get_failed_tests(self, days: int = 7) -> List[Dict]:
        """
        Get failed test runs from recent days
        
        Args:
            days: Number of days to look back
            
        Returns:
            List of failed test run dictionaries
        """
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT * FROM test_runs
            WHERE status = 'fail'
                AND timestamp > datetime('now', '-' || ? || ' days')
            ORDER BY timestamp DESC
        ''', (days,))
        return [dict(row) for row in cursor.fetchall()]
    
    def cleanup_old_data(self, days: int = 90) -> int:
        """
        Remove old test runs and associated screenshots
        
        Args:
            days: Delete data older than this many days
            
        Returns:
            Number of test runs deleted
        """
        cursor = self.conn.cursor()
        
        # Get old test runs
        cursor.execute('''
            SELECT id FROM test_runs
            WHERE timestamp < datetime('now', '-' || ? || ' days')
        ''', (days,))
        old_runs = cursor.fetchall()
        
        if not old_runs:
            return 0
        
        # Delete associated screenshots from disk
        for row in old_runs:
            run_id = row['id']
            cursor.execute('SELECT file_path FROM screenshots WHERE test_run_id = ?', (run_id,))
            for screenshot_row in cursor.fetchall():
                file_path = self.screenshot_dir / screenshot_row['file_path']
                if file_path.exists():
                    try:
                        file_path.unlink()
                    except Exception as e:
                        print(f"Warning: Could not delete {file_path}: {e}")
        
        # Delete from database (cascades to screenshots and test_steps)
        cursor.execute('''
            DELETE FROM test_runs 
            WHERE timestamp < datetime('now', '-' || ? || ' days')
        ''', (days,))
        
        self.conn.commit()
        
        # Clean up empty directories
        self._cleanup_empty_dirs()
        
        return len(old_runs)
    
    def _cleanup_empty_dirs(self):
        """Remove empty directories in screenshot folder"""
        for root, dirs, files in os.walk(self.screenshot_dir, topdown=False):
            for directory in dirs:
                dir_path = Path(root) / directory
                try:
                    if not any(dir_path.iterdir()):
                        dir_path.rmdir()
                except Exception:
                    pass
    
    def get_storage_stats(self) -> Dict:
        """
        Get storage statistics
        
        Returns:
            Dictionary with storage statistics
        """
        cursor = self.conn.cursor()
        
        # Database size
        db_size = os.path.getsize(self.db_path) if os.path.exists(self.db_path) else 0
        
        # Screenshot statistics
        cursor.execute('''
            SELECT 
                COUNT(*) as total_screenshots,
                SUM(file_size) as total_size,
                AVG(file_size) as avg_size
            FROM screenshots
        ''')
        screenshot_stats = dict(cursor.fetchone())
        
        return {
            'database_size_mb': round(db_size / (1024 * 1024), 2),
            'total_screenshots': screenshot_stats['total_screenshots'],
            'screenshots_size_mb': round((screenshot_stats['total_size'] or 0) / (1024 * 1024), 2),
            'avg_screenshot_size_kb': round((screenshot_stats['avg_size'] or 0) / 1024, 2),
            'total_size_mb': round((db_size + (screenshot_stats['total_size'] or 0)) / (1024 * 1024), 2)
        }
    
    def close(self):
        """Close database connection"""
        if self.conn:
            self.conn.close()
    
    def __enter__(self):
        """Context manager entry"""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.close()


# Utility functions for easy access
def get_database() -> TestDatabase:
    """Get database instance"""
    return TestDatabase()


def print_test_statistics():
    """Print test statistics to console"""
    with get_database() as db:
        stats = db.get_test_statistics()
        storage = db.get_storage_stats()
        
        print("\n" + "="*60)
        print("TEST STATISTICS")
        print("="*60)
        print(f"Total Test Runs: {stats.get('total_runs', 0) or 0}")
        print(f"Passed: {stats.get('passes', 0) or 0} ({stats.get('pass_rate', 0) or 0}%)")
        print(f"Failed: {stats.get('fails', 0) or 0}")
        print(f"Unique Tests: {stats.get('unique_tests', 0) or 0}")
        print(f"Total Steps Executed: {stats.get('total_steps_executed', 0) or 0}")
        print(f"Average Duration: {stats.get('avg_duration') or 0:.2f}s")
        print(f"Min/Max Duration: {stats.get('min_duration') or 0:.2f}s / {stats.get('max_duration') or 0:.2f}s")
        
        print("\n" + "="*60)
        print("STORAGE STATISTICS")
        print("="*60)
        print(f"Database Size: {storage['database_size_mb']} MB")
        print(f"Screenshots: {storage['total_screenshots']} files")
        print(f"Screenshots Size: {storage['screenshots_size_mb']} MB")
        print(f"Average Screenshot: {storage['avg_screenshot_size_kb']} KB")
        print(f"Total Storage Used: {storage['total_size_mb']} MB")
        print("="*60 + "\n")


def print_flaky_tests(days: int = 7):
    """Print flaky tests to console"""
    with get_database() as db:
        flaky = db.get_flaky_tests(days=days)
        
        if not flaky:
            print(f"\n✅ No flaky tests found in the last {days} days!")
            return
        
        print("\n" + "="*60)
        print(f"FLAKY TESTS (Last {days} days)")
        print("="*60)
        for test in flaky:
            print(f"\n❌ {test['test_name']}")
            print(f"   Total Runs: {test['total_runs']}")
            print(f"   Passes: {test['passes']} | Fails: {test['fails']}")
            print(f"   Failure Rate: {test['failure_rate']}%")
            print(f"   Avg Duration: {test['avg_duration']:.2f}s")
        print("="*60 + "\n")


if __name__ == "__main__":
    # Test database creation
    print("Initializing test database...")
    db = TestDatabase()
    print(f"✅ Database created: {db.db_path}")
    print(f"✅ Screenshot directory: {db.screenshot_dir}")
    
    # Print statistics
    print_test_statistics()
    
    db.close()
