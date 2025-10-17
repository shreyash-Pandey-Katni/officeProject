# Shadow DOM and iframe Support - Implementation Summary

## Problem
The event trackers could not capture clicks and inputs from:
1. **Shadow DOM elements** - Web components using Shadow DOM (e.g., many modern UI frameworks)
2. **iframe elements** - Content inside iframes (same-origin only)

## Root Cause
JavaScript event listeners were only attached to the main `document` object. Shadow DOM and iframes create isolated DOM contexts that don't bubble events to the main document.

## Solution Implemented

### 1. Enhanced Click Tracker (inject_click_tracker)

**Added automatic injection into iframes:**
```javascript
var iframes = document.querySelectorAll('iframe');
for (var i = 0; i < iframes.length; i++) {
    var iframeDoc = iframes[i].contentDocument;
    if (iframeDoc && !iframeDoc._clickTrackerInjected) {
        iframeDoc.addEventListener('click', function(e) {
            // Capture click with inIframe: true flag
        }, true);
        iframeDoc._clickTrackerInjected = true;
    }
}
```

**Added automatic injection into shadow roots:**
```javascript
function injectIntoShadowRoots(root) {
    var elements = root.querySelectorAll('*');
    for (var i = 0; i < elements.length; i++) {
        if (elements[i].shadowRoot && !elements[i].shadowRoot._clickTrackerInjected) {
            shadowRoot.addEventListener('click', function(e) {
                // Capture click with inShadowRoot: true flag
            }, true);
            shadowRoot._clickTrackerInjected = true;
            // Recursively handle nested shadow roots
            injectIntoShadowRoots(shadowRoot);
        }
    }
}
```

### 2. Enhanced Input Tracker (inject_input_tracker)

**Same approach for input events:**
- Injects into all same-origin iframes
- Injects into all shadow roots (including nested)
- Marks contexts as injected to avoid duplicates

### 3. Dynamic Reinjection (reinject_into_dynamic_contexts)

**Handles dynamically added iframes and shadow roots:**
```python
def reinject_into_dynamic_contexts(self):
    """Reinject trackers into dynamically added iframes and shadow roots"""
    # Called periodically in monitor loop
    # Scans for new iframes and shadow roots
    # Injects trackers if not already injected
```

Called in the monitor loop every iteration to catch:
- iframes loaded via AJAX
- Shadow DOMs created dynamically
- New components added after page load

### 4. Context Identification

**Captured events include context flags:**
```python
clickData = {
    'tagName': 'BUTTON',
    'text': 'Click me',
    'inIframe': True,          # If clicked in iframe
    'iframeIndex': 2,          # Which iframe (0-based)
    'inShadowRoot': True,      # If clicked in shadow DOM
    # ... other properties
}
```

**Console logging shows context:**
```
[CLICK] Captured click on BUTTON element (in iframe)
[CLICK] Captured click on BUTTON element (in shadow DOM)
[CLICK] Captured click on BUTTON element
```

## Files Modified

### main.py

**Line 1460-1590 (inject_click_tracker):**
- Added iframe injection loop
- Added shadow root injection with recursive function
- Added context markers

**Line 1698-1900 (inject_input_tracker):**
- Added iframe injection loop
- Added shadow root injection with recursive function  
- Added context markers

**Line 1985-2045 (reinject_into_dynamic_contexts - NEW METHOD):**
- Scans for new iframes and shadow roots
- Reinjects trackers if needed
- Called periodically in monitor loop

**Line 2139 (monitor_activities):**
- Added call to `reinject_into_dynamic_contexts()`
- Runs every iteration before collecting events

**Line 2047-2065 (collect_click_events):**
- Enhanced logging to show context (iframe/shadow DOM)

## Limitations

### 1. Cross-Origin iframes
**Cannot capture events from cross-origin iframes** due to browser security:
```javascript
// This will fail for iframes from different domains
var iframeDoc = iframe.contentDocument; // SecurityError
```

**Example:**
- Main page: `https://example.com`
- iframe: `https://ads.google.com` ❌ Cannot access
- iframe: `https://example.com/widget` ✅ Can access

### 2. Closed Shadow DOM
**Cannot access closed shadow roots:**
```javascript
// Closed shadow root
element.attachShadow({mode: 'closed'});
// element.shadowRoot is null
```

**Workaround:** Most frameworks use open shadow roots by default.

### 3. Performance
**Reinjection has overhead:**
- Scans entire DOM for new shadow roots every iteration
- Could be slow on pages with 1000s of elements
- Consider throttling if performance issues occur

## Testing

### Test File: tests/test_shadow_dom_iframe.py

**Tests:**
1. Regular DOM button clicks ✅
2. Regular DOM input capture ✅
3. Shadow DOM button clicks (requires injection)
4. Shadow DOM input capture (requires injection)
5. iframe button clicks (requires injection)
6. iframe input capture (requires injection)

**Run test:**
```bash
python tests/test_shadow_dom_iframe.py
```

## Usage

### Automatic (No Code Changes Needed)

The recorder now automatically handles shadow DOM and iframes:

```python
from main import BrowserActivityRecorder

driver = webdriver.Chrome()
recorder = BrowserActivityRecorder(driver)

driver.get("https://example.com")  # Page with shadow DOM/iframes
recorder.inject_click_tracker()    # Injects into main + shadow + iframes
recorder.inject_input_tracker()    # Injects into main + shadow + iframes

# Events from all contexts are captured automatically!
```

### Manual Testing

To manually test a specific page:

```python
# Navigate to page with shadow DOM
driver.get("https://some-site-with-web-components.com")

# Inject trackers (automatic shadow DOM/iframe support)
recorder.inject_click_tracker()
recorder.inject_input_tracker()

# Monitor will automatically reinject into new contexts
recorder.monitor_activities()
```

## Debug Output

Look for these messages:

```
[INFO] Click tracker injected into main DOM, iframes, and shadow roots
[INFO] Input tracker injected into main DOM, iframes, and shadow roots
[CLICK] Captured click on BUTTON element (in iframe)
[CLICK] Captured click on DIV element (in shadow DOM)
```

## Known Working Sites

Sites with shadow DOM that should now work:
- Salesforce Lightning (uses shadow DOM extensively)
- Polymer-based applications
- Lit-element applications
- Shoelace UI components
- Fast Foundation components

Sites with iframes that should now work:
- Pages with embedded widgets (same-origin)
- CMS systems with iframe editors
- Dashboards with iframe panels

## Future Improvements

1. **Mutation Observer for iframes/shadow:**
   - Watch for new iframes/shadow roots being added
   - Inject immediately instead of periodic scanning

2. **Better cross-origin handling:**
   - Detect cross-origin iframes
   - Log warning for cross-origin content
   - Provide alternative tracking methods

3. **Performance optimization:**
   - Cache shadow root references
   - Only scan changed DOM subtrees
   - Throttle reinjection on large DOMs

4. **Closed shadow DOM workaround:**
   - Intercept attachShadow calls
   - Force open mode or store references
   - Requires early page injection
