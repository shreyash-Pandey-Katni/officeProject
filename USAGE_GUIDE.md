# Quick Start Guide: Using Enhanced Locators and VLM Features

## Installation

```bash
# Phase 1: No additional dependencies (already included)

# Phase 2: Install Ollama and Granite model
# 1. Install Ollama (if not already installed)
curl -fsSL https://ollama.ai/install.sh | sh

# 2. Download Granite model
ollama pull granite3.1-dense:8b

# 3. Verify installation
ollama list  # Should show granite3.1-dense:8b

# 4. Test Ollama API
curl http://localhost:11434/api/tags
```

## Basic Usage

### Recording with Multi-Selector Locators (Automatic)

```python
# Just record normally - locators captured automatically!
python main.py

# Navigate and interact with the website
# Each click/input will automatically capture:
#   - ID, name, class, tag name
#   - XPath, CSS selector, text content
#   - ARIA labels, placeholders
#   - Coordinates as last fallback
```

### Replaying with Enhanced Element Finding

```python
python replay_browser_activities.py

# The executor will automatically:
# 1. Try multi-selector locators (Phase 1)
# 2. Fall back to legacy methods if needed
# 3. Use VLM as final fallback (Phase 2, if Ollama available)
```

## Advanced Usage

### Programmatic Recording

```python
from selenium import webdriver
from main import BrowserActivityRecorder

# Create driver and recorder
options = webdriver.ChromeOptions()
options.add_argument("--start-maximized")
driver = webdriver.Chrome(options=options)

recorder = BrowserActivityRecorder(driver)

# Navigate
driver.get("https://example.com")

# Your test actions...
# Locators are automatically captured!

# Save activities
import json
with open('my_test_activities.json', 'w') as f:
    json.dump(recorder.activity_log, f, indent=2)

driver.quit()
```

### Programmatic Replay with Assertions

```python
from selenium import webdriver
from activity_executor import ActivityExecutor
from assertions import AssertionBuilder
import json

# Create driver and executor
driver = webdriver.Chrome()
executor = ActivityExecutor(driver)

# Load activities
with open('my_test_activities.json', 'r') as f:
    activities = json.load(f)

# Add assertions before steps
for activity in activities:
    # Execute activity
    result = executor.execute_activity(activity)
    
    # Add assertion for next step
    if activity['action'] == 'click':
        # Verify element was clicked
        executor.add_assertion(
            AssertionBuilder()
                .url_contains("expected-page")
                .timeout(10)
                .required()
                .build()
        )
    
    # Check result
    if not result['success']:
        print(f"❌ Failed: {result['error']}")
        
        # Analyze failure with VLM (Phase 2)
        if executor.vlm_enabled:
            analysis = executor.analyze_failure(
                activity=activity,
                error_message=result['error'],
                before_screenshot=result.get('screenshot_before'),
                after_screenshot=result.get('screenshot_after')
            )
            
            if analysis:
                print(f"\n🔍 Failure Analysis:")
                print(f"Root Cause: {analysis['root_cause']}")
                print(f"Confidence: {analysis['confidence']:.2f}")
                print(f"\n💡 Suggested Fixes:")
                for i, fix in enumerate(analysis['fixes'][:3], 1):
                    print(f"{i}. {fix['description']}")
                    print(f"   Code: {fix['code_change']}")
                    print(f"   Priority: {fix['priority']}")
        break
    else:
        print(f"✓ Passed: {activity['action']} - {result['method']}")

driver.quit()
```

### Using VLM Element Finder Directly

