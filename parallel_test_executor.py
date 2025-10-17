"""
Parallel Test Execution Engine
Run multiple browser tests in parallel to reduce total execution time

Phase 4 - Optimization Feature #1

Example:
    executor = ParallelTestExecutor(max_workers=4)
    results = executor.run_tests([
        "test1.json",
        "test2.json",
        "test3.json"
    ])
    
    # 4 tests that would take 20 minutes sequentially
    # Now complete in ~5 minutes with parallel execution!
"""

from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor, as_completed
from datetime import datetime
import json
import time
import threading
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
import traceback


@dataclass
class TestResult:
    """Result of a single test execution"""
    test_file: str
    status: str  # success, failed, error
    start_time: datetime
    end_time: datetime
    duration_seconds: float
    activities_executed: int
    activities_failed: int
    error_message: Optional[str] = None
    screenshots_captured: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'test_file': self.test_file,
            'status': self.status,
            'start_time': self.start_time.isoformat(),
            'end_time': self.end_time.isoformat(),
            'duration_seconds': self.duration_seconds,
            'activities_executed': self.activities_executed,
            'activities_failed': self.activities_failed,
            'error_message': self.error_message,
            'screenshots_captured': self.screenshots_captured
        }


@dataclass
class ParallelExecutionSummary:
    """Summary of parallel test execution"""
    total_tests: int
    successful_tests: int
    failed_tests: int
    error_tests: int
    total_duration_seconds: float
    average_test_duration: float
    sequential_estimated_time: float
    time_saved_seconds: float
    speedup_factor: float
    test_results: List[TestResult]
    
    def print_summary(self):
        """Print human-readable summary"""
        print("\n" + "="*80)
        print("PARALLEL TEST EXECUTION SUMMARY")
        print("="*80)
        
        print(f"\n📊 Test Statistics:")
        print(f"  Total Tests: {self.total_tests}")
        print(f"  ✅ Successful: {self.successful_tests}")
        print(f"  ❌ Failed: {self.failed_tests}")
        print(f"  ⚠️  Errors: {self.error_tests}")
        
        print(f"\n⚡ Performance:")
        print(f"  Parallel Execution Time: {self.total_duration_seconds:.1f}s ({self.total_duration_seconds/60:.1f}m)")
        print(f"  Sequential Estimate: {self.sequential_estimated_time:.1f}s ({self.sequential_estimated_time/60:.1f}m)")
        print(f"  Time Saved: {self.time_saved_seconds:.1f}s ({self.time_saved_seconds/60:.1f}m)")
        print(f"  Speedup: {self.speedup_factor:.2f}x faster")
        
        print(f"\n📈 Per-Test Results:")
        for result in self.test_results:
            status_icon = "✅" if result.status == "success" else "❌" if result.status == "failed" else "⚠️"
            print(f"  {status_icon} {Path(result.test_file).name}: {result.duration_seconds:.1f}s ({result.activities_executed} activities)")
            if result.error_message:
                print(f"     Error: {result.error_message[:100]}")
        
        print("\n" + "="*80)


