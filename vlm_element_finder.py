#!/usr/bin/env python3
"""
VLM-Based Element Finding Module
Uses Vision-Language Models to locate elements when traditional locators fail
"""

import os
import base64
import json
import requests
from typing import Dict, Any, Optional, Tuple, List
from dataclasses import dataclass
from datetime import datetime
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webelement import WebElement
from selenium.common.exceptions import NoSuchElementException
from PIL import Image
import io


@dataclass
class ElementContext:
    """Context information for element finding"""
    description: str
    visual_cues: List[str]
    nearby_elements: List[str]
    expected_properties: Dict[str, Any]
    screenshot_path: Optional[str] = None


@dataclass
class VLMFindResult:
    """Result from VLM element finding"""
    found: bool
    coordinates: Optional[Tuple[int, int]] = None
    bounding_box: Optional[Dict[str, int]] = None
    confidence: float = 0.0
    element_description: str = ""
    suggested_locator: Optional[Dict[str, str]] = None
    reasoning: str = ""
    timestamp: str = ""


class VLMElementFinder:
    """
    Uses Vision-Language Models to find elements when traditional methods fail.
    
    This is a revolutionary approach that makes tests resilient to UI changes
    by using visual understanding instead of brittle selectors.
    """
    
    def __init__(self, ollama_url: str = "http://localhost:11434", model: str = "granite3.1-dense:8b"):
        """
        Initialize VLM Element Finder using Ollama
        
        Args:
            ollama_url: Ollama API URL (default: http://localhost:11434)
            model: Ollama model to use (default: granite3.1-dense:8b)
        """
        self.ollama_url = ollama_url
        self.model = model
        self.cache_enabled = True
        self.response_cache: Dict[str, VLMFindResult] = {}
        
        # Test Ollama connection
        try:
            response = requests.get(f"{self.ollama_url}/api/tags", timeout=2)
            if response.status_code != 200:
                raise ValueError(f"Ollama not responding at {self.ollama_url}")
        except requests.exceptions.RequestException as e:
            raise ValueError(f"Cannot connect to Ollama at {self.ollama_url}. Is Ollama running? Error: {e}")
        
    def find_element_by_description(
        self,
        driver: WebDriver,
        description: str,
        visual_cues: Optional[List[str]] = None,
        nearby_elements: Optional[List[str]] = None,
        expected_properties: Optional[Dict[str, Any]] = None,
        screenshot_path: Optional[str] = None
    ) -> VLMFindResult:
        """
        Find element using VLM with natural language description
        
        Args:
            driver: Selenium WebDriver instance
            description: Human-readable description of element (e.g., "Search button")
            visual_cues: Visual hints (e.g., ["magnifying glass icon", "blue background"])
            nearby_elements: Nearby stable elements (e.g., ["IBM logo", "navigation bar"])
            expected_properties: Expected attributes (e.g., {"tag": "button", "text": "Search"})
            screenshot_path: Path to save screenshot (optional)
        
        Returns:
            VLMFindResult with coordinates, confidence, and suggested locator
        """
        context = ElementContext(
            description=description,
            visual_cues=visual_cues or [],
            nearby_elements=nearby_elements or [],
            expected_properties=expected_properties or {},
            screenshot_path=screenshot_path
        )
        
        # Capture screenshot
        screenshot_bytes = driver.get_screenshot_as_png()
        
        # Check cache
        cache_key = self._get_cache_key(screenshot_bytes, description)
        if self.cache_enabled and cache_key in self.response_cache:
            print("[VLM] Using cached result")
            return self.response_cache[cache_key]
        
        # Save screenshot if path provided
        if screenshot_path:
            with open(screenshot_path, 'wb') as f:
                f.write(screenshot_bytes)
        
        # Call VLM
        result = self._call_vlm_find_element(screenshot_bytes, context, driver)
        
        # Cache result
        if self.cache_enabled:
            self.response_cache[cache_key] = result
        
        return result
    
    def _call_vlm_find_element(
        self,
        screenshot_bytes: bytes,
        context: ElementContext,
        driver: WebDriver
    ) -> VLMFindResult:
        """Call VLM to find element in screenshot"""
        
        # Get viewport size for coordinate normalization
        viewport_width = driver.execute_script("return window.innerWidth")
        viewport_height = driver.execute_script("return window.innerHeight")
        
        # Build prompt
        prompt = self._build_find_prompt(context, viewport_width, viewport_height)
        
        # Encode screenshot
        screenshot_base64 = base64.standard_b64encode(screenshot_bytes).decode("utf-8")
        
        try:
            # Call Ollama with vision
            payload = {
                "model": self.model,
                "prompt": prompt,
                "images": [screenshot_base64],
                "stream": False
            }
            
            response = requests.post(
                f"{self.ollama_url}/api/generate",
                json=payload,
                timeout=60
            )
            
            if response.status_code != 200:
                raise Exception(f"Ollama API error: {response.status_code} - {response.text}")
            
            # Parse response
            response_data = response.json()
            response_text = response_data.get('response', '')
            
            result = self._parse_vlm_response(response_text, viewport_width, viewport_height)
            
            return result
            
        except Exception as e:
            print(f"[VLM] Error calling Ollama API: {e}")
            return VLMFindResult(
                found=False,
                reasoning=f"VLM API error: {str(e)}",
                timestamp=datetime.now().isoformat()
            )
    
    def _build_find_prompt(
        self,
        context: ElementContext,
        viewport_width: int,
        viewport_height: int
    ) -> str:
        """Build prompt for VLM element finding"""
        
        prompt = f"""You are analyzing a webpage screenshot to locate a specific element.

**Target Element:** {context.description}

**Viewport Size:** {viewport_width}x{viewport_height}

"""
        
        if context.visual_cues:
            prompt += "**Visual Cues:**\n"
            for cue in context.visual_cues:
                prompt += f"- {cue}\n"
            prompt += "\n"
        
        if context.nearby_elements:
            prompt += "**Nearby Elements (for reference):**\n"
            for element in context.nearby_elements:
                prompt += f"- {element}\n"
            prompt += "\n"
        
        if context.expected_properties:
            prompt += "**Expected Properties:**\n"
            for key, value in context.expected_properties.items():
                prompt += f"- {key}: {value}\n"
            prompt += "\n"
        
        prompt += """**Your Task:**
1. Locate the target element in the screenshot
2. Provide the center coordinates [x, y] in pixels
3. Provide the bounding box [x, y, width, height]
4. Rate your confidence (0.0 to 1.0)
5. Suggest the best CSS selector or XPath to find this element
6. Explain your reasoning

**Response Format (JSON):**
```json
{
  "found": true/false,
  "coordinates": [x, y],
  "bounding_box": {
    "x": int,
    "y": int,
    "width": int,
    "height": int
  },
  "confidence": 0.0-1.0,
  "element_description": "Detailed description of what you see",
  "suggested_locator": {
    "type": "css/xpath/id/class",
    "value": "selector string"
  },
  "reasoning": "Why you think this is the correct element"
}
```

**Important:**
- Coordinates must be within viewport bounds (0 to {viewport_width}, 0 to {viewport_height})
- Be precise with coordinates (center of clickable area)
- Only return found=true if you're confident (>0.7)
- Provide actionable selector in suggested_locator
"""
        
        return prompt
    
    def _parse_vlm_response(
        self,
        response_text: str,
        viewport_width: int,
        viewport_height: int
    ) -> VLMFindResult:
        """Parse VLM response into structured result"""
        
        try:
            # Extract JSON from response
            json_start = response_text.find('{')
            json_end = response_text.rfind('}') + 1
            
            if json_start == -1 or json_end == 0:
                raise ValueError("No JSON found in response")
            
            json_str = response_text[json_start:json_end]
            data = json.loads(json_str)
            
            # Validate coordinates
            coords = data.get('coordinates')
            if coords:
                coords = tuple(coords)
                # Clamp to viewport
                coords = (
                    max(0, min(coords[0], viewport_width)),
                    max(0, min(coords[1], viewport_height))
                )
            
            result = VLMFindResult(
                found=data.get('found', False),
                coordinates=coords,
                bounding_box=data.get('bounding_box'),
                confidence=float(data.get('confidence', 0.0)),
                element_description=data.get('element_description', ''),
                suggested_locator=data.get('suggested_locator'),
                reasoning=data.get('reasoning', ''),
                timestamp=datetime.now().isoformat()
            )
            
            return result
            
        except Exception as e:
            print(f"[VLM] Error parsing response: {e}")
            print(f"[VLM] Response: {response_text}")
            
            return VLMFindResult(
                found=False,
                reasoning=f"Failed to parse VLM response: {str(e)}",
                timestamp=datetime.now().isoformat()
            )
    
    def click_element_by_description(
        self,
        driver: WebDriver,
        description: str,
        **kwargs
    ) -> Tuple[bool, str]:
        """
        Find and click element using VLM
        
        Returns:
            (success: bool, message: str)
        """
        result = self.find_element_by_description(driver, description, **kwargs)
        
        if not result.found or not result.coordinates:
            return False, f"Element not found: {result.reasoning}"
        
        if result.confidence < 0.7:
            return False, f"Low confidence ({result.confidence:.2f}): {result.reasoning}"
        
        try:
            # Click at coordinates using JavaScript
            x, y = result.coordinates
            driver.execute_script(f"""
                var element = document.elementFromPoint({x}, {y});
                if (element) {{
                    element.click();
                }}
            """)
            
            return True, f"Clicked at ({x}, {y}) with confidence {result.confidence:.2f}"
            
        except Exception as e:
            return False, f"Click failed: {str(e)}"
    
    def verify_element_visible(
        self,
        driver: WebDriver,
        description: str,
        **kwargs
    ) -> Tuple[bool, float, str]:
        """
        Verify element is visible using VLM
        
        Returns:
            (visible: bool, confidence: float, message: str)
        """
        result = self.find_element_by_description(driver, description, **kwargs)
        
        return (
            result.found,
            result.confidence,
            result.element_description or result.reasoning
        )
    
    def get_element_properties(
        self,
        driver: WebDriver,
        description: str,
        **kwargs
    ) -> Optional[Dict[str, Any]]:
        """
        Get element properties using VLM
        
        Returns:
            Dictionary with element properties or None
        """
        result = self.find_element_by_description(driver, description, **kwargs)
        
        if not result.found:
            return None
        
        return {
            'description': result.element_description,
            'coordinates': result.coordinates,
            'bounding_box': result.bounding_box,
            'confidence': result.confidence,
            'suggested_locator': result.suggested_locator
        }
    
    def _get_cache_key(self, screenshot_bytes: bytes, description: str) -> str:
        """Generate cache key from screenshot and description"""
        import hashlib
        screenshot_hash = hashlib.sha256(screenshot_bytes).hexdigest()[:16]
        desc_hash = hashlib.sha256(description.encode()).hexdigest()[:16]
        return f"{screenshot_hash}_{desc_hash}"
    
    def clear_cache(self):
        """Clear response cache"""
        self.response_cache.clear()


