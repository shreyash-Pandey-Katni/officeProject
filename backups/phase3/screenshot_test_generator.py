"""
Test Generation from Screenshots
REVOLUTIONARY: Upload workflow screenshots, AI generates executable test script

This is the most powerful Phase 3 feature - non-technical users can create tests
by just capturing screenshots of their workflow!

Example:
    1. User records workflow with screenshots
    2. AI analyzes screenshots and generates test
    3. Test can be executed immediately
"""

from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
from pathlib import Path
import requests
import base64
import json
import re


@dataclass
class WorkflowStep:
    """Represents a single step in the workflow"""
    screenshot_number: int
    screenshot_path: str
    action: str  # navigate, click, input, verify
    description: str
    element_description: Optional[str] = None
    input_value: Optional[str] = None
    url: Optional[str] = None
    confidence: float = 0.0


@dataclass
class GeneratedTestFromScreenshots:
    """Complete test generated from screenshots"""
    test_name: str
    test_description: str
    workflow_steps: List[WorkflowStep]
    total_screenshots: int
    generation_confidence: float
    
    def to_activity_log(self) -> List[Dict[str, Any]]:
        """Convert to activity_log.json format"""
        activities = []
        
        for step in self.workflow_steps:
            if step.action == 'navigate':
                activities.append({
                    'action': 'navigation',
                    'details': {
                        'url': step.url,
                        'description': step.description
                    }
                })
            
            elif step.action == 'click':
                activities.append({
                    'action': 'click',
                    'details': {
                        'tagName': 'BUTTON',
                        'text': step.element_description,
                        'description': step.description,
                        'vlm_description': step.element_description
                    },
                    'locators': {
                        'text': step.element_description,
                        'description': step.element_description
                    }
                })
            
            elif step.action == 'input':
                activities.append({
                    'action': 'text_input',
                    'details': {
                        'tagName': 'INPUT',
                        'value': step.input_value,
                        'placeholder': step.element_description,
                        'description': step.description,
                        'vlm_description': step.element_description
                    },
                    'locators': {
                        'placeholder': step.element_description,
                        'description': step.element_description
                    }
                })
            
            elif step.action == 'verify':
                activities.append({
                    'action': 'verification',
                    'details': {
                        'type': 'content_check',
                        'criteria': step.description,
                        'description': step.description
                    }
                })
        
        return activities


