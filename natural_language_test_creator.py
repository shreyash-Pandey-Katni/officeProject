"""
Natural Language Test Creator
Converts plain English test descriptions into executable test scripts using Ollama + Granite

Example:
    Test: Login Flow
    
    1. Go to https://example.com
    2. Click the login button in header
    3. Enter email: test@example.com
    4. Enter password: Password123
    5. Click submit button
    6. Verify dashboard appears
    
    → Converts to executable activity_log.json
"""

from typing import Dict, List, Any, Optional
import requests
import json
import re
from dataclasses import dataclass


@dataclass
class TestStep:
    """Represents a single test step"""
    step_number: int
    action: str  # navigate, click, input, verify, wait
    description: str
    target: Optional[str] = None  # Element description
    value: Optional[str] = None  # Input value or verification criteria
    url: Optional[str] = None  # For navigation
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'step_number': self.step_number,
            'action': self.action,
            'description': self.description,
            'target': self.target,
            'value': self.value,
            'url': self.url
        }


@dataclass
class GeneratedTest:
    """Represents a complete generated test"""
    test_name: str
    test_description: str
    steps: List[TestStep]
    estimated_duration: int  # seconds
    confidence: float
    
    def to_activity_log(self) -> List[Dict[str, Any]]:
        """Convert to activity_log.json format"""
        activities = []
        
        for step in self.steps:
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
                        'tagName': 'BUTTON',  # Generic, will be found by VLM
                        'text': step.target,
                        'description': step.description,
                        'vlm_description': step.target  # Use VLM to find this
                    },
                    'locators': {
                        'text': step.target,
                        'description': step.target
                    }
                })
            
            elif step.action == 'input':
                activities.append({
                    'action': 'text_input',
                    'details': {
                        'tagName': 'INPUT',
                        'value': step.value,
                        'placeholder': step.target,
                        'description': step.description,
                        'vlm_description': step.target
                    },
                    'locators': {
                        'placeholder': step.target,
                        'description': step.target,
                        'value': step.value
                    }
                })
            
            elif step.action == 'verify':
                # Add as custom verification step
                activities.append({
                    'action': 'verification',
                    'details': {
                        'type': 'content_check',
                        'criteria': step.value,
                        'description': step.description
                    }
                })
            
            elif step.action == 'wait':
                activities.append({
                    'action': 'wait',
                    'details': {
                        'duration': 2,  # Default 2 seconds
                        'description': step.description
                    }
                })
        
        return activities


