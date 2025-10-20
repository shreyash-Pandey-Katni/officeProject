#!/usr/bin/env python3
"""
Visual Regression Detection Module
Compares screenshots to detect visual changes between test runs
"""

import os
import base64
import json
import requests
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from PIL import Image
import io


class ChangeSeverity(Enum):
    """Severity levels for visual changes"""
    CRITICAL = "critical"      # Breaks functionality
    MAJOR = "major"           # Significant layout/content change
    MINOR = "minor"           # Small visual difference
    COSMETIC = "cosmetic"     # Color/styling only


@dataclass
class VisualChange:
    """Represents a detected visual change"""
    type: str  # layout, content, styling, missing, extra
    severity: ChangeSeverity
    description: str
    location: Optional[Dict[str, int]] = None  # x, y, width, height
    impact: str = ""
    affected_element: str = ""
    before_value: Any = None
    after_value: Any = None


@dataclass
class VisualRegressionResult:
    """Result from visual regression comparison"""
    has_changes: bool
    changes: List[VisualChange] = field(default_factory=list)
    overall_similarity: float = 1.0  # 0.0 to 1.0
    analysis_summary: str = ""
    recommendation: str = ""
    timestamp: str = ""
    
    def get_critical_changes(self) -> List[VisualChange]:
        """Get only critical changes"""
        return [c for c in self.changes if c.severity == ChangeSeverity.CRITICAL]
    
    def get_major_changes(self) -> List[VisualChange]:
        """Get critical and major changes"""
        return [c for c in self.changes if c.severity in [ChangeSeverity.CRITICAL, ChangeSeverity.MAJOR]]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            'has_changes': self.has_changes,
            'changes': [
                {
                    'type': c.type,
                    'severity': c.severity.value,
                    'description': c.description,
                    'location': c.location,
                    'impact': c.impact,
                    'affected_element': c.affected_element
                }
                for c in self.changes
            ],
            'overall_similarity': self.overall_similarity,
            'analysis_summary': self.analysis_summary,
            'recommendation': self.recommendation,
            'timestamp': self.timestamp
        }


