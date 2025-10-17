# Enhanced Features Guide

This guide covers the two major enhancements to the browser automation framework:
1. **Multi-Strategy Element Locators** - Resilient element finding with automatic fallback
2. **Assertion Framework** - Comprehensive test validation capabilities

## Table of Contents
- [Quick Start](#quick-start)
- [Multi-Strategy Locators](#multi-strategy-locators)
- [Assertion Framework](#assertion-framework)
- [Integration Guide](#integration-guide)
- [Best Practices](#best-practices)
- [Troubleshooting](#troubleshooting)

---

## Quick Start

### Run the Demo
```bash
python demo_enhanced_features.py
```

This comprehensive demo shows:
- How to create multi-strategy locators
- All 24 assertion types available
- Integration examples
- Real-world use cases

### Basic Example
```python
from element_locator import ElementLocator
from assertions import AssertionBuilder

# Create locator with fallback strategies
search_btn = (ElementLocator("Search Button")
              .add_id("search-btn")
              .add_class("search-button")
              .add_xpath("//button[@aria-label='Search']"))

# Add assertions
executor.add_assertion(
    AssertionBuilder.element_visible("input[name='q']")
)
executor.add_assertion(
    AssertionBuilder.text_present("Search results")
)
```

---

## Multi-Strategy Locators

### Why Multi-Strategy?

**Problem**: Traditional tests use a single locator (e.g., XPath). When the UI changes, tests break.

**Solution**: Store multiple ways to find the same element. If one fails, automatically try the next.

### Priority System

Strategies are tried in this order (lower = higher priority):

| Priority | Strategy | Example | Use Case |
|----------|----------|---------|----------|
| 10 | ID | `search-btn` | Most stable, preferred |
| 20 | Name | `username` | Form fields |
| 30 | CSS | `[aria-label='Search']` | Modern selectors |
| 40 | XPath | `//button[@id='search']` | Complex queries |
| 50 | Link Text | `Learn More` | Links |
| 60 | Partial Link | `Learn` | Flexible links |
| 70 | Tag Name | `button` | Generic fallback |
| 80 | Class | `btn-primary` | Styling-based |
| 90 | Text Content | `Search` | Human-readable |
| 100 | Coordinates | `(1575, 14)` | Last resort |

### Creating Locators

#### Method 1: Fluent API
```python
from element_locator import ElementLocator

locator = (ElementLocator("Login Button")
           .add_id("login-btn")
           .add_class("btn-primary")
           .add_xpath("//button[@type='submit']")
           .add_text("Log in"))
```

#### Method 2: Individual Additions
```python
locator = ElementLocator("Search Button")
locator.add_id("search-btn")
locator.add_css("[aria-label='Search']")
locator.add_coordinates(1575, 14)
```

#### Method 3: From Recorded Activity
```python
from element_locator import create_locator_from_activity

activity = {
    "action": "click",
    "details": {
        "id": "search-btn",
        "className": "search-button",
        "xpath": "//button[@id='search-btn']",
        "text": "Search",
        "coordinates": {"x": 1575, "y": 14}
    }
}

locator = create_locator_from_activity(activity)
# Automatically creates locator with all available strategies
```

### Using Locators

#### In ActivityExecutor
```python
# Automatic - activities are converted to enhanced locators
executor = ActivityExecutor(driver)
executor.execute_activity(activity)  # Uses multi-strategy automatically
```

#### Manual Element Finding
```python
# Find element with fallback
element, strategy = locator.find_element(driver)
if element:
    print(f"Found using {strategy.type}: {strategy.value}")
    element.click()
```

### Success Tracking

Locators track which strategies work:

```python
# After successful find
strategy.record_success()

# After failure
strategy.record_failure()

# Check success rate
rate = strategy.success_rate()  # Returns 0.0 to 1.0
```

This helps identify the most reliable locators for each element.

### Serialization

Store locators in JSON for reuse:

```python
# Save
locator_dict = locator.to_dict()
json.dump(locator_dict, file)

# Restore
locator = ElementLocator.from_dict(locator_dict)
```

---

## Assertion Framework

### Why Assertions?

**Problem**: Tests click buttons but don't verify the expected result happened.

**Solution**: Add explicit checks for expected outcomes (visibility, text, counts, etc.).

### Assertion Types (24 Total)

#### Element State
- `element_visible` - Check if element is visible
- `element_not_visible` - Check if element is hidden
- `element_exists` - Check if element exists in DOM
- `element_enabled` - Check if element is enabled
- `element_disabled` - Check if element is disabled

#### Text Validation
- `text_present` - Check if text exists anywhere on page
- `text_contains` - Check if specific text is present
- `text_equals` - Check if text exactly matches

#### URL Validation
- `url_equals` - Check if URL exactly matches
- `url_contains` - Check if URL contains substring
- `url_matches` - Check if URL matches regex pattern

#### Element Count
- `element_count` - Check exact element count
- `element_count_min` - Check minimum element count
- `element_count_max` - Check maximum element count

#### Attributes
- `attribute_equals` - Check if attribute value matches
- `attribute_contains` - Check if attribute contains substring
- `attribute_exists` - Check if attribute exists

#### Page State
- `page_title_equals` - Check if page title exactly matches
- `page_title_contains` - Check if page title contains text
- `alert_present` - Check if JavaScript alert is present

#### Advanced (Not yet implemented)
- `javascript_returns_true` - Run custom JavaScript
- `response_time_under` - Check performance
- `cookie_exists` - Check cookies
- `local_storage_contains` - Check local storage

### Creating Assertions

#### Method 1: Builder Pattern (Recommended)
```python
from assertions import AssertionBuilder

# Simple assertions
assertion1 = AssertionBuilder.element_visible(".modal")
assertion2 = AssertionBuilder.text_present("Success")
assertion3 = AssertionBuilder.url_contains("search")

# With custom timeout
assertion4 = AssertionBuilder.element_visible(
    ".slow-loading",
    timeout=10.0
)

# Complex assertions
assertion5 = AssertionBuilder.element_count_min(
    ".result-item",
    min_count=5,
    timeout=8.0
)

assertion6 = AssertionBuilder.attribute_equals(
    "#username",
    attribute="placeholder",
    value="Enter username"
)
```

#### Method 2: Quick Functions
```python
from assertions import (
    assert_element_visible,
    assert_text_present,
    assert_url_contains,
    assert_element_count_min
)

# One-liners
assert_element_visible(".modal")
assert_text_present("results found")
assert_url_contains("/search")
assert_element_count_min(".item", 1)
```

#### Method 3: Direct Instantiation
```python
from assertions import ElementVisibleAssertion

assertion = ElementVisibleAssertion(
    selector=".modal-dialog",
    timeout=5.0,
    required=True
)
```

### Using Assertions

#### In ActivityExecutor
```python
from activity_executor import ActivityExecutor
from assertions import AssertionBuilder

executor = ActivityExecutor(driver)

# Add assertions before executing activity
executor.add_assertion(
    AssertionBuilder.element_visible(".search-field")
)
executor.add_assertion(
    AssertionBuilder.text_present("Search")
)

# Execute activity - assertions run automatically after
result = executor.execute_activity(activity)

# Check assertion results
if 'assertions' in result:
    for assertion_result in result['assertions']:
        print(f"{assertion_result['description']}: {assertion_result['passed']}")
```

#### Manual Execution
```python
from assertions import AssertionBuilder

assertion = AssertionBuilder.element_visible(".modal")
result = assertion.execute(driver)

if result.passed:
    print(f"✓ {result.message}")
else:
    print(f"✗ {result.message}")
    print(f"Error: {result.error}")
```

### Assertion Options

#### Timeout
How long to wait for assertion to pass:
```python
# Default 5 seconds
AssertionBuilder.element_visible(".modal")

# Custom timeout
AssertionBuilder.element_visible(".modal", timeout=10.0)
```

#### Required vs Optional
- **Required** (default): Test fails if assertion fails
- **Optional**: Test continues with warning

```python
# Required (fails test if not visible)
AssertionBuilder.element_visible(".critical", required=True)

# Optional (warning only)
AssertionBuilder.element_visible(".optional", required=False)
```

#### Retry Logic
Assertions automatically retry until:
- Condition passes → Success
- Timeout reached → Failure

No need to add manual waits!

---

## Integration Guide

### Full Test Example

```python
from selenium import webdriver
from activity_executor import ActivityExecutor
from element_locator import ElementLocator
from assertions import AssertionBuilder

# Setup
driver = webdriver.Chrome()
executor = ActivityExecutor(driver)

# Navigate
driver.get("https://www.ibm.com")

# Step 1: Click search button with multi-strategy locator
search_activity = {
    "action": "click",
    "details": {
        "id": "search-btn",
        "className": "search-button",
        "xpath": "//button[@aria-label='Search']",
        "text": "Search",
        "coordinates": {"x": 1575, "y": 14}
    }
}

# Add assertion to verify search field appears
executor.add_assertion(
    AssertionBuilder.element_visible("input[name='q']", timeout=5.0)
)

# Execute - uses multi-strategy locator, runs assertion
result = executor.execute_activity(search_activity)

# Step 2: Type search query
input_activity = {
    "action": "text_input",
    "details": {
        "id": "search-input",
        "name": "q",
        "xpath": "//input[@name='q']",
        "text": "",
        "value": "cloud computing"
    }
}

# Add assertions for search results
executor.add_assertion(
    AssertionBuilder.element_count_min(".search-result", 1)
)
executor.add_assertion(
    AssertionBuilder.url_contains("search")
)
executor.add_assertion(
    AssertionBuilder.text_present("results")
)

result = executor.execute_activity(input_activity)

# Check results
print(f"Success: {result['success']}")
for assertion_result in result.get('assertions', []):
    status = "✓" if assertion_result['passed'] else "✗"
    print(f"{status} {assertion_result['description']}")
```

### Recording with Multiple Locators

Update `main.py` to capture multiple locators:

```python
def get_element_info(element):
    """Capture multiple locator strategies"""
    info = {
        "tagName": element.tag_name,
        "id": element.get_attribute("id") or "",
        "name": element.get_attribute("name") or "",
        "className": element.get_attribute("class") or "",
        "xpath": get_xpath(element),
        "text": element.text or "",
        "coordinates": {
            "x": element.location['x'],
            "y": element.location['y']
        }
    }
    return info
```

### Database Integration

Assertion results are automatically saved:

```python
# In test_database.py - test_steps table includes assertions
{
    "step_number": 1,
    "action": "click",
    "success": true,
    "assertions": [
        {
            "type": "element_visible",
            "description": "Search field visible",
            "passed": true,
            "message": "Element found and visible",
            "execution_time": 0.123
        }
    ]
}
```

View with CLI:
```bash
python db_utils.py --details <test_run_id>
```

---

## Best Practices

### Multi-Strategy Locators

1. **Order by Stability**
   - Most stable first (ID, name)
   - Less stable last (class, text)
   
2. **Include Coordinates as Fallback**
   - Always add coordinates as last resort
   - Works even when all selectors fail
   
3. **Test Each Strategy**
   - Verify each locator works in isolation
   - Don't rely on untested strategies
   
4. **Monitor Success Rates**
   - Check which strategies work best
   - Remove unreliable strategies
   
5. **Keep Descriptions Clear**
   - Use human-readable names
   - Example: "Search Button" not "btn_1"

### Assertions

1. **Assert Expected Outcomes**
   - Don't just click - verify what should happen
   - Example: After login → Assert user menu visible
   
2. **Use Appropriate Timeouts**
   - Fast operations: 2-3 seconds
   - API calls: 5-10 seconds
   - Heavy pages: 10-15 seconds
   
3. **Make Critical Assertions Required**
   - Login successful → Required
   - Optional ad loaded → Optional
   
4. **Group Related Assertions**
   - Add all assertions for a step together
   - Makes test intent clear
   
5. **Descriptive Messages**
   - Clear description helps debugging
   - Good: "Login button should be visible"
   - Bad: "Check element"

### Combined Usage

1. **Locator + Assertion Pattern**
   ```python
   # Find element with multiple strategies
   element_locator = ElementLocator("Submit").add_id("submit")...
   
   # Verify expected result
   executor.add_assertion(AssertionBuilder.text_present("Success"))
   ```

2. **Progressive Enhancement**
   - Start with basic locators (ID, XPath)
   - Add assertions as test matures
   - Monitor and refine based on failures

3. **Failure Analysis**
   - Locator failed → UI changed
   - Assertion failed → Business logic issue
   - Both failed → Major problem

---

## Troubleshooting

### Locator Issues

#### All Strategies Fail
```
Error: Could not find element with any strategy
```

**Solutions**:
1. Check element exists on page
2. Verify timing (wait for page load)
3. Check for iframe/shadow DOM
4. Update strategies with correct values

#### Specific Strategy Always Fails
```
Strategy 'xpath' never succeeds (0/5 attempts)
```

**Solutions**:
1. Verify XPath is correct
2. Check for dynamic IDs in XPath
3. Remove unreliable strategy
4. Update strategy with better selector

### Assertion Issues

#### Assertion Timeout
```
Assertion failed: Element '.modal' not visible within 5.0s
```

**Solutions**:
1. Increase timeout: `timeout=10.0`
2. Check element selector is correct
3. Verify element actually appears
4. Check for timing issues (page load, animation)

#### Flaky Assertions
```
Sometimes passes, sometimes fails
```

**Solutions**:
1. Increase timeout
2. Add wait_for_page_ready() before assertion
3. Check for animations/transitions
4. Use element_visible instead of element_exists

### Integration Issues

#### Assertions Not Running
```
No assertion results in output
```

**Solutions**:
1. Verify assertions added before execute_activity()
2. Check executor.use_enhanced_locators = True
3. Ensure latest version of activity_executor.py

#### Results Not in Database
```
Assertion results not saved
```

**Solutions**:
1. Check TestDatabase initialized
2. Verify database connection
3. Check result dict includes 'assertions'
4. Update test_database.py schema if needed

---

## Examples

### Example 1: Search Test
```python
# Click search button
executor.add_assertion(AssertionBuilder.element_visible("input[name='q']"))
executor.execute_activity(click_search)

# Type query
executor.add_assertion(AssertionBuilder.element_count_min(".result", 1))
executor.add_assertion(AssertionBuilder.url_contains("search"))
executor.execute_activity(type_query)
```

### Example 2: Login Test
```python
# Enter username
executor.add_assertion(AssertionBuilder.element_enabled("#password"))
executor.execute_activity(type_username)

# Enter password
executor.add_assertion(AssertionBuilder.element_enabled("button[type='submit']"))
executor.execute_activity(type_password)

# Click login
executor.add_assertion(AssertionBuilder.url_equals("https://app.example.com/dashboard"))
executor.add_assertion(AssertionBuilder.element_visible(".user-menu"))
executor.execute_activity(click_login)
```

### Example 3: Form Validation
```python
# Submit empty form
executor.add_assertion(AssertionBuilder.text_present("Email is required"))
executor.add_assertion(AssertionBuilder.element_visible(".error-message"))
executor.execute_activity(click_submit)

# Fill form
executor.add_assertion(AssertionBuilder.text_present("Success"))
executor.add_assertion(AssertionBuilder.element_not_visible(".error-message"))
executor.execute_activity(fill_and_submit)
```

---

## Next Steps

1. **Run the Demo**: `python demo_enhanced_features.py`
2. **Update Your Tests**: Add locators and assertions
3. **Monitor Results**: Use `db_utils.py --details`
4. **Refine Strategies**: Remove unreliable locators
5. **Add More Assertions**: Catch regressions early

For more information:
- `element_locator.py` - Full API documentation
- `assertions.py` - All assertion types
- `demo_enhanced_features.py` - Comprehensive examples
- `FUTURE_IMPROVEMENTS_AND_VLM_OPPORTUNITIES.md` - Upcoming features