class NaturalLanguageTestCreator:
    """
    Converts natural language test descriptions to executable tests
    Uses Ollama + Granite for intelligent parsing
    """
    
    def __init__(
        self,
        ollama_url: str = "http://localhost:11434",
        model: str = "granite3.2-vision:latest"
    ):
        """
        Initialize the test creator
        
        Args:
            ollama_url: URL of Ollama API
            model: Model name to use
        """
        self.ollama_url = ollama_url
        self.model = model
        
        # Test connection
        try:
            response = requests.get(f"{ollama_url}/api/tags", timeout=2)
            if response.status_code == 200:
                print("[NL Test Creator] ✓ Connected to Ollama")
            else:
                print(f"[NL Test Creator] ⚠️  Ollama returned status {response.status_code}")
        except Exception as e:
            print(f"[NL Test Creator] ❌ Could not connect to Ollama: {e}")
            print("  Make sure Ollama is running: ollama serve")
            raise
    
    def create_test_from_description(
        self,
        test_description: str,
        test_name: Optional[str] = None
    ) -> GeneratedTest:
        """
        Generate executable test from natural language description
        
        Args:
            test_description: Plain English description of test
            test_name: Optional test name (extracted from description if not provided)
        
        Returns:
            GeneratedTest object with parsed steps
        """
        print(f"\n[NL Test Creator] Parsing test description...")
        
        # Build prompt for Ollama
        prompt = self._build_parsing_prompt(test_description)
        
        # Call Ollama
        response = self._call_ollama(prompt)
        
        # Parse response
        test = self._parse_ollama_response(response, test_description, test_name)
        
        print(f"[NL Test Creator] ✓ Generated test with {len(test.steps)} steps")
        print(f"[NL Test Creator] Confidence: {test.confidence:.2f}")
        
        return test
    
    def _build_parsing_prompt(self, test_description: str) -> str:
        """Build prompt for Ollama to parse test description"""
        return f"""You are a test automation expert. Parse this natural language test description into structured test steps.

Test Description:
{test_description}

Extract:
1. Test name (if mentioned)
2. Test description/purpose
3. Individual test steps with:
   - Action type: navigate, click, input, verify, wait
   - Target element description
   - Input value (if applicable)
   - URL (for navigation)

Output as JSON:
{{
  "test_name": "extracted or generated test name",
  "test_description": "what the test validates",
  "steps": [
    {{
      "step_number": 1,
      "action": "navigate",
      "description": "human readable step description",
      "url": "https://example.com"
    }},
    {{
      "step_number": 2,
      "action": "click",
      "description": "Click the login button",
      "target": "login button in header"
    }},
    {{
      "step_number": 3,
      "action": "input",
      "description": "Enter email address",
      "target": "email input field",
      "value": "test@example.com"
    }},
    {{
      "step_number": 4,
      "action": "verify",
      "description": "Verify dashboard appears",
      "value": "dashboard page is visible"
    }}
  ]
}}

Rules:
- For "Go to" → action: navigate
- For "Click" → action: click
- For "Enter/Type" → action: input
- For "Verify/Check/Ensure" → action: verify
- For "Wait" → action: wait
- Extract URLs from text
- Keep target descriptions natural (they'll be found by VLM)
- Output ONLY valid JSON, no extra text

JSON:"""
    
    def _call_ollama(self, prompt: str, timeout: int = 60) -> str:
        """Call Ollama API with prompt"""
        try:
            # Build payload for chat API (Ollama v0.12+)
            payload = {
                "model": self.model,
                "messages": [
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                "stream": False,
                "options": {
                    "temperature": 0.1,  # Low temperature for consistent parsing
                    "top_p": 0.9
                }
            }
            
            response = requests.post(
                f"{self.ollama_url}/api/chat",
                json=payload,
                timeout=timeout
            )
            
            response.raise_for_status()
            response_data = response.json()
            return response_data.get('message', {}).get('content', '')
            
        except Exception as e:
            print(f"[NL Test Creator] ❌ Ollama API error: {e}")
            raise
    
    def _parse_ollama_response(
        self,
        response: str,
        original_description: str,
        test_name: Optional[str]
    ) -> GeneratedTest:
        """Parse Ollama JSON response into GeneratedTest"""
        try:
            # Extract JSON from response (might have extra text)
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                json_str = json_match.group(0)
                data = json.loads(json_str)
            else:
                raise ValueError("No JSON found in response")
            
            # Extract test metadata
            test_name = test_name or data.get('test_name', 'Generated Test')
            test_desc = data.get('test_description', original_description)
            
            # Parse steps
            steps = []
            for step_data in data.get('steps', []):
                step = TestStep(
                    step_number=step_data.get('step_number', len(steps) + 1),
                    action=step_data.get('action', 'unknown'),
                    description=step_data.get('description', ''),
                    target=step_data.get('target'),
                    value=step_data.get('value'),
                    url=step_data.get('url')
                )
                steps.append(step)
            
            # Estimate duration (2 seconds per step + 5 second buffer)
            estimated_duration = len(steps) * 2 + 5
            
            # Calculate confidence based on parsing quality
            confidence = self._calculate_confidence(data, steps)
            
            return GeneratedTest(
                test_name=test_name,
                test_description=test_desc,
                steps=steps,
                estimated_duration=estimated_duration,
                confidence=confidence
            )
            
        except Exception as e:
            print(f"[NL Test Creator] ❌ Error parsing response: {e}")
            print(f"Response was: {response[:500]}")
            raise
    
    def _calculate_confidence(self, data: Dict, steps: List[TestStep]) -> float:
        """Calculate confidence score for generated test"""
        score = 1.0
        
        # Penalize if no test name
        if not data.get('test_name'):
            score -= 0.1
        
        # Penalize if no steps
        if not steps:
            score -= 0.5
        
        # Penalize if steps missing key info
        for step in steps:
            if step.action in ['click', 'input'] and not step.target:
                score -= 0.1
            if step.action == 'input' and not step.value:
                score -= 0.1
            if step.action == 'navigate' and not step.url:
                score -= 0.1
        
        return max(0.0, min(1.0, score))
    
    def save_test(
        self,
        test: GeneratedTest,
        output_file: str = "generated_test.json"
    ):
        """Save generated test to file"""
        activities = test.to_activity_log()
        
        with open(output_file, 'w') as f:
            json.dump(activities, f, indent=2)
        
        print(f"[NL Test Creator] ✓ Test saved to: {output_file}")
        print(f"[NL Test Creator] Activities: {len(activities)}")
    
    def print_test_summary(self, test: GeneratedTest):
        """Print human-readable test summary"""
        print(f"\n{'='*80}")
        print(f"Test: {test.test_name}")
        print(f"{'='*80}")
        print(f"Description: {test.test_description}")
        print(f"Steps: {len(test.steps)}")
        print(f"Estimated Duration: {test.estimated_duration}s")
        print(f"Confidence: {test.confidence:.2f}")
        print(f"\n{'='*80}")
        print(f"Test Steps:")
        print(f"{'='*80}\n")
        
        for step in test.steps:
            print(f"{step.step_number}. [{step.action.upper()}] {step.description}")
            if step.url:
                print(f"   → URL: {step.url}")
            if step.target:
                print(f"   → Target: {step.target}")
            if step.value:
                print(f"   → Value: {step.value}")
            print()


# Example usage and demo
def demo():
    """Demo the natural language test creator"""
    
    print("="*80)
    print("NATURAL LANGUAGE TEST CREATOR - DEMO")
    print("="*80)
    
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
    
    print("\n✓ Ollama is running")
    print("✓ Ready to create tests from natural language\n")
    
    # Example test description
    test_description = """
Test: User Login Flow

1. Go to https://example.com
2. Click the login button in top right corner
3. Enter email: test@example.com in the email field
4. Enter password: Password123 in the password field
5. Click the submit button
6. Verify dashboard appears with welcome message
7. Verify user name is displayed
"""
    
    print("="*80)
    print("Example Test Description:")
    print("="*80)
    print(test_description)
    
    # Create test creator
    creator = NaturalLanguageTestCreator()
    
    # Generate test
    print("\n" + "="*80)
    print("Generating Test...")
    print("="*80)
    
    test = creator.create_test_from_description(test_description)
    
    # Print summary
    creator.print_test_summary(test)
    
    # Save to file
    creator.save_test(test, "example_generated_test.json")
    
    print("="*80)
    print("Benefits:")
    print("="*80)
    print("✓ No code required - just write what you want to test")
    print("✓ AI extracts structure automatically")
    print("✓ VLM will find elements by description during execution")
    print("✓ 10x faster than manual test creation")
    print("✓ Non-technical team members can create tests")
    print("\n" + "="*80)
    print("To execute this test:")
    print("="*80)
    print("cp example_generated_test.json activity_log.json")
    print("python replay_browser_activities.py")
    print("="*80)


if __name__ == "__main__":
    demo()