```python
from selenium import webdriver
from vlm_element_finder import VLMElementFinder

driver = webdriver.Chrome()
driver.get("https://example.com")

# Initialize VLM finder
vlm_finder = VLMElementFinder()

# Find element by natural language description
result = vlm_finder.find_element_by_description(
    driver=driver,
    description="blue search button with magnifying glass icon",
    visual_cues=["right side of navigation bar", "next to logo"],
    expected_properties={"tag": "button", "text": "Search"}
)

if result.found:
    print(f"✓ Found at coordinates: {result.coordinates}")
    print(f"Confidence: {result.confidence:.2f}")
    print(f"Suggested locator: {result.suggested_locator}")
    
    # Click the element
    success, message = vlm_finder.click_element_by_description(
        driver=driver,
        description="blue search button"
    )
    
    if success:
        print(f"✓ Clicked: {message}")
else:
    print(f"✗ Not found: {result.reasoning}")

driver.quit()
```

### Custom Locator Strategy

```python
from element_locator import ElementLocator

# Create custom locator with specific priorities
locator = ElementLocator("Login button")

# Add strategies in desired order
locator.add_id("login-btn")                    # Priority 10
locator.add_css("[aria-label='Sign in']")      # Priority 30
locator.add_text("Login")                       # Priority 90
locator.add_coordinates(1200, 800)              # Priority 100

# Find element
element, method, error = locator.find_element(driver, timeout=10.0)

if element:
    print(f"✓ Found using: {method}")
    element.click()
else:
    print(f"✗ Not found: {error}")
```

### Intelligent Failure Analysis

```python
from intelligent_failure_analyzer import IntelligentFailureAnalyzer

analyzer = IntelligentFailureAnalyzer()

# Analyze a failure
analysis = analyzer.analyze_failure(
    step_description="Click search button in header",
    error_message="NoSuchElementException: Unable to locate element",
    before_screenshot=open('before.png', 'rb').read(),  # Last good state
    after_screenshot=open('after.png', 'rb').read(),     # Failed state
    page_url="https://example.com"
)

print(f"Root Cause: {analysis.root_cause.value}")
print(f"Description: {analysis.description}")
print(f"Confidence: {analysis.confidence:.2f}")

print(f"\nSuggested Fixes:")
for fix in analysis.fixes:
    print(f"- {fix.description}")
    print(f"  Code: {fix.code_change}")
    print(f"  Priority: {fix.priority.value}")
    print(f"  Effort: {fix.estimated_effort}")
    print(f"  Confidence: {fix.confidence:.2f}")
    print()

# Generate HTML report
report_html = analyzer.generate_html_report(analysis)
with open('failure_report.html', 'w') as f:
    f.write(report_html)
```

## Configuration

### Disable VLM Features

```python
# VLM features automatically disabled if Ollama not available
# Force disable:
executor = ActivityExecutor(driver)
executor.vlm_enabled = False
```

### Disable Enhanced Locators (use legacy only)

```python
executor = ActivityExecutor(driver)
executor.use_enhanced_locators = False
```

### Configure VLM Settings

```python
from vlm_element_finder import VLMElementFinder

vlm_finder = VLMElementFinder(
    ollama_url="http://localhost:11434",  # Custom Ollama URL
    model="granite3.1-dense:8b",          # Model name
    cache_enabled=True,                    # Enable response caching
    timeout=30                             # Request timeout
)
```

## Monitoring & Debugging

### Check VLM Status

```python
executor = ActivityExecutor(driver)

if executor.vlm_enabled:
    print("✓ VLM features available")
    print(f"  - VLM Finder: {executor.vlm_finder is not None}")
    print(f"  - Failure Analyzer: {executor.failure_analyzer is not None}")
else:
    print("✗ VLM features disabled (Ollama not available)")
```

### Track Locator Success Rates

```python
from collections import Counter

# After replay
methods_used = Counter()

for activity in replayed_activities:
    method = activity['result'].get('method', 'unknown')
    methods_used[method] += 1

print("\nLocator Strategy Usage:")
for method, count in methods_used.most_common():
    percentage = count / len(replayed_activities) * 100
    print(f"  {method}: {count} ({percentage:.1f}%)")

# Example output:
# locator_id: 45 (50.0%)
# locator_css: 27 (30.0%)
# vlm_finder: 14 (15.5%)
# locator_coordinates: 4 (4.5%)
```

