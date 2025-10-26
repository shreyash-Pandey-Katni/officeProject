from typing import Optional, Tuple


class VLMElementFinder:
    """Stub implementation for VLM-based element finder.
    Provides a minimal interface expected by ActivityExecutor.
    """

    class Result:
        def __init__(self, found: bool, coordinates: Optional[Tuple[int, int]] = None):
            self.found = found
            self.coordinates = coordinates

    def find_element_by_description(self, driver, description: str, screenshot_path: Optional[str] = None):
        # Placeholder: always return not found
        return self.Result(False)
