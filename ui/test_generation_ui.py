"""
Test Generation UI - Web Interface
Flask-based web application for easy test creation

Features:
- Natural language test creation
- Screenshot upload for test generation
- Test history and management
- Live preview of generated tests
- One-click test execution
- No coding required!

Usage:
    python test_generation_ui.py
    # Opens web browser at http://localhost:5000
"""

from flask import Flask, render_template, request, jsonify, send_file, redirect, url_for
from werkzeug.utils import secure_filename
from pathlib import Path
import json
import os
from datetime import datetime
import sys
import logging
import traceback
from selenium.webdriver.common.by import By

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('test_generation_ui.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Add project root to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

# Import our Phase 3 modules
try:
    from ui.natural_language_test_creator import NaturalLanguageTestCreator
    from ui.screenshot_test_generator import ScreenshotTestGenerator
    from core.analyzers.content_verifier import ContentVerifier
    logger.info("Successfully imported Phase 3 modules")
except ImportError as e:
    logger.error(f"Could not import Phase 3 modules: {e}")
    print(f"⚠️  Warning: Could not import Phase 3 modules: {e}")
    print("Make sure all required modules are available in the organized structure")

# Get the project root directory
PROJECT_ROOT = Path(__file__).parent.parent
UI_DIR = Path(__file__).parent

# Configure Flask with proper paths
app = Flask(__name__, 
            template_folder=str(UI_DIR / 'templates'),
            static_folder=str(UI_DIR / 'static'))
app.config['SECRET_KEY'] = 'test-generation-ui-secret-key'
app.config['UPLOAD_FOLDER'] = str(PROJECT_ROOT / 'uploads')
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size
app.config['GENERATED_TESTS_FOLDER'] = str(PROJECT_ROOT / 'tests' / 'test_cases')

# Module-level storage for active recorders (cleaner than dynamic app attributes)
active_recorders = {}

# Create necessary directories
Path(app.config['UPLOAD_FOLDER']).mkdir(exist_ok=True)
Path(app.config['GENERATED_TESTS_FOLDER']).mkdir(exist_ok=True)

# Allowed file extensions
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


@app.route('/')
def index():
    """Main landing page"""
    return render_template('index.html')


@app.route('/natural-language')
def natural_language_page():
    """Natural language test creation page"""
    return render_template('natural_language.html')


@app.route('/screenshot-upload')
def screenshot_upload_page():
    """Screenshot-based test generation page"""
    return render_template('screenshot_upload.html')


@app.route('/test-library')
def test_library_page():
    """View all generated tests"""
    tests = []
    test_dir = Path(app.config['GENERATED_TESTS_FOLDER'])
    
    for test_file in test_dir.glob('*.json'):
        try:
            with open(test_file, 'r') as f:
                test_data = json.load(f)
            
            tests.append({
                'filename': test_file.name,
                'name': test_file.stem.replace('_', ' ').title(),
                'created': datetime.fromtimestamp(test_file.stat().st_mtime).strftime('%Y-%m-%d %H:%M'),
                'activities': len(test_data) if isinstance(test_data, list) else 0,
                'size': f"{test_file.stat().st_size / 1024:.1f} KB"
            })
        except:
            pass
    
    tests.sort(key=lambda x: x['created'], reverse=True)
    return render_template('test_library.html', tests=tests)


@app.route('/record-test')
def record_test_page():
    """Browser recording page"""
    return render_template('record_test.html')



@app.route('/api/generate-from-text', methods=['POST'])
def generate_from_text():
    """API endpoint: Generate test from natural language"""
    try:
        data = request.get_json()
        test_description = data.get('description', '')
        test_name = data.get('name', 'Generated Test')
        
        if not test_description:
            return jsonify({'success': False, 'error': 'Test description is required'}), 400
        
        # Create test generator
        creator = NaturalLanguageTestCreator()
        
        # Generate test
        test = creator.create_test_from_description(test_description, test_name)
        
        # Save to file
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"{test_name.lower().replace(' ', '_')}_{timestamp}.json"
        filepath = Path(app.config['GENERATED_TESTS_FOLDER']) / filename
        
        creator.save_test(test, str(filepath))
        
        # Return success with test details
        return jsonify({
            'success': True,
            'filename': filename,
            'test_name': test.test_name,
            'steps': len(test.steps),
            'confidence': test.confidence,
            'duration': test.estimated_duration,
            'activities': test.to_activity_log()
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/generate-from-screenshots', methods=['POST'])
def generate_from_screenshots():
    """API endpoint: Generate test from uploaded screenshots"""
    try:
        if 'screenshots' not in request.files:
            return jsonify({'success': False, 'error': 'No screenshots uploaded'}), 400
        
        files = request.files.getlist('screenshots')
        test_name = request.form.get('test_name', 'Screenshot Test')
        annotations = request.form.get('annotations', '').split('\n')
        
        if not files:
            return jsonify({'success': False, 'error': 'No screenshots provided'}), 400
        
        # Save uploaded files
        screenshot_paths = []
        upload_dir = Path(app.config['UPLOAD_FOLDER']) / datetime.now().strftime('%Y%m%d_%H%M%S')
        upload_dir.mkdir(exist_ok=True)
        
        for i, file in enumerate(files):
            if file and allowed_file(file.filename):
                filename = secure_filename(f"{i+1}_{file.filename}")
                filepath = upload_dir / filename
                file.save(str(filepath))
                screenshot_paths.append(str(filepath))
        
        if not screenshot_paths:
            return jsonify({'success': False, 'error': 'No valid screenshots uploaded'}), 400
        
        # Generate test
        generator = ScreenshotTestGenerator()
        test = generator.generate_test_from_screenshots(
            screenshot_paths=screenshot_paths,
            test_name=test_name,
            annotations=annotations if annotations and annotations[0] else None
        )
        
        # Save test
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"{test_name.lower().replace(' ', '_')}_{timestamp}.json"
        filepath = Path(app.config['GENERATED_TESTS_FOLDER']) / filename
        
        generator.save_test(test, str(filepath))
        
        return jsonify({
            'success': True,
            'filename': filename,
            'test_name': test.test_name,
            'steps': len(test.workflow_steps),
            'confidence': test.generation_confidence,
            'screenshots': len(screenshot_paths)
        })
        
    except Exception as e:
        logger.error(f"Screenshot test generation failed: {e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/start-recording', methods=['POST'])
def start_recording():
    """API endpoint: Start browser recording"""
    try:
        data = request.get_json()
        url = data.get('url', 'https://www.google.com')
        test_name = data.get('test_name', 'recorded_test')
        enable_hover = data.get('enable_hover_recording', True)
        
        logger.info(f"Starting recording: URL={url}, test_name={test_name}, hover={enable_hover}")
        
        # Import recorder
        from main import BrowserActivityRecorder
        from selenium import webdriver
        from selenium.webdriver.chrome.options import Options
        
        # Setup Chrome
        chrome_options = Options()
        chrome_options.add_argument("--start-maximized")
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option('useAutomationExtension', False)
        
        driver = webdriver.Chrome(options=chrome_options)
        driver.get(url)
        
        # Create recorder with hover setting
        recorder = BrowserActivityRecorder(driver, enable_hover_recording=enable_hover)
        
        # Start monitoring in background thread
        import threading
        monitor_thread = threading.Thread(target=recorder.monitor_activities, daemon=True)
        monitor_thread.start()
        
        # Store in module-level storage
        active_recorders['current'] = {
            'recorder': recorder,
            'driver': driver,
            'test_name': test_name,
            'start_time': datetime.now(),
            'monitor_thread': monitor_thread
        }
        
        logger.info(f"Recording started successfully for test: {test_name}")
        return jsonify({
            'status': 'success',
            'message': 'Recording started successfully'
        })
        
    except Exception as e:
        logger.error(f"Failed to start recording: {e}", exc_info=True)
        return jsonify({'status': 'error', 'message': str(e)}), 500


@app.route('/api/stop-recording', methods=['POST'])
def stop_recording():
    """API endpoint: Stop browser recording and save test"""
    try:
        if 'current' not in active_recorders:
            logger.warning("Attempted to stop recording with no active session")
            return jsonify({'status': 'error', 'message': 'No active recording session'}), 400
        
        session = active_recorders['current']
        recorder = session['recorder']
        driver = session['driver']
        test_name = session['test_name']
        
        logger.info(f"Stopping recording for test: {test_name}")
        
        # Stop recording by setting flag
        recorder.stop_recording()
        
        # Wait a moment for any pending activities
        import time
        time.sleep(2)
        
        # Save activity log
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"{test_name}_{timestamp}.json"
        filepath = Path(app.config['GENERATED_TESTS_FOLDER']) / filename
        
        with open(filepath, 'w') as f:
            json.dump(recorder.activity_log, f, indent=2)
        
        logger.info(f"Saved {len(recorder.activity_log)} activities to {filepath}")
        
        # Close browser
        driver.quit()
        
        # Remove from active sessions
        del active_recorders['current']
        
        return jsonify({
            'status': 'success',
            'activity_log': str(filepath),
            'activities': len(recorder.activity_log),
            'message': f'Recording saved with {len(recorder.activity_log)} activities'
        })
        
    except Exception as e:
        logger.error(f"Failed to stop recording: {e}", exc_info=True)
        return jsonify({'status': 'error', 'message': str(e)}), 500


@app.route('/api/recording-status', methods=['GET'])
def recording_status():
    """API endpoint: Get current recording status"""
    try:
        if 'current' not in active_recorders:
            return jsonify({
                'is_recording': False,
                'message': 'No active recording'
            })
        
        session = active_recorders['current']
        recorder = session['recorder']
        
        duration = (datetime.now() - session['start_time']).total_seconds()
        
        # Count activity types
        activity_counts = {
            'clicks': 0,
            'text_inputs': 0,
            'change_inputs': 0,
            'hovers': 0,
            'total': len(recorder.activity_log)
        }
        
        for activity in recorder.activity_log:
            activity_type = activity.get('type', '')
            if activity_type == 'click':
                activity_counts['clicks'] += 1
            elif activity_type == 'text_input':
                activity_counts['text_inputs'] += 1
            elif activity_type == 'change_input':
                activity_counts['change_inputs'] += 1
            elif activity_type == 'hover':
                activity_counts['hovers'] += 1
        
        return jsonify({
            'is_recording': True,
            'test_name': session['test_name'],
            'activity_counts': activity_counts,
            'duration': duration
        })
        
    except Exception as e:
        return jsonify({
            'is_recording': False,
            'error': str(e)
        })


@app.route('/api/test/<filename>')
def get_test(filename):
    """API endpoint: Get test details"""
    try:
        filepath = Path(app.config['GENERATED_TESTS_FOLDER']) / secure_filename(filename)
        
        if not filepath.exists():
            return jsonify({'success': False, 'error': 'Test not found'}), 404
        
        with open(filepath, 'r') as f:
            test_data = json.load(f)
        
        return jsonify({
            'success': True,
            'filename': filename,
            'data': test_data
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/test/<filename>/download')
def download_test(filename):
    """API endpoint: Download test file"""
    try:
        filepath = Path(app.config['GENERATED_TESTS_FOLDER']) / secure_filename(filename)
        
        if not filepath.exists():
            return "Test not found", 404
        
        return send_file(filepath, as_attachment=True)
        
    except Exception as e:
        return str(e), 500


@app.route('/api/test/<filename>/delete', methods=['POST'])
def delete_test(filename):
    """API endpoint: Delete test"""
    try:
        filepath = Path(app.config['GENERATED_TESTS_FOLDER']) / secure_filename(filename)
        
        if filepath.exists():
            filepath.unlink()
            return jsonify({'success': True})
        else:
            return jsonify({'success': False, 'error': 'Test not found'}), 404
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/test-editor/<filename>')
def test_editor(filename):
    """Page: Test editor"""
    try:
        filepath = Path(app.config['GENERATED_TESTS_FOLDER']) / secure_filename(filename)
        
        if not filepath.exists():
            return "Test not found", 404
        
        with open(filepath, 'r') as f:
            test_data = json.load(f)
        
        return render_template('test_editor.html', 
                             filename=filename, 
                             test_data=json.dumps(test_data, indent=2))
    except Exception as e:
        return str(e), 500


@app.route('/api/test/<filename>/update', methods=['POST'])
def update_test(filename):
    """API endpoint: Update test"""
    try:
        filepath = Path(app.config['GENERATED_TESTS_FOLDER']) / secure_filename(filename)
        
        if not filepath.exists():
            return jsonify({'success': False, 'error': 'Test not found'}), 404
        
        # Get updated test data from request
        updated_data = request.json
        
        if not updated_data:
            return jsonify({'success': False, 'error': 'No data provided'}), 400
        
        # Validate it's valid JSON
        try:
            # If it's a string, parse it
            if isinstance(updated_data, str):
                updated_data = json.loads(updated_data)
        except json.JSONDecodeError as e:
            return jsonify({'success': False, 'error': f'Invalid JSON: {str(e)}'}), 400
        
        # Save updated test
        with open(filepath, 'w') as f:
            json.dump(updated_data, f, indent=2)
        
        return jsonify({'success': True, 'message': 'Test updated successfully'})
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/test/<filename>/run', methods=['POST'])
def run_test(filename):
    """API endpoint: Run test case"""
    try:
        from selenium import webdriver
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC
        from selenium.common.exceptions import TimeoutException, WebDriverException
        import time
        
        filepath = Path(app.config['GENERATED_TESTS_FOLDER']) / secure_filename(filename)
        
        if not filepath.exists():
            return jsonify({'success': False, 'error': 'Test not found'}), 404
        
        # Load test data
        with open(filepath, 'r') as f:
            test_data = json.load(f)
        
        # Get activities - handle both formats
        if isinstance(test_data, list):
            # New format: array of activities
            activities = test_data
        elif isinstance(test_data, dict):
            # Old format: object with activities key
            activities = test_data.get('activities', [])
        else:
            return jsonify({'success': False, 'error': 'Invalid test format'}), 400
            
        if not activities:
            return jsonify({'success': False, 'error': 'No activities found in test'}), 400
        
        # Initialize results
        results = {
            'success': True,
            'test_name': filename,
            'total_steps': len(activities),
            'executed_steps': 0,
            'failed_steps': 0,
            'steps': [],
            'start_time': datetime.now().isoformat(),
            'end_time': None,
            'duration': 0,
            'error': None
        }
        
        driver = None
        
        try:
            # Set up Chrome options
            options = webdriver.ChromeOptions()
            options.add_argument('--no-sandbox')
            options.add_argument('--disable-dev-shm-usage')
            options.add_argument('--window-size=1920,1080')
            # Don't run headless so user can see the test execution
            # options.add_argument('--headless')
            
            # Initialize driver
            driver = webdriver.Chrome(options=options)
            driver.implicitly_wait(10)
            
            # Execute each activity
            for idx, activity in enumerate(activities, 1):
                # Get action name - handle both old and new formats
                action = activity.get('action', 'unknown')
                
                step_result = {
                    'step': idx,
                    'action': action,
                    'status': 'success',
                    'error': None,
                    'timestamp': datetime.now().isoformat()
                }
                
                try:
                    # Handle different action types
                    if action in ['navigate', 'navigation']:
                        # Get URL from different possible locations
                        url = (activity.get('url') or 
                               activity.get('details', {}).get('url', ''))
                        if url:
                            driver.get(url)
                            step_result['details'] = f"Navigated to {url}"
                        else:
                            step_result['status'] = 'skipped'
                            step_result['details'] = "No URL provided"
                        
                    elif action == 'click':
                        element = find_element(driver, activity)
                        element.click()
                        text = activity.get('details', {}).get('text', 'element')
                        step_result['details'] = f"Clicked {text}"
                        
                    elif action in ['input', 'text_input']:
                        element = find_element(driver, activity)
                        # Get value from different possible locations
                        value = (activity.get('value') or 
                                activity.get('details', {}).get('value') or 
                                activity.get('locators', {}).get('value', ''))
                        if value:
                            element.clear()
                            element.send_keys(value)
                            step_result['details'] = f"Entered text: {value}"
                        else:
                            step_result['status'] = 'skipped'
                            step_result['details'] = "No value to enter"
                        
                    elif action == 'wait':
                        wait_time = activity.get('duration', 2)
                        time.sleep(wait_time)
                        step_result['details'] = f"Waited {wait_time} seconds"
                        
                    elif action == 'scroll':
                        scroll_amount = activity.get('amount', 500)
                        driver.execute_script(f"window.scrollBy(0, {scroll_amount});")
                        step_result['details'] = f"Scrolled {scroll_amount}px"
                    
                    elif action == 'scroll_to_element':
                        # Scroll to a specific element
                        element = find_element(driver, activity)
                        driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", element)
                        text = activity.get('details', {}).get('text', 'element')
                        step_result['details'] = f"Scrolled to {text}"
                    
                    elif action == 'switch_tab':
                        # Switch to a tab by title or URL pattern
                        pattern = activity.get('details', {}).get('pattern', '')
                        match_type = activity.get('details', {}).get('match_type', 'title')
                        use_regex = activity.get('details', {}).get('use_regex', True)
                        
                        current_handle = driver.current_window_handle
                        all_handles = driver.window_handles
                        
                        found = False
                        import re
                        for handle in all_handles:
                            if handle == current_handle:
                                continue
                            driver.switch_to.window(handle)
                            match_value = driver.title if match_type == 'title' else driver.current_url
                            
                            if use_regex:
                                if re.search(pattern, match_value, re.IGNORECASE):
                                    found = True
                                    break
                            else:
                                if pattern.lower() in match_value.lower():
                                    found = True
                                    break
                        
                        if not found:
                            driver.switch_to.window(current_handle)
                            raise Exception(f"No tab found matching {match_type}: {pattern}")
                        
                        step_result['details'] = f"Switched to tab: {driver.title}"
                    
                    elif action == 'switch_window':
                        # Switch to a window by title pattern
                        pattern = activity.get('details', {}).get('pattern', '')
                        use_regex = activity.get('details', {}).get('use_regex', True)
                        
                        current_handle = driver.current_window_handle
                        all_handles = driver.window_handles
                        
                        found = False
                        import re
                        for handle in all_handles:
                            if handle == current_handle:
                                continue
                            driver.switch_to.window(handle)
                            
                            if use_regex:
                                if re.search(pattern, driver.title, re.IGNORECASE):
                                    found = True
                                    break
                            else:
                                if pattern.lower() in driver.title.lower():
                                    found = True
                                    break
                        
                        if not found:
                            driver.switch_to.window(current_handle)
                            raise Exception(f"No window found matching title: {pattern}")
                        
                        step_result['details'] = f"Switched to window: {driver.title}"
                    
                    elif action == 'verification':
                        # Skip verification steps for now
                        step_result['status'] = 'skipped'
                        step_result['details'] = "Verification step (not implemented)"
                        
                    else:
                        step_result['status'] = 'skipped'
                        step_result['details'] = f"Unsupported action: {action}"
                    
                    if step_result['status'] != 'skipped':
                        results['executed_steps'] += 1
                    
                except Exception as e:
                    step_result['status'] = 'failed'
                    step_result['error'] = str(e)
                    results['failed_steps'] += 1
                
                results['steps'].append(step_result)
                
                # Small delay between actions for visibility
                time.sleep(0.5)
            
            # Calculate final results
            results['end_time'] = datetime.now().isoformat()
            start = datetime.fromisoformat(results['start_time'])
            end = datetime.fromisoformat(results['end_time'])
            results['duration'] = (end - start).total_seconds()
            
            if results['failed_steps'] > 0:
                results['success'] = False
                results['error'] = f"{results['failed_steps']} step(s) failed"
            
        except Exception as e:
            results['success'] = False
            results['error'] = f"Test execution failed: {str(e)}"
            results['end_time'] = datetime.now().isoformat()
            
        finally:
            # Close browser
            if driver:
                try:
                    time.sleep(2)  # Let user see final state
                    driver.quit()
                except:
                    pass
        
        return jsonify(results)
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


def find_element(driver, activity):
    """Find element using available selectors"""
    # Try to get selectors from different locations
    selectors = activity.get('selectors', {}) or activity.get('locators', {})
    details = activity.get('details', {})
    
    # Try selectors in order of reliability
    # 1. Try CSS selector
    if 'css' in selectors:
        return driver.find_element(By.CSS_SELECTOR, selectors['css'])
    
    # 2. Try XPath
    if 'xpath' in selectors:
        return driver.find_element(By.XPATH, selectors['xpath'])
    
    # 3. Try ID
    if 'id' in selectors:
        return driver.find_element(By.ID, selectors['id'])
    
    # 4. Try name
    if 'name' in selectors:
        return driver.find_element(By.NAME, selectors['name'])
    
    # 5. Try tag name
    if 'tag' in selectors:
        return driver.find_element(By.TAG_NAME, selectors['tag'])
    
    # 6. Try by text content
    if 'text' in selectors or 'text' in details:
        text = selectors.get('text') or details.get('text', '')
        if text:
            # Try to find by link text first
            try:
                return driver.find_element(By.LINK_TEXT, text)
            except Exception:
                # Try partial link text
                try:
                    return driver.find_element(By.PARTIAL_LINK_TEXT, text)
                except Exception:
                    # Try XPath with text
                    return driver.find_element(By.XPATH, f"//*[contains(text(), '{text}')]")
    
    # 7. Try by placeholder
    if 'placeholder' in selectors or 'placeholder' in details:
        placeholder = selectors.get('placeholder') or details.get('placeholder', '')
        if placeholder:
            return driver.find_element(By.XPATH, f"//input[@placeholder='{placeholder}']")
    
    # 8. Try by tag name from details
    if 'tagName' in details:
        tag = details['tagName'].lower()
        # For common elements, try to be more specific
        if tag == 'button':
            return driver.find_element(By.TAG_NAME, 'button')
        elif tag == 'input':
            return driver.find_element(By.TAG_NAME, 'input')
        elif tag == 'a':
            return driver.find_element(By.TAG_NAME, 'a')
        else:
            return driver.find_element(By.TAG_NAME, tag)
    
    # If nothing works, raise an error
    raise ValueError(f"No valid selector found. Activity: {activity}")



def create_html_templates():
    """Create HTML templates for the UI"""
    
    # Base template
    base_html = '''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{% block title %}Test Generation UI{% endblock %}</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
        }
        
        .container {
            max-width: 1200px;
            margin: 0 auto;
            background: white;
            border-radius: 12px;
            box-shadow: 0 10px 40px rgba(0,0,0,0.2);
            overflow: hidden;
        }
        
        .header {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 30px;
            text-align: center;
        }
        
        .header h1 {
            font-size: 2.5em;
            margin-bottom: 10px;
        }
        
        .header p {
            font-size: 1.2em;
            opacity: 0.9;
        }
        
        .nav {
            background: #f8f9fa;
            padding: 15px 30px;
            display: flex;
            gap: 15px;
            border-bottom: 2px solid #e9ecef;
        }
        
        .nav a {
            padding: 10px 20px;
            background: white;
            color: #667eea;
            text-decoration: none;
            border-radius: 6px;
            font-weight: 600;
            transition: all 0.3s;
            border: 2px solid transparent;
        }
        
        .nav a:hover {
            background: #667eea;
            color: white;
            transform: translateY(-2px);
        }
        
        .nav a.active {
            background: #667eea;
            color: white;
            border-color: #5568d3;
        }
        
        .content {
            padding: 40px;
        }
        
        .card {
            background: white;
            border: 2px solid #e9ecef;
            border-radius: 12px;
            padding: 30px;
            margin-bottom: 20px;
            transition: all 0.3s;
        }
        
        .card:hover {
            box-shadow: 0 5px 20px rgba(0,0,0,0.1);
            transform: translateY(-2px);
        }
        
        .card h2 {
            color: #667eea;
            margin-bottom: 15px;
            font-size: 1.8em;
        }
        
        .card p {
            color: #6c757d;
            line-height: 1.6;
            margin-bottom: 20px;
        }
        
        .btn {
            padding: 12px 30px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            border: none;
            border-radius: 6px;
            font-size: 1em;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.3s;
            text-decoration: none;
            display: inline-block;
            margin: 5px;
        }
        
        .btn:hover {
            transform: translateY(-2px);
            box-shadow: 0 5px 15px rgba(102, 126, 234, 0.4);
        }
        
        .btn-primary {
            background: linear-gradient(135deg, #28a745 0%, #20c997 100%);
        }
        
        .btn-primary:hover {
            box-shadow: 0 5px 15px rgba(40, 167, 69, 0.4);
        }
        
        .btn-secondary {
            background: #6c757d;
        }
        
        .btn-warning {
            background: linear-gradient(135deg, #ffc107 0%, #ff9800 100%);
        }
        
        .btn-warning:hover {
            box-shadow: 0 5px 15px rgba(255, 193, 7, 0.4);
        }
        
        .btn-danger {
            background: #dc3545;
        }
        
        textarea, input[type="text"], input[type="file"] {
            width: 100%;
            padding: 12px;
            border: 2px solid #e9ecef;
            border-radius: 6px;
            font-size: 1em;
            font-family: inherit;
            margin-bottom: 15px;
            transition: border-color 0.3s;
        }
        
        textarea:focus, input[type="text"]:focus {
            outline: none;
            border-color: #667eea;
        }
        
        textarea {
            min-height: 200px;
            resize: vertical;
        }
        
        .alert {
            padding: 15px 20px;
            border-radius: 6px;
            margin-bottom: 20px;
            font-weight: 500;
        }
        
        .alert-success {
            background: #d4edda;
            color: #155724;
            border: 2px solid #c3e6cb;
        }
        
        .alert-error {
            background: #f8d7da;
            color: #721c24;
            border: 2px solid #f5c6cb;
        }
        
        .alert-info {
            background: #d1ecf1;
            color: #0c5460;
            border: 2px solid #bee5eb;
        }
        
        .loading {
            display: none;
            text-align: center;
            padding: 20px;
        }
        
        .spinner {
            border: 4px solid #f3f3f3;
            border-top: 4px solid #667eea;
            border-radius: 50%;
            width: 40px;
            height: 40px;
            animation: spin 1s linear infinite;
            margin: 0 auto;
        }
        
        @keyframes spin {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
        }
        
        .test-list {
            list-style: none;
        }
        
        .test-item {
            background: #f8f9fa;
            padding: 20px;
            border-radius: 8px;
            margin-bottom: 15px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        
        .test-info h3 {
            color: #667eea;
            margin-bottom: 8px;
        }
        
        .test-meta {
            font-size: 0.9em;
            color: #6c757d;
        }
        
        .test-actions {
            display: flex;
            gap: 10px;
        }
        
        .feature-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 20px;
            margin-top: 30px;
        }
        
        .feature {
            text-align: center;
            padding: 20px;
        }
        
        .feature-icon {
            font-size: 3em;
            margin-bottom: 15px;
        }
        
        .feature h3 {
            color: #667eea;
            margin-bottom: 10px;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🚀 Test Generation UI</h1>
            <p>Create automated tests without writing code!</p>
        </div>
        
        <div class="nav">
            <a href="/" {% if request.path == '/' %}class="active"{% endif %}>🏠 Home</a>
            <a href="/natural-language" {% if request.path == '/natural-language' %}class="active"{% endif %}>✍️ Natural Language</a>
            <a href="/screenshot-upload" {% if request.path == '/screenshot-upload' %}class="active"{% endif %}>📸 Screenshots</a>
            <a href="/test-library" {% if request.path == '/test-library' %}class="active"{% endif %}>📚 Test Library</a>
        </div>
        
        <div class="content">
            {% block content %}{% endblock %}
        </div>
    </div>
    
    {% block scripts %}{% endblock %}
</body>
</html>'''
    
    # Index page
    index_html = '''{% extends "base.html" %}

{% block content %}
<div class="card">
    <h2>Welcome to Test Generation UI! 🎉</h2>
    <p>Create automated browser tests in three easy ways:</p>
</div>

<div class="feature-grid">
    <div class="card feature">
        <div class="feature-icon">✍️</div>
        <h3>Natural Language</h3>
        <p>Write your test in plain English. No coding required!</p>
        <a href="/natural-language" class="btn">Start Writing</a>
    </div>
    
    <div class="card feature">
        <div class="feature-icon">📸</div>
        <h3>Upload Screenshots</h3>
        <p>Upload workflow screenshots. AI generates the test automatically!</p>
        <a href="/screenshot-upload" class="btn">Upload Screenshots</a>
    </div>
    
    <div class="card feature">
        <div class="feature-icon">📚</div>
        <h3>Test Library</h3>
        <p>View, download, and manage all your generated tests.</p>
        <a href="/test-library" class="btn">View Library</a>
    </div>
</div>

<div class="card" style="margin-top: 30px;">
    <h2>✨ Key Features</h2>
    <ul style="list-style-position: inside; line-height: 2;">
        <li>✅ <strong>No Coding Required</strong> - Anyone can create tests</li>
        <li>✅ <strong>AI-Powered</strong> - Uses advanced vision language models</li>
        <li>✅ <strong>Instant Results</strong> - Generate tests in seconds</li>
        <li>✅ <strong>100% Free</strong> - Uses local Ollama (no cloud costs)</li>
        <li>✅ <strong>Export Ready</strong> - Download tests as JSON</li>
    </ul>
</div>
{% endblock %}'''
    
    # Natural language page
    nl_html = '''{% extends "base.html" %}

{% block content %}
<div class="card">
    <h2>✍️ Create Test from Natural Language</h2>
    <p>Describe your test in plain English. Our AI will convert it to an executable test!</p>
    
    <form id="nlForm">
        <label for="testName"><strong>Test Name:</strong></label>
        <input type="text" id="testName" name="testName" placeholder="e.g., User Login Flow" required>
        
        <label for="testDescription"><strong>Test Description:</strong></label>
        <textarea id="testDescription" name="testDescription" placeholder="Example:&#10;&#10;Test: User Login Flow&#10;&#10;1. Go to https://example.com&#10;2. Click the login button in top right corner&#10;3. Enter email: test@example.com&#10;4. Enter password: Password123&#10;5. Click submit button&#10;6. Verify dashboard appears" required></textarea>
        
        <button type="submit" class="btn">🚀 Generate Test</button>
    </form>
    
    <div id="loading" class="loading">
        <div class="spinner"></div>
        <p>Generating test... This may take 10-30 seconds.</p>
    </div>
    
    <div id="result"></div>
</div>

<div class="card">
    <h3>💡 Tips for Best Results:</h3>
    <ul style="list-style-position: inside; line-height: 2;">
        <li>Be specific about element locations (e.g., "button in top right corner")</li>
        <li>Include verification steps to check results</li>
        <li>Number your steps clearly</li>
        <li>Mention any wait times if needed</li>
    </ul>
</div>
{% endblock %}

{% block scripts %}
<script>
document.getElementById('nlForm').addEventListener('submit', async (e) => {
    e.preventDefault();
    
    const name = document.getElementById('testName').value;
    const description = document.getElementById('testDescription').value;
    
    document.getElementById('loading').style.display = 'block';
    document.getElementById('result').innerHTML = '';
    
    try {
        const response = await fetch('/api/generate-from-text', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({name, description})
        });
        
        const data = await response.json();
        
        if (data.success) {
            document.getElementById('result').innerHTML = `
                <div class="alert alert-success">
                    <h3>✅ Test Generated Successfully!</h3>
                    <p><strong>Test Name:</strong> ${data.test_name}</p>
                    <p><strong>Steps:</strong> ${data.steps}</p>
                    <p><strong>Confidence:</strong> ${(data.confidence * 100).toFixed(0)}%</p>
                    <p><strong>File:</strong> ${data.filename}</p>
                    <a href="/api/test/${data.filename}/download" class="btn">📥 Download</a>
                    <a href="/test-library" class="btn btn-secondary">📚 View in Library</a>
                </div>
            `;
        } else {
            document.getElementById('result').innerHTML = `
                <div class="alert alert-error">
                    <h3>❌ Generation Failed</h3>
                    <p>${data.error}</p>
                </div>
            `;
        }
    } catch (error) {
        document.getElementById('result').innerHTML = `
            <div class="alert alert-error">
                <h3>❌ Error</h3>
                <p>${error.message}</p>
            </div>
        `;
    } finally {
        document.getElementById('loading').style.display = 'none';
    }
});
</script>
{% endblock %}'''
    
    # Screenshot upload page
    screenshot_html = '''{% extends "base.html" %}

{% block content %}
<div class="card">
    <h2>📸 Generate Test from Screenshots</h2>
    <p>Upload screenshots of your workflow. AI will analyze them and generate a test!</p>
    
    <form id="screenshotForm" enctype="multipart/form-data">
        <label for="testNameScreenshot"><strong>Test Name:</strong></label>
        <input type="text" id="testNameScreenshot" name="testName" placeholder="e.g., Search Workflow" required>
        
        <label for="screenshots"><strong>Upload Screenshots (in order):</strong></label>
        <input type="file" id="screenshots" name="screenshots" multiple accept="image/*" required>
        <p style="color: #6c757d; font-size: 0.9em; margin-top: -10px;">Select multiple files (hold Ctrl/Cmd)</p>
        
        <label for="annotations"><strong>Annotations (optional, one per line):</strong></label>
        <textarea id="annotations" name="annotations" placeholder="Screenshot 1: Homepage loaded&#10;Screenshot 2: Clicked search button&#10;Screenshot 3: Entered search query&#10;Screenshot 4: Results displayed"></textarea>
        
        <button type="submit" class="btn">🚀 Generate Test</button>
    </form>
    
    <div id="loadingScreenshot" class="loading">
        <div class="spinner"></div>
        <p>Analyzing screenshots... This may take 30-60 seconds.</p>
    </div>
    
    <div id="resultScreenshot"></div>
</div>

<div class="card">
    <h3>💡 Tips for Best Results:</h3>
    <ul style="list-style-position: inside; line-height: 2;">
        <li>Upload screenshots in chronological order</li>
        <li>Include all important steps in your workflow</li>
        <li>Use clear, high-resolution screenshots</li>
        <li>Add annotations to help AI understand context</li>
    </ul>
</div>
{% endblock %}

{% block scripts %}
<script>
document.getElementById('screenshotForm').addEventListener('submit', async (e) => {
    e.preventDefault();
    
    const formData = new FormData(e.target);
    
    document.getElementById('loadingScreenshot').style.display = 'block';
    document.getElementById('resultScreenshot').innerHTML = '';
    
    try {
        const response = await fetch('/api/generate-from-screenshots', {
            method: 'POST',
            body: formData
        });
        
        const data = await response.json();
        
        if (data.success) {
            document.getElementById('resultScreenshot').innerHTML = `
                <div class="alert alert-success">
                    <h3>✅ Test Generated Successfully!</h3>
                    <p><strong>Test Name:</strong> ${data.test_name}</p>
                    <p><strong>Steps:</strong> ${data.steps}</p>
                    <p><strong>Confidence:</strong> ${(data.confidence * 100).toFixed(0)}%</p>
                    <p><strong>Screenshots Analyzed:</strong> ${data.screenshots}</p>
                    <p><strong>File:</strong> ${data.filename}</p>
                    <a href="/api/test/${data.filename}/download" class="btn">📥 Download</a>
                    <a href="/test-library" class="btn btn-secondary">📚 View in Library</a>
                </div>
            `;
        } else {
            document.getElementById('resultScreenshot').innerHTML = `
                <div class="alert alert-error">
                    <h3>❌ Generation Failed</h3>
                    <p>${data.error}</p>
                </div>
            `;
        }
    } catch (error) {
        document.getElementById('resultScreenshot').innerHTML = `
            <div class="alert alert-error">
                <h3>❌ Error</h3>
                <p>${error.message}</p>
            </div>
        `;
    } finally {
        document.getElementById('loadingScreenshot').style.display = 'none';
    }
});
</script>
{% endblock %}'''
    
    # Test library page
    library_html = '''{% extends "base.html" %}

{% block content %}
<div class="card">
    <h2>📚 Test Library</h2>
    <p>All your generated tests in one place.</p>
</div>

{% if tests %}
<ul class="test-list">
    {% for test in tests %}
    <li class="test-item">
        <div class="test-info">
            <h3>{{ test.name }}</h3>
            <div class="test-meta">
                <span>📅 {{ test.created }}</span> |
                <span>🔢 {{ test.activities }} activities</span> |
                <span>💾 {{ test.size }}</span>
            </div>
        </div>
        <div class="test-actions">
            <button onclick="runTest('{{ test.filename }}')" class="btn btn-primary">▶️ Run Test</button>
            <a href="/test-editor/{{ test.filename }}" class="btn btn-warning">✏️ Edit</a>
            <a href="/api/test/{{ test.filename }}/download" class="btn">📥 Download</a>
            <button onclick="deleteTest('{{ test.filename }}')" class="btn btn-danger">🗑️ Delete</button>
        </div>
    </li>
    {% endfor %}
</ul>
{% else %}
<div class="alert alert-info">
    <p>📭 No tests yet. Create your first test using Natural Language or Screenshot Upload!</p>
</div>
{% endif %}

<!-- Test execution results modal -->
<div id="testResultModal" style="display: none; position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.8); z-index: 1000; overflow-y: auto;">
    <div style="max-width: 900px; margin: 50px auto; background: white; border-radius: 10px; padding: 30px;">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px;">
            <h2 id="modalTitle">Test Execution Results</h2>
            <button onclick="closeModal()" class="btn btn-danger">✕ Close</button>
        </div>
        <div id="modalContent"></div>
    </div>
</div>

{% endblock %}

{% block scripts %}
<script>
async function deleteTest(filename) {
    if (!confirm('Are you sure you want to delete this test?')) return;
    
    try {
        const response = await fetch(`/api/test/${filename}/delete`, {
            method: 'POST'
        });
        
        const data = await response.json();
        
        if (data.success) {
            location.reload();
        } else {
            alert('Failed to delete test: ' + data.error);
        }
    } catch (error) {
        alert('Error: ' + error.message);
    }
}

async function runTest(filename) {
    // Show modal with loading state
    const modal = document.getElementById('testResultModal');
    const modalContent = document.getElementById('modalContent');
    const modalTitle = document.getElementById('modalTitle');
    
    modalTitle.textContent = '▶️ Running Test...';
    modalContent.innerHTML = `
        <div class="loading">
            <div class="spinner"></div>
            <p>Executing test "${filename}"...</p>
            <p style="color: #666; font-size: 14px;">A browser window will open. Please wait...</p>
        </div>
    `;
    modal.style.display = 'block';
    
    try {
        const response = await fetch(`/api/test/${filename}/run`, {
            method: 'POST'
        });
        
        const data = await response.json();
        
        modalTitle.textContent = data.success ? '✅ Test Completed' : '❌ Test Failed';
        
        // Build steps HTML
        let stepsHtml = '';
        if (data.steps && data.steps.length > 0) {
            stepsHtml = '<div style="margin-top: 20px;"><h3>Execution Steps:</h3><ul style="list-style: none; padding: 0;">';
            data.steps.forEach(step => {
                const icon = step.status === 'success' ? '✅' : step.status === 'failed' ? '❌' : '⏭️';
                const color = step.status === 'success' ? '#28a745' : step.status === 'failed' ? '#dc3545' : '#6c757d';
                stepsHtml += `
                    <li style="padding: 10px; margin: 5px 0; background: #f8f9fa; border-left: 4px solid ${color}; border-radius: 4px;">
                        <strong>${icon} Step ${step.step}: ${step.action}</strong>
                        ${step.details ? '<br><span style="color: #666;">' + step.details + '</span>' : ''}
                        ${step.error ? '<br><span style="color: #dc3545;">Error: ' + step.error + '</span>' : ''}
                    </li>
                `;
            });
            stepsHtml += '</ul></div>';
        }
        
        modalContent.innerHTML = `
            <div class="alert ${data.success ? 'alert-success' : 'alert-error'}">
                <h3>${data.success ? '✅ Test Passed' : '❌ Test Failed'}</h3>
                <div style="margin-top: 15px;">
                    <p><strong>Test:</strong> ${data.test_name}</p>
                    <p><strong>Duration:</strong> ${data.duration ? data.duration.toFixed(2) + 's' : 'N/A'}</p>
                    <p><strong>Total Steps:</strong> ${data.total_steps}</p>
                    <p><strong>Executed:</strong> ${data.executed_steps}</p>
                    <p><strong>Failed:</strong> ${data.failed_steps}</p>
                    ${data.error ? '<p style="color: #dc3545;"><strong>Error:</strong> ' + data.error + '</p>' : ''}
                </div>
                ${stepsHtml}
            </div>
        `;
    } catch (error) {
        modalTitle.textContent = '❌ Execution Error';
        modalContent.innerHTML = `
            <div class="alert alert-error">
                <h3>❌ Error</h3>
                <p>${error.message}</p>
            </div>
        `;
    }
}

function closeModal() {
    document.getElementById('testResultModal').style.display = 'none';
}

// Close modal when clicking outside
document.addEventListener('click', function(event) {
    const modal = document.getElementById('testResultModal');
    if (event.target === modal) {
        closeModal();
    }
});
</script>
{% endblock %}'''
    
    # Test editor page
    editor_html = '''{% extends "base.html" %}

{% block content %}
<div class="card">
    <h2>✏️ Edit Test: {{ filename }}</h2>
    <p>Modify your test case directly. Changes are saved in JSON format.</p>
</div>

<div class="card">
    <form id="editorForm">
        <label for="testData"><strong>Test JSON:</strong></label>
        <textarea id="testData" name="testData" style="font-family: monospace; min-height: 400px;">{{ test_data }}</textarea>
        
        <div style="display: flex; gap: 10px; margin-top: 20px;">
            <button type="submit" class="btn btn-primary">💾 Save Changes</button>
            <button type="button" onclick="formatJSON()" class="btn btn-secondary">🔧 Format JSON</button>
            <button type="button" onclick="validateJSON()" class="btn btn-secondary">✓ Validate</button>
            <a href="/test-library" class="btn">← Back to Library</a>
        </div>
    </form>
    
    <div id="result" style="margin-top: 20px;"></div>
</div>

<div class="card" style="background: #f8f9fa;">
    <h3>📘 Editing Guide</h3>
    <div style="margin-top: 15px;">
        <h4>Common Actions:</h4>
        <ul style="line-height: 1.8;">
            <li><strong>navigation</strong>: Navigate to a URL
                <pre style="background: white; padding: 10px; border-radius: 4px; margin-top: 5px;">{
  "action": "navigation",
  "details": {"url": "https://example.com"}
}</pre>
            </li>
            <li><strong>click</strong>: Click an element
                <pre style="background: white; padding: 10px; border-radius: 4px; margin-top: 5px;">{
  "action": "click",
  "details": {"text": "Login"},
  "locators": {"css": "#login-btn"}
}</pre>
            </li>
            <li><strong>text_input</strong>: Enter text
                <pre style="background: white; padding: 10px; border-radius: 4px; margin-top: 5px;">{
  "action": "text_input",
  "details": {"value": "test@example.com"},
  "locators": {"name": "email"}
}</pre>
            </li>
            <li><strong>wait</strong>: Pause execution
                <pre style="background: white; padding: 10px; border-radius: 4px; margin-top: 5px;">{
  "action": "wait",
  "details": {"duration": 3}
}</pre>
            </li>
        </ul>
        
        <h4 style="margin-top: 20px;">Locator Types:</h4>
        <ul>
            <li><code>css</code>: CSS selector (#id, .class, tag)</li>
            <li><code>xpath</code>: XPath expression</li>
            <li><code>id</code>: Element ID</li>
            <li><code>name</code>: Element name attribute</li>
            <li><code>text</code>: Element text content</li>
            <li><code>placeholder</code>: Input placeholder</li>
        </ul>
    </div>
</div>
{% endblock %}

{% block scripts %}
<script>
const filename = '{{ filename }}';

document.getElementById('editorForm').addEventListener('submit', async (e) => {
    e.preventDefault();
    
    const testData = document.getElementById('testData').value;
    const resultDiv = document.getElementById('result');
    
    // Validate JSON first
    try {
        const parsed = JSON.parse(testData);
        
        // Send update request
        const response = await fetch(`/api/test/${filename}/update`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(parsed)
        });
        
        const data = await response.json();
        
        if (data.success) {
            resultDiv.innerHTML = `
                <div class="alert alert-success">
                    <h3>✅ Test Saved Successfully!</h3>
                    <p>${data.message}</p>
                    <a href="/test-library" class="btn">← Back to Library</a>
                    <button onclick="location.reload()" class="btn btn-secondary">🔄 Reload</button>
                </div>
            `;
        } else {
            resultDiv.innerHTML = `
                <div class="alert alert-error">
                    <h3>❌ Save Failed</h3>
                    <p>${data.error}</p>
                </div>
            `;
        }
    } catch (error) {
        resultDiv.innerHTML = `
            <div class="alert alert-error">
                <h3>❌ Invalid JSON</h3>
                <p>${error.message}</p>
                <p>Please fix the JSON syntax before saving.</p>
            </div>
        `;
    }
});

function formatJSON() {
    const textarea = document.getElementById('testData');
    try {
        const parsed = JSON.parse(textarea.value);
        textarea.value = JSON.stringify(parsed, null, 2);
        document.getElementById('result').innerHTML = `
            <div class="alert alert-success">
                <p>✅ JSON formatted successfully!</p>
            </div>
        `;
    } catch (error) {
        document.getElementById('result').innerHTML = `
            <div class="alert alert-error">
                <p>❌ Invalid JSON: ${error.message}</p>
            </div>
        `;
    }
}

function validateJSON() {
    const textarea = document.getElementById('testData');
    try {
        const parsed = JSON.parse(textarea.value);
        const stepCount = Array.isArray(parsed) ? parsed.length : parsed.activities?.length || 0;
        document.getElementById('result').innerHTML = `
            <div class="alert alert-success">
                <h3>✅ Valid JSON</h3>
                <p><strong>Format:</strong> ${Array.isArray(parsed) ? 'Array' : 'Object'}</p>
                <p><strong>Steps:</strong> ${stepCount}</p>
            </div>
        `;
    } catch (error) {
        document.getElementById('result').innerHTML = `
            <div class="alert alert-error">
                <h3>❌ Invalid JSON</h3>
                <p>${error.message}</p>
            </div>
        `;
    }
}
</script>
{% endblock %}'''
    
    # Write templates
    templates_dir = Path('templates')
    templates_dir.mkdir(exist_ok=True)
    
    (templates_dir / 'base.html').write_text(base_html)
    (templates_dir / 'index.html').write_text(index_html)
    (templates_dir / 'natural_language.html').write_text(nl_html)
    (templates_dir / 'screenshot_upload.html').write_text(screenshot_html)
    (templates_dir / 'test_library.html').write_text(library_html)
    (templates_dir / 'test_editor.html').write_text(editor_html)
    
    print("✓ HTML templates created")


def main():
    """Start the web UI"""
    print("="*80)
    print("TEST GENERATION UI")
    print("="*80)
    print()
    print("🚀 Starting web server...")
    print()
    
    # Create templates
    create_html_templates()
    
    print()
    print("="*80)
    print("✅ Server is ready!")
    print("="*80)
    print()
    print("🌐 Open your browser and go to:")
    print()
    print("    http://localhost:5000")
    print()
    print("="*80)
    print()
    print("Features:")
    print("  ✍️  Natural Language Test Creation")
    print("  📸 Screenshot-Based Test Generation")
    print("  📚 Test Library & Management")
    print("  📥 Download Tests as JSON")
    print()
    print("Press Ctrl+C to stop the server")
    print("="*80)
    print()
    
    # Start Flask app
    app.run(debug=True, host='0.0.0.0', port=5000)


if __name__ == '__main__':
    main()