### Debug Locator Failures

```python
import logging

# Enable debug logging
logging.basicConfig(level=logging.DEBUG)

# Run replay - will show detailed locator attempts
executor = ActivityExecutor(driver)
result = executor.execute_activity(activity)

# Output will show:
# [LOCATOR] Finding element: BUTTON with text 'Search'
# [LOCATOR] Trying 6 strategies...
# [LOCATOR] Trying strategy: id = search-btn
# [LOCATOR] ✓ Found element using id: search-btn
```

## Best Practices

### 1. Recording Best Practices

- **Use Semantic HTML**: Elements with IDs and ARIA labels are more stable
- **Avoid Recording During Loading**: Wait for page to fully load before recording
- **Include Context**: Record nearby stable elements for better VLM fallback

### 2. Replay Best Practices

- **Check VLM Status First**: Verify Ollama is running before important test runs
- **Monitor Locator Success**: Track which strategies work best for your app
- **Use Assertions**: Add assertions to verify each step succeeded
- **Analyze Failures**: Use failure analysis to improve test stability

### 3. VLM Usage Best Practices

- **Cache Wisely**: Enable caching for faster repeated tests
- **Good Descriptions**: Use specific, unique descriptions for elements
- **Visual Cues**: Provide context about element location/appearance
- **Strategic Use**: Use VLM as fallback, not primary strategy

### 4. Performance Optimization

- **Prefer Stable Locators**: ID and name are fastest
- **Limit VLM Calls**: Use caching and only when necessary
- **Timeouts**: Set reasonable timeouts (5-10s for locators, 30s for VLM)
- **Parallel Tests**: VLM calls are independent, safe for parallel execution

## Troubleshooting

### Locators Not Working

```python
# Debug locator creation
details = activity['details']
locators = activity.get('locators', {})

print(f"Available locators: {list(locators.keys())}")
print(f"ID: {locators.get('id')}")
print(f"CSS: {locators.get('css_selector')}")
print(f"XPath: {locators.get('xpath')}")

# Try each manually
if locators.get('id'):
    try:
        elem = driver.find_element(By.ID, locators['id'])
        print(f"✓ ID locator works: {locators['id']}")
    except:
        print(f"✗ ID locator failed")
```

### VLM Not Finding Elements

```python
# Check VLM result details
result = vlm_finder.find_element_by_description(
    driver=driver,
    description="search button"
)

print(f"Found: {result.found}")
print(f"Confidence: {result.confidence:.2f}")
print(f"Reasoning: {result.reasoning}")
print(f"Coordinates: {result.coordinates}")
print(f"Element Description: {result.element_description}")
print(f"Suggested Locator: {result.suggested_locator}")

# If confidence low, add more context
result = vlm_finder.find_element_by_description(
    driver=driver,
    description="search button",
    visual_cues=["blue background", "magnifying glass icon"],
    nearby_elements=["navigation bar", "company logo"]
)
```

### Ollama Connection Issues

```bash
# Check if Ollama is running
curl http://localhost:11434/api/tags

# If not running, start it
ollama serve

# In another terminal
ollama pull granite3.1-dense:8b

# Test with simple prompt
curl http://localhost:11434/api/generate -d '{
  "model": "granite3.1-dense:8b",
  "prompt": "Hello",
  "stream": false
}'
```

## Examples Repository

See `examples/` directory for complete working examples:

- `basic_recording.py` - Simple recording example
- `replay_with_assertions.py` - Replay with assertion checks
- `vlm_element_finding.py` - Direct VLM usage
- `failure_analysis.py` - Analyze and fix failures
- `custom_locators.py` - Create custom locator strategies

## Support

For issues and questions:
1. Check `INTEGRATION_SUMMARY.md` for detailed documentation
2. Review `PHASE2_OLLAMA_GUIDE.md` for VLM-specific help
3. Enable debug logging for troubleshooting
4. Test Ollama connection separately if VLM issues

**Happy Testing! 🚀**
