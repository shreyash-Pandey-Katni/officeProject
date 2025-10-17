# HTML Extraction for Shadow DOM and iframe Elements

## Overview
This document describes the implementation of enhanced HTML extraction that supports elements inside Shadow DOM and iframe contexts.

## Problem Statement
The original `get_element_html()` method only supported regular DOM elements. When trying to extract HTML from elements inside Shadow DOM or iframes, it would return `null`, limiting:
- Debugging capabilities
- Activity log completeness
- Fallback element identification
- VLM-based element matching

## Solution Architecture

### Enhanced Method Signature
```python
def get_element_html(self, xpath=None, css_selector=None, in_shadow_root=False, in_iframe=False):
    """Get the full HTML of a specific element, including shadow DOM and iframe contexts"""
```

### Context Detection
The method now accepts two new parameters:
- `in_shadow_root`: Boolean flag indicating the element is in a Shadow DOM
- `in_iframe`: Boolean flag indicating the element is in an iframe

These flags are extracted from the activity details that already contain `inShadowRoot` and `inIframe` fields from our event tracking.

### Implementation Details

#### 1. Shadow DOM HTML Extraction
When `in_shadow_root=True`, the method uses recursive JavaScript to search through all shadow roots:

```javascript
function findInShadowDOM(root, selector) {
    // Try to find in current root
    let element = root.querySelector(selector);
    if (element) return element;
    
    // Search in all shadow roots recursively
    let allElements = root.querySelectorAll('*');
    for (let el of allElements) {
        if (el.shadowRoot) {
            element = findInShadowDOM(el.shadowRoot, selector);
            if (element) return element;
        }
    }
    return null;
}

let element = findInShadowDOM(document, cssSelector);
return element ? element.outerHTML : null;
```

**Key Features:**
- Recursive search through all shadow roots
- Supports both CSS selectors and XPath (with fallback)
- Returns `outerHTML` when element is found
- Returns `null` if not found

#### 2. iframe HTML Extraction
When `in_iframe=True`, the method searches through all same-origin iframes:

```javascript
function findInIframes(selector) {
    // Try main document first
    let element = document.querySelector(selector);
    if (element) return element.outerHTML;
    
    // Search in all iframes
    let iframes = document.querySelectorAll('iframe');
    for (let iframe of iframes) {
        try {
            let iframeDoc = iframe.contentDocument || iframe.contentWindow.document;
            element = iframeDoc.querySelector(selector);
            if (element) return element.outerHTML;
        } catch (e) {
            // Cross-origin iframe, skip
            console.log('Cross-origin iframe, skipping');
        }
    }
    return null;
}

return findInIframes(cssSelector);
```

**Key Features:**
- Searches main document first as fallback
- Iterates through all iframe elements
- Handles cross-origin iframes gracefully (skips them)
- Returns `outerHTML` when element is found
- Returns `null` if not found

#### 3. Regular DOM (Fallback)
When both flags are `False`, uses the original logic:

```javascript
// For CSS selector
var element = document.querySelector(cssSelector);
return element ? element.outerHTML : null;

// For XPath
var element = document.evaluate(xpath, document, null, 
    XPathResult.FIRST_ORDERED_NODE_TYPE, null).singleNodeValue;
return element ? element.outerHTML : null;
```

## Integration Points

### Call Site Update
The `trigger_async_vlm_description()` method was updated to pass context flags:

```python
def trigger_async_vlm_description(self, activity_index, screenshot_path, details, event_type):
    """Trigger async VLM description generation"""
    # Extract element HTML with context awareness
    xpath = details.get('xpath')
    css_selector = details.get('cssSelector')
    in_shadow_root = details.get('inShadowRoot', False)
    in_iframe = details.get('inIframe', False)
    
    element_html = self.get_element_html(
        xpath=xpath, 
        css_selector=css_selector,
        in_shadow_root=in_shadow_root,
        in_iframe=in_iframe
    )
    # ... rest of the method
```

**Data Flow:**
1. Event tracking JavaScript captures `inShadowRoot` and `inIframe` flags
2. Flags are stored in activity details
3. Details are passed to `trigger_async_vlm_description()`
4. Flags are extracted and passed to `get_element_html()`
5. Correct extraction method is used based on flags
6. HTML is stored in VLM results and activity logs

## Testing

### Test Coverage
Created comprehensive test (`tests/test_html_extraction.py`) covering:
1. **Regular DOM extraction** - Basic element HTML extraction
2. **Shadow DOM extraction** - Element inside shadow root
3. **iframe extraction** - Element inside same-origin iframe

