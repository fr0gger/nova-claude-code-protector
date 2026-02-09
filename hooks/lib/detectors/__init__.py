"""
Nova-tracer Detector Plugins
============================

Detector plugins must export:
- DETECTOR_NAME: str - unique identifier (e.g., "nova", "yara")
- create_detector(config: dict) -> DetectorInterface

Example plugin structure:

    # hooks/lib/detectors/my_detector.py
    from .base import DetectorInterface, DetectionResult

    DETECTOR_NAME = "my_detector"

    class MyDetector(DetectorInterface):
        DETECTOR_NAME = "my_detector"

        def scan(self, text: str, config: dict) -> DetectionResult:
            # Implementation
            pass

        def load_rules(self, rules_path: Path) -> None:
            pass

        def is_available(self) -> bool:
            return True

    def create_detector(config: dict) -> DetectorInterface:
        return MyDetector()
"""

from .base import DetectionResult, DetectorInterface
from .registry import DetectorRegistry

__all__ = ["DetectionResult", "DetectorInterface", "DetectorRegistry"]