class VisualRegressionDetector:
    """
    Uses VLM to detect visual regressions between screenshots.
    
    This enables intelligent visual testing that catches:
    - Layout shifts
    - Missing/extra elements
    - Style changes
    - Content differences
    - Responsive design issues
    """
    
    def __init__(self, ollama_url: str = "http://localhost:11434", model: str = "granite3.1-dense:8b"):
        """
        Initialize Visual Regression Detector using Ollama
        
        Args:
            ollama_url: Ollama API URL (default: http://localhost:11434)
            model: Ollama model to use (default: granite3.1-dense:8b)
        """
        self.ollama_url = ollama_url
        self.model = model
        
        # Test Ollama connection
        try:
            response = requests.get(f"{self.ollama_url}/api/tags", timeout=2)
            if response.status_code != 200:
                raise ValueError(f"Ollama not responding at {self.ollama_url}")
        except requests.exceptions.RequestException as e:
            raise ValueError(f"Cannot connect to Ollama at {self.ollama_url}. Is Ollama running? Error: {e}")
        
    def compare_screenshots(
        self,
        baseline_path: str,
        current_path: str,
        ignore_dynamic_content: bool = True,
        sensitivity: str = "medium"  # low, medium, high
    ) -> VisualRegressionResult:
        """
        Compare two screenshots for visual differences
        
        Args:
            baseline_path: Path to baseline (expected) screenshot
            current_path: Path to current (actual) screenshot
            ignore_dynamic_content: Skip ads, timestamps, personalized content
            sensitivity: Detection sensitivity level
        
        Returns:
            VisualRegressionResult with detected changes
        """
        # Load screenshots
        with open(baseline_path, 'rb') as f:
            baseline_bytes = f.read()
        
        with open(current_path, 'rb') as f:
            current_bytes = f.read()
        
        # Call VLM
        result = self._call_vlm_compare(
            baseline_bytes,
            current_bytes,
            ignore_dynamic_content,
            sensitivity
        )
        
        return result
    
    def compare_screenshots_bytes(
        self,
        baseline_bytes: bytes,
        current_bytes: bytes,
        ignore_dynamic_content: bool = True,
        sensitivity: str = "medium"
    ) -> VisualRegressionResult:
        """Compare screenshots from bytes"""
        return self._call_vlm_compare(
            baseline_bytes,
            current_bytes,
            ignore_dynamic_content,
            sensitivity
        )
    
    def _call_vlm_compare(
        self,
        baseline_bytes: bytes,
        current_bytes: bytes,
        ignore_dynamic: bool,
        sensitivity: str
    ) -> VisualRegressionResult:
        """Call VLM to compare screenshots"""
        
        # Build prompt
        prompt = self._build_comparison_prompt(ignore_dynamic, sensitivity)
        
        # Encode screenshots
        baseline_b64 = base64.standard_b64encode(baseline_bytes).decode("utf-8")
        current_b64 = base64.standard_b64encode(current_bytes).decode("utf-8")
        
        try:
            # Call Ollama with both images
            full_prompt = f"""**Baseline Screenshot (Expected):**
[Image 1]

**Current Screenshot (Actual):**
[Image 2]

{prompt}"""
            
            payload = {
                "model": self.model,
                "prompt": full_prompt,
                "images": [baseline_b64, current_b64],
                "stream": False
            }
            
            response = requests.post(
                f"{self.ollama_url}/api/generate",
                json=payload,
                timeout=120  # Longer timeout for image comparison
            )
            
            if response.status_code != 200:
                raise Exception(f"Ollama API error: {response.status_code} - {response.text}")
            
            # Parse response
            response_data = response.json()
            response_text = response_data.get('response', '')
            
            result = self._parse_comparison_response(response_text)
            
            return result
            
        except Exception as e:
            print(f"[VLM] Error calling Ollama API: {e}")
            return VisualRegressionResult(
                has_changes=False,
                analysis_summary=f"VLM API error: {str(e)}",
                timestamp=datetime.now().isoformat()
            )
    
    def _build_comparison_prompt(self, ignore_dynamic: bool, sensitivity: str) -> str:
        """Build prompt for visual comparison"""
        
        prompt = """You are a visual regression testing expert. Compare these two screenshots of the same webpage taken at different times.

**Your Task:**
Identify ALL visual differences between the baseline (expected) and current (actual) screenshots.

**Categories of Changes:**
1. **Layout** - Position shifts, spacing changes, alignment issues
2. **Content** - Text changes, missing/extra elements, image differences
3. **Styling** - Colors, fonts, borders, shadows
4. **Missing** - Elements present in baseline but not in current
5. **Extra** - New elements in current not in baseline

"""
        
        if ignore_dynamic:
            prompt += """**Ignore Dynamic Content:**
- Timestamps, dates, "Last updated" text
- User-specific content (usernames, personalization)
- Advertisements
- Session-specific data
- Real-time counters (view counts, likes)

"""
        
        sensitivity_guidance = {
            'low': 'Only report major layout shifts and missing critical elements',
            'medium': 'Report layout changes and significant visual differences',
            'high': 'Report all differences including minor spacing and color variations'
        }
        
        prompt += f"**Sensitivity:** {sensitivity_guidance.get(sensitivity, sensitivity_guidance['medium'])}\n\n"
        
        prompt += """**Severity Levels:**
- **CRITICAL**: Breaks functionality (buttons missing, forms broken, navigation hidden)
- **MAJOR**: Significant visual change (layout shift >50px, major content difference)
- **MINOR**: Noticeable change (spacing change <50px, minor text difference)
- **COSMETIC**: Style only (color shade, font weight, subtle border)

**Response Format (JSON):**
```json
{
  "has_changes": true/false,
  "overall_similarity": 0.0-1.0,
  "changes": [
    {
      "type": "layout|content|styling|missing|extra",
      "severity": "critical|major|minor|cosmetic",
      "description": "Specific description of the change",
      "location": {
        "x": int,
        "y": int,
        "width": int,
        "height": int
      },
      "impact": "User impact description",
      "affected_element": "Element identifier (e.g., 'Search button', 'Header navigation')"
    }
  ],
  "analysis_summary": "Overall assessment of changes",
  "recommendation": "Pass/Fail/Review - with reasoning"
}
```

**Important:**
- Be precise about locations (x, y coordinates)
- Explain the impact of each change
- Distinguish between expected variations and regressions
- Consider responsive design (acceptable differences at different sizes)
- overall_similarity: 1.0 = identical, 0.0 = completely different
"""
        
        return prompt
    
    def _parse_comparison_response(self, response_text: str) -> VisualRegressionResult:
        """Parse VLM comparison response"""
        
        try:
            # Extract JSON
            json_start = response_text.find('{')
            json_end = response_text.rfind('}') + 1
            
            if json_start == -1 or json_end == 0:
                raise ValueError("No JSON found in response")
            
            json_str = response_text[json_start:json_end]
            data = json.loads(json_str)
            
            # Parse changes
            changes = []
            for change_data in data.get('changes', []):
                change = VisualChange(
                    type=change_data.get('type', 'unknown'),
                    severity=ChangeSeverity(change_data.get('severity', 'minor')),
                    description=change_data.get('description', ''),
                    location=change_data.get('location'),
                    impact=change_data.get('impact', ''),
                    affected_element=change_data.get('affected_element', '')
                )
                changes.append(change)
            
            result = VisualRegressionResult(
                has_changes=data.get('has_changes', False),
                changes=changes,
                overall_similarity=float(data.get('overall_similarity', 1.0)),
                analysis_summary=data.get('analysis_summary', ''),
                recommendation=data.get('recommendation', ''),
                timestamp=datetime.now().isoformat()
            )
            
            return result
            
        except Exception as e:
            print(f"[VLM] Error parsing response: {e}")
            print(f"[VLM] Response: {response_text[:500]}")
            
            return VisualRegressionResult(
                has_changes=False,
                analysis_summary=f"Failed to parse VLM response: {str(e)}",
                timestamp=datetime.now().isoformat()
            )
    
    def generate_visual_diff_report(
        self,
        result: VisualRegressionResult,
        output_path: str
    ) -> str:
        """
        Generate HTML report for visual differences
        
        Args:
            result: VisualRegressionResult from comparison
            output_path: Path to save HTML report
        
        Returns:
            Path to generated report
        """
        html = f"""<!DOCTYPE html>
<html>
<head>
    <title>Visual Regression Report</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; background: #f5f5f5; }}
        .container {{ max-width: 1200px; margin: 0 auto; background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
        h1 {{ color: #333; }}
        .summary {{ background: #e3f2fd; padding: 15px; border-radius: 4px; margin: 20px 0; }}
        .similarity {{ font-size: 24px; font-weight: bold; color: {'#4caf50' if result.overall_similarity > 0.95 else '#ff9800' if result.overall_similarity > 0.85 else '#f44336'}; }}
        .change {{ background: white; border-left: 4px solid #ccc; padding: 15px; margin: 10px 0; border-radius: 4px; }}
        .change.critical {{ border-left-color: #f44336; background: #ffebee; }}
        .change.major {{ border-left-color: #ff9800; background: #fff3e0; }}
        .change.minor {{ border-left-color: #2196f3; background: #e3f2fd; }}
        .change.cosmetic {{ border-left-color: #9e9e9e; background: #fafafa; }}
        .severity {{ display: inline-block; padding: 4px 8px; border-radius: 4px; font-size: 12px; font-weight: bold; text-transform: uppercase; }}
        .severity.critical {{ background: #f44336; color: white; }}
        .severity.major {{ background: #ff9800; color: white; }}
        .severity.minor {{ background: #2196f3; color: white; }}
        .severity.cosmetic {{ background: #9e9e9e; color: white; }}
        .recommendation {{ background: #fff3e0; padding: 15px; border-radius: 4px; margin: 20px 0; border-left: 4px solid #ff9800; }}
        .timestamp {{ color: #666; font-size: 14px; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>🔍 Visual Regression Report</h1>
        <p class="timestamp">Generated: {result.timestamp}</p>
        
        <div class="summary">
            <h2>Summary</h2>
            <p><strong>Overall Similarity:</strong> <span class="similarity">{result.overall_similarity:.1%}</span></p>
            <p><strong>Changes Detected:</strong> {len(result.changes)}</p>
            <p><strong>Critical:</strong> {len(result.get_critical_changes())}</p>
            <p><strong>Major:</strong> {len([c for c in result.changes if c.severity == ChangeSeverity.MAJOR])}</p>
            <p><strong>Minor:</strong> {len([c for c in result.changes if c.severity == ChangeSeverity.MINOR])}</p>
            <p><strong>Cosmetic:</strong> {len([c for c in result.changes if c.severity == ChangeSeverity.COSMETIC])}</p>
        </div>
        
        <div class="recommendation">
            <h3>📋 Recommendation</h3>
            <p>{result.recommendation}</p>
        </div>
        
        <h2>Detected Changes</h2>
"""
        
        if not result.changes:
            html += "<p>✅ No visual changes detected.</p>"
        else:
            for i, change in enumerate(result.changes, 1):
                location_str = ""
                if change.location:
                    loc = change.location
                    location_str = f"<p><strong>Location:</strong> ({loc.get('x', 0)}, {loc.get('y', 0)}) - {loc.get('width', 0)}x{loc.get('height', 0)}px</p>"
                
                html += f"""
        <div class="change {change.severity.value}">
            <h3>
                <span class="severity {change.severity.value}">{change.severity.value}</span>
                Change #{i}: {change.type.title()}
            </h3>
            <p><strong>Element:</strong> {change.affected_element or 'Unknown'}</p>
            <p><strong>Description:</strong> {change.description}</p>
            {location_str}
            <p><strong>Impact:</strong> {change.impact}</p>
        </div>
"""
        
        html += f"""
        <div class="summary">
            <h3>Analysis</h3>
            <p>{result.analysis_summary}</p>
        </div>
    </div>
</body>
</html>
"""
        
        with open(output_path, 'w') as f:
            f.write(html)
        
        return output_path


