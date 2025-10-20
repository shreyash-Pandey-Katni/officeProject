"""
Assertion Framework for Browser Automation Testing
Provides various assertion types to validate test expectations
"""

from typing import Dict, List, Optional, Any, Callable
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.common.exceptions import NoSuchElementException
from enum import Enum
import time
import re


class AssertionType(Enum):
    """Types of assertions available"""
    ELEMENT_VISIBLE = "element_visible"
    ELEMENT_NOT_VISIBLE = "element_not_visible"
    ELEMENT_EXISTS = "element_exists"
    ELEMENT_NOT_EXISTS = "element_not_exists"
    TEXT_PRESENT = "text_present"
    TEXT_NOT_PRESENT = "text_not_present"
    TEXT_EQUALS = "text_equals"
    TEXT_CONTAINS = "text_contains"
    URL_EQUALS = "url_equals"
    URL_CONTAINS = "url_contains"
    URL_MATCHES = "url_matches"
    ELEMENT_COUNT = "element_count"
    ELEMENT_COUNT_MIN = "element_count_min"
    ELEMENT_COUNT_MAX = "element_count_max"
    ATTRIBUTE_EQUALS = "attribute_equals"
    ATTRIBUTE_CONTAINS = "attribute_contains"
    ATTRIBUTE_EXISTS = "attribute_exists"
    CSS_PROPERTY_EQUALS = "css_property_equals"
    PAGE_TITLE_EQUALS = "page_title_equals"
    PAGE_TITLE_CONTAINS = "page_title_contains"
    ELEMENT_ENABLED = "element_enabled"
    ELEMENT_DISABLED = "element_disabled"
    ALERT_PRESENT = "alert_present"
    ALERT_NOT_PRESENT = "alert_not_present"


class AssertionResult:
    """Result of an assertion"""
    
    def __init__(self, assertion_type: AssertionType, passed: bool, 
                 message: str, expected: Any = None, actual: Any = None):
        self.type = assertion_type
        self.passed = passed
        self.message = message
        self.expected = expected
        self.actual = actual
        self.timestamp = time.time()
    
    def to_dict(self) -> Dict:
        """Convert to dictionary"""
        return {
            'type': self.type.value,
            'passed': self.passed,
            'message': self.message,
            'expected': self.expected,
            'actual': self.actual,
            'timestamp': self.timestamp
        }
    
    def __str__(self) -> str:
        status = "✓ PASS" if self.passed else "✗ FAIL"
        return f"{status}: {self.message}"
    
    def __repr__(self) -> str:
        return f"AssertionResult(type={self.type.value}, passed={self.passed})"


