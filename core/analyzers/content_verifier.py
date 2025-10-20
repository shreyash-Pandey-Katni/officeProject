"""
Content Verification Module
Uses VLM to verify page content quality, relevance, and layout correctness

Features:
- Content relevance checking
- Layout validation
- Error detection
- Visual quality assessment
- Completeness verification
"""

from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
import requests
import base64
from selenium import webdriver


class VerificationStatus(Enum):
    """Verification result status"""
    PASS = "pass"
    FAIL = "fail"
    WARNING = "warning"


class IssueType(Enum):
    """Types of issues that can be detected"""
    BROKEN_LAYOUT = "broken_layout"
    MISSING_CONTENT = "missing_content"
    ERROR_MESSAGE = "error_message"
    LOW_CONTRAST = "low_contrast"
    BROKEN_IMAGE = "broken_image"
    MISALIGNED_ELEMENT = "misaligned_element"
    IRRELEVANT_CONTENT = "irrelevant_content"
    INCOMPLETE_PAGE = "incomplete_page"


@dataclass
class ContentIssue:
    """Represents a detected content issue"""
    issue_type: IssueType
    severity: VerificationStatus  # WARNING or FAIL
    message: str
    location: Optional[str] = None
    confidence: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'type': self.issue_type.value,
            'severity': self.severity.value,
            'message': self.message,
            'location': self.location,
            'confidence': self.confidence
        }


@dataclass
class ContentVerificationResult:
    """Complete verification result"""
    status: VerificationStatus
    relevance_score: float  # 0.0-1.0
    layout_correct: bool
    issues: List[ContentIssue]
    visual_quality_score: float  # 0.0-1.0
    completeness_score: float  # 0.0-1.0
    overall_score: float  # 0.0-1.0
    analysis: str  # Detailed analysis from VLM
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'status': self.status.value,
            'relevance_score': self.relevance_score,
            'layout_correct': self.layout_correct,
            'issues': [issue.to_dict() for issue in self.issues],
            'visual_quality_score': self.visual_quality_score,
            'completeness_score': self.completeness_score,
            'overall_score': self.overall_score,
            'analysis': self.analysis
        }


class ContentVerifier:
    """
    Verify page content quality using VLM
    Uses Ollama + Granite for intelligent content analysis
    """
    
    def __init__(
        self,
        ollama_url: str = "http://localhost:11434",
        model: str = "granite3.2-vision:latest"
    ):
        """
        Initialize content verifier
        
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
                print("[Content Verifier] ✓ Connected to Ollama")
            else:
                print(f"[Content Verifier] ⚠️  Ollama returned status {response.status_code}")
        except Exception as e:
            print(f"[Content Verifier] ❌ Could not connect to Ollama: {e}")
            print("  Make sure Ollama is running: ollama serve")
            raise
    
    def verify_page_content(
        self,
        driver: webdriver.Chrome,
        expected_content: str,
        page_context: Optional[str] = None,
        screenshot_path: Optional[str] = None
    ) -> ContentVerificationResult:
        """
        Verify page content meets expectations
        
        Args:
            driver: Selenium WebDriver instance
            expected_content: What should be on the page (e.g., "search results for cloud computing")
            page_context: Additional context about the page
            screenshot_path: Optional path to save screenshot
        
        Returns:
            ContentVerificationResult with detailed analysis
        """
        print(f"[Content Verifier] Verifying: {expected_content}")
        
        # Capture screenshot
        screenshot_bytes = driver.get_screenshot_as_png()
        
        # Save if path provided
        if screenshot_path:
            with open(screenshot_path, 'wb') as f:
                f.write(screenshot_bytes)
        
        # Get page URL and title for context
        page_url = driver.current_url
        page_title = driver.title
        
        # Build verification prompt
        prompt = self._build_verification_prompt(
            expected_content,
            page_url,
            page_title,
            page_context
        )
        
        # Call VLM
        response = self._call_vlm(screenshot_bytes, prompt)
        
        # Parse response
        result = self._parse_verification_response(response)
        
        print(f"[Content Verifier] Status: {result.status.value.upper()}")
        print(f"[Content Verifier] Overall Score: {result.overall_score:.2f}")
        
        if result.issues:
            print(f"[Content Verifier] Issues Found: {len(result.issues)}")
            for issue in result.issues[:3]:  # Show first 3
                print(f"  • [{issue.severity.value}] {issue.message}")
        
        return result
    
    def verify_search_results(
        self,
        driver: webdriver.Chrome,
        query: str,
        min_results: int = 1
    ) -> ContentVerificationResult:
        """
        Verify search results page
        
        Args:
            driver: Selenium WebDriver
            query: Search query that was executed
            min_results: Minimum expected results
        
        Returns:
            ContentVerificationResult
        """
        return self.verify_page_content(
            driver=driver,
            expected_content=f"search results for query '{query}' with at least {min_results} relevant results",
            page_context=f"User searched for: {query}"
        )
    
    def verify_form_page(
        self,
        driver: webdriver.Chrome,
        form_fields: List[str]
    ) -> ContentVerificationResult:
        """
        Verify form page has all required fields
        
        Args:
            driver: Selenium WebDriver
            form_fields: List of required field names
        
        Returns:
            ContentVerificationResult
        """
        fields_str = ", ".join(form_fields)
        return self.verify_page_content(
            driver=driver,
            expected_content=f"form with fields: {fields_str}",
            page_context="User is on a form page"
        )
    
    def verify_dashboard(
        self,
        driver: webdriver.Chrome,
        expected_widgets: List[str]
    ) -> ContentVerificationResult:
        """
        Verify dashboard page
        
        Args:
            driver: Selenium WebDriver
            expected_widgets: List of expected dashboard widgets/sections
        
        Returns:
            ContentVerificationResult
        """
        widgets_str = ", ".join(expected_widgets)
        return self.verify_page_content(
            driver=driver,
            expected_content=f"dashboard with sections: {widgets_str}",
            page_context="User logged in and viewing dashboard"
        )
    
    def _build_verification_prompt(
        self,
        expected_content: str,
        page_url: str,
        page_title: str,
        page_context: Optional[str]
    ) -> str:
        """Build prompt for VLM content verification"""
        
        context_line = f"\nContext: {page_context}" if page_context else ""
        
        return f"""You are a quality assurance expert analyzing a webpage screenshot.

