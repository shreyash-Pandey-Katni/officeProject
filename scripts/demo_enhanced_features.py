#!/usr/bin/env python3
"""
Demo: Enhanced Element Locators and Assertions
Demonstrates the new multi-strategy locator and assertion features
"""

from element_locator import ElementLocator, create_locator_from_activity
from assertions import AssertionBuilder, assert_element_visible, assert_text_present
import json


def demo_element_locators():
    """Demonstrate multi-strategy element locators"""
    print("\n" + "="*80)
    print("ELEMENT LOCATOR DEMONSTRATION")
    print("="*80 + "\n")
    
    # Example 1: Create locator with multiple strategies
    print("1. Creating Search Button Locator with Multiple Strategies:")
    print("-" * 80)
    
    search_button = ElementLocator("IBM Search Button")
    search_button.add_id("search-btn")
    search_button.add_class("search-button")
    search_button.add_css("[aria-label='Search']")
    search_button.add_xpath("//button[@aria-label='Search']")
    search_button.add_text("Search")
    search_button.add_coordinates(1575, 14)
    
    print(f"Description: {search_button.description}")
    print(f"Total Strategies: {len(search_button.strategies)}")
    print("\nStrategies (in priority order):")
    for strategy in search_button.get_sorted_strategies():
        print(f"  {strategy.priority:3d}. {strategy.type:20s} = {strategy.value}")
    
    # Example 2: Fluent API
    print("\n\n2. Using Fluent API:")
    print("-" * 80)
    
    login_button = (ElementLocator("Login Button")
                    .add_id("login-submit")
                    .add_class("btn-primary")
                    .add_xpath("//button[@type='submit']")
                    .add_text("Log in"))
    
    print(f"Created: {login_button}")
    print(f"Strategies: {len(login_button.strategies)}")
    
    # Example 3: Create from activity
    print("\n\n3. Creating Locator from Recorded Activity:")
    print("-" * 80)
    
    activity = {
        "action": "click",
        "details": {
            "tagName": "BUTTON",
            "id": "search-btn",
            "className": "search-button primary",
            "xpath": "//button[@id='search-btn']",
            "text": "Search",
            "coordinates": {"x": 1575, "y": 14},
            "inShadowRoot": False
        }
    }
    
    locator = create_locator_from_activity(activity)
    print(f"Activity: {activity['action']} on {activity['details']['tagName']}")
    print(f"Created locator with {len(locator.strategies)} strategies:")
    for strategy in locator.strategies:
        print(f"  - {strategy.type}: {strategy.value}")
    
    # Example 4: Serialization
    print("\n\n4. Serialization (for storing in activity logs):")
    print("-" * 80)
    
    locator_dict = search_button.to_dict()
    print(json.dumps(locator_dict, indent=2))
    
    # Restore from dict
    restored = ElementLocator.from_dict(locator_dict)
    print(f"\nRestored: {restored}")
    print(f"Strategies match: {len(restored.strategies) == len(search_button.strategies)}")
    
    # Example 5: Success tracking
    print("\n\n5. Success Rate Tracking:")
    print("-" * 80)
    
    # Simulate some successes and failures
    test_locator = ElementLocator("Test Element").add_id("test").add_class("test-class")
    
    # Simulate ID strategy succeeding
    test_locator.strategies[0].record_success()
    test_locator.strategies[0].record_success()
    test_locator.strategies[0].record_success()
    test_locator.strategies[0].record_failure()
    
    # Simulate class strategy failing
    test_locator.strategies[1].record_failure()
    test_locator.strategies[1].record_failure()
    
    print("Strategy Performance:")
    for strategy in test_locator.strategies:
        success_rate = strategy.success_rate() * 100
        total = strategy.success_count + strategy.failure_count
        print(f"  {strategy.type:15s}: {strategy.success_count}/{total} = {success_rate:.1f}%")


