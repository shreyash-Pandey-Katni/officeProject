"""
Element Finder with Visual Detection
Uses multiple strategies to locate elements in the browser
"""
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoSuchElementException, TimeoutException
from typing import Dict, Any, Optional, Tuple
from llm_helpers import OllamaVLM, OllamaLLM
import time
import os


class VisualElementFinder:
    """Find elements using visual cues and multiple fallback strategies"""
    
    def __init__(self, driver: webdriver.Chrome):
        self.driver = driver
        self.vlm = OllamaVLM(model="granite3.2-vision")
        self.llm = OllamaLLM(model="gemma2:2b")
        self.wait = WebDriverWait(driver, 10)
    
    def find_element(self, element_details: Dict[str, Any], screenshot_path: Optional[str] = None) -> Tuple[Optional[Any], str]:
        """
        Find element using visual-first approach with multiple fallbacks
        Returns: (element, method_used)
        """
        print(f"\n[FINDER] Searching for element: {element_details.get('tagName', 'unknown')}")
        
        # Strategy 1: Visual detection using VLM (PRIMARY)
        if screenshot_path:
            element, method = self._find_by_visual_detection(element_details, screenshot_path)
            if element:
                return element, method
        
        # Strategy 2: Try XPath selector
        element, method = self._find_by_xpath(element_details)
        if element:
            return element, method
        
        # Strategy 3: Try CSS selector
        element, method = self._find_by_css(element_details)
        if element:
            return element, method
        
        # Strategy 4: Try by ID
        element, method = self._find_by_id(element_details)
        if element:
            return element, method
        
        # Strategy 5: Try by text content
        element, method = self._find_by_text(element_details)
        if element:
            return element, method
        
        # Strategy 6: Try by coordinates (click at position)
        element, method = self._find_by_coordinates(element_details)
        if element:
            return element, method
        
        # Strategy 7: Try alternative selectors suggested by LLM
        element, method = self._find_by_llm_suggestions(element_details)
        if element:
            return element, method
        
        print("[FINDER] ✗ Element not found with any method")
        return None, "not_found"
    
    def _find_by_visual_detection(self, element_details: Dict[str, Any], 
                                  screenshot_path: str) -> Tuple[Optional[Any], str]:
        """Use VLM to detect element visually using VLM description, verify its location AND check if it's ready"""
        try:
            print("[FINDER] Attempting visual detection with VLM...")
            
            # Get VLM description from element details (if available)
            vlm_description = element_details.get('vlm_description', '')
            if vlm_description:
                print(f"[FINDER] Using VLM description: {vlm_description[:150]}...")
            
            # Get expected coordinates from log
            coords = element_details.get('coordinates', {})
            if not coords:
                return None, ""
            
            center_x = coords.get('elementCenterX', 0)
            center_y = coords.get('elementCenterY', 0)
            
            if center_x == 0 or center_y == 0:
                return None, ""
            
            # Capture current screenshot for readiness check
            current_screenshot = screenshot_path.replace('screenshots/', 'replay_screenshots/temp_current.png')
            try:
                import os
                os.makedirs(os.path.dirname(current_screenshot), exist_ok=True)
                self.driver.save_screenshot(current_screenshot)
            except:
                current_screenshot = screenshot_path  # Fallback to original
            
            # If VLM description is available, use it for better element detection
            if vlm_description:
                # Create enhanced element details with VLM description
                enhanced_details = element_details.copy()
                enhanced_details['vlm_description'] = vlm_description
                
                # Use VLM to verify element using the description
                element_state = self.vlm.is_element_visible_and_ready(
                    current_screenshot, enhanced_details, coords
                )
            else:
                # Use VLM to check element state (verify position + readiness in one call)
                element_state = self.vlm.is_element_visible_and_ready(
                    current_screenshot, element_details, coords
                )
            
            print(f"[FINDER] VLM Analysis: Visible={element_state['visible']}, "
                  f"Loaded={element_state['fully_loaded']}, "
                  f"Interactable={element_state['interactable']}")
            
            if element_state['ready']:
                print(f"[FINDER] ✓ VLM: Element at ({center_x:.0f}, {center_y:.0f}) is ready")
                print(f"[FINDER]   Reason: {element_state['reason']}")
                
                # Try to find element at those coordinates using JavaScript
                element = self._get_element_at_coordinates(center_x, center_y)
                if element:
                    return element, "visual_detection_verified"
                else:
                    # If can't get element, return coordinates for action execution
                    return {"click_at_coords": (center_x, center_y)}, "visual_coordinates"
            
            elif element_state['visible'] and element_state['fully_loaded'] and not element_state['interactable']:
                # Element exists but not interactable yet - wait and retry
                print(f"[FINDER] Element found but not interactable: {element_state['reason']}")
                print("[FINDER] Waiting 2 seconds for element to become ready...")
                time.sleep(2)
                
                # Retry readiness check
                self.driver.save_screenshot(current_screenshot)
                element_state = self.vlm.is_element_visible_and_ready(
                    current_screenshot, element_details, coords
                )
                
                if element_state['ready']:
                    print(f"[FINDER] ✓ Element now ready after waiting")
                    element = self._get_element_at_coordinates(center_x, center_y)
                    if element:
                        return element, "visual_detection_verified_after_wait"
                    else:
                        return {"click_at_coords": (center_x, center_y)}, "visual_coordinates_after_wait"
                else:
                    print(f"[FINDER] Element still not ready: {element_state['reason']}")
            
            print("[FINDER] VLM could not verify element at expected position or not ready")
            
            # Try to find similar element using VLM with description
            if vlm_description:
                print("[FINDER] Using VLM description to find similar element...")
                found_coords = self._find_by_vlm_description(current_screenshot, vlm_description, element_details)
                if found_coords:
                    x = found_coords.get('elementCenterX', 0)
                    y = found_coords.get('elementCenterY', 0)
                    print(f"[FINDER] ✓ VLM found element using description at ({x:.0f}, {y:.0f})")
                    
                    # Check if this element is ready
                    found_state = self.vlm.is_element_visible_and_ready(
                        current_screenshot, element_details, found_coords
                    )
                    
                    if found_state['ready']:
                        print(f"[FINDER] ✓ Element found by description is ready for interaction")
                        element = self._get_element_at_coordinates(x, y)
                        if element:
                            return element, "visual_detection_by_description"
                        else:
                            return {"click_at_coords": (x, y)}, "visual_coordinates_by_description"
                    else:
                        print(f"[FINDER] Element found by description not ready: {found_state['reason']}")
            else:
                # Try to find similar element using VLM (old method)
                found_coords = self.vlm.find_similar_element(current_screenshot, element_details)
                if found_coords:
                    x = found_coords.get('elementCenterX', 0)
                    y = found_coords.get('elementCenterY', 0)
                    print(f"[FINDER] ✓ VLM found similar element at ({x:.0f}, {y:.0f})")
                    
                    # Check if this element is ready too
                    found_state = self.vlm.is_element_visible_and_ready(
                        current_screenshot, element_details, found_coords
                    )
                    
                    if found_state['ready']:
                        print(f"[FINDER] ✓ Similar element is ready for interaction")
                        element = self._get_element_at_coordinates(x, y)
                        if element:
                            return element, "visual_detection_similar"
                        else:
                            return {"click_at_coords": (x, y)}, "visual_coordinates_alt"
                    else:
                        print(f"[FINDER] Similar element not ready: {found_state['reason']}")
            
            # Clean up temp screenshot
            try:
                if os.path.exists(current_screenshot) and 'temp_current' in current_screenshot:
                    os.remove(current_screenshot)
            except:
                pass
            
        except Exception as e:
            print(f"[FINDER] Visual detection error: {e}")
        
        return None, ""
    
    def _find_by_vlm_description(self, screenshot_path: str, vlm_description: str, 
                                  element_details: Dict[str, Any]) -> Optional[Dict[str, float]]:
        """Use VLM description to find element in current page"""
        try:
            # Create a detailed prompt using the VLM description
            prompt = f"""Analyze this screenshot and locate the following element:

ELEMENT DESCRIPTION (from previous recording):
{vlm_description}

Also looking for:
- Tag: {element_details.get('tagName', 'unknown')}
- Text: {element_details.get('text', '')}

Provide the approximate X and Y coordinates where this element appears in the current screenshot.
Format your response as: "COORDINATES: X=<number>, Y=<number>" """

            # Encode screenshot
            image_base64 = self.vlm.encode_image(screenshot_path)
            
            # Call VLM
            response = self.vlm._call_ollama_vision(prompt, image_base64)
            
            # Parse coordinates from response
            import re
            coord_match = re.search(r'X[=:\s]+(\d+).*?Y[=:\s]+(\d+)', response, re.IGNORECASE)
            if coord_match:
                x = float(coord_match.group(1))
                y = float(coord_match.group(2))
                print(f"[FINDER] VLM extracted coordinates: ({x}, {y})")
                
                return {
                    'elementCenterX': x,
                    'elementCenterY': y,
                    'viewportX': x,
                    'viewportY': y
                }
            else:
                print(f"[FINDER] Could not parse coordinates from VLM response")
                return None
                
        except Exception as e:
            print(f"[FINDER] Error finding element by VLM description: {e}")
            return None
    
    def _get_element_at_coordinates(self, x: float, y: float) -> Optional[Any]:
        """Get element at specific coordinates using JavaScript"""
        try:
            script = f"""
            return document.elementFromPoint({x}, {y});
            """
            element = self.driver.execute_script(script)
            if element:
                print(f"[FINDER] Found element at coordinates using JavaScript")
            return element
        except Exception as e:
            print(f"[FINDER] Could not get element at coordinates: {e}")
            return None
    
    def _find_by_xpath(self, element_details: Dict[str, Any]) -> Tuple[Optional[Any], str]:
        """Find element using XPath"""
        try:
            selectors = element_details.get('selectors', {})
            xpath = selectors.get('xpath', '')
            
            if xpath:
                print(f"[FINDER] Trying XPath: {xpath[:80]}")
                element = self.wait.until(EC.presence_of_element_located((By.XPATH, xpath)))
                print("[FINDER] ✓ Found by XPath")
                return element, "xpath"
        except (NoSuchElementException, TimeoutException):
            pass
        except Exception as e:
            print(f"[FINDER] XPath error: {e}")
        
        return None, ""
    
    def _find_by_css(self, element_details: Dict[str, Any]) -> Tuple[Optional[Any], str]:
        """Find element using CSS selector"""
        try:
            selectors = element_details.get('selectors', {})
            css = selectors.get('cssSelector', '')
            
            if css:
                print(f"[FINDER] Trying CSS selector: {css[:80]}")
                element = self.wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, css)))
                print("[FINDER] ✓ Found by CSS selector")
                return element, "css_selector"
        except (NoSuchElementException, TimeoutException):
            pass
        except Exception as e:
            print(f"[FINDER] CSS selector error: {e}")
        
        return None, ""
    
    def _find_by_id(self, element_details: Dict[str, Any]) -> Tuple[Optional[Any], str]:
        """Find element by ID"""
        try:
            elem_id = element_details.get('id', '')
            if elem_id:
                print(f"[FINDER] Trying ID: {elem_id}")
                element = self.driver.find_element(By.ID, elem_id)
                print("[FINDER] ✓ Found by ID")
                return element, "id"
        except NoSuchElementException:
            pass
        except Exception as e:
            print(f"[FINDER] ID search error: {e}")
        
        return None, ""
    
    def _find_by_text(self, element_details: Dict[str, Any]) -> Tuple[Optional[Any], str]:
        """Find element by text content"""
        try:
            text = element_details.get('text', '').strip()
            tag = element_details.get('tagName', '*').lower()
            
            if text and len(text) > 0:
                # Try exact text match
                xpath = f"//{tag}[contains(text(), '{text}')]"
                print(f"[FINDER] Trying text search: {text[:50]}")
                element = self.driver.find_element(By.XPATH, xpath)
                print("[FINDER] ✓ Found by text content")
                return element, "text_content"
        except NoSuchElementException:
            pass
        except Exception as e:
            print(f"[FINDER] Text search error: {e}")
        
        return None, ""
    
    def _find_by_coordinates(self, element_details: Dict[str, Any]) -> Tuple[Optional[Any], str]:
        """Find element by clicking at coordinates"""
        try:
            coords = element_details.get('coordinates', {})
            x = coords.get('elementCenterX', 0)
            y = coords.get('elementCenterY', 0)
            
            if x > 0 and y > 0:
                print(f"[FINDER] Trying coordinates: ({x:.0f}, {y:.0f})")
                element = self._get_element_at_coordinates(x, y)
                if element:
                    print("[FINDER] ✓ Found element at coordinates")
                    return element, "coordinates"
                else:
                    # Return special marker for coordinate-based clicking
                    return {"click_at_coords": (x, y)}, "coordinates_fallback"
        except Exception as e:
            print(f"[FINDER] Coordinate search error: {e}")
        
        return None, ""
    
    def _find_by_llm_suggestions(self, element_details: Dict[str, Any]) -> Tuple[Optional[Any], str]:
        """Try alternative selectors suggested by LLM"""
        try:
            print("[FINDER] Asking LLM for alternative selectors...")
            suggestions = self.llm.suggest_alternative_selector(element_details)
            
            for i, selector in enumerate(suggestions, 1):
                try:
                    print(f"[FINDER] Trying LLM suggestion {i}: {selector}")
                    element = self.driver.find_element(By.CSS_SELECTOR, selector)
                    print(f"[FINDER] ✓ Found by LLM suggestion {i}")
                    return element, f"llm_suggestion_{i}"
                except NoSuchElementException:
                    continue
        except Exception as e:
            print(f"[FINDER] LLM suggestion error: {e}")
        
        return None, ""