class ParallelTestExecutor:
    """
    Execute multiple browser tests in parallel
    Supports both threading (I/O-bound) and multiprocessing (CPU-bound)
    """
    
    def __init__(
        self,
        max_workers: int = 4,
        headless: bool = True,
        use_multiprocessing: bool = False,
        timeout_per_test: int = 300,
        output_dir: str = "parallel_test_results"
    ):
        """
        Initialize parallel test executor
        
        Args:
            max_workers: Number of parallel test executions
            headless: Run browsers in headless mode
            use_multiprocessing: Use processes instead of threads (more isolated)
            timeout_per_test: Timeout for each test in seconds
            output_dir: Directory to store test results and screenshots
        """
        self.max_workers = max_workers
        self.headless = headless
        self.use_multiprocessing = use_multiprocessing
        self.timeout_per_test = timeout_per_test
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        
        print(f"[Parallel Executor] Initialized with {max_workers} workers")
        print(f"[Parallel Executor] Mode: {'Multiprocessing' if use_multiprocessing else 'Threading'}")
        print(f"[Parallel Executor] Headless: {headless}")
    
    def run_tests(
        self,
        test_files: List[str],
        continue_on_failure: bool = True
    ) -> ParallelExecutionSummary:
        """
        Run multiple tests in parallel
        
        Args:
            test_files: List of test file paths
            continue_on_failure: Continue running other tests if one fails
        
        Returns:
            ParallelExecutionSummary with results
        """
        print(f"\n[Parallel Executor] Starting parallel execution of {len(test_files)} tests...")
        print(f"[Parallel Executor] Max workers: {self.max_workers}")
        
        start_time = datetime.now()
        results = []
        
        # Choose executor type
        ExecutorClass = ProcessPoolExecutor if self.use_multiprocessing else ThreadPoolExecutor
        
        with ExecutorClass(max_workers=self.max_workers) as executor:
            # Submit all tests
            future_to_test = {
                executor.submit(self._run_single_test, test_file): test_file
                for test_file in test_files
            }
            
            # Collect results as they complete
            for future in as_completed(future_to_test):
                test_file = future_to_test[future]
                try:
                    result = future.result(timeout=self.timeout_per_test)
                    results.append(result)
                    
                    status_icon = "✅" if result.status == "success" else "❌"
                    print(f"[Parallel Executor] {status_icon} {Path(test_file).name} completed in {result.duration_seconds:.1f}s")
                    
                except Exception as e:
                    error_result = TestResult(
                        test_file=test_file,
                        status="error",
                        start_time=datetime.now(),
                        end_time=datetime.now(),
                        duration_seconds=0,
                        activities_executed=0,
                        activities_failed=0,
                        error_message=f"Execution error: {str(e)}"
                    )
                    results.append(error_result)
                    print(f"[Parallel Executor] ❌ {Path(test_file).name} error: {e}")
        
        end_time = datetime.now()
        total_duration = (end_time - start_time).total_seconds()
        
        # Calculate summary
        summary = self._create_summary(results, total_duration)
        
        # Save results
        self._save_results(summary)
        
        return summary
    
    def _run_single_test(self, test_file: str) -> TestResult:
        """Run a single test (executed in parallel)"""
        test_start = datetime.now()
        activities_executed = 0
        activities_failed = 0
        screenshots = []
        error_message = None
        status = "success"
        
        driver = None
        
        try:
            # Load test
            with open(test_file, 'r') as f:
                activities = json.load(f)
            
            # Setup browser
            options = Options()
            if self.headless:
                options.add_argument('--headless')
            options.add_argument('--no-sandbox')
            options.add_argument('--disable-dev-shm-usage')
            options.add_argument('--disable-gpu')
            
            driver = webdriver.Chrome(options=options)
            driver.set_page_load_timeout(30)
            
            # Execute activities
            for i, activity in enumerate(activities):
                try:
                    self._execute_activity(driver, activity, test_file, i)
                    activities_executed += 1
                except Exception as e:
                    activities_failed += 1
                    error_message = f"Activity {i} failed: {str(e)}"
                    status = "failed"
                    print(f"[Test {Path(test_file).name}] Activity {i} failed: {e}")
                    break
            
        except Exception as e:
            status = "error"
            error_message = f"Test execution error: {str(e)}\n{traceback.format_exc()}"
            print(f"[Test {Path(test_file).name}] Error: {e}")
        
        finally:
            if driver:
                try:
                    driver.quit()
                except:
                    pass
        
        test_end = datetime.now()
        duration = (test_end - test_start).total_seconds()
        
        return TestResult(
            test_file=test_file,
            status=status,
            start_time=test_start,
            end_time=test_end,
            duration_seconds=duration,
            activities_executed=activities_executed,
            activities_failed=activities_failed,
            error_message=error_message,
            screenshots_captured=screenshots
        )
    
    def _execute_activity(self, driver: webdriver.Chrome, activity: Dict[str, Any], test_file: str, index: int):
        """Execute a single activity"""
        action = activity.get('action', '')
        details = activity.get('details', {})
        
        if action == 'navigation':
            url = details.get('url', '')
            driver.get(url)
            time.sleep(1)  # Brief wait for page load
        
        elif action == 'click':
            # Simple click implementation - Phase 1/2 integration would be more sophisticated
            element = self._find_element(driver, details)
            if element:
                element.click()
                time.sleep(0.5)
        
        elif action == 'text_input':
            element = self._find_element(driver, details)
            if element:
                value = details.get('value', '')
                element.clear()
                element.send_keys(value)
                time.sleep(0.3)
        
        elif action == 'wait':
            duration = details.get('duration', 1)
            time.sleep(duration)
        
        # Add more action types as needed
    
    def _find_element(self, driver: webdriver.Chrome, details: Dict[str, Any]):
        """Find element using available locators"""
        from selenium.webdriver.common.by import By
        
        # Try multiple selector strategies
        locators = details.get('locators', {})
        
        # Try ID
        if 'id' in locators:
            try:
                return driver.find_element(By.ID, locators['id'])
            except:
                pass
        
        # Try CSS
        if 'css' in locators:
            try:
                return driver.find_element(By.CSS_SELECTOR, locators['css'])
            except:
                pass
        
        # Try text content
        if 'text' in details:
            try:
                return driver.find_element(By.XPATH, f"//*[contains(text(), '{details['text']}')]")
            except:
                pass
        
        raise Exception(f"Could not find element with locators: {locators}")
    
    def _create_summary(self, results: List[TestResult], total_duration: float) -> ParallelExecutionSummary:
        """Create execution summary"""
        total_tests = len(results)
        successful = sum(1 for r in results if r.status == "success")
        failed = sum(1 for r in results if r.status == "failed")
        errors = sum(1 for r in results if r.status == "error")
        
        # Calculate estimated sequential time
        sequential_time = sum(r.duration_seconds for r in results)
        
        # Calculate speedup
        speedup = sequential_time / total_duration if total_duration > 0 else 1
        time_saved = sequential_time - total_duration
        
        avg_duration = sequential_time / total_tests if total_tests > 0 else 0
        
        return ParallelExecutionSummary(
            total_tests=total_tests,
            successful_tests=successful,
            failed_tests=failed,
            error_tests=errors,
            total_duration_seconds=total_duration,
            average_test_duration=avg_duration,
            sequential_estimated_time=sequential_time,
            time_saved_seconds=time_saved,
            speedup_factor=speedup,
            test_results=results
        )
    
    def _save_results(self, summary: ParallelExecutionSummary):
        """Save execution results to file"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        result_file = self.output_dir / f"parallel_execution_{timestamp}.json"
        
        result_data = {
            'timestamp': timestamp,
            'summary': {
                'total_tests': summary.total_tests,
                'successful_tests': summary.successful_tests,
                'failed_tests': summary.failed_tests,
                'error_tests': summary.error_tests,
                'total_duration_seconds': summary.total_duration_seconds,
                'sequential_estimated_time': summary.sequential_estimated_time,
                'time_saved_seconds': summary.time_saved_seconds,
                'speedup_factor': summary.speedup_factor
            },
            'test_results': [r.to_dict() for r in summary.test_results]
        }
        
        with open(result_file, 'w') as f:
            json.dump(result_data, f, indent=2)
        
        print(f"\n[Parallel Executor] Results saved to: {result_file}")


# Demo
def demo():
    """Demo parallel test execution"""
    
    print("="*80)
    print("PARALLEL TEST EXECUTION - DEMO")
    print("="*80)
    print("\n⚡ Phase 4 Feature: Run Multiple Tests Simultaneously!\n")
    
    # Check if we have test files
    test_files = list(Path(".").glob("*test*.json"))
    
    if not test_files:
        print("📝 Creating sample tests for demo...")
        
        # Create sample tests
        sample_tests = []
        for i in range(1, 4):
            test_data = [
                {
                    "action": "navigation",
                    "details": {"url": f"https://example.com/page{i}"}
                },
                {
                    "action": "wait",
                    "details": {"duration": 2}
                }
            ]
            
            test_file = f"sample_test_{i}.json"
            with open(test_file, 'w') as f:
                json.dump(test_data, f, indent=2)
            
            sample_tests.append(test_file)
            print(f"  ✓ Created {test_file}")
        
        test_files = sample_tests
    else:
        test_files = [str(f) for f in test_files[:3]]  # Limit to 3 for demo
        print(f"📂 Found {len(test_files)} test files")
    
    print("\n" + "="*80)
    print("Running Tests in Parallel")
    print("="*80)
    
    # Run parallel execution
    executor = ParallelTestExecutor(
        max_workers=2,  # Use 2 workers for demo
        headless=True
    )
    
    summary = executor.run_tests(test_files)
    
    # Print summary
    summary.print_summary()
    
    print("\n" + "="*80)
    print("Benefits of Parallel Execution:")
    print("="*80)
    print("✅ Faster feedback - get results in minutes, not hours")
    print("✅ Better resource utilization - use multiple CPU cores")
    print("✅ Scalable - easily run 10, 50, 100+ tests")
    print("✅ Cost-effective - reduce CI/CD time and costs")
    print(f"✅ Time savings - {summary.speedup_factor:.1f}x faster execution!")
    
    print("\n" + "="*80)
    print("Usage in Your Tests:")
    print("="*80)
    print("""
from parallel_test_executor import ParallelTestExecutor

# Create executor
executor = ParallelTestExecutor(
    max_workers=4,      # Run 4 tests simultaneously
    headless=True,      # Headless browser for speed
    timeout_per_test=300  # 5 minutes per test
)

# Run all your tests
results = executor.run_tests([
    "login_test.json",
    "checkout_test.json",
    "search_test.json",
    "profile_test.json"
])

# Get summary
results.print_summary()

# Check if all passed
all_passed = results.failed_tests == 0 and results.error_tests == 0
""")
    
    print("\n" + "="*80)


if __name__ == "__main__":
    demo()