def demo_assertions():
    """Demonstrate assertion framework"""
    print("\n\n" + "="*80)
    print("ASSERTION FRAMEWORK DEMONSTRATION")
    print("="*80 + "\n")
    
    # Example 1: Create assertions using builder
    print("1. Creating Assertions with Builder Pattern:")
    print("-" * 80)
    
    assertions = [
        AssertionBuilder.element_visible(".search-results", timeout=5.0),
        AssertionBuilder.text_present("results found"),
        AssertionBuilder.url_contains("search"),
        AssertionBuilder.element_count_min(".result-item", 1),
        AssertionBuilder.page_title_contains("Search"),
    ]
    
    print("Created assertions:")
    for i, assertion in enumerate(assertions, 1):
        print(f"  {i}. {assertion.description}")
        print(f"     Type: {assertion.type.value}")
        print(f"     Timeout: {assertion.timeout}s")
        print(f"     Required: {assertion.required}")
    
    # Example 2: Custom assertion parameters
    print("\n\n2. Assertions with Custom Parameters:")
    print("-" * 80)
    
    custom_assertions = [
        AssertionBuilder.element_count(".product-card", 12),
        AssertionBuilder.attribute_equals("#username", "placeholder", "Enter your username"),
        AssertionBuilder.element_visible("button[type='submit']"),
    ]
    
    for assertion in custom_assertions:
        print(f"  - {assertion.description}")
        print(f"    Params: {assertion.params}")
    
    # Example 3: Test case with assertions
    print("\n\n3. Example Test Case with Assertions:")
    print("-" * 80)
    
    test_case = {
        "name": "Search Functionality Test",
        "steps": [
            {
                "action": "navigation",
                "url": "https://www.ibm.com",
                "assertions": []
            },
            {
                "action": "click",
                "element": "Search button",
                "assertions": [
                    "Search field becomes visible",
                    "Search placeholder text appears"
                ]
            },
            {
                "action": "text_input",
                "text": "cloud computing",
                "assertions": [
                    "Minimum 1 search result",
                    "URL contains 'search'",
                    "Page title contains search term"
                ]
            }
        ]
    }
    
    print(f"Test: {test_case['name']}")
    for i, step in enumerate(test_case['steps'], 1):
        print(f"\n  Step {i}: {step['action']}")
        if step['assertions']:
            print(f"  Assertions:")
            for assertion_desc in step['assertions']:
                print(f"    ✓ {assertion_desc}")
    
    # Example 4: Assertion serialization
    print("\n\n4. Assertion Serialization:")
    print("-" * 80)
    
    assertion = AssertionBuilder.element_visible(".modal-dialog")
    assertion_dict = assertion.to_dict()
    print(json.dumps(assertion_dict, indent=2))
    
    # Example 5: Available assertion types
    print("\n\n5. Available Assertion Types:")
    print("-" * 80)
    
    from assertions import AssertionType
    
    assertion_categories = {
        "Element State": [
            AssertionType.ELEMENT_VISIBLE,
            AssertionType.ELEMENT_NOT_VISIBLE,
            AssertionType.ELEMENT_EXISTS,
            AssertionType.ELEMENT_ENABLED,
            AssertionType.ELEMENT_DISABLED,
        ],
        "Text Validation": [
            AssertionType.TEXT_PRESENT,
            AssertionType.TEXT_CONTAINS,
            AssertionType.TEXT_EQUALS,
        ],
        "URL Validation": [
            AssertionType.URL_EQUALS,
            AssertionType.URL_CONTAINS,
            AssertionType.URL_MATCHES,
        ],
        "Element Count": [
            AssertionType.ELEMENT_COUNT,
            AssertionType.ELEMENT_COUNT_MIN,
            AssertionType.ELEMENT_COUNT_MAX,
        ],
        "Attributes": [
            AssertionType.ATTRIBUTE_EQUALS,
            AssertionType.ATTRIBUTE_CONTAINS,
            AssertionType.ATTRIBUTE_EXISTS,
        ],
        "Page State": [
            AssertionType.PAGE_TITLE_EQUALS,
            AssertionType.PAGE_TITLE_CONTAINS,
            AssertionType.ALERT_PRESENT,
        ]
    }
    
    for category, types in assertion_categories.items():
        print(f"\n  {category}:")
        for assertion_type in types:
            print(f"    - {assertion_type.value}")


def demo_integration():
    """Demonstrate how both features work together"""
    print("\n\n" + "="*80)
    print("INTEGRATION DEMONSTRATION")
    print("="*80 + "\n")
    
    print("Example: Complete Test Step with Enhanced Features")
    print("-" * 80)
    
    # Create a test step with multi-strategy locator and assertions
    test_step = {
        "step_number": 1,
        "action": "click",
        "description": "Click search button",
        
        # Multi-strategy locator
        "locator": {
            "description": "Search button",
            "strategies": [
                {"type": "id", "value": "search-btn", "priority": 10},
                {"type": "class", "value": "search-button", "priority": 80},
                {"type": "xpath", "value": "//button[@aria-label='Search']", "priority": 40},
                {"type": "text_content", "value": "Search", "priority": 90},
                {"type": "coordinates", "value": {"x": 1575, "y": 14}, "priority": 100}
            ]
        },
        
        # Assertions to check after click
        "assertions": [
            {
                "type": "element_visible",
                "description": "Search input field should appear",
                "params": {"selector": "input[name='q']"},
                "timeout": 5.0,
                "required": True
            },
            {
                "type": "element_enabled",
                "description": "Search input should be enabled",
                "params": {"selector": "input[name='q']"},
                "timeout": 2.0,
                "required": True
            }
        ]
    }
    
    print(json.dumps(test_step, indent=2))
    
    print("\n\nExecution Flow:")
    print("-" * 80)
    print("1. Try to find element using locator strategies (in priority order):")
    print("   a. Try ID: 'search-btn'")
    print("   b. If fails, try XPath: //button[@aria-label='Search']")
    print("   c. If fails, try Class: 'search-button'")
    print("   d. If fails, try Text: 'Search'")
    print("   e. If fails, try Coordinates: (1575, 14)")
    print("\n2. Click the element when found")
    print("\n3. Wait for page to settle (0.5s)")
    print("\n4. Execute assertions:")
    print("   ✓ Check search input field is visible")
    print("   ✓ Check search input field is enabled")
    print("\n5. Record results (success/failure, method used, assertion results)")


