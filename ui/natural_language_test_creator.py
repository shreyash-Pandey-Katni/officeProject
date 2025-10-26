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
        model: str = "granite4:tiny-h"
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
        return f"""You are an expert test automation parser. STRICTLY extract structured test steps ONLY from the user's description.

User Description (verbatim):
<<<BEGIN_DESCRIPTION>>>
{test_description}
<<<END_DESCRIPTION>>>

Your job: Transform ONLY the information explicitly present (or trivially implied in a single line) into a normalized JSON structure. DO NOT:
- Invent steps, data, credentials, generic 'login' or 'dashboard' flows
- Add example.com or placeholder URLs unless they appear exactly
- Fabricate email/password/sample values
- Reorder steps unless a line clearly contains multiple sequential actions (then split preserving order)

Actions allowed: navigate, click, input, verify, wait

Mapping rules:
- Lines starting with / containing: "Go to", "Open", URL → navigate (include exact URL if present)
- "Click", "Press", "Select" → click
- "Enter", "Type", "Fill" → input (value is the literal text provided after a separator like ':', 'as', or 'with')
- "Verify", "Check", "Ensure", "Assert" → verify (value = the verification phrase)
- Explicit waits (e.g. 'wait 5 seconds') → wait (duration not required; just describe)
- If a single line mixes multiple actions (e.g. "Enter email then click submit") split into two consecutive steps maintaining order

Target field:
- For click/input: concise natural description of the element (reuse phrasing from the line; do not generalize)
- For verify: omit target; put assertion text in value

Value field:
- For input: the exact text/value provided by user in the line (do not guess if absent)
- For verify: the exact expected condition phrase

Test name:
- If a line explicitly declares a test name (e.g. starts with 'Test:'), use that (trim 'Test:' prefix)
- Else derive a concise snake_case name from the first meaningful action phrase (max 5 words)

Test description:
- One short sentence summarizing the overall purpose using ONLY concepts present

Output Schema (NO sample/hardcoded business data):
{{
    "test_name": string,
    "test_description": string,
    "steps": [
        {{
            "step_number": 1,
            "action": "navigate|click|input|verify|wait",
            "description": "concise natural language restatement of the step",
            "target": "element description if click/input else null or omit",
            "value": "input value or verification criteria if applicable",
            "url": "only if navigate and explicit URL present"
        }}
    ]
}}

STRICT OUTPUT REQUIREMENTS:
- Output ONLY valid JSON (no markdown, no prose, no backticks)
- step_number must start at 1 and increment by 1 without gaps
- Do not include fields with null if you prefer to omit them; but never invent content
- If the description provides fewer details than the schema allows, leave those fields out

If the user description contains zero actionable steps, return an empty steps array with a reasonable test_name.

Return JSON now:
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
            print(f"[NL Test Creator] Raw Ollama response length: {len(response)} chars")
            print(f"[NL Test Creator] Raw Ollama response preview: {response[:500]}")
            
            # Extract JSON from response (might have extra text)
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                json_str = json_match.group(0)
                print(f"[NL Test Creator] Extracted JSON: {json_str[:500]}")
                data = json.loads(json_str)
                print(f"[NL Test Creator] Parsed JSON keys: {list(data.keys())}")
            else:
                print(f"[NL Test Creator] ⚠️ No JSON pattern found in response")
                raise ValueError("No JSON found in response")
            
            # Extract test metadata
            test_name = test_name or data.get('test_name', 'Generated Test')
            test_desc = data.get('test_description', original_description)
            
            # Parse steps with defensive checks
            raw_steps = data.get('steps')
            print(f"[NL Test Creator] Raw steps from JSON: {raw_steps}")
            
            if raw_steps is None:
                print("[NL Test Creator] ⚠️ 'steps' key missing in model response")
                # Try to extract from description as fallback
                raw_steps = self._extract_steps_heuristically(original_description)
                print(f"[NL Test Creator] Heuristic extraction produced {len(raw_steps)} steps")
                
            if not isinstance(raw_steps, list):
                print(f"[NL Test Creator] ⚠️ 'steps' is not a list (type={type(raw_steps)})")
                raw_steps = []

            steps: List[TestStep] = []
            for step_data in raw_steps:
                # Normalize/repair URL for navigation steps if missing or domain-only
                url_value = step_data.get('url')
                if step_data.get('action') == 'navigate':
                    if not url_value:
                        desc_text = step_data.get('description', '')
                        # Prefer quoted content first
                        quoted_match = re.search(r'"([^"]+)"', desc_text) or re.search(r"'([^']+)'", desc_text)
                        candidate = None
                        if quoted_match:
                            candidate = quoted_match.group(1).strip()
                        else:
                            # Match domains with multi-level TLDs and common TLD set; allow optional path/query after first space
                            # Examples: sub.domain.co.uk, app.service.internal, portal.company.cloud, foo.bar.dev
                            domain_pattern = r"\b([a-zA-Z0-9.-]+\.(?:com|net|org|io|dev|app|cloud|co\.uk|co\.in|ai|tech|solutions|cloudflare))(?:/[^\s'\"]*)?\b"
                            domain_match = re.search(domain_pattern, desc_text)
                            if domain_match:
                                candidate = domain_match.group(0).strip()
                                # Lowercase host portion (before first /)
                                if '/' in candidate:
                                    host, rest = candidate.split('/', 1)
                                    candidate = host.lower() + '/' + rest
                                else:
                                    candidate = candidate.lower()
                                # Remove trailing punctuation if any
                                candidate = candidate.rstrip('.,)')
                        if candidate:
                            if not candidate.lower().startswith(('http://', 'https://')):
                                candidate = f'https://{candidate}'
                            url_value = candidate
                    else:
                        if url_value and not url_value.lower().startswith(('http://', 'https://')):
                            url_value = f'https://{url_value}'
                
                step = TestStep(
                    step_number=step_data.get('step_number', len(steps) + 1),
                    action=step_data.get('action', 'unknown'),
                    description=step_data.get('description', ''),
                    target=step_data.get('target'),
                    value=step_data.get('value'),
                    url=url_value
                )
                steps.append(step)
            before_post = len(steps)
            steps = self._post_process_steps(steps, original_description)
            after_post = len(steps)
            print(f"[NL Test Creator] Post-processing steps: before={before_post} after={after_post}")
            
            # Estimate duration (2 seconds per step + 5 second buffer)
            estimated_duration = len(steps) * 2 + 5
            
            # Calculate confidence based on parsing quality
            confidence = self._calculate_confidence(data, steps)
            
            return GeneratedTest(
                test_name=test_name or "generated_test",
                test_description=test_desc,
                steps=steps,
                estimated_duration=estimated_duration,
                confidence=confidence
            )
            
        except Exception as e:
            print(f"[NL Test Creator] ❌ Error parsing response: {e}")
            print(f"Response was: {response[:500]}")
            raise

    def _post_process_steps(self, steps: List[TestStep], original_description: str) -> List[TestStep]:
        """Improve model output: ensure verification + conditional click separation and clean targets.

        Rules implemented:
        - If a click step's description contains patterns like 'check if'/'if' with a quoted string earlier, insert a preceding verification step.
        - Remove artificial suffix ' text' from targets when quoted value exists (e.g., 'store text' -> 'store').
        - Avoid duplicate insertion if a verification for same criteria already immediately precedes.
        """
        processed: List[TestStep] = []
        # Build set of existing verification criteria to avoid duplicates
        existing_verifications = set()
        for s in steps:
            if s.action == 'verification' and s.value:
                existing_verifications.add(s.value.lower())

        for step in steps:
            # Clean target suffix
            if step.target and step.target.lower().endswith(' text'):
                # If there's a quoted string in description or original description containing the base part
                base = step.target[:-5].strip()
                if base:
                    step.target = base
                    if step.action == 'click':
                        # Also adjust description and value references
                        if 'store text' in step.description.lower() and base.lower() == 'store':
                            step.description = re.sub(r'store text', 'store', step.description, flags=re.IGNORECASE)
            # Split combined verification + click
            if step.action == 'click':
                desc_lower = step.description.lower()
                # Look for pattern of conditional click
                combined_pattern = re.compile(r'(check if|if)\s+"([^"]+)".*?click', re.IGNORECASE)
                match = combined_pattern.search(step.description) or combined_pattern.search(original_description)
                if match:
                    criteria = match.group(2).strip()
                    # Create verification step if not already preceding
                    prev = processed[-1] if processed else None
                    already = prev and prev.action == 'verification' and (prev.value or prev.target or prev.description).lower().find(criteria.lower()) != -1
                    if not already and criteria.lower() not in existing_verifications:
                        verification_step = TestStep(
                            step_number=step.step_number,  # Will renumber later
                            action='verification',
                            description=f'Verify "{criteria}" is present',
                            target=None,
                            value=criteria,
                            url=None
                        )
                        print(f"[NL Test Creator] Inserting verification step for conditional criteria: {criteria}")
                        processed.append(verification_step)
                        existing_verifications.add(criteria.lower())
                    # Ensure click step target uses criteria only
                    if criteria and (not step.target or criteria.lower() in step.target.lower()):
                        step.target = criteria
                        # Optionally refine description
                        if 'click' in desc_lower and 'store text' in desc_lower and criteria.lower() == 'store':
                            step.description = re.sub(r'store text', 'store', step.description, flags=re.IGNORECASE)
            processed.append(step)

        # Renumber steps sequentially
        for i, s in enumerate(processed, 1):
            s.step_number = i
        return processed
    
    def _extract_steps_heuristically(self, description: str) -> List[Dict[str, Any]]:
        """Fallback heuristic extraction when model fails to return steps"""
        print("[NL Test Creator] Attempting heuristic step extraction...")
        steps = []
        step_num = 1
        
        # Split by newlines and numbered lists
        lines = description.strip().split('\n')
        
        for line in lines:
            line = line.strip()
            if not line or line.startswith('#') or line.lower().startswith('test:'):
                continue
            
            # Remove leading numbers/bullets
            line = re.sub(r'^\d+[\.)]\s*', '', line)
            line = re.sub(r'^[-*]\s*', '', line)
            
            if not line:
                continue
            
            # Detect action type
            action = 'unknown'
            target = None
            value = None
            url = None
            
            line_lower = line.lower()
            
            # Navigation
            if any(kw in line_lower for kw in ['go to', 'open', 'navigate', 'visit']):
                action = 'navigate'
                # Extract URL
                url_match = re.search(r'https?://[^\s]+', line)
                if url_match:
                    url = url_match.group(0)
                else:
                    # Look for quoted or domain-like strings
                    quoted = re.search(r'"([^"]+)"', line) or re.search(r"'([^']+)'", line)
                    if quoted:
                        candidate = quoted.group(1)
                        if '.' in candidate:
                            url = f"https://{candidate}" if not candidate.startswith('http') else candidate
            
            # Click
            elif any(kw in line_lower for kw in ['click', 'press', 'select', 'tap']):
                action = 'click'
                # Extract target
                quoted = re.search(r'"([^"]+)"', line) or re.search(r"'([^']+)'", line)
                if quoted:
                    target = quoted.group(1)
                else:
                    # Extract after "on" or "the"
                    match = re.search(r'(?:on|the)\s+(.+?)(?:\s+button|\s+link|$)', line, re.IGNORECASE)
                    if match:
                        target = match.group(1).strip()
            
            # Input
            elif any(kw in line_lower for kw in ['enter', 'type', 'fill', 'input']):
                action = 'input'
                # Extract value (after colon or quoted)
                quoted = re.search(r'"([^"]+)"', line) or re.search(r"'([^']+)'", line)
                if quoted:
                    value = quoted.group(1)
                else:
                    colon_match = re.search(r':\s*(.+?)(?:\s+in|\s+to|$)', line)
                    if colon_match:
                        value = colon_match.group(1).strip()
                
                # Extract target (field description)
                field_match = re.search(r'(?:in|to|into)\s+(?:the\s+)?(.+?)(?:\s+field|$)', line, re.IGNORECASE)
                if field_match:
                    target = field_match.group(1).strip()
            
            # Verify
            elif any(kw in line_lower for kw in ['verify', 'check', 'assert', 'ensure', 'confirm']):
                action = 'verify'
                # Extract criteria
                quoted = re.search(r'"([^"]+)"', line) or re.search(r"'([^']+)'", line)
                if quoted:
                    value = quoted.group(1)
                else:
                    # Extract after "that" or "if"
                    match = re.search(r'(?:that|if)\s+(.+)', line, re.IGNORECASE)
                    if match:
                        value = match.group(1).strip()
            
            # Wait
            elif 'wait' in line_lower:
                action = 'wait'
            
            if action != 'unknown':
                steps.append({
                    'step_number': step_num,
                    'action': action,
                    'description': line,
                    'target': target,
                    'value': value,
                    'url': url
                })
                step_num += 1
        
        print(f"[NL Test Creator] Heuristic extraction found {len(steps)} steps")
        return steps

    
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
    except Exception:
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