def demo():
    """Demo VLM element finding"""
    print("\n" + "="*80)
    print("VLM ELEMENT FINDER - DEMO (Ollama + Granite)")
    print("="*80 + "\n")
    
    # Check for Ollama
    try:
        response = requests.get("http://localhost:11434/api/tags", timeout=2)
        if response.status_code == 200:
            print("✓ Ollama is running")
            print(f"✓ Model: granite3.1-dense:8b")
        else:
            print("❌ Ollama not responding")
            print("\nTo use VLM features:")
            print("  1. Install Ollama: https://ollama.ai/")
            print("  2. Pull model: ollama pull granite3.1-dense:8b")
            print("  3. Start Ollama: ollama serve")
            return
    except requests.exceptions.RequestException:
        print("❌ Ollama not running")
        print("\nTo use VLM features:")
        print("  1. Install Ollama: https://ollama.ai/")
        print("  2. Pull model: ollama pull granite3.1-dense:8b")
        print("  3. Start Ollama: ollama serve")
        return
    
    print("\n" + "-"*80)
    print("Example Usage:")
    print("-"*80 + "\n")
    
    example_code = '''
from selenium import webdriver
from vlm_element_finder import VLMElementFinder

# Setup (Ollama must be running with granite3.1-dense:8b)
driver = webdriver.Chrome()
vlm = VLMElementFinder()  # Uses localhost:11434 by default

# Navigate to page
driver.get("https://www.ibm.com")

# Find element with natural language description
result = vlm.find_element_by_description(
    driver,
    description="Search button",
    visual_cues=["magnifying glass icon", "top right corner"],
    nearby_elements=["IBM logo", "navigation menu"],
    expected_properties={"tag": "button", "aria-label": "Search"}
)

if result.found:
    print(f"✓ Found at: {result.coordinates}")
    print(f"  Confidence: {result.confidence:.2%}")
    print(f"  Description: {result.element_description}")
    print(f"  Suggested selector: {result.suggested_locator}")
    
    # Click using VLM
    success, message = vlm.click_element_by_description(
        driver,
        "Search button"
    )
    print(f"Click result: {message}")
else:
    print(f"✗ Not found: {result.reasoning}")
'''
    
    print(example_code)
    
    print("\n" + "-"*80)
    print("Benefits:")
    print("-"*80 + "\n")
    
    benefits = [
        "✓ Tests survive UI redesigns (IDs/classes can change)",
        "✓ Works across localized versions (language-independent)",
        "✓ Handles dynamic UIs (A/B tests, personalization)",
        "✓ More human-like element finding",
        "✓ Self-documenting (descriptions are readable)",
        "✓ Automatic locator suggestions (updates test code)"
    ]
    
    for benefit in benefits:
        print(f"  {benefit}")
    
    print("\n" + "-"*80)
    print("Use Cases:")
    print("-"*80 + "\n")
    
    use_cases = [
        "1. Fallback when traditional locators fail",
        "2. Testing redesigned/refactored pages",
        "3. Cross-language testing (same UI, different text)",
        "4. Testing custom web components",
        "5. Self-healing test automation",
        "6. Visual element verification"
    ]
    
    for use_case in use_cases:
        print(f"  {use_case}")
    
    print("\n" + "="*80 + "\n")


if __name__ == "__main__":
    demo()
