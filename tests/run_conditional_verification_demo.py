"""Demo test for conditional verification actions.

This script constructs activities including a verification step with on_pass and on_fail
follow-up actions, then runs them with a headless Chrome (or prints what would run if
Chrome not available).

It is meant as a lightweight runtime check rather than a formal unit test framework.
"""
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from core.executors.activity_executor import ActivityExecutor
import json


def build_demo_activities():
    # Navigate to example page
    activities = [
        {
            "action": "navigation",
            "details": {"url": "https://example.com", "description": "Open example domain"}
        },
        {
            "action": "verification",
            "details": {
                "criteria": "Example Domain",  # Known text on example.com
                "description": "Check heading text appears",
                "on_pass": [
                    {"action": "click", "details": {"text": "More information", "tagName": "A", "description": "(demo) would click link if present", "locators": {"text": "More information"}}},
                ],
                "on_fail": [
                    {"action": "navigation", "details": {"url": "https://www.iana.org/domains/reserved", "description": "Fallback navigation if heading missing"}}
                ]
            }
        }
    ]
    return activities


def run_demo():
    activities = build_demo_activities()

    try:
        opts = Options()
        opts.add_argument("--headless=new")
        driver = webdriver.Chrome(options=opts)
    except Exception as e:
        print("Unable to start Chrome driver, printing intended execution only:")
        print(e)
        print(json.dumps(activities, indent=2))
        return

    executor = ActivityExecutor(driver)
    results = []
    for act in activities:
        res = executor.execute_activity(act)
        results.append(res)
    driver.quit()

    print("\nExecution Results:")
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    run_demo()