def demo_benefits():
    """Show the benefits of these features"""
    print("\n\n" + "="*80)
    print("BENEFITS & USE CASES")
    print("="*80 + "\n")
    
    benefits = {
        "Multi-Strategy Locators": [
            "✓ Tests survive UI changes (ID changed? XPath still works)",
            "✓ Automatic fallback (primary method fails → tries backup)",
            "✓ Learning system (tracks which strategies work best)",
            "✓ Better debugging (see which method was used)",
            "✓ Coordinate fallback (works even when all selectors fail)"
        ],
        "Assertion Framework": [
            "✓ Verify expected outcomes (not just element presence)",
            "✓ Catch regressions early (validate business logic)",
            "✓ Better test reports (know exactly what failed)",
            "✓ Flexible validation (element state, content, count, etc.)",
            "✓ Optional assertions (warnings vs failures)"
        ],
        "Combined Power": [
            "✓ Robust tests (multiple ways to find + verify result)",
            "✓ Clear test intent (what you're clicking + what should happen)",
            "✓ Self-documenting (locators and assertions explain the test)",
            "✓ Easy maintenance (update one strategy, not the whole test)",
            "✓ Better failure analysis (know which part failed)"
        ]
    }
    
    for category, items in benefits.items():
        print(f"{category}:")
        for item in items:
            print(f"  {item}")
        print()
    
    print("\nExample Scenarios:")
    print("-" * 80)
    
    scenarios = [
        {
            "scenario": "UI Redesign",
            "problem": "Button ID changed from 'search-btn' to 'global-search'",
            "solution": "Locator automatically tries XPath, class, text, coordinates",
            "result": "✓ Test continues working without modification"
        },
        {
            "scenario": "Flaky Test",
            "problem": "Test clicks button but doesn't verify result loaded",
            "solution": "Add assertion: element_visible('.results', timeout=10)",
            "result": "✓ Test waits for results, catches timing issues"
        },
        {
            "scenario": "Regression Detection",
            "problem": "Search returns 0 results (backend bug)",
            "solution": "Add assertion: element_count_min('.result-item', 1)",
            "result": "✓ Test fails immediately, catches regression"
        },
        {
            "scenario": "Internationalization",
            "problem": "Button text changes by language ('Search' vs 'Buscar')",
            "solution": "Use multiple locators: ID, XPath, coordinates",
            "result": "✓ Test works across all language versions"
        }
    ]
    
    for i, scenario in enumerate(scenarios, 1):
        print(f"\n{i}. {scenario['scenario']}")
        print(f"   Problem:  {scenario['problem']}")
        print(f"   Solution: {scenario['solution']}")
        print(f"   Result:   {scenario['result']}")


def main():
    """Run all demonstrations"""
    print("\n" + "="*80)
    print("ENHANCED ELEMENT LOCATORS & ASSERTIONS - FEATURE DEMO")
    print("="*80)
    
    demo_element_locators()
    demo_assertions()
    demo_integration()
    demo_benefits()
    
    print("\n\n" + "="*80)
    print("NEXT STEPS")
    print("="*80 + "\n")
    
    print("1. Run tests with enhanced locators:")
    print("   python replay_browser_activities.py")
    print("   (Automatically uses multi-strategy locators)")
    print()
    print("2. Add assertions to your tests:")
    print("   Edit activity_log.json and add 'assertions' field")
    print()
    print("3. View results:")
    print("   python db_utils.py --details <test_run_id>")
    print("   (See which locator strategies worked and assertion results)")
    print()
    print("4. Check documentation:")
    print("   - element_locator.py: Full API documentation")
    print("   - assertions.py: All assertion types")
    print("   - FUTURE_IMPROVEMENTS_AND_VLM_OPPORTUNITIES.md: More ideas")
    
    print("\n" + "="*80 + "\n")


if __name__ == "__main__":
    main()