Page URL: {page_url}
Page Title: {page_title}
Expected Content: {expected_content}{context_line}

Analyze the screenshot and verify:

1. **Content Relevance** (0.0-1.0):
   - Does the page content match what's expected?
   - Is the content relevant and appropriate?

2. **Layout Correctness** (true/false):
   - Is the layout correct and complete?
   - Are all major sections visible?
   - Is the page fully loaded?

3. **Visual Quality** (0.0-1.0):
   - Does the page look professional?
   - Are images loading correctly?
   - Is text readable?

4. **Completeness** (0.0-1.0):
   - Is the page fully rendered?
   - Are there any loading indicators or spinners?
   - Is any content obviously missing?

5. **Issues**:
   - List any problems (broken layout, error messages, missing content, etc.)
   - Classify severity as "warning" or "fail"
   - Provide specific location if possible

Output as JSON:
{{
  "relevance_score": 0.95,
  "layout_correct": true,
  "visual_quality_score": 0.90,
  "completeness_score": 0.95,
  "issues": [
    {{
      "type": "low_contrast",
      "severity": "warning",
      "message": "Footer text has low contrast",
      "location": "bottom footer",
      "confidence": 0.85
    }}
  ],
  "analysis": "Detailed analysis of the page..."
}}

Rules:
- relevance_score: 1.0 = perfect match, 0.0 = completely wrong
- layout_correct: false if anything looks broken
- visual_quality_score: 1.0 = professional, 0.0 = broken
- completeness_score: 1.0 = fully loaded, 0.0 = empty/loading
- issues: array of problems found (empty if none)
- analysis: 2-3 sentence summary

