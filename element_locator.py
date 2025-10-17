"""
Enhanced Element Locator with Multiple Fallback Strategies
Implements smart element location with multiple selector types and priorities
"""

from typing import Dict, List, Optional, Tuple, Any
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webelement import WebElement
from selenium.common.exceptions import NoSuchElementException, StaleElementReferenceException
import time


class LocatorStrategy:
    """Defines a single locator strategy"""
    
    def __init__(self, strategy_type: str, value: Any, priority: int = 100):
        """
        Initialize locator strategy
        
        Args:
            strategy_type: Type of locator (id, class, xpath, css, text, coordinates)
            value: Locator value
            priority: Priority (lower = higher priority, 0-1000)
        """
        self.type = strategy_type
        self.value = value
        self.priority = priority
        self.success_count = 0
        self.failure_count = 0
    
    def success_rate(self) -> float:
        """Calculate success rate of this strategy"""
        total = self.success_count + self.failure_count
        if total == 0:
            return 0.0
        return self.success_count / total
    
    def record_success(self):
        """Record successful element location"""
        self.success_count += 1
    
    def record_failure(self):
        """Record failed element location"""
        self.failure_count += 1
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for storage"""
        return {
            'type': self.type,
            'value': self.value,
            'priority': self.priority,
            'success_count': self.success_count,
            'failure_count': self.failure_count
        }
    
    @staticmethod
    def from_dict(data: Dict) -> 'LocatorStrategy':
        """Create from dictionary"""
        strategy = LocatorStrategy(
            strategy_type=data['type'],
            value=data['value'],
            priority=data.get('priority', 100)
        )
        strategy.success_count = data.get('success_count', 0)
        strategy.failure_count = data.get('failure_count', 0)
        return strategy


class ElementLocator:
    """
    Multi-strategy element locator with intelligent fallback
    Stores multiple ways to locate an element and tries them in priority order
    """
    
    # Priority order for locator types (lower = higher priority)
    PRIORITY_ORDER = {
        'id': 10,
        'name': 20,
        'css': 30,
        'xpath': 40,
        'link_text': 50,
        'partial_link_text': 60,
        'tag_name': 70,
        'class': 80,
        'text_content': 90,
        'coordinates': 100
    }
    
    def __init__(self, element_description: str = ""):
        """
        Initialize element locator
        
        Args:
            element_description: Human-readable description of element
        """
        self.description = element_description
        self.strategies: List[LocatorStrategy] = []
        self.last_successful_strategy: Optional[LocatorStrategy] = None
        self.visual_context: Dict[str, Any] = {}
    
    def add_strategy(self, strategy_type: str, value: Any, priority: Optional[int] = None) -> 'ElementLocator':
        """
        Add a locator strategy
        
        Args:
            strategy_type: Type of locator
            value: Locator value
            priority: Custom priority (optional, defaults to type priority)
        """
        if priority is None:
            priority = self.PRIORITY_ORDER.get(strategy_type, 100)
        
        strategy = LocatorStrategy(strategy_type, value, priority)
        self.strategies.append(strategy)
        return self
    
    def add_id(self, element_id: str) -> 'ElementLocator':
        """Add ID locator"""
        return self.add_strategy('id', element_id)
    
    def add_name(self, name: str) -> 'ElementLocator':
        """Add name attribute locator"""
        return self.add_strategy('name', name)
    
    def add_class(self, class_name: str) -> 'ElementLocator':
        """Add class name locator"""
        return self.add_strategy('class', class_name)
    
    def add_css(self, css_selector: str) -> 'ElementLocator':
        """Add CSS selector"""
        return self.add_strategy('css', css_selector)
    
    def add_xpath(self, xpath: str) -> 'ElementLocator':
        """Add XPath locator"""
        return self.add_strategy('xpath', xpath)
    
    def add_text(self, text: str) -> 'ElementLocator':
        """Add text content locator"""
        return self.add_strategy('text_content', text)
    
    def add_coordinates(self, x: int, y: int) -> 'ElementLocator':
        """Add coordinate-based locator"""
        return self.add_strategy('coordinates', {'x': x, 'y': y})
    
    def add_link_text(self, text: str, partial: bool = False) -> 'ElementLocator':
        """Add link text locator"""
        strategy_type = 'partial_link_text' if partial else 'link_text'
        return self.add_strategy(strategy_type, text)
    
    def set_visual_context(self, context: Dict[str, Any]) -> 'ElementLocator':
        """
        Set visual context for element
        
        Args:
            context: Visual information (nearby elements, position, etc.)
        """
        self.visual_context = context
        return self
    
    def get_sorted_strategies(self) -> List[LocatorStrategy]:
        """Get strategies sorted by priority and success rate"""
        # If we have a last successful strategy, try it first
        if self.last_successful_strategy:
            strategies = [self.last_successful_strategy]
            strategies.extend([s for s in self.strategies if s != self.last_successful_strategy])
        else:
            strategies = sorted(self.strategies, key=lambda s: (s.priority, -s.success_rate()))
        
        return strategies
    
    def find_element(self, driver: webdriver.Chrome, timeout: float = 5.0) -> Tuple[Optional[WebElement], Optional[str], Optional[str]]:
        """
        Find element using available strategies in priority order
        
        Args:
            driver: Selenium WebDriver instance
            timeout: Maximum time to wait for element
        
        Returns:
            Tuple of (element, method_used, error_message)
        """
        start_time = time.time()
        strategies = self.get_sorted_strategies()
        last_error = "No locator strategies available"
        
        print(f"[LOCATOR] Finding element: {self.description}")
        print(f"[LOCATOR] Trying {len(strategies)} strategies...")
        
        for strategy in strategies:
            if time.time() - start_time > timeout:
                print(f"[LOCATOR] Timeout reached after {timeout}s")
                break
            
            try:
                element = self._try_strategy(driver, strategy)
                if element and element.is_displayed():
                    print(f"[LOCATOR] ✓ Found element using {strategy.type}: {strategy.value}")
                    strategy.record_success()
                    self.last_successful_strategy = strategy
                    return element, strategy.type, None
                else:
                    strategy.record_failure()
                    last_error = f"Element found but not displayed ({strategy.type})"
            
            except (NoSuchElementException, StaleElementReferenceException) as e:
                strategy.record_failure()
                last_error = f"{strategy.type} failed: {str(e)}"
                print(f"[LOCATOR] ✗ {strategy.type} failed")
            
            except Exception as e:
                strategy.record_failure()
                last_error = f"{strategy.type} error: {str(e)}"
                print(f"[LOCATOR] ✗ {strategy.type} error: {e}")
        
        print(f"[LOCATOR] ✗ All strategies failed for: {self.description}")
        return None, None, last_error
    
    def _try_strategy(self, driver: webdriver.Chrome, strategy: LocatorStrategy) -> Optional[WebElement]:
        """
        Try a single locator strategy
        
        Args:
            driver: Selenium WebDriver
            strategy: Locator strategy to try
        
        Returns:
            WebElement if found, None otherwise
        """
        if strategy.type == 'id':
            return driver.find_element(By.ID, strategy.value)
        
        elif strategy.type == 'name':
            return driver.find_element(By.NAME, strategy.value)
        
        elif strategy.type == 'class':
            return driver.find_element(By.CLASS_NAME, strategy.value)
        
        elif strategy.type == 'css':
            return driver.find_element(By.CSS_SELECTOR, strategy.value)
        
        elif strategy.type == 'xpath':
            return driver.find_element(By.XPATH, strategy.value)
        
        elif strategy.type == 'link_text':
            return driver.find_element(By.LINK_TEXT, strategy.value)
        
        elif strategy.type == 'partial_link_text':
            return driver.find_element(By.PARTIAL_LINK_TEXT, strategy.value)
        
        elif strategy.type == 'tag_name':
            return driver.find_element(By.TAG_NAME, strategy.value)
        
        elif strategy.type == 'text_content':
            # Find by text content using XPath
            xpath = f"//*[contains(text(), '{strategy.value}')]"
            return driver.find_element(By.XPATH, xpath)
        
        elif strategy.type == 'coordinates':
            # Coordinate-based clicking requires ActionChains
            # Return a special marker that caller can detect
            return None  # Coordinates handled separately by caller
        
        return None
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for storage"""
        return {
            'description': self.description,
            'strategies': [s.to_dict() for s in self.strategies],
            'visual_context': self.visual_context
        }
    
    @staticmethod
    def from_dict(data: Dict) -> 'ElementLocator':
        """Create from dictionary"""
        locator = ElementLocator(data.get('description', ''))
        locator.strategies = [LocatorStrategy.from_dict(s) for s in data.get('strategies', [])]
        locator.visual_context = data.get('visual_context', {})
        return locator
    
    @staticmethod
    def from_element(element: WebElement, description: str = "") -> 'ElementLocator':
        """
        Create locator from existing WebElement
        Extracts all possible locator strategies
        
        Args:
            element: Selenium WebElement
            description: Human-readable description
        
        Returns:
            ElementLocator with multiple strategies
        """
        locator = ElementLocator(description)
        
        try:
            # ID (highest priority)
            element_id = element.get_attribute('id')
            if element_id:
                locator.add_id(element_id)
            
            # Name
            name = element.get_attribute('name')
            if name:
                locator.add_name(name)
            
            # Class (first class only)
            classes = element.get_attribute('class')
            if classes:
                first_class = classes.split()[0]
                locator.add_class(first_class)
            
            # Tag name
            tag_name = element.tag_name
            if tag_name:
                locator.add_strategy('tag_name', tag_name)
            
            # Text content
            text = element.text
            if text and len(text) > 0 and len(text) < 100:  # Reasonable text length
                locator.add_text(text.strip())
            
            # Link text for anchor tags
            if tag_name == 'a':
                href_text = element.get_attribute('href')
                if href_text:
                    locator.add_strategy('link_text', text.strip())
            
            # Location
            location = element.location
            if location:
                locator.add_coordinates(location['x'], location['y'])
        
        except Exception as e:
            print(f"[LOCATOR] Warning: Could not extract all locators: {e}")
        
        return locator
    
    def __str__(self) -> str:
        """String representation"""
        return f"ElementLocator('{self.description}', {len(self.strategies)} strategies)"
    
    def __repr__(self) -> str:
        """Detailed string representation"""
        strategies_str = ", ".join([f"{s.type}={s.value}" for s in self.strategies[:3]])
        if len(self.strategies) > 3:
            strategies_str += f", ... (+{len(self.strategies)-3} more)"
        return f"ElementLocator({strategies_str})"