class ScreenshotTestGenerator:
    """
    Generate executable tests from workflow screenshots
    Uses Ollama + Granite vision capabilities
    """
    
    def __init__(
        self,
        ollama_url: str = "http://localhost:11434",
        model: str = "granite3.1-dense:8b"
    ):
        """
        Initialize screenshot test generator
        
        Args:
            ollama_url: URL of Ollama API
            model: Model name to use (must support vision)
        """
        self.ollama_url = ollama_url
        self.model = model
        
        # Test connection
        try:
            response = requests.get(f"{ollama_url}/api/tags", timeout=2)
            if response.status_code == 200:
                print("[Screenshot Test Generator] ✓ Connected to Ollama")
            else:
                print(f"[Screenshot Test Generator] ⚠️  Ollama returned status {response.status_code}")
        except Exception as e:
            print(f"[Screenshot Test Generator] ❌ Could not connect to Ollama: {e}")
            print("  Make sure Ollama is running: ollama serve")
            raise
    
    def generate_test_from_screenshots(
        self,
        screenshot_paths: List[str],
        test_name: Optional[str] = None,
        annotations: Optional[List[str]] = None
    ) -> GeneratedTestFromScreenshots:
        """
        Generate test from a sequence of screenshots
        
        Args:
            screenshot_paths: List of screenshot file paths in workflow order
            test_name: Optional test name
            annotations: Optional annotations for each screenshot (user descriptions)
        
        Returns:
            GeneratedTestFromScreenshots with complete test
        """
        print(f"\n[Screenshot Test Generator] Analyzing {len(screenshot_paths)} screenshots...")
        
        if not screenshot_paths:
            raise ValueError("No screenshots provided")
        
        # Analyze workflow
        workflow_steps = self._analyze_workflow(screenshot_paths, annotations)
        
        # Generate test metadata
        test_name = test_name or self._generate_test_name(workflow_steps)
        test_description = self._generate_test_description(workflow_steps)
        
        # Calculate confidence
        confidence = self._calculate_generation_confidence(workflow_steps)
        
        test = GeneratedTestFromScreenshots(
            test_name=test_name,
            test_description=test_description,
            workflow_steps=workflow_steps,
            total_screenshots=len(screenshot_paths),
            generation_confidence=confidence
        )
        
        print(f"[Screenshot Test Generator] ✓ Generated test: {test_name}")
        print(f"[Screenshot Test Generator] Steps: {len(workflow_steps)}")
        print(f"[Screenshot Test Generator] Confidence: {confidence:.2f}")
        
        return test
    
    def _analyze_workflow(
        self,
        screenshot_paths: List[str],
        annotations: Optional[List[str]]
    ) -> List[WorkflowStep]:
        """Analyze screenshots to extract workflow steps"""
        
        # Load all screenshots
        screenshots = []
        for path in screenshot_paths:
            with open(path, 'rb') as f:
                screenshot_bytes = f.read()
            screenshots.append((path, screenshot_bytes))
        
        # Build analysis prompt
        prompt = self._build_workflow_analysis_prompt(len(screenshots), annotations)
        
        # Call VLM with all screenshots
        response = self._call_vlm_with_multiple_screenshots(screenshots, prompt)
        
        # Parse workflow steps
        workflow_steps = self._parse_workflow_response(response, screenshot_paths)
        
        return workflow_steps
    
    def _build_workflow_analysis_prompt(
        self,
        num_screenshots: int,
        annotations: Optional[List[str]]
    ) -> str:
        """Build prompt for workflow analysis"""
        
        annotation_section = ""
        if annotations:
            annotation_section = "\n\nUser Annotations:"
            for i, annotation in enumerate(annotations, 1):
                annotation_section += f"\nScreenshot {i}: {annotation}"
        
        return f"""You are a test automation expert. Analyze this sequence of {num_screenshots} screenshots showing a user workflow.

Task: Extract the test steps from these screenshots.{annotation_section}

For each screenshot transition, identify:
1. What action was performed (navigate, click, input, verify)
2. Which element was interacted with (describe it clearly)
3. What value was entered (if input)
4. What URL is shown (if navigation)

Output as JSON array:
[
  {{
    "screenshot_number": 1,
    "action": "navigate",
    "description": "User navigated to homepage",
    "url": "https://example.com",
    "confidence": 0.95
  }},
  {{
    "screenshot_number": 2,
    "action": "click",
    "description": "User clicked the search button",
    "element_description": "search button in top navigation bar",
    "confidence": 0.90
  }},
  {{
    "screenshot_number": 3,
    "action": "input",
    "description": "User entered search query",
    "element_description": "search input field",
    "input_value": "cloud computing",
    "confidence": 0.85
  }},
  {{
    "screenshot_number": 4,
    "action": "verify",
    "description": "Search results page appeared",
    "confidence": 0.90
  }}
]

Rules:
- Compare consecutive screenshots to determine actions
- For clicks: describe the element that was clicked
- For inputs: extract the text that was entered
- For navigation: extract the URL
- For verification: describe what should be validated
- Be specific about element descriptions (they'll be found by VLM)
- confidence: 0.0-1.0 based on how clear the action is

JSON:"""
    
    def _call_vlm_with_multiple_screenshots(
        self,
        screenshots: List[Tuple[str, bytes]],
        prompt: str,
        timeout: int = 120
    ) -> str:
        """Call Ollama VLM with multiple screenshots"""
        try:
            # Encode all screenshots
            screenshot_base64_list = []
            for path, screenshot_bytes in screenshots:
                screenshot_base64 = base64.standard_b64encode(screenshot_bytes).decode("utf-8")
                screenshot_base64_list.append(screenshot_base64)
                print(f"[Screenshot Test Generator] Loaded: {Path(path).name}")
            
            # Build payload with multiple images
            payload = {
                "model": self.model,
                "prompt": prompt,
                "images": screenshot_base64_list,  # Array of images
                "stream": False,
                "options": {
                    "temperature": 0.2,
                    "top_p": 0.9
                }
            }
            
            print(f"[Screenshot Test Generator] Analyzing workflow...")
            
            # Call Ollama
            response = requests.post(
                f"{self.ollama_url}/api/generate",
                json=payload,
                timeout=timeout
            )
            
            response.raise_for_status()
            response_data = response.json()
            return response_data.get('response', '')
            
        except Exception as e:
            print(f"[Screenshot Test Generator] ❌ VLM API error: {e}")
            raise
    
    def _parse_workflow_response(
        self,
        response: str,
        screenshot_paths: List[str]
    ) -> List[WorkflowStep]:
        """Parse VLM response into workflow steps"""
        try:
            # Extract JSON array from response
            json_match = re.search(r'\[.*\]', response, re.DOTALL)
            if json_match:
                json_str = json_match.group(0)
                data = json.loads(json_str)
            else:
                raise ValueError("No JSON array found in response")
            
            # Parse workflow steps
            workflow_steps = []
            for step_data in data:
                step = WorkflowStep(
                    screenshot_number=step_data.get('screenshot_number', len(workflow_steps) + 1),
                    screenshot_path=screenshot_paths[step_data.get('screenshot_number', 1) - 1]
                    if step_data.get('screenshot_number', 1) <= len(screenshot_paths)
                    else screenshot_paths[0],
                    action=step_data.get('action', 'unknown'),
                    description=step_data.get('description', ''),
                    element_description=step_data.get('element_description'),
                    input_value=step_data.get('input_value'),
                    url=step_data.get('url'),
                    confidence=step_data.get('confidence', 0.5)
                )
                workflow_steps.append(step)
            
            return workflow_steps
            
        except Exception as e:
            print(f"[Screenshot Test Generator] ❌ Error parsing response: {e}")
            print(f"Response was: {response[:500]}")
            raise
    
    def _generate_test_name(self, workflow_steps: List[WorkflowStep]) -> str:
        """Generate test name from workflow"""
        if not workflow_steps:
            return "Generated Test"
        
        # Extract key actions
        actions = [step.action for step in workflow_steps]
        has_login = any('login' in step.description.lower() for step in workflow_steps)
        has_search = any('search' in step.description.lower() for step in workflow_steps)
        has_form = any('input' in actions or 'form' in step.description.lower() for step in workflow_steps)
        
        if has_login:
            return "User Login Flow Test"
        elif has_search:
            return "Search Functionality Test"
        elif has_form:
            return "Form Submission Test"
        else:
            return f"Workflow Test ({len(workflow_steps)} steps)"
    
    def _generate_test_description(self, workflow_steps: List[WorkflowStep]) -> str:
        """Generate test description from workflow"""
        if not workflow_steps:
            return "Generated from screenshots"
        
        # Summarize workflow
        actions = [step.description for step in workflow_steps]
        return f"Test workflow: {' → '.join(actions[:3])}" + ("..." if len(actions) > 3 else "")
    
    def _calculate_generation_confidence(self, workflow_steps: List[WorkflowStep]) -> float:
        """Calculate overall confidence in generated test"""
        if not workflow_steps:
            return 0.0
        
        # Average confidence of all steps
        confidences = [step.confidence for step in workflow_steps]
        return sum(confidences) / len(confidences)
    
    def save_test(
        self,
        test: GeneratedTestFromScreenshots,
        output_file: str = "screenshot_generated_test.json"
    ):
        """Save generated test to file"""
        activities = test.to_activity_log()
        
        with open(output_file, 'w') as f:
            json.dump(activities, f, indent=2)
        
        print(f"[Screenshot Test Generator] ✓ Test saved to: {output_file}")
    
    def print_test_summary(self, test: GeneratedTestFromScreenshots):
        """Print human-readable test summary"""
        print(f"\n{'='*80}")
        print(f"Generated Test: {test.test_name}")
        print(f"{'='*80}")
        print(f"Description: {test.test_description}")
        print(f"Screenshots Analyzed: {test.total_screenshots}")
        print(f"Workflow Steps: {len(test.workflow_steps)}")
        print(f"Confidence: {test.generation_confidence:.2f}")
        
        print(f"\n{'='*80}")
        print(f"Workflow Steps:")
        print(f"{'='*80}\n")
        
        for step in test.workflow_steps:
            print(f"{step.screenshot_number}. [{step.action.upper()}] {step.description}")
            print(f"   Screenshot: {Path(step.screenshot_path).name}")
            if step.element_description:
                print(f"   Element: {step.element_description}")
            if step.input_value:
                print(f"   Value: {step.input_value}")
            if step.url:
                print(f"   URL: {step.url}")
            print(f"   Confidence: {step.confidence:.2f}")
            print()