class Assertion:
    """
    Base assertion class
    Defines an assertion to be checked during test execution
    """
    
    def __init__(self, assertion_type: AssertionType, 
                 description: str = "", 
                 timeout: float = 5.0,
                 required: bool = True):
        """
        Initialize assertion
        
        Args:
            assertion_type: Type of assertion
            description: Human-readable description
            timeout: Maximum time to wait for condition
            required: If True, test fails when assertion fails
        """
        self.type = assertion_type
        self.description = description
        self.timeout = timeout
        self.required = required
        self.params: Dict[str, Any] = {}
    
    def set_param(self, key: str, value: Any) -> 'Assertion':
        """Set assertion parameter"""
        self.params[key] = value
        return self
    
    def execute(self, driver: webdriver.Chrome) -> AssertionResult:
        """
        Execute the assertion
        
        Args:
            driver: Selenium WebDriver
        
        Returns:
            AssertionResult
        """
        start_time = time.time()
        last_error = None
        
        # Retry until timeout
        while time.time() - start_time < self.timeout:
            try:
                result = self._check(driver)
                if result.passed or not self.required:
                    return result
                last_error = result.message
            except Exception as e:
                last_error = str(e)
            
            time.sleep(0.5)
        
        # Timeout reached
        return AssertionResult(
            self.type,
            False,
            f"Assertion failed after {self.timeout}s: {last_error or 'timeout'}",
            expected=self.params.get('expected'),
            actual=None
        )
    
    def _check(self, driver: webdriver.Chrome) -> AssertionResult:
        """
        Check the assertion (to be overridden by subclasses)
        
        Args:
            driver: Selenium WebDriver
        
        Returns:
            AssertionResult
        """
        raise NotImplementedError("Subclasses must implement _check()")
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for storage"""
        return {
            'type': self.type.value,
            'description': self.description,
            'timeout': self.timeout,
            'required': self.required,
            'params': self.params
        }
    
    @staticmethod
    def from_dict(data: Dict) -> 'Assertion':
        """Create assertion from dictionary"""
        assertion_type = AssertionType(data['type'])
        assertion = Assertion(
            assertion_type,
            data.get('description', ''),
            data.get('timeout', 5.0),
            data.get('required', True)
        )
        assertion.params = data.get('params', {})
        return assertion


class ElementVisibleAssertion(Assertion):
    """Assert that an element is visible"""
    
    def __init__(self, selector: str, by: str = By.CSS_SELECTOR, **kwargs):
        super().__init__(AssertionType.ELEMENT_VISIBLE, **kwargs)
        self.set_param('selector', selector)
        self.set_param('by', by)
    
    def _check(self, driver: webdriver.Chrome) -> AssertionResult:
        selector = self.params['selector']
        by = self.params.get('by', By.CSS_SELECTOR)
        
        try:
            element = driver.find_element(by, selector)
            if element.is_displayed():
                return AssertionResult(
                    self.type, True,
                    f"Element '{selector}' is visible",
                    expected=True, actual=True
                )
            else:
                return AssertionResult(
                    self.type, False,
                    f"Element '{selector}' exists but not visible",
                    expected=True, actual=False
                )
        except NoSuchElementException:
            return AssertionResult(
                self.type, False,
                f"Element '{selector}' not found",
                expected=True, actual=False
            )


class TextPresentAssertion(Assertion):
    """Assert that specific text is present on the page"""
    
    def __init__(self, text: str, case_sensitive: bool = True, **kwargs):
        super().__init__(AssertionType.TEXT_PRESENT, **kwargs)
        self.set_param('text', text)
        self.set_param('case_sensitive', case_sensitive)
    
    def _check(self, driver: webdriver.Chrome) -> AssertionResult:
        text = self.params['text']
        case_sensitive = self.params.get('case_sensitive', True)
        
        page_source = driver.page_source
        if not case_sensitive:
            text = text.lower()
            page_source = page_source.lower()
        
        if text in page_source:
            return AssertionResult(
                self.type, True,
                f"Text '{text}' found on page",
                expected=text, actual="present"
            )
        else:
            return AssertionResult(
                self.type, False,
                f"Text '{text}' not found on page",
                expected=text, actual="not present"
            )


class URLContainsAssertion(Assertion):
    """Assert that URL contains specific text"""
    
    def __init__(self, text: str, **kwargs):
        super().__init__(AssertionType.URL_CONTAINS, **kwargs)
        self.set_param('text', text)
    
    def _check(self, driver: webdriver.Chrome) -> AssertionResult:
        text = self.params['text']
        current_url = driver.current_url
        
        if text in current_url:
            return AssertionResult(
                self.type, True,
                f"URL contains '{text}'",
                expected=text, actual=current_url
            )
        else:
            return AssertionResult(
                self.type, False,
                f"URL does not contain '{text}'",
                expected=text, actual=current_url
            )


class ElementCountAssertion(Assertion):
    """Assert element count matches expected value"""
    
    def __init__(self, selector: str, count: int, by: str = By.CSS_SELECTOR, **kwargs):
        super().__init__(AssertionType.ELEMENT_COUNT, **kwargs)
        self.set_param('selector', selector)
        self.set_param('count', count)
        self.set_param('by', by)
    
    def _check(self, driver: webdriver.Chrome) -> AssertionResult:
        selector = self.params['selector']
        expected_count = self.params['count']
        by = self.params.get('by', By.CSS_SELECTOR)
        
        elements = driver.find_elements(by, selector)
        actual_count = len(elements)
        
        if actual_count == expected_count:
            return AssertionResult(
                self.type, True,
                f"Element count matches: {actual_count} == {expected_count}",
                expected=expected_count, actual=actual_count
            )
        else:
            return AssertionResult(
                self.type, False,
                f"Element count mismatch: expected {expected_count}, found {actual_count}",
                expected=expected_count, actual=actual_count
            )


class ElementCountMinAssertion(Assertion):
    """Assert minimum element count"""
    
    def __init__(self, selector: str, min_count: int, by: str = By.CSS_SELECTOR, **kwargs):
        super().__init__(AssertionType.ELEMENT_COUNT_MIN, **kwargs)
        self.set_param('selector', selector)
        self.set_param('min_count', min_count)
        self.set_param('by', by)
    
    def _check(self, driver: webdriver.Chrome) -> AssertionResult:
        selector = self.params['selector']
        min_count = self.params['min_count']
        by = self.params.get('by', By.CSS_SELECTOR)
        
        elements = driver.find_elements(by, selector)
        actual_count = len(elements)
        
        if actual_count >= min_count:
            return AssertionResult(
                self.type, True,
                f"Element count {actual_count} >= {min_count}",
                expected=f">= {min_count}", actual=actual_count
            )
        else:
            return AssertionResult(
                self.type, False,
                f"Element count {actual_count} < {min_count}",
                expected=f">= {min_count}", actual=actual_count
            )


class AttributeEqualsAssertion(Assertion):
    """Assert element attribute equals expected value"""
    
    def __init__(self, selector: str, attribute: str, value: str, 
                 by: str = By.CSS_SELECTOR, **kwargs):
        super().__init__(AssertionType.ATTRIBUTE_EQUALS, **kwargs)
        self.set_param('selector', selector)
        self.set_param('attribute', attribute)
        self.set_param('value', value)
        self.set_param('by', by)
    
    def _check(self, driver: webdriver.Chrome) -> AssertionResult:
        selector = self.params['selector']
        attribute = self.params['attribute']
        expected_value = self.params['value']
        by = self.params.get('by', By.CSS_SELECTOR)
        
        try:
            element = driver.find_element(by, selector)
            actual_value = element.get_attribute(attribute)
            
            if actual_value == expected_value:
                return AssertionResult(
                    self.type, True,
                    f"Attribute '{attribute}' equals '{expected_value}'",
                    expected=expected_value, actual=actual_value
                )
            else:
                return AssertionResult(
                    self.type, False,
                    f"Attribute '{attribute}' mismatch",
                    expected=expected_value, actual=actual_value
                )
        except NoSuchElementException:
            return AssertionResult(
                self.type, False,
                f"Element '{selector}' not found",
                expected=expected_value, actual=None
            )


class PageTitleContainsAssertion(Assertion):
    """Assert page title contains text"""
    
    def __init__(self, text: str, **kwargs):
        super().__init__(AssertionType.PAGE_TITLE_CONTAINS, **kwargs)
        self.set_param('text', text)
    
    def _check(self, driver: webdriver.Chrome) -> AssertionResult:
        text = self.params['text']
        title = driver.title
        
        if text in title:
            return AssertionResult(
                self.type, True,
                f"Page title contains '{text}'",
                expected=text, actual=title
            )
        else:
            return AssertionResult(
                self.type, False,
                f"Page title does not contain '{text}'",
                expected=text, actual=title
            )


class AssertionBuilder:
    """Fluent builder for creating assertions"""
    
    @staticmethod
    def element_visible(selector: str, by: str = By.CSS_SELECTOR, 
                       timeout: float = 5.0) -> ElementVisibleAssertion:
        """Create element visibility assertion"""
        return ElementVisibleAssertion(
            selector, by,
            description=f"Element '{selector}' should be visible",
            timeout=timeout
        )
    
    @staticmethod
    def text_present(text: str, timeout: float = 5.0) -> TextPresentAssertion:
        """Create text presence assertion"""
        return TextPresentAssertion(
            text,
            description=f"Text '{text}' should be present",
            timeout=timeout
        )
    
    @staticmethod
    def url_contains(text: str, timeout: float = 5.0) -> URLContainsAssertion:
        """Create URL contains assertion"""
        return URLContainsAssertion(
            text,
            description=f"URL should contain '{text}'",
            timeout=timeout
        )
    
    @staticmethod
    def element_count(selector: str, count: int, by: str = By.CSS_SELECTOR,
                     timeout: float = 5.0) -> ElementCountAssertion:
        """Create element count assertion"""
        return ElementCountAssertion(
            selector, count, by,
            description=f"Element count for '{selector}' should be {count}",
            timeout=timeout
        )
    
    @staticmethod
    def element_count_min(selector: str, min_count: int, by: str = By.CSS_SELECTOR,
                         timeout: float = 5.0) -> ElementCountMinAssertion:
        """Create minimum element count assertion"""
        return ElementCountMinAssertion(
            selector, min_count, by,
            description=f"Element count for '{selector}' should be >= {min_count}",
            timeout=timeout
        )
    
    @staticmethod
    def attribute_equals(selector: str, attribute: str, value: str,
                        by: str = By.CSS_SELECTOR, timeout: float = 5.0) -> AttributeEqualsAssertion:
        """Create attribute equals assertion"""
        return AttributeEqualsAssertion(
            selector, attribute, value, by,
            description=f"Attribute '{attribute}' should equal '{value}'",
            timeout=timeout
        )
    
    @staticmethod
    def page_title_contains(text: str, timeout: float = 5.0) -> PageTitleContainsAssertion:
        """Create page title contains assertion"""
        return PageTitleContainsAssertion(
            text,
            description=f"Page title should contain '{text}'",
            timeout=timeout
        )


# Convenience functions
def assert_element_visible(driver: webdriver.Chrome, selector: str, 
                          by: str = By.CSS_SELECTOR, timeout: float = 5.0) -> AssertionResult:
    """Quick assertion: element is visible"""
    return AssertionBuilder.element_visible(selector, by, timeout).execute(driver)


def assert_text_present(driver: webdriver.Chrome, text: str, 
                       timeout: float = 5.0) -> AssertionResult:
    """Quick assertion: text is present"""
    return AssertionBuilder.text_present(text, timeout).execute(driver)


def assert_url_contains(driver: webdriver.Chrome, text: str, 
                       timeout: float = 5.0) -> AssertionResult:
    """Quick assertion: URL contains text"""
    return AssertionBuilder.url_contains(text, timeout).execute(driver)


def assert_element_count_min(driver: webdriver.Chrome, selector: str, min_count: int,
                             by: str = By.CSS_SELECTOR, timeout: float = 5.0) -> AssertionResult:
    """Quick assertion: minimum element count"""
    return AssertionBuilder.element_count_min(selector, min_count, by, timeout).execute(driver)


if __name__ == "__main__":
    # Example usage
    print("Assertion Framework Demo\n")
    
    # Create assertions using builder
    assertions = [
        AssertionBuilder.element_visible(".search-results"),
        AssertionBuilder.text_present("results found"),
        AssertionBuilder.url_contains("search"),
        AssertionBuilder.element_count_min(".result-item", 1),
        AssertionBuilder.page_title_contains("Search"),
    ]
    
    print("Created assertions:")
    for assertion in assertions:
        print(f"  - {assertion.description}")
    
    print("\nAssertion types available:")
    for assertion_type in AssertionType:
        print(f"  - {assertion_type.value}")