JSON:"""
    
    def _call_vlm(
        self,
        screenshot_bytes: bytes,
        prompt: str,
        timeout: int = 60
    ) -> str:
        """Call Ollama VLM with screenshot and prompt"""
        try:
            # Encode screenshot
            screenshot_base64 = base64.standard_b64encode(screenshot_bytes).decode("utf-8")
            
            # Build payload for chat API (Ollama v0.12+)
            payload = {
                "model": self.model,
                "messages": [
                    {
                        "role": "user",
                        "content": prompt,
                        "images": [screenshot_base64]
                    }
                ],
                "stream": False,
                "options": {
                    "temperature": 0.2,
                    "top_p": 0.9
                }
            }
            
            # Call Ollama chat API
            response = requests.post(
                f"{self.ollama_url}/api/chat",
                json=payload,
                timeout=timeout
            )
            
            response.raise_for_status()
            response_data = response.json()
            return response_data.get('message', {}).get('content', '')
            
        except Exception as e:
            print(f"[Content Verifier] ❌ VLM API error: {e}")
            raise
    
    def _parse_verification_response(self, response: str) -> ContentVerificationResult:
        """Parse VLM response into ContentVerificationResult"""
        import json
        import re
        
        try:
            # Extract JSON from response
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                json_str = json_match.group(0)
                data = json.loads(json_str)
            else:
                raise ValueError("No JSON found in response")
            
            # Extract scores
            relevance = data.get('relevance_score', 0.5)
            layout_correct = data.get('layout_correct', True)
            visual_quality = data.get('visual_quality_score', 0.5)
            completeness = data.get('completeness_score', 0.5)
            analysis = data.get('analysis', '')
            
            # Parse issues
            issues = []
            for issue_data in data.get('issues', []):
                try:
                    issue_type = IssueType(issue_data.get('type', 'broken_layout'))
                except ValueError:
                    issue_type = IssueType.BROKEN_LAYOUT
                
                try:
                    severity = VerificationStatus(issue_data.get('severity', 'warning'))
                except ValueError:
                    severity = VerificationStatus.WARNING
                
                issue = ContentIssue(
                    issue_type=issue_type,
                    severity=severity,
                    message=issue_data.get('message', ''),
                    location=issue_data.get('location'),
                    confidence=issue_data.get('confidence', 0.0)
                )
                issues.append(issue)
            
            # Calculate overall score
            overall_score = (relevance + visual_quality + completeness) / 3.0
            if not layout_correct:
                overall_score *= 0.7  # Penalize broken layout
            
            # Determine status
            fail_issues = [i for i in issues if i.severity == VerificationStatus.FAIL]
            if fail_issues or overall_score < 0.5:
                status = VerificationStatus.FAIL
            elif issues or overall_score < 0.8:
                status = VerificationStatus.WARNING
            else:
                status = VerificationStatus.PASS
            
            return ContentVerificationResult(
                status=status,
                relevance_score=relevance,
                layout_correct=layout_correct,
                issues=issues,
                visual_quality_score=visual_quality,
                completeness_score=completeness,
                overall_score=overall_score,
                analysis=analysis
            )
            
        except Exception as e:
            print(f"[Content Verifier] ❌ Error parsing response: {e}")
            print(f"Response was: {response[:500]}")
            
            # Return failed verification
            return ContentVerificationResult(
                status=VerificationStatus.FAIL,
                relevance_score=0.0,
                layout_correct=False,
                issues=[ContentIssue(
                    issue_type=IssueType.BROKEN_LAYOUT,
                    severity=VerificationStatus.FAIL,
                    message=f"Failed to verify content: {e}",
                    confidence=1.0
                )],
                visual_quality_score=0.0,
                completeness_score=0.0,
                overall_score=0.0,
                analysis="Verification failed"
            )


# Demo
def demo():
    """Demo the content verifier"""
    from selenium import webdriver
    
    print("="*80)
    print("CONTENT VERIFICATION - DEMO")
    print("="*80)
    
    # Check if Ollama is available
    try:
        response = requests.get("http://localhost:11434/api/tags", timeout=2)
        if response.status_code != 200:
            print("\n❌ Ollama is not running!")
            print("Please start Ollama: ollama serve")
            return
    except:
        print("\n❌ Cannot connect to Ollama!")
        print("Please start Ollama: ollama serve")
        return
    
    print("\n✓ Ollama is running")
    print("✓ Starting content verification demo\n")
    
    # Create verifier
    verifier = ContentVerifier()
    
    # Launch browser
    print("Launching browser...")
    options = webdriver.ChromeOptions()
    options.add_argument("--start-maximized")
    driver = webdriver.Chrome(options=options)
    
    try:
        # Navigate to example page
        print("Navigating to IBM website...")
        driver.get("https://www.ibm.com")
        
        import time
        time.sleep(3)  # Wait for page load
        
        # Verify homepage content
        print("\n" + "="*80)
        print("Verifying Homepage Content...")
        print("="*80)
        
        result = verifier.verify_page_content(
            driver=driver,
            expected_content="IBM homepage with navigation menu, hero section, and product information",
            page_context="User navigated to IBM homepage"
        )
        
        # Print results
        print(f"\n{'='*80}")
        print(f"Verification Results:")
        print(f"{'='*80}")
        print(f"Status: {result.status.value.upper()}")
        print(f"Overall Score: {result.overall_score:.2f}")
        print(f"Relevance: {result.relevance_score:.2f}")
        print(f"Visual Quality: {result.visual_quality_score:.2f}")
        print(f"Completeness: {result.completeness_score:.2f}")
        print(f"Layout Correct: {result.layout_correct}")
        
        if result.issues:
            print(f"\nIssues Found ({len(result.issues)}):")
            for i, issue in enumerate(result.issues, 1):
                print(f"\n{i}. [{issue.severity.value.upper()}] {issue.issue_type.value}")
                print(f"   {issue.message}")
                if issue.location:
                    print(f"   Location: {issue.location}")
                print(f"   Confidence: {issue.confidence:.2f}")
        else:
            print("\n✅ No issues found!")
        
        print(f"\nAnalysis:")
        print(f"{result.analysis}")
        
        print(f"\n{'='*80}")
        print("Benefits:")
        print(f"{'='*80}")
        print("✓ Automated content quality verification")
        print("✓ Catches layout issues before users see them")
        print("✓ Verifies content relevance automatically")
        print("✓ Detects error messages and broken elements")
        print("✓ No manual visual inspection needed")
        
    finally:
        print("\nClosing browser...")
        driver.quit()
    
    print(f"\n{'='*80}")
    print("Demo Complete!")
    print(f"{'='*80}")


if __name__ == "__main__":
    demo()
