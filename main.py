from selenium import webdriver
from selenium.webdriver.common.by import By
import time
import json
import os
from datetime import datetime
from PIL import Image
from io import BytesIO
from concurrent.futures import ThreadPoolExecutor
import queue
import threading
from llm_helpers import OllamaVLM

# Placeholder for LLM integration
def convert_to_natural_language(activity_log):
    """Placeholder: convert activity logs to natural language (LLM hook)."""
    print("\n=== Activity Log ===")
    for activity in activity_log:
        print(json.dumps(activity, indent=2))

class BrowserActivityRecorder:
    def __init__(self, driver):
        self.driver = driver
        self.activity_log = []
        self.previous_url = ""
        self.previous_title = ""
        self.previous_window_handles = []
        self.element_tracker = {}
        self.use_cdp = False
        self.injection_failed_count = 0
        self.screenshot_counter = 0
        
        # Create screenshots directory
        self.screenshots_dir = "screenshots"
        if not os.path.exists(self.screenshots_dir):
            os.makedirs(self.screenshots_dir)
        
        # Initialize VLM for async description generation
        self.vlm = OllamaVLM(model="granite3.2-vision")
        
        # Async task queue for VLM processing
        self.vlm_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="VLM")
        self.vlm_task_queue = queue.Queue()
        self.vlm_results = {}  # Store VLM results by activity index
        self.vlm_lock = threading.Lock()
        
        # Network monitoring for loading detection
        self.pending_network_requests = 0
        self.network_monitoring_enabled = False
        
        # Try to enable CDP for more reliable tracking
        try:
            self.driver.execute_cdp_cmd('Network.enable', {})
            self.driver.execute_cdp_cmd('Page.enable', {})
            self.use_cdp = True
            self.network_monitoring_enabled = True
            print("[INFO] Chrome DevTools Protocol enabled for enhanced tracking")
        except Exception:
            print("[INFO] CDP not available, using JavaScript injection method")
        
        # Setup DOM mutation observer for loading detection
        self._setup_mutation_observer()
        self._setup_network_tracker()
        
    def record_activity(self, action_type, details):
        """Record an activity with timestamp"""
        activity = {
            "timestamp": datetime.now().isoformat(),
            "action": action_type,
            "details": details
        }

        # Attach window/tab context so replay can properly switch
        try:
            current_handle = self.driver.current_window_handle
            handles = list(self.driver.window_handles)
            activity["window_handle"] = current_handle
            activity["tab_index"] = handles.index(current_handle) if current_handle in handles else 0
            activity["total_tabs"] = len(handles)
        except Exception:
            # If driver context not available, skip adding tab metadata
            pass
        
        # Capture multiple locators for click, input, and hover events (Phase 1 enhancement)
        if action_type in ["click", "text_input", "hover"]:
            locators = self.capture_multiple_locators(details)
            if locators:
                activity["locators"] = locators
        
        # Get activity index before appending
        activity_index = len(self.activity_log)
        self.activity_log.append(activity)
        
        # Capture screenshot & trigger VLM for click and text input events
        if action_type in ["click", "text_input"]:
            screenshot_info = self.capture_screenshot_with_highlight(details)
            if screenshot_info:
                activity["screenshot"] = screenshot_info
                screenshot_path = screenshot_info.get('path')
                if screenshot_path:
                    self.trigger_async_vlm_description(
                        activity_index,
                        screenshot_path,
                        details,
                        action_type
                    )
            # Print concise summary
            if action_type == "click":
                summary = f"Element: {details.get('tagName', 'N/A')}"
                if details.get('id'):
                    summary += f", ID: {details['id']}"
                if details.get('text'):
                    summary += f", Text: {details['text'][:30]}"
                coords = details.get('coordinates', {})
                if coords:
                    summary += f", Position: ({coords.get('clickX', 0):.0f}, {coords.get('clickY', 0):.0f})"
                print(f"[{action_type}] {summary}")
            else:  # text_input
                summary = f"Field: {details.get('tagName', 'N/A')}"
                if details.get('id'):
                    summary += f", ID: {details['id']}"
                elif details.get('name'):
                    summary += f", Name: {details['name']}"
                if details.get('label'):
                    summary += f", Label: {details['label'][:30]}"
                if details.get('value'):
                    value = details['value'][:30] + "..." if len(details['value']) > 30 else details['value']
                    summary += f", Value: {value}"
                print(f"[{action_type}] {summary}")
        elif action_type == "hover":
            # Add a synthesized description for VLM hover fallback
            txt = details.get('text') or details.get('title') or details.get('ariaLabel') or ''
            tag = details.get('tagName','element')
            description_parts = [tag]
            if txt:
                description_parts.append(f"with text '{txt[:60]}'")
            if details.get('id'):
                description_parts.append(f"id '{details['id']}'")
            if details.get('className'):
                # keep only first class token to avoid noise
                first_class = str(details.get('className')).split()[0]
                description_parts.append(f"class '{first_class}'")
            synthesized = ' '.join(description_parts)
            details['vlm_description'] = synthesized  # mutate details so executor receives it
            summary = f"Hover: {synthesized[:100]}"
            print(f"[{action_type}] {summary}")
            # (No screenshot captured for hover events)
    
    def capture_multiple_locators(self, element_details):
        """Return a dictionary of multiple locator strategies for robust replay."""
        locators = {}
        try:
            if element_details.get('id'):
                locators['id'] = element_details['id']
            if element_details.get('name'):
                locators['name'] = element_details['name']
            if element_details.get('className'):
                locators['class'] = element_details['className']
            if element_details.get('tagName'):
                locators['tag_name'] = element_details['tagName']
            if element_details.get('text'):
                locators['text'] = element_details['text'][:100]
            if element_details.get('placeholder'):
                locators['placeholder'] = element_details['placeholder']
            if element_details.get('type'):
                locators['type'] = element_details['type']
            if element_details.get('ariaLabel'):
                locators['aria_label'] = element_details['ariaLabel']
            if element_details.get('value'):
                locators['value'] = element_details['value']
            if element_details.get('cssSelector'):
                locators['css_selector'] = element_details['cssSelector']
            if element_details.get('xpath'):
                locators['xpath'] = element_details['xpath']
            coords = element_details.get('coordinates', {})
            if coords and all(k in coords for k in ['clickX', 'clickY', 'width', 'height']):
                locators['coordinates'] = {
                    'x': coords['clickX'],
                    'y': coords['clickY'],
                    'width': coords['width'],
                    'height': coords['height']
                }
            if element_details.get('inShadowRoot'):
                locators['in_shadow_root'] = True
            if element_details.get('inIframe'):
                locators['in_iframe'] = True
            if element_details.get('label'):
                locators['label'] = element_details['label']
        except Exception as e:
            print(f"[WARNING] Error capturing locators: {e}")
        return locators
    
    def capture_screenshot_with_highlight(self, details):
        """Capture screenshot and highlight the element"""
        try:
            self.screenshot_counter += 1
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            screenshot_filename = f"screenshot_{self.screenshot_counter}_{timestamp}.png"
            screenshot_path = os.path.join(self.screenshots_dir, screenshot_filename)
            
            # Capture full page screenshot
            screenshot_png = self.driver.get_screenshot_as_png()
            
            # Get element coordinates from details
            coords = details.get('coordinates', {})
            if coords:
                # Open image with PIL
                image = Image.open(BytesIO(screenshot_png))
                
                # Add visual marker for VLM focus (optional but helpful)
                from PIL import ImageDraw
                draw = ImageDraw.Draw(image)
                
                # Get element bounds
                left = coords.get('elementLeft', 0)
                top = coords.get('elementTop', 0)
                width = coords.get('elementWidth', 0)
                height = coords.get('elementHeight', 0)
                
                # Draw red bounding box around element
                if left > 0 and top > 0 and width > 0 and height > 0:
                    # Draw rectangle
                    draw.rectangle(
                        [(left, top), (left + width, top + height)],
                        outline='red',
                        width=3
                    )
                    
                    # Draw center crosshair
                    center_x = coords.get('elementCenterX', left + width/2)
                    center_y = coords.get('elementCenterY', top + height/2)
                    crosshair_size = 10
                    draw.line(
                        [(center_x - crosshair_size, center_y), (center_x + crosshair_size, center_y)],
                        fill='red',
                        width=2
                    )
                    draw.line(
                        [(center_x, center_y - crosshair_size), (center_x, center_y + crosshair_size)],
                        fill='red',
                        width=2
                    )
                
                # Save the highlighted screenshot
                image.save(screenshot_path)
                
                # Return screenshot metadata
                return {
                    "filename": screenshot_filename,
                    "path": screenshot_path,
                    "element_bounds": {
                        "left": coords.get('elementLeft', 0),
                        "top": coords.get('elementTop', 0),
                        "width": coords.get('elementWidth', 0),
                        "height": coords.get('elementHeight', 0)
                    },
                    "viewport_size": {
                        "width": coords.get('viewportWidth', 0),
                        "height": coords.get('viewportHeight', 0)
                    }
                }
            else:
                # No coordinates, just save screenshot
                image = Image.open(BytesIO(screenshot_png))
                image.save(screenshot_path)
                return {
                    "filename": screenshot_filename,
                    "path": screenshot_path
                }
        except Exception as e:
            print(f"[WARNING] Screenshot capture failed: {str(e)[:100]}")
            return None
    
    def get_element_html(self, xpath=None, css_selector=None, in_shadow_root=False, in_iframe=False):
        """Get the full HTML of a specific element, including shadow DOM and iframe contexts"""
        try:
            # Generate the appropriate JavaScript code based on context
            if in_shadow_root:
                # Search in shadow DOM recursively
                if css_selector:
                    js_code = f"""
                    // Recursive shadow DOM search for CSS selector
                    function findInShadowDOM(root, selector) {{
                        // Try to find in current root
                        let element = root.querySelector(selector);
                        if (element) return element;
                        
                        // Search in all shadow roots
                        let allElements = root.querySelectorAll('*');
                        for (let el of allElements) {{
                            if (el.shadowRoot) {{
                                element = findInShadowDOM(el.shadowRoot, selector);
                                if (element) return element;
                            }}
                        }}
                        return null;
                    }}
                    
                    let element = findInShadowDOM(document, "{css_selector}");
                    return element ? element.outerHTML : null;
                    """
                elif xpath:
                    # XPath in shadow DOM is more complex - convert to attributes
                    js_code = f"""
                    // Recursive shadow DOM search for XPath attributes
                    function findInShadowDOM(root) {{
                        // Try to find in current root using XPath
                        try {{
                            let result = document.evaluate("{xpath}", root, null, XPathResult.FIRST_ORDERED_NODE_TYPE, null);
                            if (result && result.singleNodeValue) return result.singleNodeValue;
                        }} catch (e) {{
                            // XPath might not work in shadow root, try alternative
                        }}
                        
                        // Search in all shadow roots
                        let allElements = root.querySelectorAll('*');
                        for (let el of allElements) {{
                            if (el.shadowRoot) {{
                                let element = findInShadowDOM(el.shadowRoot);
                                if (element) return element;
                            }}
                        }}
                        return null;
                    }}
                    
                    let element = findInShadowDOM(document);
                    return element ? element.outerHTML : null;
                    """
                else:
                    return None
                    
            elif in_iframe:
                # Search in iframes
                if css_selector:
                    js_code = f"""
                    // Search in all iframes for CSS selector
                    function findInIframes(selector) {{
                        // Try main document first
                        let element = document.querySelector(selector);
                        if (element) return element.outerHTML;
                        
                        // Search in all iframes
                        let iframes = document.querySelectorAll('iframe');
                        for (let iframe of iframes) {{
                            try {{
                                let iframeDoc = iframe.contentDocument || iframe.contentWindow.document;
                                element = iframeDoc.querySelector(selector);
                                if (element) return element.outerHTML;
                            }} catch (e) {{
                                // Cross-origin iframe, skip
                                console.log('Cross-origin iframe, skipping');
                            }}
                        }}
                        return null;
                    }}
                    
                    return findInIframes("{css_selector}");
                    """
                elif xpath:
                    js_code = f"""
                    // Search in all iframes for XPath
                    function findInIframes(xpath) {{
                        // Try main document first
                        try {{
                            let result = document.evaluate(xpath, document, null, XPathResult.FIRST_ORDERED_NODE_TYPE, null);
                            if (result && result.singleNodeValue) return result.singleNodeValue.outerHTML;
                        }} catch (e) {{
                            console.log('XPath error in main document:', e);
                        }}
                        
                        // Search in all iframes
                        let iframes = document.querySelectorAll('iframe');
                        for (let iframe of iframes) {{
                            try {{
                                let iframeDoc = iframe.contentDocument || iframe.contentWindow.document;
                                let result = iframeDoc.evaluate(xpath, iframeDoc, null, XPathResult.FIRST_ORDERED_NODE_TYPE, null);
                                if (result && result.singleNodeValue) return result.singleNodeValue.outerHTML;
                            }} catch (e) {{
                                // Cross-origin iframe or XPath error, skip
                                console.log('Error in iframe:', e);
                            }}
                        }}
                        return null;
                    }}
                    
                    return findInIframes("{xpath}");
                    """
                else:
                    return None
                    
            else:
                # Regular DOM search (existing logic)
                if xpath:
                    js_code = f"""
                    var element = document.evaluate("{xpath}", document, null, XPathResult.FIRST_ORDERED_NODE_TYPE, null).singleNodeValue;
                    return element ? element.outerHTML : null;
                    """
                elif css_selector:
                    js_code = f"""
                    var element = document.querySelector("{css_selector}");
                    return element ? element.outerHTML : null;
                    """
                else:
                    return None
            
            element_html = self.driver.execute_script(js_code)
            return element_html if element_html else None
            
        except Exception as e:
            print(f"[WARNING] Failed to extract element HTML: {e}")
            return None
    
    def _process_vlm_description(self, activity_index, screenshot_path, element_html, coordinates, event_type):
        """Process VLM description generation (runs in background thread)"""
        try:
            # Generate VLM description
            description = self.vlm.generate_element_description(
                image_path=screenshot_path,
                element_html=element_html or "HTML not available",
                coordinates=coordinates,
                event_type=event_type
            )
            
            # Store result
            with self.vlm_lock:
                self.vlm_results[activity_index] = {
                    'vlm_description': description,
                    'element_html': element_html,
                    'processing_completed': True
                }
                
        except Exception as e:
            print(f"[ERROR] VLM processing failed for activity {activity_index}: {e}")
            with self.vlm_lock:
                self.vlm_results[activity_index] = {
                    'vlm_description': f"VLM processing failed: {str(e)}",
                    'element_html': element_html,
                    'processing_completed': False
                }
    
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
        
        # Get coordinates
        coordinates = details.get('coordinates', {})
        
        # Submit to thread pool
        # Fire-and-forget; joined later during finalize_vlm_processing
        _vlm_future = self.vlm_executor.submit(
            self._process_vlm_description,
            activity_index,
            screenshot_path,
            element_html,
            coordinates,
            event_type
        )
        
        print(f"[VLM] Queued description generation for activity {activity_index}")
        
    def finalize_vlm_processing(self):
        """Wait for all VLM tasks to complete and update activity log"""
        print("\n[VLM] Waiting for async description generation to complete...")
        
        # Shutdown executor and wait for all tasks
        self.vlm_executor.shutdown(wait=True)
        
        # Update activity log with VLM results
        with self.vlm_lock:
            for activity_index, vlm_data in self.vlm_results.items():
                if activity_index < len(self.activity_log):
                    self.activity_log[activity_index]['vlm_description'] = vlm_data.get('vlm_description', '')
                    self.activity_log[activity_index]['element_html'] = vlm_data.get('element_html', '')
        
        print(f"[VLM] Completed {len(self.vlm_results)} descriptions")
    
    def optimize_activity_log(self):
        """
        Use VLM to optimize activity log by consolidating sequential actions
        - Merge sequential typing in same field into single action with final value
        - Remove redundant clicks on same element
        - Keep only meaningful navigation changes
        """
        print("\n[OPTIMIZER] Analyzing activity log for optimization...")
        original_count = len(self.activity_log)
        
        if original_count == 0:
            return
        
        optimized_log = []
        i = 0
        
        while i < len(self.activity_log):
            current = self.activity_log[i]
            action = current.get('action', '')
            
            # Handle text input consolidation
            if action == 'text_input':
                consolidated = self._consolidate_text_inputs(i)
                if consolidated:
                    optimized_log.append(consolidated['activity'])
                    i = consolidated['end_index'] + 1
                    print(f"[OPTIMIZER] Consolidated {consolidated['merged_count']} typing actions into 1")
                    continue
            
            # Handle click deduplication
            elif action == 'click':
                if self._is_redundant_click(i, optimized_log):
                    print(f"[OPTIMIZER] Removed redundant click at index {i}")
                    i += 1
                    continue
            
            # Keep all other actions (navigation, etc.)
            optimized_log.append(current)
            i += 1
        
        # Update activity log
        self.activity_log = optimized_log
        removed_count = original_count - len(optimized_log)
        
        print(f"[OPTIMIZER] ✓ Optimization complete:")
        print(f"[OPTIMIZER]   Original: {original_count} activities")
        print(f"[OPTIMIZER]   Optimized: {len(optimized_log)} activities")
        print(f"[OPTIMIZER]   Removed: {removed_count} redundant activities ({removed_count/original_count*100:.1f}%)")
    
    def _consolidate_text_inputs(self, start_index):
        """
        Consolidate sequential text inputs into the same field
        Returns: {activity, end_index, merged_count} or None
        """
        if start_index >= len(self.activity_log):
            return None
        
        first_activity = self.activity_log[start_index]
        first_details = first_activity.get('details', {})
        
        # Get field identifier (xpath, id, or name)
        field_xpath = first_details.get('xpath', '')
        field_id = first_details.get('id', '')
        field_name = first_details.get('name', '')
        
        if not (field_xpath or field_id or field_name):
            return None
        
        # Find all consecutive text inputs to the same field
        merged_activities = [first_activity]
        j = start_index + 1
        
        while j < len(self.activity_log):
            next_activity = self.activity_log[j]
            next_action = next_activity.get('action', '')
            
            # Stop if not a text input
            if next_action != 'text_input':
                break
            
            next_details = next_activity.get('details', {})
            
            # Check if same field
            same_field = False
            if field_xpath and next_details.get('xpath') == field_xpath:
                same_field = True
            elif field_id and next_details.get('id') == field_id:
                same_field = True
            elif field_name and next_details.get('name') == field_name:
                same_field = True
            
            if not same_field:
                break
            
            merged_activities.append(next_activity)
            j += 1
        
        # If only one activity, no consolidation needed
        if len(merged_activities) == 1:
            return None
        
        # Get final value from last activity
        last_activity = merged_activities[-1]
        final_value = last_activity.get('details', {}).get('value', '')
        
        # Create consolidated activity using last activity as base
        consolidated_activity = last_activity.copy()
        
        # Update value to show it was consolidated
        consolidated_details = consolidated_activity.get('details', {}).copy()
        consolidated_details['value'] = final_value
        consolidated_details['consolidated_from'] = len(merged_activities)
        consolidated_activity['details'] = consolidated_details
        
        # Keep the VLM description and screenshot from the last action
        # (most accurate representation of final state)
        
        return {
            'activity': consolidated_activity,
            'end_index': j - 1,
            'merged_count': len(merged_activities)
        }
    
    def _is_redundant_click(self, current_index, optimized_log):
        """
        Check if a click is redundant (clicking same element multiple times)
        """
        if not optimized_log:
            return False
        
        current = self.activity_log[current_index]
        current_details = current.get('details', {})
        
        # Look at last few activities in optimized log
        for prev_activity in reversed(optimized_log[-3:]):
            if prev_activity.get('action') != 'click':
                continue
            
            prev_details = prev_activity.get('details', {})
            
            # Check if same element by comparing identifiers
            same_element = False
            
            # Compare by xpath
            if current_details.get('xpath') and current_details.get('xpath') == prev_details.get('xpath'):
                same_element = True
            # Compare by id
            elif current_details.get('id') and current_details.get('id') == prev_details.get('id'):
                same_element = True
            # Compare by coordinates (within tolerance)
            elif self._same_coordinates(current_details.get('coordinates', {}), 
                                       prev_details.get('coordinates', {})):
                same_element = True
            
            if same_element:
                # Check if clicks are close in time (within 2 seconds)
                current_time = current.get('timestamp', '')
                prev_time = prev_activity.get('timestamp', '')
                
                try:
                    current_dt = datetime.fromisoformat(current_time)
                    prev_dt = datetime.fromisoformat(prev_time)
                    time_diff = (current_dt - prev_dt).total_seconds()
                    
                    if time_diff < 2:  # Clicks within 2 seconds
                        return True  # Redundant
                except Exception:
                    pass
        
        return False
    
    def _same_coordinates(self, coords1, coords2, tolerance=10):
        """Check if two sets of coordinates are the same (within tolerance)"""
        if not coords1 or not coords2:
            return False
        
        x1 = coords1.get('elementCenterX', 0)
        y1 = coords1.get('elementCenterY', 0)
        x2 = coords2.get('elementCenterX', 0)
        y2 = coords2.get('elementCenterY', 0)
        
        if x1 == 0 or y1 == 0 or x2 == 0 or y2 == 0:
            return False
        
        return abs(x1 - x2) <= tolerance and abs(y1 - y2) <= tolerance
        
    def track_navigation(self):
        """Track URL changes"""
        current_url = self.driver.current_url
        current_title = self.driver.title
        
        if current_url != self.previous_url:
            self.record_activity("navigation", {
                "url": current_url,
                "title": current_title,
                "previous_url": self.previous_url
            })
            self.previous_url = current_url
            self.previous_title = current_title
            
            # Return True to indicate page changed (need to re-inject)
            return True
        return False
            
    def track_tab_switching(self):
        """Track tab/window switching"""
        # Initialization
        if not hasattr(self, 'tab_metadata'):
            self.tab_metadata = {}
        if not hasattr(self, 'previous_handle'):
            try:
                self.previous_handle = self.driver.current_window_handle
            except Exception:
                self.previous_handle = None
        if not self.previous_window_handles:
            try:
                self.previous_window_handles = list(self.driver.window_handles)
            except Exception:
                self.previous_window_handles = []

        try:
            current_handles = list(self.driver.window_handles)
        except Exception:
            return False

        switched = False

        # Detect added/removed tabs without switching context (avoid forcing focus)
        if current_handles != self.previous_window_handles:
            added = [h for h in current_handles if h not in self.previous_window_handles]
            removed = [h for h in self.previous_window_handles if h not in current_handles]

            for h in added:
                # Don't switch; metadata will be enriched on first activation
                self.tab_metadata[h] = {"first_title": None, "first_url": None, "created_at": datetime.now().isoformat()}
                self.record_activity("new_tab", {
                    "handle": h,
                    "title": None,
                    "url": None,
                    "total_tabs": len(current_handles)
                })
            for h in removed:
                self.record_activity("tab_closed", {"handle": h, "total_tabs": len(current_handles)})
                if h in self.tab_metadata:
                    del self.tab_metadata[h]
            self.previous_window_handles = current_handles.copy()

        # Current active handle as reported by driver
        try:
            current_handle = self.driver.current_window_handle
        except Exception:
            current_handle = None

        # If no change, nothing to do
        if current_handle is None or current_handle == self.previous_handle:
            return False

        # Update metadata for newly active tab
        try:
            cur_title = self.driver.title
            cur_url = self.driver.current_url
        except Exception:
            cur_title = ""
            cur_url = ""
        if current_handle in self.tab_metadata:
            meta = self.tab_metadata[current_handle]
            if meta.get('first_title') is None:
                meta['first_title'] = cur_title
            if meta.get('first_url') is None:
                meta['first_url'] = cur_url
        else:
            self.tab_metadata[current_handle] = {"first_title": cur_title, "first_url": cur_url, "created_at": datetime.now().isoformat()}

        # Record switch
        self.record_activity("switch_tab", {
            "from_window": self.previous_handle,
            "to_window": current_handle,
            "title": cur_title,
            "url": cur_url,
            "pattern": cur_title[:80],
            "match_type": "title",
            "use_regex": False
        })
        switched = True

        # Re-inject trackers in the now-active context (safe; no tab iteration)
        try:
            self.inject_click_tracker()
            self.inject_input_tracker()
        except Exception as reinject_err:
            print(f"[TAB] Reinjection failed after switch: {reinject_err}")

        self.previous_handle = current_handle
        return switched
            
    def is_page_loading(self):
        """
        Enhanced page loading detection with network monitoring and DOM mutations
        Combines multiple detection methods for accuracy
        Returns: (is_loading: bool, reason: str)
        """
        try:
            # Check 1: Document ready state (1ms)
            doc_state = self.driver.execute_script("return document.readyState;")
            if doc_state != "complete":
                return True, f"document.readyState = '{doc_state}'"
            
            # Check 2: Network activity monitoring (5ms) - COMMENTED OUT
            # network_reason = self._check_network_activity()
            # if network_reason:
            #     return True, network_reason
            
            # Check 3: DOM mutations (10ms)
            mutation_reason = self._check_dom_mutations()
            if mutation_reason:
                return True, mutation_reason
            
            # Check 4: Visual loaders and animations (50ms)
            loader_reason = self._check_visual_loaders()
            if loader_reason:
                return True, loader_reason
            
            # Check 5: Framework-specific checks (5ms)
            framework_reason = self._check_framework_loading()
            if framework_reason:
                return True, framework_reason
            
            # All checks passed - page is ready
            return False, "All checks passed"
            
        except Exception as e:
            # On error, assume loading (safe default)
            return True, f"Check error: {str(e)}"
    
    def _setup_mutation_observer(self):
        """
        Setup MutationObserver to track DOM changes
        Called once during initialization
        """
        try:
            self.driver.execute_script("""
                if (!window._loadingObserver) {
                    window._mutationCount = 0;
                    window._lastMutationTime = Date.now();
                    
                    window._loadingObserver = new MutationObserver((mutations) => {
                        // Filter out trivial mutations
                        let significantMutations = mutations.filter(m => {
                            // Ignore style/class changes unless significant
                            if (m.type === 'attributes') {
                                return m.attributeName === 'class' && 
                                       (m.target.className.includes('loading') || 
                                        m.target.className.includes('skeleton'));
                            }
                            return true;
                        });
                        
                        window._mutationCount += significantMutations.length;
                        window._lastMutationTime = Date.now();
                    });
                    
                    // Observe document body for changes
                    window._loadingObserver.observe(document.body, {
                        childList: true,
                        subtree: true,
                        attributes: true,
                        attributeFilter: ['class', 'style', 'hidden']
                    });
                    
                    console.log('[MUTATION] Observer initialized');
                }
            """)
        except Exception as e:
            print(f"[WARNING] Could not setup mutation observer: {e}")
    
    def _setup_network_tracker(self):
        """
        Setup JavaScript-based network request tracking
        Tracks fetch and XMLHttpRequest
        """
        try:
            self.driver.execute_script("""
                if (!window._networkTracker) {
                    window._networkTracker = {
                        pendingRequests: 0,
                        lastRequestTime: 0
                    };
                    
                    // Track fetch requests
                    const originalFetch = window.fetch;
                    window.fetch = function(...args) {
                        window._networkTracker.pendingRequests++;
                        window._networkTracker.lastRequestTime = Date.now();
                        
                        return originalFetch.apply(this, args)
                            .then(response => {
                                window._networkTracker.pendingRequests--;
                                return response;
                            })
                            .catch(error => {
                                window._networkTracker.pendingRequests--;
                                throw error;
                            });
                    };
                    
                    // Track XMLHttpRequest
                    const originalOpen = XMLHttpRequest.prototype.open;
                    const originalSend = XMLHttpRequest.prototype.send;
                    
                    XMLHttpRequest.prototype.open = function(...args) {
                        this._tracked = true;
                        return originalOpen.apply(this, args);
                    };
                    
                    XMLHttpRequest.prototype.send = function(...args) {
                        if (this._tracked) {
                            window._networkTracker.pendingRequests++;
                            window._networkTracker.lastRequestTime = Date.now();
                            
                            this.addEventListener('loadend', () => {
                                window._networkTracker.pendingRequests--;
                            });
                        }
                        return originalSend.apply(this, args);
                    };
                    
                    console.log('[NETWORK] Tracker initialized');
                }
            """)
        except Exception as e:
            print(f"[WARNING] Could not setup network tracker: {e}")
    
    def _check_network_activity(self):
        """
        Check if there are active network requests
        Uses both JavaScript tracker and Performance API
        Returns: reason string if active, None if not active
        """
        try:
            result = self.driver.execute_script("""
                let reasons = [];
                
                // Check JavaScript tracker
                if (window._networkTracker && window._networkTracker.pendingRequests > 0) {
                    reasons.push('Active fetch/XHR: ' + window._networkTracker.pendingRequests);
                }
                
                // Check Performance API for in-progress requests
                let inProgress = window.performance.getEntriesByType('resource')
                    .filter(r => r.duration === 0 || (performance.now() - r.startTime) < 100);
                
                if (inProgress.length > 0) {
                    reasons.push('Resources loading: ' + inProgress.length);
                }
                
                // Check jQuery if present
                if (window.jQuery && jQuery.active > 0) {
                    reasons.push('jQuery.active: ' + jQuery.active);
                }
                
                return reasons.length > 0 ? reasons.join(', ') : null;
            """)
            
            if result:
                return f"Network activity - {result}"
                
            return None
            
        except Exception:
            return None
    
    def _check_dom_mutations(self):
        """
        Check if DOM is actively mutating
        Indicates dynamic content loading
        Returns: reason string if mutating, None if not
        """
        try:
            result = self.driver.execute_script("""
                if (!window._loadingObserver) return null;
                
                let now = Date.now();
                let timeSinceLastMutation = now - window._lastMutationTime;
                let recentMutations = window._mutationCount;
                
                // Reset counter for next check
                window._mutationCount = 0;
                
                // More lenient thresholds to avoid pausing after click-triggered DOM changes
                // Only consider loading if:
                // 1. Very recent mutations (< 150ms) AND many mutations (> 10)
                // 2. OR sustained heavy mutations (> 20 changes)
                if (timeSinceLastMutation < 150 && recentMutations > 10) {
                    return 'DOM mutations ' + timeSinceLastMutation + 'ms ago (' + recentMutations + ' changes)';
                }
                if (recentMutations > 20) {
                    return 'Heavy DOM mutations: ' + recentMutations + ' changes';
                }
                
                return null;
            """)
            
            return result
            
        except Exception:
            return None
    
    def _check_visual_loaders(self):
        """
        Check for common visual loading indicators using JavaScript
        Much faster than VLM analysis
        Returns: reason string if loaders found, None if not
        """
        try:
            result = self.driver.execute_script("""
                let found = [];
                
                // Helper function to check if element is truly visible
                function isElementVisible(el) {
                    // Must have dimensions
                    if (el.offsetWidth <= 0 || el.offsetHeight <= 0) {
                        return false;
                    }
                    
                    // Must be in document and have offsetParent (not display:none)
                    if (!el.offsetParent && el.tagName !== 'BODY' && el.tagName !== 'HTML') {
                        return false;
                    }
                    
                    // Check computed style
                    let style = window.getComputedStyle(el);
                    
                    // Display check
                    if (style.display === 'none') {
                        return false;
                    }
                    
                    // Visibility check
                    if (style.visibility === 'hidden' || style.visibility === 'collapse') {
                        return false;
                    }
                    
                    // Opacity check - consider < 0.1 as invisible
                    let opacity = parseFloat(style.opacity);
                    if (opacity < 0.1) {
                        return false;
                    }
                    
                    // Check if element is in viewport or at least rendered
                    let rect = el.getBoundingClientRect();
                    if (rect.width === 0 || rect.height === 0) {
                        return false;
                    }
                    
                    // Check if element is off-screen (negative positioning)
                    if (rect.right < 0 || rect.bottom < 0) {
                        return false;
                    }
                    
                    // Check for clip-path or clip that hides the element
                    if (style.clip && style.clip !== 'auto' && style.clip.includes('rect(0')) {
                        return false;
                    }
                    
                    // Check ALL parent elements up to body/html for hidden properties
                    let parent = el.parentElement;
                    while (parent && parent.tagName !== 'BODY' && parent.tagName !== 'HTML') {
                        let parentStyle = window.getComputedStyle(parent);
                        
                        // Check if parent is hidden in any way
                        if (parentStyle.display === 'none') {
                            return false;
                        }
                        
                        if (parentStyle.visibility === 'hidden' || parentStyle.visibility === 'collapse') {
                            return false;
                        }
                        
                        let parentOpacity = parseFloat(parentStyle.opacity);
                        if (parentOpacity < 0.1) {
                            return false;
                        }
                        
                        // Check if parent has zero dimensions (collapsed)
                        if (parent.offsetWidth === 0 || parent.offsetHeight === 0) {
                            return false;
                        }
                        
                        parent = parent.parentElement;
                    }
                    
                    return true;
                }
                
                // Check for common loading class names
                const loadingClasses = [
                    'loading', 'spinner', 'loader', 'skeleton',
                    'shimmer', 'progress', 'loading-overlay', 'preloader'
                ];
                
                for (let cls of loadingClasses) {
                    let elements = document.querySelectorAll(`[class*="${cls}"]`);
                    for (let el of elements) {
                        if (isElementVisible(el)) {
                            found.push('[class*="' + cls + '"]');
                            break;
                        }
                    }
                }
                
                // Check for loading text
                let bodyText = document.body.innerText || '';
                if (/loading|please wait|processing|cargando/i.test(bodyText)) {
                    // Make sure it's visible and not just in hidden elements
                    let walker = document.createTreeWalker(
                        document.body,
                        NodeFilter.SHOW_TEXT,
                        null
                    );
                    
                    while (walker.nextNode()) {
                        let node = walker.currentNode;
                        if (/loading|please wait|processing/i.test(node.textContent)) {
                            let parent = node.parentElement;
                            if (parent && isElementVisible(parent)) {
                                found.push('Loading text');
                                break;
                            }
                        }
                    }
                }
                
                // Check for progress bars
                let progressBars = document.querySelectorAll('progress, [role="progressbar"]');
                for (let bar of progressBars) {
                    if (isElementVisible(bar)) {
                        found.push('Progress bar');
                        break;
                    }
                }
                
                // Check for CSS animations (spinners) - only check common loading elements
                let loadingSelectors = [
                    '[class*="loading"]', '[class*="spinner"]', '[class*="loader"]',
                    '[class*="rotating"]', '[class*="spinning"]'
                ];
                
                for (let selector of loadingSelectors) {
                    let elements = document.querySelectorAll(selector);
                    for (let el of elements) {
                        if (!isElementVisible(el)) continue;
                        
                        let style = window.getComputedStyle(el);
                        if (style.animation && style.animation !== 'none') {
                            // Check if animation looks like a loader (rotating, spinning)
                            if (/rotate|spin|pulse|bounce/i.test(style.animation)) {
                                found.push('CSS animation');
                                break;
                            }
                        }
                    }
                    if (found.includes('CSS animation')) break;
                }
                
                return found.length > 0 ? found.join(', ') : null;
            """)
            
            if result:
                return f"Visible loaders: {result}"
            
            return None
            
        except Exception:
            return None
    
    def _check_framework_loading(self):
        """
        Check loading state for popular JavaScript frameworks
        Returns: reason string if loading detected, None if not
        """
        try:
            result = self.driver.execute_script("""
                let found = [];
                
                // Angular
                if (window.getAllAngularRootElements) {
                    try {
                        let roots = window.getAllAngularRootElements();
                        if (roots && roots.length > 0) {
                            let ngApp = roots[0];
                            // Check for Angular loading indicators
                            if (ngApp.querySelector('[ng-if*="loading"]') ||
                                ngApp.querySelector('[ng-show*="loading"]')) {
                                found.push('Angular loading');
                            }
                        }
                    } catch(e) {}
                }
                
                // Vue (check for v-loading directive)
                if (window.__VUE__) {
                    let vLoading = document.querySelector('[v-loading="true"]');
                    if (vLoading) found.push('Vue v-loading');
                }
                
                // React (check for common loading components)
                let reactLoading = document.querySelector('[data-testid*="loading"], [class*="Loading"]');
                if (reactLoading && reactLoading.offsetParent !== null) {
                    found.push('React loading component');
                }
                
                // jQuery AJAX
                if (window.jQuery && jQuery.active > 0) {
                    found.push('jQuery.active: ' + jQuery.active);
                }
                
                return found.length > 0 ? found.join(', ') : null;
            """)
            
            if result:
                return f"Framework loading - {result}"
            
            return None
            
        except Exception:
            return None
    
    def get_loading_details(self):
        """
        Get detailed information about what's causing loading state
        Useful for debugging
        """
        details = {
            'document_ready': False,
            'network_activity': False,
            'dom_mutations': False,            # bool
            'dom_mutations_reason': '',        # textual reason
            'visual_loaders': False,           # bool
            'visual_loaders_reason': '',       # textual reason
            'framework_loading': False,        # bool
            'framework_loading_reason': '',    # textual reason
            'overall_loading': False,
            'error': ''
        }
        
        try:
            # Check each component
            doc_state = self.driver.execute_script("return document.readyState;")
            details['document_ready'] = (doc_state == "complete")
            # details['network_activity'] = self._check_network_activity()  # COMMENTED OUT
            details['network_activity'] = False  # Always false (network check disabled)
            dom_mut = self._check_dom_mutations()
            details['dom_mutations'] = bool(dom_mut)
            details['dom_mutations_reason'] = dom_mut or ''

            vis_load = self._check_visual_loaders()
            details['visual_loaders'] = bool(vis_load)
            details['visual_loaders_reason'] = vis_load or ''

            fw_load = self._check_framework_loading()
            details['framework_loading'] = bool(fw_load)
            details['framework_loading_reason'] = fw_load or ''
            
            # Overall status
            details['overall_loading'] = (
                not details['document_ready'] or
                # details['network_activity'] or  # COMMENTED OUT
                details['dom_mutations'] or
                details['visual_loaders'] or
                details['framework_loading']
            )
            
        except Exception as e:
            details['error'] = str(e)
        
        return details
    
    def check_and_handle_popup(self):
        """
        Detect and handle browser pop-ups (alert, confirm, prompt)
        Returns: True if popup was handled, False otherwise
        """
        try:
            # Check for alert/confirm/prompt
            alert = self.driver.switch_to.alert
            
            # Get alert details
            alert_text = alert.text
            alert_type = self._detect_alert_type(alert)
            
            print(f"[POPUP] Detected {alert_type}: {alert_text[:50]}...")
            
            # Capture screenshot before handling
            screenshot_info = None
            try:
                self.screenshot_counter += 1
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                screenshot_filename = f"popup_{self.screenshot_counter}_{timestamp}.png"
                screenshot_path = os.path.join(self.screenshots_dir, screenshot_filename)
                self.driver.save_screenshot(screenshot_path)
                screenshot_info = {"filename": screenshot_filename, "path": screenshot_path}
            except Exception:
                print("[POPUP] Failed capturing popup screenshot")
            
            # Record the popup
            popup_details = {
                "type": alert_type,
                "text": alert_text,
                "action": "accept",  # Default action
                "input_value": None
            }
            
            # Handle based on type
            if alert_type == "prompt":
                # For prompt, we'll accept with empty string
                # In future, could use VLM to determine appropriate input
                try:
                    alert.send_keys("")  # Send empty or default value
                    popup_details["input_value"] = ""
                except Exception:
                    print("[POPUP] Prompt input send failed")
            
            # Accept the alert/confirm/prompt
            alert.accept()
            popup_details["action"] = "accept"
            
            # Record activity
            self.record_activity("popup_handled", popup_details)
            
            if screenshot_info:
                self.activity_log[-1]["screenshot"] = screenshot_info
            
            print(f"[POPUP] Handled {alert_type} by accepting")
            return True
            
        except Exception as e:
            # No alert present or error handling it
            error_str = str(e).lower()
            if "no such alert" not in error_str and "no alert is present" not in error_str:
                # Real error, not just "no alert"
                pass
            return False
    
    def _detect_alert_type(self, alert):
        """
        Detect if alert is alert, confirm, or prompt
        This is tricky as Selenium doesn't directly expose the type
        """
        try:
            # Try to send keys - only prompts accept input
            alert.send_keys("")
            return "prompt"
        except Exception:
            return "confirm"
    
    def check_modal_dialogs(self):
        """
        Detect custom modal dialogs (non-native popups) and automatically click buttons
        These are HTML/CSS modals, not browser alerts
        """
        try:
            # Common modal patterns
            modal_selectors = [
                "[role='dialog']",
                ".modal.show",
                ".modal.in",
                ".popup-overlay",
                ".dialog-overlay",
                "[aria-modal='true']",
                ".sweet-alert",
                ".swal2-container",
                ".dialog",
                ".popup"
            ]
            
            for selector in modal_selectors:
                try:
                    modals = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    for modal in modals:
                        if modal.is_displayed():
                            print(f"[MODAL] Detected custom modal dialog with selector: {selector}")
                            
                            # Try to find and click a button automatically
                            button_clicked = self._find_and_click_dialog_button(modal, selector)
                            
                            if button_clicked:
                                return True
                            else:
                                # Just record detection if no button found
                                self._record_modal_detection(modal, selector)
                                return True
                except Exception:
                    continue
            
            return False
            
        except Exception:
            return False
    
    def _find_and_click_dialog_button(self, modal, modal_selector):
        """
        Find and click dialog buttons automatically based on text or position
        Returns: True if button was clicked, False otherwise
        """
        try:
            # Common button text patterns (priority order)
            button_texts = [
                'OK', 'Ok', 'okay', 'Okay',
                'Close', 'close', 
                'Confirm', 'confirm',
                'Accept', 'accept',
                'Yes', 'yes',
                'Continue', 'continue',
                'Submit', 'submit',
                'Got it', 'got it',
                'Dismiss', 'dismiss',
                'Cancel', 'cancel',
                'No', 'no'
            ]
            
            # Common button selectors
            button_selectors = [
                'button',
                '[role="button"]',
                'a.btn',
                'a.button',
                '.btn',
                '.button',
                'input[type="button"]',
                'input[type="submit"]',
                '[data-dismiss="modal"]',
                '.modal-close',
                '.dialog-close',
                '.close',
                '.swal2-confirm',
                '.swal2-cancel'
            ]
            
            # Find all potential buttons in the modal
            all_buttons = []
            for btn_selector in button_selectors:
                try:
                    buttons = modal.find_elements(By.CSS_SELECTOR, btn_selector)
                    all_buttons.extend(buttons)
                except Exception:
                    continue
            
            if not all_buttons:
                print("[MODAL] No buttons found in modal")
                return False
            
            # Remove duplicates
            unique_buttons = []
            seen = set()
            for btn in all_buttons:
                try:
                    # Use location as unique identifier
                    loc = (btn.location['x'], btn.location['y'])
                    if loc not in seen and btn.is_displayed():
                        seen.add(loc)
                        unique_buttons.append(btn)
                except Exception:
                    continue
            
            print(f"[MODAL] Found {len(unique_buttons)} unique button(s)")
            
            # Try to match button by text (priority order)
            for text_pattern in button_texts:
                for button in unique_buttons:
                    try:
                        btn_text = button.text.strip()
                        btn_value = button.get_attribute('value') or ''
                        btn_aria = button.get_attribute('aria-label') or ''
                        
                        # Check if text matches
                        if (text_pattern.lower() in btn_text.lower() or 
                            text_pattern.lower() in btn_value.lower() or
                            text_pattern.lower() in btn_aria.lower()):
                            
                            print(f"[MODAL] Found button with text: '{btn_text or btn_value or btn_aria}'")
                            
                            # Capture details before clicking
                            button_details = self._capture_button_details(button, modal_selector, text_pattern)
                            
                            # Scroll into view
                            self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", button)
                            time.sleep(0.3)
                            
                            # Click the button
                            try:
                                button.click()
                            except Exception:
                                # Fallback to JavaScript click
                                self.driver.execute_script("arguments[0].click();", button)
                            
                            print(f"[MODAL] Clicked button: '{btn_text or btn_value or btn_aria}'")
                            
                            # Record the click
                            self.record_activity("modal_button_click", button_details)
                            
                            # Wait for modal to close
                            time.sleep(0.5)
                            
                            return True
                    except Exception:
                        continue
            
            # If no text match, click the first visible button (fallback)
            if unique_buttons:
                button = unique_buttons[0]
                try:
                    btn_text = button.text.strip() or button.get_attribute('value') or 'Unknown'
                    print(f"[MODAL] No text match, clicking first button: '{btn_text}'")
                    
                    button_details = self._capture_button_details(button, modal_selector, 'first_button')
                    
                    self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", button)
                    time.sleep(0.3)
                    
                    try:
                        button.click()
                    except Exception:
                        self.driver.execute_script("arguments[0].click();", button)
                    
                    print(f"[MODAL] Clicked first available button")
                    
                    self.record_activity("modal_button_click", button_details)
                    time.sleep(0.5)
                    
                    return True
                except Exception as click_err:
                    print(f"[MODAL] Error clicking button: {click_err}")
                    return False
            
            return False
            
        except Exception as modal_err:
            print(f"[MODAL] Error finding/clicking button: {modal_err}")
            return False
    
    def _capture_button_details(self, button, modal_selector, matched_text):
        """Capture comprehensive details about a dialog button"""
        try:
            # Get button properties
            btn_text = button.text.strip()
            btn_tag = button.tag_name
            btn_id = button.get_attribute('id') or ''
            btn_class = button.get_attribute('class') or ''
            btn_type = button.get_attribute('type') or ''
            btn_value = button.get_attribute('value') or ''
            btn_aria = button.get_attribute('aria-label') or ''
            
            # Get coordinates
            location = button.location
            size = button.size
            
            # Get XPath/CSS
            try:
                btn_xpath = self.driver.execute_script("""
                    function getXPath(element) {
                        if (element.id !== '') return '//*[@id="' + element.id + '"]';
                        if (element === document.body) return '/html/body';
                        var ix = 0;
                        var siblings = element.parentNode.childNodes;
                        for (var i = 0; i < siblings.length; i++) {
                            var sibling = siblings[i];
                            if (sibling === element) {
                                return getXPath(element.parentNode) + '/' + element.tagName.toLowerCase() + '[' + (ix + 1) + ']';
                            }
                            if (sibling.nodeType === 1 && sibling.tagName === element.tagName) ix++;
                        }
                    }
                    return getXPath(arguments[0]);
                """, button)
            except Exception:
                btn_xpath = ''
            
            details = {
                "modal_selector": modal_selector,
                "matched_text": matched_text,
                "button_text": btn_text,
                "button_tag": btn_tag,
                "button_id": btn_id,
                "button_class": btn_class,
                "button_type": btn_type,
                "button_value": btn_value,
                "button_aria_label": btn_aria,
                "coordinates": {
                    "x": location['x'],
                    "y": location['y'],
                    "width": size['width'],
                    "height": size['height']
                },
                "xpath": btn_xpath
            }
            
            # Capture screenshot with button highlighted
            try:
                screenshot_details = {
                    "coordinates": {
                        "x": location['x'],
                        "y": location['y'],
                        "width": size['width'],
                        "height": size['height']
                    }
                }
                screenshot_path = self.capture_screenshot_with_highlight(screenshot_details)
                details["screenshot"] = screenshot_path
            except Exception as screenshot_err:
                print(f"[MODAL] Screenshot capture failed: {screenshot_err}")
            
            return details
            
        except Exception as e:
            print(f"[MODAL] Error capturing button details: {e}")
            return {
                "modal_selector": modal_selector,
                "matched_text": matched_text,
                "error": str(e)
            }
    
    def _record_modal_detection(self, modal, selector):
        """Record detection of custom modal dialog"""
        try:
            # Get modal details
            modal_text = modal.text[:200] if modal.text else ""
            
            # Try to find close button
            close_selectors = [
                "button.close",
                "[aria-label='Close']",
                ".modal-close",
                "[data-dismiss='modal']"
            ]
            
            has_close_button = False
            for close_sel in close_selectors:
                try:
                    if modal.find_elements(By.CSS_SELECTOR, close_sel):
                        has_close_button = True
                        break
                except Exception:
                    continue
            
            # Record modal detection
            self.record_activity("modal_detected", {
                "selector": selector,
                "text": modal_text,
                "has_close_button": has_close_button,
                "note": "Custom modal dialog detected - may require manual handling"
            })
            
        except Exception as e:
            print(f"[MODAL] Error recording modal: {e}")
    
    def inject_click_tracker(self):
        """Inject JavaScript to track clicks with comprehensive element information"""
        script = """
        // Helper function to get XPath
        function getXPath(element) {
            if (element.id !== '') {
                return '//*[@id="' + element.id + '"]';
            }
            if (element === document.body) {
                return '/html/body';
            }
            var ix = 0;
            var siblings = element.parentNode ? element.parentNode.childNodes : [];
            for (var i = 0; i < siblings.length; i++) {
                var sibling = siblings[i];
                if (sibling === element) {
                    var tagName = element.tagName.toLowerCase();
                    return getXPath(element.parentNode) + '/' + tagName + '[' + (ix + 1) + ']';
                }
                if (sibling.nodeType === 1 && sibling.tagName === element.tagName) {
                    ix++;
                }
            }
        }
        
        // Helper function to get CSS selector
        function getCssSelector(element) {
            if (element.id) {
                return '#' + element.id;
            }
            var path = [];
            while (element.nodeType === Node.ELEMENT_NODE) {
                var selector = element.nodeName.toLowerCase();
                if (element.id) {
                    selector += '#' + element.id;
                    path.unshift(selector);
                    break;
                } else {
                    var sibling = element;
                    var nth = 1;
                    while (sibling.previousElementSibling) {
                        sibling = sibling.previousElementSibling;
                        if (sibling.nodeName.toLowerCase() === selector) nth++;
                    }
                    if (nth !== 1) selector += ':nth-of-type(' + nth + ')';
                }
                path.unshift(selector);
                element = element.parentNode;
            }
            return path.join(' > ');
        }
        
        // Helper function to get computed styles
        function getVisualProperties(element) {
            var computed = window.getComputedStyle(element);
            return {
                backgroundColor: computed.backgroundColor,
                color: computed.color,
                fontSize: computed.fontSize,
                fontFamily: computed.fontFamily,
                fontWeight: computed.fontWeight,
                border: computed.border,
                padding: computed.padding,
                margin: computed.margin,
                display: computed.display,
                width: computed.width,
                height: computed.height,
                position: computed.position,
                zIndex: computed.zIndex,
                opacity: computed.opacity,
                cursor: computed.cursor
            };
        }
        
        if (!window.clickTrackerInjected) {
            window.clickEvents = [];
            window.lastClickTime = 0;
            window.clickPending = false;
            
            // Capture click immediately and mark as pending
            document.addEventListener('click', function(e) {
                var element = e.target;
                var now = Date.now();
                
                // Debounce to avoid duplicate events
                if (now - window.lastClickTime < 100) return;
                window.lastClickTime = now;
                window.clickPending = true;
                
                // Get bounding rectangle for coordinates
                var rect = element.getBoundingClientRect();
                
                // Get viewport dimensions
                var viewportWidth = window.innerWidth || document.documentElement.clientWidth;
                var viewportHeight = window.innerHeight || document.documentElement.clientHeight;
                
                // Calculate click coordinates relative to element
                var relativeX = e.clientX - rect.left;
                var relativeY = e.clientY - rect.top;
                
                var clickData = {
                    // Basic element info
                    tagName: element.tagName,
                    id: element.id || '',
                    className: element.className || '',
                    name: element.name || '',
                    type: element.type || '',
                    value: element.value || '',
                    
                    // Text content
                    text: element.innerText ? element.innerText.substring(0, 100) : '',
                    textContent: element.textContent ? element.textContent.substring(0, 100) : '',
                    title: element.title || '',
                    alt: element.alt || '',
                    placeholder: element.placeholder || '',
                    
                    // Link information
                    href: element.href || '',
                    target: element.target || '',
                    
                    // Coordinates
                    coordinates: {
                        // Click position in viewport
                        clickX: e.clientX,
                        clickY: e.clientY,
                        // Click position in page
                        pageX: e.pageX,
                        pageY: e.pageY,
                        // Click position relative to element
                        relativeX: relativeX,
                        relativeY: relativeY,
                        // Element position and size
                        elementLeft: rect.left,
                        elementTop: rect.top,
                        elementRight: rect.right,
                        elementBottom: rect.bottom,
                        elementWidth: rect.width,
                        elementHeight: rect.height,
                        // Element center point
                        elementCenterX: rect.left + rect.width / 2,
                        elementCenterY: rect.top + rect.height / 2,
                        // Viewport dimensions
                        viewportWidth: viewportWidth,
                        viewportHeight: viewportHeight,
                        // Scroll position
                        scrollX: window.scrollX || window.pageXOffset,
                        scrollY: window.scrollY || window.pageYOffset
                    },
                    
                    // Selectors for element identification
                    selectors: {
                        xpath: getXPath(element),
                        cssSelector: getCssSelector(element)
                    },
                    
                    // Visual properties
                    visualProperties: getVisualProperties(element),
                    
                    // Attributes
                    attributes: {},
                    
                    // Parent information
                    parent: {
                        tagName: element.parentElement ? element.parentElement.tagName : '',
                        id: element.parentElement ? element.parentElement.id : '',
                        className: element.parentElement ? element.parentElement.className : ''
                    },
                    
                    // Siblings count
                    siblingsCount: element.parentElement ? element.parentElement.children.length : 0,
                    
                    // Image source if applicable
                    src: element.src || '',
                    
                    // ARIA attributes for accessibility
                    ariaLabel: element.getAttribute('aria-label') || '',
                    ariaRole: element.getAttribute('role') || '',
                    
                    // Data attributes
                    dataAttributes: {},
                    
                    // Timestamp
                    timestamp: new Date().toISOString()
                };
                
                // Collect all attributes
                if (element.attributes) {
                    for (var i = 0; i < element.attributes.length; i++) {
                        var attr = element.attributes[i];
                        clickData.attributes[attr.name] = attr.value;
                        
                        // Separately collect data-* attributes
                        if (attr.name.startsWith('data-')) {
                            clickData.dataAttributes[attr.name] = attr.value;
                        }
                    }
                }
                
                window.clickEvents.push(clickData);
                
                // Clear pending flag after a short delay to ensure event is captured
                setTimeout(function() {
                    window.clickPending = false;
                }, 50);
            }, true);
            window.clickTrackerInjected = true;
            
            // Inject into iframes
            try {
                var iframes = document.querySelectorAll('iframe');
                for (var i = 0; i < iframes.length; i++) {
                    try {
                        var iframeDoc = iframes[i].contentDocument || iframes[i].contentWindow.document;
                        if (iframeDoc && !iframeDoc._clickTrackerInjected) {
                            iframeDoc.addEventListener('click', function(e) {
                                var element = e.target;
                                var now = Date.now();
                                if (now - window.lastClickTime < 100) return;
                                window.lastClickTime = now;
                                window.clickPending = true;
                                
                                var rect = element.getBoundingClientRect();
                                var clickData = {
                                    tagName: element.tagName,
                                    id: element.id || '',
                                    className: element.className || '',
                                    text: element.innerText ? element.innerText.substring(0, 100) : '',
                                    href: element.href || '',
                                    type: element.type || '',
                                    inIframe: true,
                                    iframeIndex: i,
                                    coordinates: {
                                        clickX: e.clientX,
                                        clickY: e.clientY,
                                        pageX: e.pageX,
                                        pageY: e.pageY
                                    },
                                    timestamp: new Date().toISOString()
                                };
                                window.clickEvents.push(clickData);
                                setTimeout(function() { window.clickPending = false; }, 50);
                            }, true);
                            iframeDoc._clickTrackerInjected = true;
                        }
                    } catch(e) {
                        // Cross-origin iframe, skip
                    }
                }
            } catch(e) {}
            
            // Inject into shadow DOMs
            try {
                function injectIntoShadowRoots(root) {
                    var elements = root.querySelectorAll('*');
                    for (var i = 0; i < elements.length; i++) {
                        if (elements[i].shadowRoot && !elements[i].shadowRoot._clickTrackerInjected) {
                            var shadowRoot = elements[i].shadowRoot;
                            shadowRoot.addEventListener('click', function(e) {
                                var element = e.target;
                                var now = Date.now();
                                if (now - window.lastClickTime < 100) return;
                                window.lastClickTime = now;
                                window.clickPending = true;
                                
                                var rect = element.getBoundingClientRect();
                                var clickData = {
                                    tagName: element.tagName,
                                    id: element.id || '',
                                    className: element.className || '',
                                    text: element.innerText ? element.innerText.substring(0, 100) : '',
                                    href: element.href || '',
                                    type: element.type || '',
                                    inShadowRoot: true,
                                    coordinates: {
                                        clickX: e.clientX,
                                        clickY: e.clientY,
                                        pageX: e.pageX,
                                        pageY: e.pageY
                                    },
                                    timestamp: new Date().toISOString()
                                };
                                window.clickEvents.push(clickData);
                                setTimeout(function() { window.clickPending = false; }, 50);
                            }, true);
                            shadowRoot._clickTrackerInjected = true;
                            
                            // Recursively inject into nested shadow roots
                            injectIntoShadowRoots(shadowRoot);
                        }
                    }
                }
                injectIntoShadowRoots(document);
            } catch(e) {}
        }
        return window.clickTrackerInjected;
        """
        try:
            result = self.driver.execute_script(script)
            if result:
                self.injection_failed_count = 0
                print("[INFO] Click tracker injected into main DOM, iframes, and shadow roots")
                return True
            else:
                self.injection_failed_count += 1
                return False
        except Exception as e:
            self.injection_failed_count += 1
            if self.injection_failed_count <= 2:
                print(f"[WARNING] Click tracker injection failed: {str(e)[:100]}")
            return False

    def inject_hover_tracker(self):
        """Inject JavaScript to track hover (mouseover) events with debounce to avoid noise"""
        script = """
        function getXPath(element) {
            if (element.id !== '') {
                return '//*[@id="' + element.id + '"]';
            }
            if (element === document.body) {
                return '/html/body';
            }
            var ix = 0;
            var siblings = element.parentNode ? element.parentNode.childNodes : [];
            for (var i = 0; i < siblings.length; i++) {
                var sibling = siblings[i];
                if (sibling === element) {
                    var tagName = element.tagName.toLowerCase();
                    return getXPath(element.parentNode) + '/' + tagName + '[' + (ix + 1) + ']';
                }
                if (sibling.nodeType === 1 && sibling.tagName === element.tagName) {
                    ix++;
                }
            }
        }
        function getCssSelector(element) {
            if (element.id) {
                return '#' + element.id;
            }
            var path = [];
            while (element.nodeType === Node.ELEMENT_NODE) {
                var selector = element.nodeName.toLowerCase();
                if (element.id) {
                    selector += '#' + element.id;
                    path.unshift(selector);
                    break;
                } else {
                    var sibling = element; var nth = 1;
                    while (sibling.previousElementSibling) {
                        sibling = sibling.previousElementSibling;
                        if (sibling.nodeName.toLowerCase() === selector) nth++;
                    }
                    if (nth !== 1) selector += ':nth-of-type(' + nth + ')';
                }
                path.unshift(selector);
                element = element.parentNode;
            }
            return path.join(' > ');
        }
        if (!window.hoverTrackerInjected) {
            window.hoverEvents = [];
            window.lastHover = { selector: null, ts: 0 };
            function captureHover(e) {
                var el = e.target;
                if (!el) return;
                var now = Date.now();
                var selector = getCssSelector(el);
                // Debounce same element within 400ms
                if (window.lastHover.selector === selector && (now - window.lastHover.ts) < 400) return;
                window.lastHover.selector = selector; window.lastHover.ts = now;
                var rect = el.getBoundingClientRect();
                var data = {
                    tagName: el.tagName,
                    id: el.id || '',
                    className: el.className || '',
                    text: el.innerText ? el.innerText.substring(0,100) : '',
                    title: el.title || '',
                    href: el.href || '',
                    type: el.type || '',
                    coordinates: {
                        elementLeft: rect.left,
                        elementTop: rect.top,
                        elementWidth: rect.width,
                        elementHeight: rect.height,
                        elementCenterX: rect.left + rect.width/2,
                        elementCenterY: rect.top + rect.height/2,
                        viewportWidth: window.innerWidth || document.documentElement.clientWidth,
                        viewportHeight: window.innerHeight || document.documentElement.clientHeight,
                        scrollX: window.scrollX || window.pageXOffset,
                        scrollY: window.scrollY || window.pageYOffset
                    },
                    selectors: {
                        xpath: getXPath(el),
                        cssSelector: selector
                    },
                    inIframe: false,
                    inShadowRoot: false,
                    timestamp: new Date().toISOString()
                };
                window.hoverEvents.push(data);
            }
            document.addEventListener('mouseover', captureHover, true);
            // Iframes
            try {
                var iframes = document.querySelectorAll('iframe');
                for (var i=0;i<iframes.length;i++) {
                    try {
                        var idoc = iframes[i].contentDocument || iframes[i].contentWindow.document;
                        if (idoc && !idoc._hoverTrackerInjected) {
                            idoc.addEventListener('mouseover', function(e){
                                var el = e.target; if(!el) return; var rect = el.getBoundingClientRect();
                                var data = {
                                    tagName: el.tagName,
                                    id: el.id || '',
                                    className: el.className || '',
                                    text: el.innerText ? el.innerText.substring(0,100) : '',
                                    inIframe: true,
                                    iframeIndex: i,
                                    selectors: { xpath: getXPath(el), cssSelector: getCssSelector(el) },
                                    timestamp: new Date().toISOString()
                                };
                                window.hoverEvents.push(data);
                            }, true);
                            idoc._hoverTrackerInjected = true;
                        }
                    } catch(_e) {}
                }
            } catch(_e) {}
            // Shadow roots
            try {
                function injectShadow(root){
                    var all = root.querySelectorAll('*');
                    for (var j=0;j<all.length;j++){
                        var sr = all[j].shadowRoot;
                        if (sr && !sr._hoverTrackerInjected){
                            sr.addEventListener('mouseover', function(e){
                                var el = e.target; if(!el) return; var rect = el.getBoundingClientRect();
                                var data = {
                                    tagName: el.tagName,
                                    id: el.id || '',
                                    className: el.className || '',
                                    text: el.innerText ? el.innerText.substring(0,100) : '',
                                    inShadowRoot: true,
                                    selectors: { xpath: getXPath(el), cssSelector: getCssSelector(el) },
                                    timestamp: new Date().toISOString()
                                };
                                window.hoverEvents.push(data);
                            }, true);
                            sr._hoverTrackerInjected = true;
                            injectShadow(sr);
                        }
                    }
                }
                injectShadow(document);
            } catch(_e) {}
            window.hoverTrackerInjected = true;
        }
        return window.hoverTrackerInjected;
        """
        try:
            return self.driver.execute_script(script)
        except Exception:
            return False
            
    def inject_input_tracker(self):
        """Inject JavaScript to track text input with comprehensive element information"""
        script = """
        // Helper function to get XPath (reuse from click tracker)
        function getXPath(element) {
            if (element.id !== '') {
                return '//*[@id="' + element.id + '"]';
            }
            if (element === document.body) {
                return '/html/body';
            }
            var ix = 0;
            var siblings = element.parentNode ? element.parentNode.childNodes : [];
            for (var i = 0; i < siblings.length; i++) {
                var sibling = siblings[i];
                if (sibling === element) {
                    var tagName = element.tagName.toLowerCase();
                    return getXPath(element.parentNode) + '/' + tagName + '[' + (ix + 1) + ']';
                }
                if (sibling.nodeType === 1 && sibling.tagName === element.tagName) {
                    ix++;
                }
            }
        }
        
        // Helper function to get CSS selector
        function getCssSelector(element) {
            if (element.id) {
                return '#' + element.id;
            }
            var path = [];
            while (element.nodeType === Node.ELEMENT_NODE) {
                var selector = element.nodeName.toLowerCase();
                if (element.id) {
                    selector += '#' + element.id;
                    path.unshift(selector);
                    break;
                } else {
                    var sibling = element;
                    var nth = 1;
                    while (sibling.previousElementSibling) {
                        sibling = sibling.previousElementSibling;
                        if (sibling.nodeName.toLowerCase() === selector) nth++;
                    }
                    if (nth !== 1) selector += ':nth-of-type(' + nth + ')';
                }
                path.unshift(selector);
                element = element.parentNode;
            }
            return path.join(' > ');
        }
        
        // Helper function to get computed styles
        function getVisualProperties(element) {
            var computed = window.getComputedStyle(element);
            return {
                backgroundColor: computed.backgroundColor,
                color: computed.color,
                fontSize: computed.fontSize,
                fontFamily: computed.fontFamily,
                fontWeight: computed.fontWeight,
                border: computed.border,
                padding: computed.padding,
                margin: computed.margin,
                display: computed.display,
                width: computed.width,
                height: computed.height,
                borderRadius: computed.borderRadius,
                boxShadow: computed.boxShadow
            };
        }
        
        if (!window.inputTrackerInjected) {
            window.inputEvents = [];
            window.inputDebounce = {};
            
            document.addEventListener('input', function(e) {
                var element = e.target;
                if (element.tagName === 'INPUT' || element.tagName === 'TEXTAREA') {
                    var elementId = element.id || element.name || Math.random();
                    
                    // Debounce rapid input events
                    clearTimeout(window.inputDebounce[elementId]);
                    window.inputDebounce[elementId] = setTimeout(function() {
                        // Get bounding rectangle for coordinates
                        var rect = element.getBoundingClientRect();
                        
                        // Get viewport dimensions
                        var viewportWidth = window.innerWidth || document.documentElement.clientWidth;
                        var viewportHeight = window.innerHeight || document.documentElement.clientHeight;
                        
                        var inputData = {
                            // Basic element info
                            tagName: element.tagName,
                            type: element.type || 'text',
                            id: element.id || '',
                            name: element.name || '',
                            className: element.className || '',
                            
                            // Input properties
                            placeholder: element.placeholder || '',
                            value: element.value,
                            maxLength: element.maxLength || -1,
                            minLength: element.minLength || -1,
                            required: element.required || false,
                            disabled: element.disabled || false,
                            readOnly: element.readOnly || false,
                            autocomplete: element.autocomplete || '',
                            
                            // Label association
                            label: '',
                            
                            // Coordinates
                            coordinates: {
                                // Element position and size
                                elementLeft: rect.left,
                                elementTop: rect.top,
                                elementRight: rect.right,
                                elementBottom: rect.bottom,
                                elementWidth: rect.width,
                                elementHeight: rect.height,
                                // Element center point
                                elementCenterX: rect.left + rect.width / 2,
                                elementCenterY: rect.top + rect.height / 2,
                                // Viewport dimensions
                                viewportWidth: viewportWidth,
                                viewportHeight: viewportHeight,
                                // Scroll position
                                scrollX: window.scrollX || window.pageXOffset,
                                scrollY: window.scrollY || window.pageYOffset
                            },
                            
                            // Selectors for element identification
                            selectors: {
                                xpath: getXPath(element),
                                cssSelector: getCssSelector(element)
                            },
                            
                            // Visual properties
                            visualProperties: getVisualProperties(element),
                            
                            // Attributes
                            attributes: {},
                            
                            // Parent information
                            parent: {
                                tagName: element.parentElement ? element.parentElement.tagName : '',
                                id: element.parentElement ? element.parentElement.id : '',
                                className: element.parentElement ? element.parentElement.className : ''
                            },
                            
                            // Form information if in a form
                            form: {
                                id: element.form ? element.form.id : '',
                                name: element.form ? element.form.name : '',
                                action: element.form ? element.form.action : '',
                                method: element.form ? element.form.method : ''
                            },
                            
                            // ARIA attributes
                            ariaLabel: element.getAttribute('aria-label') || '',
                            ariaDescribedBy: element.getAttribute('aria-describedby') || '',
                            ariaRequired: element.getAttribute('aria-required') || '',
                            
                            // Data attributes
                            dataAttributes: {},
                            
                            // Input state
                            selectionStart: element.selectionStart || 0,
                            selectionEnd: element.selectionEnd || 0,
                            
                            // Timestamp
                            timestamp: new Date().toISOString()
                        };
                        
                        // Try to find associated label
                        var label = element.labels ? element.labels[0] : null;
                        if (!label && element.id) {
                            label = document.querySelector('label[for="' + element.id + '"]');
                        }
                        if (label) {
                            inputData.label = label.innerText || label.textContent || '';
                        }
                        
                        // Collect all attributes
                        if (element.attributes) {
                            for (var i = 0; i < element.attributes.length; i++) {
                                var attr = element.attributes[i];
                                inputData.attributes[attr.name] = attr.value;
                                
                                // Separately collect data-* attributes
                                if (attr.name.startsWith('data-')) {
                                    inputData.dataAttributes[attr.name] = attr.value;
                                }
                            }
                        }
                        
                        window.inputEvents.push(inputData);
                    }, 300); // Wait 300ms after last keystroke
                }
            }, true);
            window.inputTrackerInjected = true;
            
            // Inject into iframes
            try {
                var iframes = document.querySelectorAll('iframe');
                for (var i = 0; i < iframes.length; i++) {
                    try {
                        var iframeDoc = iframes[i].contentDocument || iframes[i].contentWindow.document;
                        if (iframeDoc && !iframeDoc._inputTrackerInjected) {
                            iframeDoc.addEventListener('input', function(e) {
                                var element = e.target;
                                if (element.tagName === 'INPUT' || element.tagName === 'TEXTAREA') {
                                    clearTimeout(element._inputTimeout);
                                    element._inputTimeout = setTimeout(function() {
                                        var inputData = {
                                            tagName: element.tagName,
                                            id: element.id || '',
                                            name: element.name || '',
                                            type: element.type || 'text',
                                            value: element.value,
                                            placeholder: element.placeholder || '',
                                            inIframe: true,
                                            iframeIndex: i,
                                            timestamp: new Date().toISOString()
                                        };
                                        window.inputEvents.push(inputData);
                                    }, 300);
                                }
                            }, true);
                            iframeDoc._inputTrackerInjected = true;
                        }
                    } catch(e) {
                        // Cross-origin iframe, skip
                    }
                }
            } catch(e) {}
            
            // Inject into shadow DOMs
            try {
                function injectInputIntoShadowRoots(root) {
                    var elements = root.querySelectorAll('*');
                    for (var i = 0; i < elements.length; i++) {
                        if (elements[i].shadowRoot && !elements[i].shadowRoot._inputTrackerInjected) {
                            var shadowRoot = elements[i].shadowRoot;
                            shadowRoot.addEventListener('input', function(e) {
                                var element = e.target;
                                if (element.tagName === 'INPUT' || element.tagName === 'TEXTAREA') {
                                    clearTimeout(element._inputTimeout);
                                    element._inputTimeout = setTimeout(function() {
                                        var inputData = {
                                            tagName: element.tagName,
                                            id: element.id || '',
                                            name: element.name || '',
                                            type: element.type || 'text',
                                            value: element.value,
                                            placeholder: element.placeholder || '',
                                            inShadowRoot: true,
                                            timestamp: new Date().toISOString()
                                        };
                                        window.inputEvents.push(inputData);
                                    }, 300);
                                }
                            }, true);
                            shadowRoot._inputTrackerInjected = true;
                            
                            // Recursively inject into nested shadow roots
                            injectInputIntoShadowRoots(shadowRoot);
                        }
                    }
                }
                injectInputIntoShadowRoots(document);
            } catch(e) {}
        }
        return window.inputTrackerInjected;
        """
        try:
            result = self.driver.execute_script(script)
            if result:
                print("[INFO] Input tracker injected into main DOM, iframes, and shadow roots")
                return True
            else:
                return False
        except Exception as e:
            if self.injection_failed_count <= 2:
                print(f"[WARNING] Input tracker injection failed: {str(e)[:100]}")
            return False
            
    def reinject_into_dynamic_contexts(self):
        """Reinject trackers into dynamically added iframes and shadow roots"""
        try:
            self.driver.execute_script("""
                // Reinject into new iframes
                try {
                    var iframes = document.querySelectorAll('iframe');
                    for (var i = 0; i < iframes.length; i++) {
                        try {
                            var iframeDoc = iframes[i].contentDocument || iframes[i].contentWindow.document;
                            if (iframeDoc && !iframeDoc._clickTrackerInjected) {
                                iframeDoc.addEventListener('click', function(e) {
                                    var element = e.target;
                                    var now = Date.now();
                                    if (now - window.lastClickTime < 100) return;
                                    window.lastClickTime = now;
                                    var clickData = {
                                        tagName: element.tagName,
                                        id: element.id || '',
                                        text: element.innerText ? element.innerText.substring(0, 100) : '',
                                        inIframe: true,
                                        timestamp: new Date().toISOString()
                                    };
                                    window.clickEvents.push(clickData);
                                }, true);
                                iframeDoc._clickTrackerInjected = true;
                            }
                        } catch(e) {}
                    }
                } catch(e) {}
                
                // Reinject into new shadow roots
                try {
                    function reinjectShadowRoots(root) {
                        var elements = root.querySelectorAll('*');
                        for (var i = 0; i < elements.length; i++) {
                            if (elements[i].shadowRoot && !elements[i].shadowRoot._clickTrackerInjected) {
                                var shadowRoot = elements[i].shadowRoot;
                                shadowRoot.addEventListener('click', function(e) {
                                    var element = e.target;
                                    var now = Date.now();
                                    if (now - window.lastClickTime < 100) return;
                                    window.lastClickTime = now;
                                    var clickData = {
                                        tagName: element.tagName,
                                        id: element.id || '',
                                        text: element.innerText ? element.innerText.substring(0, 100) : '',
                                        inShadowRoot: true,
                                        timestamp: new Date().toISOString()
                                    };
                                    window.clickEvents.push(clickData);
                                }, true);
                                shadowRoot._clickTrackerInjected = true;
                                reinjectShadowRoots(shadowRoot);
                            }
                        }
                    }
                    reinjectShadowRoots(document);
                } catch(e) {}
            """)
        except Exception:
            pass
    
    def collect_click_events(self):
        """Collect click events from JavaScript tracker"""
        try:
            # Always collect pending clicks, even if page is loading
            clicks = self.driver.execute_script("""
                var events = window.clickEvents || []; 
                window.clickEvents = []; 
                return events;
            """)
            if clicks:
                for click in clicks:
                    self.record_activity("click", click)
                    context = ""
                    if click.get('inIframe'):
                        context = " (in iframe)"
                    elif click.get('inShadowRoot'):
                        context = " (in shadow DOM)"
                    print(f"[CLICK] Captured click on {click.get('tagName', 'unknown')} element{context}")
        except Exception:
            pass
            
    def collect_input_events(self):
        """Collect input events from JavaScript tracker"""
        try:
            inputs = self.driver.execute_script("var events = window.inputEvents || []; window.inputEvents = []; return events;")
            if inputs:
                for inp in inputs:
                    self.record_activity("text_input", inp)
        except Exception:
            pass
    
    def fallback_track_dom_changes(self):
        """Fallback method to track DOM changes when JavaScript injection fails"""
        try:
            # Get currently focused element
            active_element = self.driver.execute_script("""
                var active = document.activeElement;
                if (active && (active.tagName === 'INPUT' || active.tagName === 'TEXTAREA')) {
                    return {
                        tagName: active.tagName,
                        type: active.type || 'text',
                        id: active.id || '',
                        name: active.name || '',
                        value: active.value,
                        placeholder: active.placeholder || ''
                    };
                }
                return null;
            """)
            
            if active_element:
                # Check if this is a new input or value changed
                element_key = f"{active_element['tagName']}_{active_element['id']}_{active_element['name']}"
                if element_key not in self.element_tracker or self.element_tracker[element_key] != active_element['value']:
                    self.element_tracker[element_key] = active_element['value']
                    if active_element['value']:  # Only log if there's actual input
                        self.record_activity("text_input_fallback", {
                            "element": active_element['tagName'],
                            "type": active_element['type'],
                            "id": active_element['id'],
                            "name": active_element['name'],
                            "placeholder": active_element['placeholder'],
                            "value": active_element['value'][:50] + "..." if len(active_element['value']) > 50 else active_element['value']
                        })
        except Exception:
            pass
    
    def fallback_track_clicks(self):
        """Fallback method to detect navigation events as potential clicks"""
        try:
            # Check if URL hash or query params changed (common after clicks)
            current_url = self.driver.current_url
            if '#' in current_url or '?' in current_url:
                # Potential click detected through URL change
                pass
        except Exception:
            pass
            
    def monitor_activities(self):
        """Main monitoring loop"""
        self.previous_window_handles = self.driver.window_handles
        trackers_injected = False
        page_loading = False
        use_fallback = False
        last_injection_url = ""
        
        while True:
            try:
                # IMPORTANT: Collect clicks FIRST before any loading checks
                # This ensures clicks that trigger DOM changes are captured
                if trackers_injected:
                    # Periodically reinject into new iframes/shadow DOMs
                    self.reinject_into_dynamic_contexts()
                    self.collect_click_events()
                    self.collect_input_events()
                
                # Check if page is loading
                is_loading, reason = self.is_page_loading()
                
                if is_loading:
                    if not page_loading:
                        print(f"[INFO] Page is loading ({reason}), pausing recording...")
                        page_loading = True
                        trackers_injected = False
                    time.sleep(0.2)
                    continue
                else:
                    if page_loading:
                        print(f"[INFO] Page loaded ({reason}), resuming recording...")
                        page_loading = False
                        trackers_injected = False
                        use_fallback = False
                        self.injection_failed_count = 0
                
                # Track navigation and check if page changed
                page_changed = self.track_navigation()
                if page_changed:
                    # URL changed, need to re-inject trackers
                    trackers_injected = False
                    last_injection_url = ""
                    print("[INFO] Page navigated, re-injecting trackers...")
                
                # Track tab switching; if switch occurred, force tracker reinjection
                tab_switched = self.track_tab_switching()
                if tab_switched:
                    trackers_injected = False
                    last_injection_url = ""
                    print("[INFO] Tab switch detected – reinjecting trackers in new tab context")
                
                # Check for pop-ups (alerts, confirms, prompts)
                self.check_and_handle_popup()
                
                # Check for custom modal dialogs
                self.check_modal_dialogs()
                
                # Check if we need to inject/re-inject trackers
                current_url = self.driver.current_url
                if not trackers_injected and current_url != last_injection_url and not use_fallback:
                    click_ok = self.inject_click_tracker()
                    input_ok = self.inject_input_tracker()
                    hover_ok = self.inject_hover_tracker()
                    trackers_injected = click_ok and input_ok and hover_ok
                    
                    if trackers_injected:
                        last_injection_url = current_url
                        print(f"[INFO] Trackers successfully injected on: {current_url[:60]}")
                    
                    # If injection fails multiple times, switch to fallback mode
                    if self.injection_failed_count > 3:
                        use_fallback = True
                        print("[INFO] JavaScript injection blocked by website security.")
                        print("[INFO] Switching to fallback tracking mode (limited functionality)")
                    
                    if not trackers_injected and not use_fallback:
                        time.sleep(0.1)
                        continue
                
                # Use fallback methods if trackers not injected
                if trackers_injected:
                    # Collect hover events when trackers active
                    try:
                        hover_events = self.driver.execute_script("return window.hoverEvents ? window.hoverEvents.splice(0, window.hoverEvents.length) : [];")
                        for he in hover_events:
                            self.record_activity("hover", he)
                    except Exception:
                        pass
                if not trackers_injected and use_fallback:
                    # Use fallback methods
                    self.fallback_track_dom_changes()
                    self.fallback_track_clicks()
                
                # Reduced sleep time for faster response
                time.sleep(0.2)
                
            except KeyboardInterrupt:
                print("\nRecording stopped by user.")
                break
            except Exception as e:
                # Handle cases where page is loading or driver is closed
                error_msg = str(e).lower()
                if "invalid session id" in error_msg or "no such window" in error_msg:
                    break
                # Reset tracker injection flag on errors
                trackers_injected = False
                time.sleep(0.2)
                
        return self.activity_log