### Test Results
```
================================================================================
SHADOW DOM & IFRAME HTML EXTRACTION TEST
================================================================================

[TEST 1] Testing Regular DOM HTML extraction...
[TEST 1] ✓ Regular DOM HTML extracted successfully
         HTML: <button id="regular-button" class="test-button">Regular Button</button>

[TEST 2] Testing Shadow DOM HTML extraction...
[TEST 2] ✓ Shadow DOM HTML extracted successfully
         HTML: <button class="shadow-button" id="shadow-button">Shadow DOM Button</button>

[TEST 3] Testing Iframe HTML extraction...
[TEST 3] ✓ Iframe HTML extracted successfully
         HTML: <button class="iframe-button" id="iframe-button">Iframe Button</button>

================================================================================
RESULTS: 3/3 tests passed
✅ SUCCESS: All HTML extraction methods working!
================================================================================
```

### Test Implementation Notes
- Uses temporary HTML file to avoid cross-origin issues
- Shadow DOM created with `attachShadow({mode: 'open'})`
- iframe uses `srcdoc` attribute for same-origin content
- Proper wait times for page and iframe loading
- Comprehensive debug logging

## Benefits

### 1. Complete Activity Logs
Activity logs now contain complete HTML for all elements:
```json
{
  "element_html": "<button class=\"shadow-button\">Click Me</button>",
  "inShadowRoot": true,
  "vlm_description": "Shadow DOM button with green background"
}
```

### 2. Better Debugging
Developers can see the actual HTML of shadow DOM/iframe elements in logs, making it easier to:
- Identify elements during replay failures
- Understand element structure
- Debug selector issues

### 3. Enhanced VLM Context
VLM description generation now has access to element HTML even for shadow DOM/iframe elements, improving:
- Description accuracy
- Element identification
- Fallback matching

### 4. Consistent Behavior
All elements are treated consistently regardless of their DOM context, providing:
- Uniform logging
- Predictable debugging experience
- Complete audit trail

## Limitations and Edge Cases

### 1. Cross-Origin iframes
- Cross-origin iframes are skipped due to browser security restrictions
- HTML extraction returns `null` for elements in cross-origin iframes
- This is expected behavior and cannot be bypassed

### 2. Closed Shadow Roots
- Shadow roots with `mode: 'closed'` cannot be accessed
- HTML extraction will return `null` for elements in closed shadow roots
- Most web components use `mode: 'open'`, so this is rare

### 3. Performance Considerations
- Shadow DOM search is recursive and may be slower for deeply nested structures
- iframe search iterates through all iframes on the page
- For pages with many iframes/shadow roots, extraction may take longer
- This is acceptable since it runs asynchronously in the VLM processing thread

### 4. XPath in Shadow DOM
- XPath support in shadow DOM is limited
- The implementation attempts XPath but falls back to recursive search
- CSS selectors are preferred for shadow DOM elements

## Compatibility

### Browser Support
- **Chrome/Chromium**: Full support (our primary target)
- **Firefox**: Should work (not tested)
- **Safari**: Should work (not tested)
- **Edge**: Full support (Chromium-based)

### Selenium Version
- Requires Selenium 4.x for modern Chrome DevTools Protocol support
- Tested with Selenium 4.27.1

## Future Enhancements

### Potential Improvements
1. **Caching**: Cache shadow root/iframe locations to avoid repeated searches
2. **Priority Search**: Search most likely contexts first based on past patterns
3. **Parallel Search**: Search shadow DOM and iframes in parallel
4. **Depth Limiting**: Add max recursion depth for shadow DOM search
5. **Better XPath**: Improve XPath support in shadow DOM contexts

### Integration Opportunities
1. **Element Finder**: Use same logic in activity_executor.py element finding
2. **Screenshot Highlighting**: Enhance highlighting for shadow DOM/iframe elements
3. **Smart Selectors**: Generate better selectors for shadow DOM/iframe elements

## Related Documentation
- `SHADOW_DOM_IFRAME_SUPPORT.md` - Recording implementation
- `EXECUTOR_SHADOW_DOM_IMPLEMENTATION.md` - Replay implementation
- `CLICK_CAPTURE_FIX_SUMMARY.md` - Click capture improvements

## Files Modified
- `main.py` (lines 208-336): Enhanced `get_element_html()` method
- `main.py` (lines 338-347): Updated `trigger_async_vlm_description()` call site

## Files Created
- `tests/test_html_extraction.py`: Comprehensive test suite

## Conclusion
This enhancement completes the shadow DOM and iframe support across the entire system:
1. ✅ **Recording**: Events captured from shadow DOM/iframe (completed earlier)
2. ✅ **Replay**: Elements found in shadow DOM/iframe (completed earlier)
3. ✅ **Extraction**: HTML extracted from shadow DOM/iframe (this implementation)

The system now provides complete support for modern web applications using Web Components and iframes.