def create_locator_from_activity(activity: Dict) -> ElementLocator:
    """
    Create ElementLocator from activity dictionary
    Extracts available locator information from recorded activity
    
    Args:
        activity: Activity dictionary from recording
    
    Returns:
        ElementLocator with available strategies
    """
    details = activity.get('details', {})
    action = activity.get('action', '')
    
    # Create description
    tag_name = details.get('tagName', 'element')
    text = details.get('text', '')
    description = f"{tag_name}"
    if text:
        description += f" with text '{text[:30]}'"
    
    locator = ElementLocator(description)
    
    # Add ID if available
    if details.get('id'):
        locator.add_id(details['id'])
    
    # Add name if available
    if details.get('name'):
        locator.add_name(details['name'])
    
    # Add class if available
    if details.get('className'):
        classes = details['className'].split()
        if classes:
            locator.add_class(classes[0])
    
    # Add XPath if available
    if details.get('xpath'):
        locator.add_xpath(details['xpath'])
    
    # Add CSS selector if available
    if details.get('selector'):
        locator.add_css(details['selector'])
    
    # Add text content if available
    if text and len(text) > 0:
        locator.add_text(text)
    
    # Add placeholder for inputs
    if details.get('placeholder'):
        locator.add_strategy('css', f'[placeholder="{details["placeholder"]}"]')
    
    # Add coordinates if available
    coords = details.get('coordinates', {})
    if coords.get('x') is not None and coords.get('y') is not None:
        locator.add_coordinates(coords['x'], coords['y'])
    
    # Add visual context
    locator.set_visual_context({
        'in_shadow_root': details.get('inShadowRoot', False),
        'in_iframe': details.get('inIframe', False),
        'tag_name': tag_name
    })
    
    return locator


if __name__ == "__main__":
    # Test locator creation
    locator = ElementLocator("Search button")
    locator.add_id("search-btn")
    locator.add_class("search-button")
    locator.add_xpath("//button[@aria-label='Search']")
    locator.add_text("Search")
    locator.add_coordinates(1575, 14)
    
    print(locator)
    print(f"Strategies: {len(locator.strategies)}")
    for s in locator.strategies:
        print(f"  - {s.type}: {s.value} (priority: {s.priority})")
    
    # Test serialization
    data = locator.to_dict()
    print(f"\nSerialized: {data}")
    
    restored = ElementLocator.from_dict(data)
    print(f"Restored: {restored}")