# Demo
def demo():
    """Demo the screenshot test generator"""
    
    print("="*80)
    print("SCREENSHOT TEST GENERATOR - DEMO")
    print("="*80)
    print("\n⭐ REVOLUTIONARY FEATURE ⭐")
    print("Create tests by just capturing screenshots of your workflow!\n")
    
    # Check if Ollama is available
    try:
        response = requests.get("http://localhost:11434/api/tags", timeout=2)
        if response.status_code != 200:
            print("\n❌ Ollama is not running!")
            print("Please start Ollama: ollama serve")
            print("And ensure granite model is available: ollama pull granite3.1-dense:8b")
            return
    except:
        print("\n❌ Cannot connect to Ollama!")
        print("Please start Ollama: ollama serve")
        return
    
    print("✓ Ollama is running")
    print("✓ Ready to generate tests from screenshots\n")
    
    print("="*80)
    print("How to Use:")
    print("="*80)
    print("1. Capture screenshots of your workflow")
    print("2. Name them in order: 1_homepage.png, 2_clicked_search.png, etc.")
    print("3. Run this generator with your screenshots")
    print("4. Get executable test instantly!")
    
    print("\n" + "="*80)
    print("Example:")
    print("="*80)
    print("""
# Create test from workflow screenshots
generator = ScreenshotTestGenerator()

test = generator.generate_test_from_screenshots(
    screenshot_paths=[
        "screenshots/1_homepage.png",
        "screenshots/2_search_button_clicked.png",
        "screenshots/3_search_typed.png",
        "screenshots/4_results_page.png"
    ],
    annotations=[
        "Started at homepage",
        "Clicked search button in header",
        "Typed 'cloud computing' in search box",
        "Search results appeared"
    ]
)

generator.save_test(test, "my_test.json")
""")
    
    print("\n" + "="*80)
    print("Benefits:")
    print("="*80)
    print("✅ No coding required - just capture screenshots!")
    print("✅ Non-technical users can create tests")
    print("✅ AI extracts workflow automatically")
    print("✅ Instant test generation")
    print("✅ Perfect for documenting manual tests")
    print("✅ Can convert recorded sessions to automated tests")
    
    print("\n" + "="*80)
    print("To try with your own screenshots:")
    print("="*80)
    print("""
from screenshot_test_generator import ScreenshotTestGenerator

generator = ScreenshotTestGenerator()
test = generator.generate_test_from_screenshots(
    screenshot_paths=[
        "path/to/screenshot1.png",
        "path/to/screenshot2.png",
        "path/to/screenshot3.png"
    ]
)

generator.print_test_summary(test)
generator.save_test(test, "generated_test.json")

# Execute the test
# cp generated_test.json activity_log.json
# python replay_browser_activities.py
""")
    
    print("\n" + "="*80)


if __name__ == "__main__":
    demo()
