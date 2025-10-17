"""
LLM Helpers for Ollama Integration
Supports LLaVA (vision) and Gemma3 (text) models
"""
import requests
import json
import base64
from typing import Dict, Any, Optional, List


class OllamaVLM:
    """Vision-Language Model integration using Ollama"""
    
    def __init__(self, model: str = "granite3.2-vision"):
        self.model = model
        self.base_url = "http://localhost:11434/api/generate"
        self.api_url = "http://localhost:11434/api/generate"
        
    def encode_image(self, image_path: str) -> str:
        """Encode image to base64"""
        with open(image_path, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode('utf-8')
    
    def find_element_in_image(self, image_path: str, element_description: Dict[str, Any]) -> Dict[str, Any]:
        """
        Use VLM to find an element in an image based on description
        Returns coordinates and confidence
        """
        # Create a detailed prompt for the VLM
        prompt = self._create_element_detection_prompt(element_description)
        
        # Encode image
        image_base64 = self.encode_image(image_path)
        
        # Call Ollama API
        response = self._call_ollama_vision(prompt, image_base64)
        
        # Parse response to extract coordinates
        return self._parse_coordinates_response(response, element_description)
    
    def verify_element_at_position(self, image_path: str, coordinates: Dict[str, float], 
                                   expected_description: Dict[str, Any]) -> bool:
        """
        Verify if the element at given coordinates matches the expected description
        """
        prompt = f"""Look at this screenshot. At coordinates (x={coordinates.get('elementCenterX', 0):.0f}, 
y={coordinates.get('elementCenterY', 0):.0f}), there should be a {expected_description.get('tagName', 'element')}.

Expected properties:
- Text: {expected_description.get('text', 'N/A')}
- Type: {expected_description.get('tagName', 'N/A')}
- Visual: {expected_description.get('visualProperties', {}).get('color', 'N/A')} text color

Does the element at that position match this description? Answer with YES or NO and explain briefly."""
        
        image_base64 = self.encode_image(image_path)
        response = self._call_ollama_vision(prompt, image_base64)
        
        # Check if response contains YES
        return "YES" in response.upper() or "CORRECT" in response.upper()
    
    def describe_element_at_position(self, image_path: str, x: float, y: float) -> str:
        """Describe what element is at the given coordinates"""
        prompt = f"""Describe the UI element located at coordinates (x={x:.0f}, y={y:.0f}) in this screenshot.
Include:
1. What type of element it is (button, link, input field, etc.)
2. What text or label it has
3. Its visual appearance (color, size, style)
4. Its likely purpose

Be concise and specific."""
        
        image_base64 = self.encode_image(image_path)
        return self._call_ollama_vision(prompt, image_base64)
    
    def find_similar_element(self, image_path: str, reference_description: Dict[str, Any]) -> Optional[Dict[str, float]]:
        """
        Find an element similar to the reference description using visual cues
        Returns estimated coordinates or None
        """
        prompt = f"""Find an element in this screenshot that matches:
- Tag: {reference_description.get('tagName', 'unknown')}
- Text: {reference_description.get('text', 'N/A')}
- ID: {reference_description.get('id', 'N/A')}
- Class: {reference_description.get('className', 'N/A')}

If found, provide the approximate X and Y coordinates (in pixels from top-left).
Format your response as: FOUND at X=<number> Y=<number>
If not found, respond with: NOT FOUND"""
        
        image_base64 = self.encode_image(image_path)
        response = self._call_ollama_vision(prompt, image_base64)
        
        # Parse coordinates from response
        if "FOUND" in response.upper():
            try:
                # Extract X and Y from response
                import re
                x_match = re.search(r'X[=:]\s*(\d+)', response, re.IGNORECASE)
                y_match = re.search(r'Y[=:]\s*(\d+)', response, re.IGNORECASE)
                
                if x_match and y_match:
                    return {
                        'elementCenterX': float(x_match.group(1)),
                        'elementCenterY': float(y_match.group(1))
                    }
            except:
                pass
        
        return None
    
    def is_page_loading(self, image_path: str) -> Dict[str, Any]:
        """
        Detect if page or parts of it are loading using visual cues
        Returns: {'loading': bool, 'indicators': List[str], 'ready': bool}
        """
        prompt = """Analyze this screenshot carefully and determine if the webpage is still loading or if it's fully loaded and ready for interaction.

Look for these loading indicators:
1. Spinning loaders or progress indicators
2. Skeleton screens or placeholder content
3. "Loading..." text messages
4. Partially rendered content
5. Blank areas that should have content
6. Progress bars
7. Animated spinners

Answer in this exact format:
LOADING: YES or NO
INDICATORS: <list any loading indicators you see, or write NONE>
READY_FOR_INTERACTION: YES or NO

Be specific about what you observe."""
        
        image_base64 = self.encode_image(image_path)
        response = self._call_ollama_vision(prompt, image_base64)
        
        # Parse response
        is_loading = "LOADING: YES" in response.upper()
        is_ready = "READY_FOR_INTERACTION: YES" in response.upper() or (not is_loading and "READY_FOR_INTERACTION: NO" not in response.upper())
        
        # Extract indicators
        indicators = []
        import re
        ind_match = re.search(r'INDICATORS:\s*(.+?)(?:\n|$)', response, re.IGNORECASE | re.DOTALL)
        if ind_match:
            indicators_text = ind_match.group(1).strip()
            if indicators_text.upper() != "NONE":
                indicators = [indicators_text]
        
        return {
            'loading': is_loading,
            'ready': is_ready,
            'indicators': indicators,
            'vlm_response': response
        }
    
    def is_element_visible_and_ready(self, image_path: str, element_description: Dict[str, Any], 
                                     coordinates: Dict[str, float]) -> Dict[str, Any]:
        """
        Check if element is visible and ready for interaction
        Returns: {'visible': bool, 'interactable': bool, 'reason': str}
        """
        x = coordinates.get('elementCenterX', 0)
        y = coordinates.get('elementCenterY', 0)
        tag = element_description.get('tagName', 'element')
        text = element_description.get('text', '')
        
        prompt = f"""Analyze the element at coordinates (X={x:.0f}, Y={y:.0f}) in this screenshot.

Expected element:
- Type: {tag}
- Text: {text}

Determine:
1. Is this element VISIBLE on the screen?
2. Is it FULLY LOADED (not a skeleton/placeholder)?
3. Is it INTERACTABLE (not disabled, not covered by another element, not grayed out)?
4. Are there any loading indicators near it?

Answer in this format:
VISIBLE: YES or NO
FULLY_LOADED: YES or NO
INTERACTABLE: YES or NO
REASON: <brief explanation>"""
        
        image_base64 = self.encode_image(image_path)
        response = self._call_ollama_vision(prompt, image_base64)
        
        # Parse response
        visible = "VISIBLE: YES" in response.upper()
        fully_loaded = "FULLY_LOADED: YES" in response.upper()
        interactable = "INTERACTABLE: YES" in response.upper()
        
        # Extract reason
        reason = ""
        import re
        reason_match = re.search(r'REASON:\s*(.+?)(?:\n|$)', response, re.IGNORECASE | re.DOTALL)
        if reason_match:
            reason = reason_match.group(1).strip()
        
        return {
            'visible': visible,
            'fully_loaded': fully_loaded,
            'interactable': interactable,
            'ready': visible and fully_loaded and interactable,
            'reason': reason,
            'vlm_response': response
        }
    
    def _create_element_detection_prompt(self, element_desc: Dict[str, Any]) -> str:
        """Create a detailed prompt for element detection"""
        text = element_desc.get('text', '')
        tag = element_desc.get('tagName', 'element')
        elem_id = element_desc.get('id', '')
        class_name = element_desc.get('className', '')
        
        prompt = f"""Analyze this screenshot and locate the following element:
- Type: {tag}
- Text content: "{text}"
- ID: {elem_id if elem_id else 'not specified'}
- CSS classes: {class_name if class_name else 'not specified'}

Describe where this element is located in the image. Provide approximate coordinates."""
        
        return prompt
    
    def _parse_coordinates_response(self, response: str, element_desc: Dict[str, Any]) -> Dict[str, Any]:
        """Parse VLM response to extract coordinates"""
        # For now, return the original coordinates from the log
        # In a more sophisticated implementation, parse VLM response
        coords = element_desc.get('coordinates', {})
        
        return {
            'found': True,
            'coordinates': coords,
            'confidence': 0.8,
            'vlm_description': response
        }
    
    def generate_element_description(self, image_path: str, element_html: str, 
                                     coordinates: Dict[str, Any], event_type: str) -> str:
        """
        Generate comprehensive natural language description of an element
        Includes: visual appearance, location context, purpose, and text content
        FOCUSED on the specific element at given coordinates
        """
        # Extract element details from HTML for focused analysis
        element_tag = self._extract_tag_from_html(element_html)
        element_text = self._extract_text_from_html(element_html)
        element_attributes = self._extract_key_attributes(element_html)
        
        # Get element bounds for focused description
        center_x = coordinates.get('elementCenterX', 0)
        center_y = coordinates.get('elementCenterY', 0)
        width = coordinates.get('elementWidth', 0)
        height = coordinates.get('elementHeight', 0)
        left = coordinates.get('elementLeft', 0)
        top = coordinates.get('elementTop', 0)
        
        # Calculate relative position percentages
        viewport_width = coordinates.get('viewportWidth', 1920)
        viewport_height = coordinates.get('viewportHeight', 1080)
        relative_x = (center_x / viewport_width * 100) if viewport_width > 0 else 50
        relative_y = (center_y / viewport_height * 100) if viewport_height > 0 else 50
        
        # Determine position description
        horizontal_pos = "left" if relative_x < 33 else "right" if relative_x > 66 else "center"
        vertical_pos = "top" if relative_y < 33 else "bottom" if relative_y > 66 else "middle"
        
        # Create FOCUSED prompt that directs VLM attention to specific area
        prompt = f"""FOCUS ON THE ELEMENT AT COORDINATES ({int(center_x)}, {int(center_y)}) in this screenshot.

TARGET ELEMENT:
- Tag: {element_tag}
- Text Content: "{element_text}"
- Position: {vertical_pos}-{horizontal_pos} of screen
- Bounding Box: x={int(left)}, y={int(top)}, width={int(width)}, height={int(height)}
- Event Type: {event_type}

ELEMENT ATTRIBUTES:
{element_attributes}

TASK: Describe ONLY the element at the specified coordinates. Focus on:

1. EXACT VISUAL APPEARANCE: 
   - What exact colors do you see (background, text, border)?
   - What is the size (small/medium/large button/field)?
   - Shape and styling (rounded corners, shadows, borders)?
   - Any icons or images visible?

2. DISTINCTIVE TEXT:
   - What exact text or label is displayed?
   - Font style (bold, normal, size)?
   
3. IMMEDIATE SURROUNDING CONTEXT:
   - What elements are IMMEDIATELY adjacent (within 50px)?
   - Left of element: ?
   - Right of element: ?
   - Above element: ?
   - Below element: ?

4. UNIQUE IDENTIFIERS:
   - Any unique visual markers (colors, icons, badges)?
   - Distinguishing features from similar elements?

Provide a CONCISE 2-3 sentence description focusing ONLY on this specific element.
Start with "This is a..." and be highly specific about visual details that make it unique."""

        # Encode image
        try:
            image_base64 = self.encode_image(image_path)
            
            # Call VLM with focused prompt
            response = self._call_ollama_vision(prompt, image_base64)
            
            if response:
                # Clean up response (remove common VLM artifacts)
                cleaned = response.strip()
                print(f"[VLM] Generated focused description ({len(cleaned)} chars)")
                print(f"[VLM] Preview: {cleaned[:100]}...")
                return cleaned
            else:
                return f"{element_tag} element at {vertical_pos}-{horizontal_pos} position ({center_x:.0f}, {center_y:.0f})"
                
        except Exception as e:
            print(f"[ERROR] Failed to generate element description: {e}")
            return f"{element_tag} element at ({center_x:.0f}, {center_y:.0f})"
    
    def _extract_tag_from_html(self, html: str) -> str:
        """Extract tag name from HTML"""
        if not html:
            return "unknown"
        import re
        match = re.search(r'<(\w+)', html)
        return match.group(1).upper() if match else "unknown"
    
    def _extract_text_from_html(self, html: str) -> str:
        """Extract visible text from HTML"""
        if not html:
            return ""
        import re
        # Remove tags and get text content
        text = re.sub(r'<[^>]+>', '', html)
        text = text.strip()
        return text[:200] if text else ""
    
    def _extract_key_attributes(self, html: str) -> str:
        """Extract key attributes from HTML for context"""
        if not html:
            return "No attributes available"
        
        import re
        attributes = []
        
        # Extract class
        class_match = re.search(r'class=["\']([^"\']+)["\']', html)
        if class_match:
            attributes.append(f"class: {class_match.group(1)[:100]}")
        
        # Extract id
        id_match = re.search(r'id=["\']([^"\']+)["\']', html)
        if id_match:
            attributes.append(f"id: {id_match.group(1)}")
        
        # Extract type (for inputs)
        type_match = re.search(r'type=["\']([^"\']+)["\']', html)
        if type_match:
            attributes.append(f"type: {type_match.group(1)}")
        
        # Extract placeholder
        placeholder_match = re.search(r'placeholder=["\']([^"\']+)["\']', html)
        if placeholder_match:
            attributes.append(f"placeholder: {placeholder_match.group(1)[:50]}")
        
        # Extract aria-label
        aria_match = re.search(r'aria-label=["\']([^"\']+)["\']', html)
        if aria_match:
            attributes.append(f"aria-label: {aria_match.group(1)[:50]}")
        
        return "\n".join(attributes) if attributes else "Standard element"
    
    def _call_ollama_vision(self, prompt: str, image_base64: str) -> str:
        """Call Ollama vision API"""
        try:
            payload = {
                "model": self.model,
                "prompt": prompt,
                "images": [image_base64],
                "stream": False
            }
            
            response = requests.post(self.api_url, json=payload, timeout=60)
            response.raise_for_status()
            
            result = response.json()
            return result.get('response', '')
        except Exception as e:
            print(f"[ERROR] Ollama vision call failed: {e}")
            return ""


class OllamaLLM:
    """Interface for Ollama Text Models (Gemma3)"""
    
    def __init__(self, model: str = "gemma2:2b", base_url: str = "http://localhost:11434"):
        self.model = model
        self.base_url = base_url
        self.api_url = f"{base_url}/api/generate"
    
    def generate_action_description(self, action_type: str, details: Dict[str, Any]) -> str:
        """Generate natural language description of an action"""
        prompt = self._create_description_prompt(action_type, details)
        return self._call_ollama(prompt)
    
    def generate_report_summary(self, results: Dict[str, Any]) -> str:
        """Generate natural language summary of replay results"""
        # Handle dictionary input with summary data
        if isinstance(results, dict):
            total = results.get('total', 0)
            passed = results.get('successful', 0)
            failed = results.get('failed', 0)
            activities = results.get('activities', [])
        else:
            # Handle list input
            passed = sum(1 for r in results if r.get('status') == 'success')
            failed = len(results) - passed
            total = len(results)
            activities = results
        
        prompt = f"""Generate a concise summary report for a browser automation replay session:

Total actions: {total}
Successful: {passed}
Failed: {failed}

Actions performed:
{self._format_actions_for_summary(activities)}

Write a brief executive summary (2-3 sentences) describing what was accomplished."""
        
        return self._call_ollama(prompt)
    
    def suggest_alternative_selector(self, element_desc: Dict[str, Any]) -> List[str]:
        """Suggest alternative selectors for finding an element"""
        prompt = f"""Given this element description, suggest 3 alternative CSS selectors:
- Tag: {element_desc.get('tagName', 'unknown')}
- ID: {element_desc.get('id', '')}
- Classes: {element_desc.get('className', '')}
- Text: {element_desc.get('text', '')}
- Name: {element_desc.get('name', '')}

Provide 3 alternative CSS selectors, one per line, starting with 'SELECTOR:'"""
        
        response = self._call_ollama(prompt)
        
        # Parse selectors from response
        import re
        selectors = re.findall(r'SELECTOR:\s*(.+)', response)
        return selectors[:3] if selectors else []
    
    def _create_description_prompt(self, action_type: str, details: Dict[str, Any]) -> str:
        """Create prompt for action description"""
        if action_type == "click":
            text = details.get('text', 'element')
            tag = details.get('tagName', 'element')
            return f"Describe this user action in one sentence: User clicked on a {tag} element with text '{text}'"
        
        elif action_type == "text_input":
            value = details.get('value', '')
            label = details.get('label', 'field')
            return f"Describe this user action in one sentence: User typed '{value}' into {label} field"
        
        elif action_type == "navigation":
            url = details.get('url', '')
            return f"Describe this user action in one sentence: User navigated to {url}"
        
        return f"Describe this user action in one sentence: User performed {action_type}"
    
    def _format_actions_for_summary(self, results: List[Dict[str, Any]]) -> str:
        """Format actions for summary"""
        lines = []
        for i, result in enumerate(results[:10], 1):  # First 10 actions
            action = result.get('action', 'unknown')
            status = "✓" if result.get('status') == 'success' else "✗"
            desc = result.get('description', '')[:60]
            lines.append(f"{i}. {status} {action}: {desc}")
        
        if len(results) > 10:
            lines.append(f"... and {len(results) - 10} more actions")
        
        return "\n".join(lines)
    
    def _call_ollama(self, prompt: str) -> str:
        """Call Ollama text API"""
        try:
            payload = {
                "model": self.model,
                "prompt": prompt,
                "stream": False
            }
            
            response = requests.post(self.api_url, json=payload, timeout=30)
            response.raise_for_status()
            
            result = response.json()
            return result.get('response', '')
        except Exception as e:
            print(f"[ERROR] Ollama text call failed: {e}")
            return ""
