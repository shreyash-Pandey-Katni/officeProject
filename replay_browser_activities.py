"""
Browser Activity Replay System
Replays recorded browser activities using VLM for element detection
"""
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from activity_executor import ActivityExecutor
from llm_helpers import OllamaLLM
from test_database import TestDatabase
import json
import time
import os
from datetime import datetime
from typing import List, Dict, Any


class BrowserActivityReplayer:
    """Replay recorded browser activities"""
    
    def __init__(self, activity_log_path: str = "activity_log.json"):
        self.activity_log_path = activity_log_path
        self.driver = None
        self.executor = None
        self.llm = OllamaLLM(model="granite3.2-vision:latest")
        self.db = TestDatabase()
        self.results = []
        self.start_time = None
        self.end_time = None
        self.test_run_id = None
    
    def load_activities(self) -> List[Dict[str, Any]]:
        """Load activities from JSON log"""
        try:
            with open(self.activity_log_path, 'r') as f:
                activities = json.load(f)
            print(f"[REPLAYER] Loaded {len(activities)} activities from {self.activity_log_path}")
            return activities
        except FileNotFoundError:
            print(f"[REPLAYER] Error: Activity log not found: {self.activity_log_path}")
            return []
        except json.JSONDecodeError as e:
            print(f"[REPLAYER] Error: Invalid JSON in activity log: {e}")
            return []
    
    def setup_browser(self):
        """Initialize Chrome browser"""
        print("[REPLAYER] Setting up Chrome browser...")
        
        chrome_options = Options()
        chrome_options.add_argument("--start-maximized")
        chrome_options.add_argument("--disable-blink-features=AutomationControlled")
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option('useAutomationExtension', False)
        
        self.driver = webdriver.Chrome(options=chrome_options)
        
        # Ensure fullscreen mode
        self.driver.maximize_window()
        
        self.executor = ActivityExecutor(self.driver)
        
        print("[REPLAYER] Browser ready")
    
    def replay_activities(self, activities: List[Dict[str, Any]]):
        """Replay all activities"""
        print(f"\n{'='*80}")
        print(f"Starting replay of {len(activities)} activities")
        print(f"{'='*80}\n")
        
        self.start_time = datetime.now()
        
        # Create test run in database
        self.test_run_id = self.db.save_test_run(
            test_name="Browser Activity Replay",
            status="running",
            duration=0
        )
        
        for i, activity in enumerate(activities, 1):
            print(f"\n[REPLAYER] Processing activity {i}/{len(activities)}")
            
            step_start_time = datetime.now()
            
            # Execute activity
            result = self.executor.execute_activity(activity)
            
            step_duration = (datetime.now() - step_start_time).total_seconds()
            
            # Add original activity info to result
            result['original_action'] = activity.get('action')
            result['original_timestamp'] = activity.get('timestamp')
            result['original_details'] = activity.get('details', {})
            result['step'] = i
            
            # Store result
            self.results.append(result)
            
            # Save step to database
            self.db.save_test_step(
                test_run_id=self.test_run_id,
                step_number=i,
                action=result['action'],
                success=result['success'],
                error=result.get('error'),
                method=result.get('method'),
                duration=step_duration,
                element_info=activity.get('details')
            )
            
            # Save screenshots to database if they exist
            if 'screenshot_before' in result and result['screenshot_before']:
                self.db.save_screenshot(
                    self.test_run_id,
                    i,
                    'before',
                    result['screenshot_before']
                )
            
            if 'screenshot_after' in result and result['screenshot_after']:
                self.db.save_screenshot(
                    self.test_run_id,
                    i,
                    'after',
                    result['screenshot_after']
                )
            
            # Wait between actions
            if i < len(activities):
                time.sleep(1)
        
        self.end_time = datetime.now()
        
        # Update test run with final status
        total_steps = len(self.results)
        passed_steps = sum(1 for r in self.results if r['success'])
        failed_steps = total_steps - passed_steps
        final_status = "pass" if failed_steps == 0 else "fail"
        duration = (self.end_time - self.start_time).total_seconds()
        
        self.db.update_test_run(
            test_run_id=self.test_run_id,
            status=final_status,
            duration=duration,
            total_steps=total_steps,
            passed_steps=passed_steps,
            failed_steps=failed_steps
        )
        
        # Print summary
        self._print_summary()
    
    def _print_summary(self):
        """Print execution summary with detailed test information"""
        total = len(self.results)
        successful = sum(1 for r in self.results if r['success'])
        failed = total - successful
        
        duration = (self.end_time - self.start_time).total_seconds()
        
        print(f"\n{'='*80}")
        print("REPLAY SUMMARY")
        print(f"{'='*80}")
        print(f"Total activities: {total}")
        print(f"Successful: {successful} ({successful/total*100:.1f}%)")
        print(f"Failed: {failed} ({failed/total*100:.1f}%)")
        print(f"Duration: {duration:.1f} seconds")
        print(f"{'='*80}\n")
        
        # Show detailed step-by-step results
        print("DETAILED RESULTS:")
        print(f"{'='*80}")
        
        for idx, result in enumerate(self.results, 1):
            status_icon = "✅" if result['success'] else "❌"
            action = result['action'].upper()
            
            print(f"\n{status_icon} Step {idx}: {action}")
            print(f"   {'─'*76}")
            
            # Show what the step tried to achieve
            if action == "NAVIGATION":
                url = result.get('original_details', {}).get('url', 'N/A')
                print(f"   Goal: Navigate to {url}")
                
            elif action == "CLICK":
                details = result.get('original_details', {})
                tag = details.get('tagName', 'element')
                text = details.get('text', '')
                elem_id = details.get('id', '')
                
                target_desc = f"{tag}"
                if elem_id:
                    target_desc += f" (id='{elem_id}')"
                elif text:
                    target_desc += f" with text '{text[:30]}...'" if len(text) > 30 else f" with text '{text}'"
                
                print(f"   Goal: Click on {target_desc}")
                
            elif action == "TEXT_INPUT":
                details = result.get('original_details', {})
                value = details.get('value', '')
                placeholder = details.get('placeholder', '')
                name = details.get('name', '')
                
                input_desc = "input field"
                if name:
                    input_desc = f"input field '{name}'"
                elif placeholder:
                    input_desc = f"input with placeholder '{placeholder}'"
                
                print(f"   Goal: Type '{value}' into {input_desc}")
            
            # Show result details
            if result['success']:
                method = result.get('method', 'unknown')
                print(f"   Result: ✓ SUCCESS (method: {method})")
            else:
                error = result.get('error', 'Unknown error')
                print(f"   Result: ✗ FAILED")
                print(f"   Reason: {error}")
            
            # Show additional context
            if result.get('original_details', {}).get('inShadowRoot'):
                print(f"   Context: Element in Shadow DOM")
            if result.get('original_details', {}).get('inIframe'):
                print(f"   Context: Element in iframe")
        
        print(f"\n{'='*80}\n")
        
        # Show failure summary if any
        if failed > 0:
            print("❌ FAILED STEPS SUMMARY:")
            for result in self.results:
                if not result['success']:
                    print(f"  • Step {result['step']}: {result['action']} - {result['error']}")
            print()
        else:
            print("✅ All steps completed successfully!")
            print()
    
    def generate_report(self, output_path: str = "replay_report.html"):
        """Generate HTML report with screenshots"""
        print(f"[REPLAYER] Generating report: {output_path}")
        
        # Get natural language summary from LLM
        summary_data = {
            'total': len(self.results),
            'successful': sum(1 for r in self.results if r['success']),
            'failed': sum(1 for r in self.results if not r['success']),
            'duration': ((self.end_time - self.start_time).total_seconds() if self.start_time and self.end_time else 0),
            'activities': [
                {
                    'action': r['action'],
                    'success': r['success'],
                    'method': r['method']
                } for r in self.results
            ]
        }
        
        nl_summary = self.llm.generate_report_summary(summary_data)
        
        # Generate HTML
        html = self._generate_html_report(nl_summary)
        
        with open(output_path, 'w') as f:
            f.write(html)
        
        print(f"[REPLAYER] Report generated: {output_path}")
    
    def _generate_html_report(self, nl_summary: str) -> str:
        """Generate HTML report content"""
        total = len(self.results)
        successful = sum(1 for r in self.results if r['success'])
        failed = total - successful
        success_rate = (successful / total * 100) if total > 0 else 0
        
        html = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Browser Activity Replay Report</title>
    <style>
        body {{
            font-family: Arial, sans-serif;
            margin: 20px;
            background-color: #f5f5f5;
        }}
        .header {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 30px;
            border-radius: 10px;
            margin-bottom: 30px;
        }}
        .header h1 {{
            margin: 0 0 10px 0;
        }}
        .summary {{
            background: white;
            padding: 20px;
            border-radius: 10px;
            margin-bottom: 30px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        .stats {{
            display: flex;
            gap: 20px;
            margin: 20px 0;
        }}
        .stat {{
            flex: 1;
            padding: 15px;
            border-radius: 8px;
            text-align: center;
        }}
        .stat.success {{
            background-color: #d4edda;
            border: 1px solid #c3e6cb;
        }}
        .stat.failed {{
            background-color: #f8d7da;
            border: 1px solid #f5c6cb;
        }}
        .stat.total {{
            background-color: #d1ecf1;
            border: 1px solid #bee5eb;
        }}
        .stat-value {{
            font-size: 32px;
            font-weight: bold;
            margin: 10px 0;
        }}
        .stat-label {{
            font-size: 14px;
            color: #666;
        }}
        .nl-summary {{
            background: #fff9e6;
            padding: 15px;
            border-left: 4px solid #ffc107;
            margin: 20px 0;
            border-radius: 4px;
        }}
        .step {{
            background: white;
            padding: 20px;
            margin-bottom: 20px;
            border-radius: 10px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        .step.success {{
            border-left: 5px solid #28a745;
        }}
        .step.failed {{
            border-left: 5px solid #dc3545;
        }}
        .step-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 15px;
        }}
        .step-number {{
            font-size: 18px;
            font-weight: bold;
            color: #333;
        }}
        .step-status {{
            padding: 5px 15px;
            border-radius: 20px;
            font-size: 12px;
            font-weight: bold;
        }}
        .step-status.success {{
            background-color: #28a745;
            color: white;
        }}
        .step-status.failed {{
            background-color: #dc3545;
            color: white;
        }}
        .step-details {{
            margin: 10px 0;
        }}
        .detail-row {{
            padding: 5px 0;
            display: flex;
        }}
        .detail-label {{
            font-weight: bold;
            width: 150px;
            color: #666;
        }}
        .detail-value {{
            flex: 1;
            color: #333;
        }}
        .screenshots {{
            display: flex;
            gap: 20px;
            margin-top: 15px;
        }}
        .screenshot {{
            flex: 1;
        }}
        .screenshot img {{
            width: 100%;
            border: 1px solid #ddd;
            border-radius: 5px;
        }}
        .screenshot-label {{
            text-align: center;
            margin-top: 5px;
            font-size: 12px;
            color: #666;
        }}
        .error-message {{
            background-color: #f8d7da;
            color: #721c24;
            padding: 10px;
            border-radius: 5px;
            margin-top: 10px;
        }}
    </style>
</head>
<body>
    <div class="header">
        <h1>🎬 Browser Activity Replay Report</h1>
        <p>Generated on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
    </div>
    
    <div class="summary">
        <h2>Executive Summary</h2>
        <div class="stats">
            <div class="stat total">
                <div class="stat-label">Total Steps</div>
                <div class="stat-value">{total}</div>
            </div>
            <div class="stat success">
                <div class="stat-label">Successful</div>
                <div class="stat-value">{successful}</div>
                <div class="stat-label">{success_rate:.1f}%</div>
            </div>
            <div class="stat failed">
                <div class="stat-label">Failed</div>
                <div class="stat-value">{failed}</div>
                <div class="stat-label">{100-success_rate:.1f}%</div>
            </div>
        </div>
        
        <div class="nl-summary">
            <h3>📝 Summary</h3>
            <p>{nl_summary}</p>
        </div>
        
        <div class="detail-row">
            <div class="detail-label">Duration:</div>
            <div class="detail-value">{(self.end_time - self.start_time).total_seconds():.1f} seconds</div>
        </div>
        <div class="detail-row">
            <div class="detail-label">Activity Log:</div>
            <div class="detail-value">{self.activity_log_path}</div>
        </div>
    </div>
    
    <h2>Step-by-Step Results</h2>
"""
        
        # Add each step
        for result in self.results:
            status_class = "success" if result['success'] else "failed"
            status_text = "✓ SUCCESS" if result['success'] else "✗ FAILED"
            
            # Get action description
            action = result['action']
            details = result.get('original_details', {})
            
            if action == 'navigation':
                action_desc = f"Navigate to {details.get('url', 'unknown URL')}"
            elif action == 'click':
                tag = details.get('tagName', 'element')
                text = details.get('text', '')
                action_desc = f"Click on {tag}" + (f" '{text[:50]}'" if text else "")
            elif action == 'text_input':
                value = details.get('value', '')
                action_desc = f"Type '{value[:50]}'"
            else:
                action_desc = action
            
            html += f"""
    <div class="step {status_class}">
        <div class="step-header">
            <div class="step-number">Step {result['step']}: {action_desc}</div>
            <div class="step-status {status_class}">{status_text}</div>
        </div>
        
        <div class="step-details">
            <div class="detail-row">
                <div class="detail-label">Action Type:</div>
                <div class="detail-value">{action}</div>
            </div>
            <div class="detail-row">
                <div class="detail-label">Detection Method:</div>
                <div class="detail-value">{result.get('method', 'N/A')}</div>
            </div>
            <div class="detail-row">
                <div class="detail-label">VLM Description:</div>
                <div class="detail-value">{'✓ Used' if result.get('used_vlm_description') else '✗ Not available'}</div>
            </div>
            <div class="detail-row">
                <div class="detail-label">Timestamp:</div>
                <div class="detail-value">{result.get('timestamp', 'N/A')}</div>
            </div>
"""
            
            if not result['success'] and result.get('error'):
                html += f"""
            <div class="error-message">
                <strong>Error:</strong> {result['error']}
            </div>
"""
            
            # Add screenshots if available
            before = result.get('screenshot_before', '')
            after = result.get('screenshot_after', '')
            
            if before or after:
                html += """
        </div>
        <div class="screenshots">
"""
                if before and os.path.exists(before):
                    html += f"""
            <div class="screenshot">
                <img src="{before}" alt="Before">
                <div class="screenshot-label">Before Action</div>
            </div>
"""
                if after and os.path.exists(after):
                    html += f"""
            <div class="screenshot">
                <img src="{after}" alt="After">
                <div class="screenshot-label">After Action</div>
            </div>
"""
                html += """
        </div>
"""
            else:
                html += """
        </div>
"""
            
            html += """
    </div>
"""
        
        html += """
</body>
</html>
"""
        return html
    
    def cleanup(self):
        """Close browser"""
        if self.driver:
            print("[REPLAYER] Closing browser...")
            self.driver.quit()
    
    def run(self):
        """Main replay execution"""
        try:
            # Load activities
            activities = self.load_activities()
            if not activities:
                print("[REPLAYER] No activities to replay")
                return
            
            # Setup browser
            self.setup_browser()
            
            # Replay activities
            self.replay_activities(activities)
            
            # Generate report
            self.generate_report()
            
        except KeyboardInterrupt:
            print("\n[REPLAYER] Interrupted by user")
        except Exception as e:
            print(f"[REPLAYER] Error: {e}")
            import traceback
            traceback.print_exc()
        finally:
            self.cleanup()


def main():
    """Entry point"""
    import sys
    
    log_path = sys.argv[1] if len(sys.argv) > 1 else "activity_log.json"
    
    print("="*80)
    print("Browser Activity Replayer with VLM Detection")
    print("="*80)
    print(f"Activity log: {log_path}")
    print("="*80)
    print()
    
    replayer = BrowserActivityReplayer(log_path)
    replayer.run()


if __name__ == "__main__":
    main()