def main():
    # Initialize the Selenium WebDriver with options
    print("Starting browser activity recorder...")
    print("The browser will open and start recording your activities.")
    print("Press Ctrl+C to stop recording.\n")
    
    # Configure Chrome options for better tracking
    options = webdriver.ChromeOptions()
    options.add_argument('--disable-blink-features=AutomationControlled')
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option('useAutomationExtension', False)
    options.add_argument('--start-maximized')  # Start browser in fullscreen/maximized mode
    
    # Add logging preferences to capture console and network events
    options.set_capability('goog:loggingPrefs', {'browser': 'ALL', 'performance': 'ALL'})
    
    driver = webdriver.Chrome(options=options)
    
    # Maximize window to ensure fullscreen
    driver.maximize_window()
    
    # Navigate to a starting page
    driver.get("https://www.ibm.com")
    
    # Create recorder instance
    recorder = BrowserActivityRecorder(driver)
    
    try:
        # Start monitoring
        activity_log = recorder.monitor_activities()
    except KeyboardInterrupt:
        print("\nRecording stopped by user.")
        activity_log = recorder.activity_log
    finally:
        print(f"\nTotal activities recorded: {len(activity_log)}")
        
        # Finalize VLM processing (wait for async tasks to complete)
        recorder.finalize_vlm_processing()
        
        # Optimize activity log (consolidate typing, remove redundant clicks)
        recorder.optimize_activity_log()
        
        # Update activity_log reference after optimization
        activity_log = recorder.activity_log
        
        # Convert the activity log to natural language
        convert_to_natural_language(activity_log)
        
        # Save activity log to file
        with open('activity_log.json', 'w') as f:
            json.dump(activity_log, f, indent=2)
        print(f"\nActivity log saved to 'activity_log.json'")

        # Close the browser
        driver.quit()

if __name__ == "__main__":
    main()