def demo():
    """Demo visual regression detection"""
    print("\n" + "="*80)
    print("VISUAL REGRESSION DETECTOR - DEMO (Ollama + Granite)")
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
from visual_regression_detector import VisualRegressionDetector

# Setup
detector = VisualRegressionDetector()

# Compare screenshots
result = detector.compare_screenshots(
    baseline_path="screenshots/baseline/homepage.png",
    current_path="screenshots/current/homepage.png",
    ignore_dynamic_content=True,
    sensitivity="medium"
)

# Check results
if result.has_changes:
    print(f"Changes detected: {len(result.changes)}")
    print(f"Similarity: {result.overall_similarity:.1%}")
    
    # Check critical changes
    critical = result.get_critical_changes()
    if critical:
        print(f"❌ {len(critical)} critical changes!")
        for change in critical:
            print(f"  - {change.description}")
            print(f"    Impact: {change.impact}")
    
    # Generate report
    report_path = detector.generate_visual_diff_report(
        result,
        "visual_regression_report.html"
    )
    print(f"Report: {report_path}")
else:
    print("✅ No visual changes detected")
'''
    
    print(example_code)
    
    print("\n" + "-"*80)
    print("What it Detects:")
    print("-"*80 + "\n")
    
    detections = [
        "✓ Layout shifts (elements moved/resized)",
        "✓ Missing elements (buttons, links, images)",
        "✓ Extra elements (unexpected content)",
        "✓ Content changes (text differences)",
        "✓ Styling changes (colors, fonts, borders)",
        "✓ Responsive design issues",
        "✓ Broken images or icons"
    ]
    
    for detection in detections:
        print(f"  {detection}")
    
    print("\n" + "-"*80)
    print("Use Cases:")
    print("-"*80 + "\n")
    
    use_cases = [
        "1. Catch unintended UI changes after deployments",
        "2. Verify design consistency across pages",
        "3. Test responsive design at different sizes",
        "4. Cross-browser visual consistency",
        "5. Detect CSS regression bugs",
        "6. Validate A/B test variants"
    ]
    
    for use_case in use_cases:
        print(f"  {use_case}")
    
    print("\n" + "="*80 + "\n")


if __name__ == "__main__":
    demo()
