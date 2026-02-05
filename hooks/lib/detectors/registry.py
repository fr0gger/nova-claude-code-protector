"""
Nova-tracer Detector Registry
=============================

Singleton registry with plugin discovery and configurable chaining behavior.
Follows the same pattern as HandlerRegistry in nova_logging.py.
"""

import importlib.util
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Dict, List, Optional

from .base import DetectionResult, DetectorInterface


# Files to skip during plugin discovery
SKIP_FILES = {"__init__.py", "base.py", "registry.py"}


class DetectorRegistry:
    """
    Singleton registry that discovers and loads detector plugins from hooks/lib/detectors/.
    
    Each plugin module must export:
    - DETECTOR_NAME: str - unique identifier
    - create_detector(config: dict) -> DetectorInterface
    
    Supports two scanning modes:
    - "parallel": Run all enabled detectors concurrently, aggregate results
    - "first_match": Run detectors in order, stop on first detection
    """

    _instance: Optional["DetectorRegistry"] = None
    _lock = threading.Lock()

    def __new__(cls) -> "DetectorRegistry":
        """Singleton pattern implementation."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._plugins: Dict[str, Any] = {}
                    cls._instance._detectors: Dict[str, DetectorInterface] = {}
                    cls._instance._discovered = False
        return cls._instance

    def _get_detectors_dir(self) -> Optional[Path]:
        """Get the path to the detectors directory."""
        # hooks/lib/detectors/registry.py -> hooks/lib/detectors/
        return Path(__file__).parent

    def discover_plugins(self) -> None:
        """
        Discover and load all detector plugins from the detectors directory.
        
        Plugins are Python files in hooks/lib/detectors/ that export:
        - DETECTOR_NAME: str
        - create_detector(config: dict) -> DetectorInterface
        """
        if self._discovered:
            return

        detectors_dir = self._get_detectors_dir()
        if not detectors_dir or not detectors_dir.exists():
            self._discovered = True
            return

        # Add hooks/lib to path so plugins can use absolute imports like:
        # from detectors.base import DetectionResult, DetectorInterface
        import sys
        lib_dir = detectors_dir.parent
        if str(lib_dir) not in sys.path:
            sys.path.insert(0, str(lib_dir))

        # Find all Python files (except internal modules)
        for py_file in detectors_dir.glob("*.py"):
            if py_file.name in SKIP_FILES or py_file.name.startswith("_"):
                continue

            try:
                # Load the module dynamically
                spec = importlib.util.spec_from_file_location(
                    f"nova_detectors.{py_file.stem}",
                    py_file
                )
                if spec and spec.loader:
                    module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(module)

                    # Check for required exports
                    if hasattr(module, "DETECTOR_NAME") and hasattr(module, "create_detector"):
                        detector_name = getattr(module, "DETECTOR_NAME")
                        self._plugins[detector_name] = module

            except Exception:
                # Fail-open: skip plugins that fail to load
                pass

        self._discovered = True

    def get_detector(
        self,
        name: str,
        config: Dict[str, Any],
    ) -> Optional[DetectorInterface]:
        """
        Get an instantiated detector by name.
        
        Args:
            name: Detector plugin name (e.g., "nova")
            config: Configuration dictionary
            
        Returns:
            Instantiated detector, or None if not found/failed
        """
        self.discover_plugins()

        # Return cached detector if available
        if name in self._detectors:
            return self._detectors[name]

        plugin = self._plugins.get(name)
        if plugin is None:
            return None

        try:
            create_fn = getattr(plugin, "create_detector")
            detector = create_fn(config)
            
            # Verify it implements the interface
            if isinstance(detector, DetectorInterface) and detector.is_available():
                self._detectors[name] = detector
                return detector
            return None
        except Exception:
            # Fail-open: return None if detector creation fails
            return None

    @property
    def available_detectors(self) -> List[str]:
        """Get list of available detector names."""
        self.discover_plugins()
        return list(self._plugins.keys())

    def scan_all(
        self,
        text: str,
        config: Dict[str, Any],
        detectors: Optional[List[str]] = None,
    ) -> List[DetectionResult]:
        """
        Run all enabled detectors in parallel and aggregate results.
        
        Args:
            text: Text content to scan
            config: Configuration dictionary
            detectors: List of detector names to use (defaults to all available)
            
        Returns:
            List of DetectionResult from all detectors
        """
        self.discover_plugins()
        
        detector_names = detectors or list(self._plugins.keys())
        results: List[DetectionResult] = []
        
        if not detector_names:
            return results

        # Get detector instances
        detector_instances = []
        for name in detector_names:
            detector = self.get_detector(name, config)
            if detector:
                detector_instances.append((name, detector))

        if not detector_instances:
            return results

        # Run detectors in parallel
        with ThreadPoolExecutor(max_workers=len(detector_instances)) as executor:
            futures = {
                executor.submit(self._safe_scan, detector, text, config): name
                for name, detector in detector_instances
            }
            
            for future in as_completed(futures):
                try:
                    result = future.result()
                    if result:
                        results.append(result)
                except Exception:
                    # Fail-open: skip failed scans
                    pass

        return results

    def scan_first(
        self,
        text: str,
        config: Dict[str, Any],
        detectors: Optional[List[str]] = None,
    ) -> Optional[DetectionResult]:
        """
        Run detectors in order and stop on first detection.
        
        Args:
            text: Text content to scan
            config: Configuration dictionary
            detectors: Ordered list of detector names (defaults to all available)
            
        Returns:
            First DetectionResult with a non-allowed verdict, or None
        """
        self.discover_plugins()
        
        detector_names = detectors or list(self._plugins.keys())
        
        for name in detector_names:
            detector = self.get_detector(name, config)
            if not detector:
                continue
                
            result = self._safe_scan(detector, text, config)
            if result and result.verdict != "allowed":
                return result
        
        return None

    def scan(
        self,
        text: str,
        config: Dict[str, Any],
    ) -> List[DetectionResult]:
        """
        Scan text using configured detection mode and detectors.
        
        Dispatches to scan_all() or scan_first() based on config.
        
        Config options:
            detection.mode: "parallel" (default) or "first_match"
            detection.detectors: List of detector names (defaults to ["nova"])
        
        Args:
            text: Text content to scan
            config: Configuration dictionary
            
        Returns:
            List of DetectionResult objects
        """
        # Get detection configuration
        detection_config = config.get("detection", {})
        mode = detection_config.get("mode", "parallel")
        detectors = detection_config.get("detectors", ["nova"])
        
        if mode == "first_match":
            result = self.scan_first(text, config, detectors)
            return [result] if result else []
        else:
            # Default: parallel mode
            return self.scan_all(text, config, detectors)

    def _safe_scan(
        self,
        detector: DetectorInterface,
        text: str,
        config: Dict[str, Any],
    ) -> Optional[DetectionResult]:
        """
        Safely execute a detector scan with error handling.
        
        Returns:
            DetectionResult or None if scan fails
        """
        try:
            start_time = time.perf_counter()
            result = detector.scan(text, config)
            elapsed_ms = int((time.perf_counter() - start_time) * 1000)
            
            # Update scan time if not already set
            if result.scan_time_ms == 0:
                result = DetectionResult(
                    verdict=result.verdict,
                    severity=result.severity,
                    rules_matched=result.rules_matched,
                    confidence=result.confidence,
                    scan_time_ms=elapsed_ms,
                    detector_name=result.detector_name,
                    raw_output=result.raw_output,
                )
            
            return result
        except Exception as e:
            # Fail-open: return scan_failed result
            return DetectionResult.scan_failed(
                detector_name=detector.DETECTOR_NAME,
                error=str(e)
            )

    @classmethod
    def reset(cls) -> None:
        """
        Reset the singleton instance.
        
        Useful for testing or when configuration changes.
        """
        with cls._lock:
            if cls._instance is not None:
                cls._instance._plugins.clear()
                cls._instance._detectors.clear()
                cls._instance._discovered = False


def aggregate_results(results: List[DetectionResult]) -> DetectionResult:
    """
    Aggregate multiple detection results into a single result.
    
    Takes the highest severity verdict and combines all matched rules.
    
    Args:
        results: List of DetectionResult objects
        
    Returns:
        Single aggregated DetectionResult
    """
    if not results:
        return DetectionResult.allowed("aggregate", 0)

    # Severity priority order
    severity_order = {"high": 3, "medium": 2, "low": 1, None: 0}
    verdict_order = {"blocked": 3, "warned": 2, "scan_failed": 1, "allowed": 0}

    # Find highest severity and verdict
    max_severity = None
    max_verdict = "allowed"
    all_rules: List[str] = []
    total_scan_time = 0
    max_confidence = 0.0
    detector_names: List[str] = []

    for result in results:
        # Track detector names
        if result.detector_name not in detector_names:
            detector_names.append(result.detector_name)
        
        # Aggregate rules
        all_rules.extend(result.rules_matched)
        
        # Sum scan times
        total_scan_time += result.scan_time_ms
        
        # Track max confidence
        max_confidence = max(max_confidence, result.confidence)
        
        # Track highest severity
        if severity_order.get(result.severity, 0) > severity_order.get(max_severity, 0):
            max_severity = result.severity
        
        # Track highest verdict
        if verdict_order.get(result.verdict, 0) > verdict_order.get(max_verdict, 0):
            max_verdict = result.verdict

    return DetectionResult(
        verdict=max_verdict,
        severity=max_severity,
        rules_matched=list(set(all_rules)),  # Deduplicate rules
        confidence=max_confidence,
        scan_time_ms=total_scan_time,
        detector_name="+".join(detector_names),
    )
