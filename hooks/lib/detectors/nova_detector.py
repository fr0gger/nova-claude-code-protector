"""
Nova-tracer NOVA Framework Detector Plugin
===========================================

Implements DetectorInterface for the NOVA Framework three-tier detection:
1. Keywords (regex patterns) - Fast, deterministic (~1ms)
2. Semantics (ML-based similarity) - Catches paraphrased attacks (~50ms)
3. LLM (AI-powered evaluation) - Sophisticated attack detection (~500-2000ms)

Requires the `nova-hunting` package to be installed.
"""

import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

# Use absolute imports - required for dynamic module loading by the registry
# The registry adds hooks/lib to sys.path before loading plugins
from detectors.base import DetectionResult, DetectorInterface


# Required export for plugin discovery
DETECTOR_NAME = "nova"


# NOVA imports are deferred to avoid import-time issues
# Check availability when is_available() is called
_NOVA_CHECKED = False
_NOVA_AVAILABLE = False
_NovaScanner = None
_NovaRuleFileParser = None


def _check_nova_availability():
    """Lazily check if NOVA Framework is available."""
    global _NOVA_CHECKED, _NOVA_AVAILABLE, _NovaScanner, _NovaRuleFileParser
    
    if _NOVA_CHECKED:
        return _NOVA_AVAILABLE
    
    _NOVA_CHECKED = True
    try:
        from nova.core.parser import NovaRuleFileParser
        from nova.core.scanner import NovaScanner
        _NovaScanner = NovaScanner
        _NovaRuleFileParser = NovaRuleFileParser
        _NOVA_AVAILABLE = True
    except ImportError:
        _NOVA_AVAILABLE = False
    
    return _NOVA_AVAILABLE


class NovaDetector(DetectorInterface):
    """
    NOVA Framework detector implementation.
    
    Uses the nova-hunting package for three-tier prompt injection detection.
    """
    
    DETECTOR_NAME = "nova"
    
    def __init__(self):
        """Initialize the NOVA detector."""
        self._scanner: Optional[Any] = None
        self._rules_loaded = False
        self._rules_path: Optional[Path] = None

    def is_available(self) -> bool:
        """Check if nova-hunting package is installed."""
        return _check_nova_availability()

    def load_rules(self, rules_path: Path) -> None:
        """
        Load NOVA rules from .nov files in the specified directory.
        
        Args:
            rules_path: Path to directory containing .nov rule files
        """
        if not _check_nova_availability():
            return
            
        if not rules_path.exists() or not rules_path.is_dir():
            return

        self._rules_path = rules_path
        self._scanner = _NovaScanner()
        parser = _NovaRuleFileParser()

        # Load rules from all .nov files
        rule_files = list(rules_path.glob("*.nov"))
        
        for rule_file in rule_files:
            try:
                rules = parser.parse_file(str(rule_file))
                self._scanner.add_rules(rules)
            except Exception:
                # Fail-open: skip rules that fail to load
                pass

        self._rules_loaded = True

    def scan(self, text: str, config: Dict[str, Any]) -> DetectionResult:
        """
        Scan text using NOVA Framework rules.
        
        Args:
            text: The text content to scan
            config: Configuration dict with NOVA settings
                - enable_keywords: Enable tier 1 keyword detection (default: True)
                - enable_semantics: Enable tier 2 semantic detection (default: True)
                - enable_llm: Enable tier 3 LLM detection (default: False)
                - debug: Enable debug output (default: False)
            
        Returns:
            DetectionResult with verdict, severity, and matched rules
        """
        import time
        start_time = time.perf_counter()
        
        if not _check_nova_availability():
            return DetectionResult.allowed(self.DETECTOR_NAME, 0)

        # Load rules if not already loaded
        if not self._rules_loaded:
            rules_dir = self._get_rules_directory(config)
            if rules_dir:
                self.load_rules(rules_dir)
            else:
                return DetectionResult.allowed(self.DETECTOR_NAME, 0)

        if not self._scanner:
            return DetectionResult.allowed(self.DETECTOR_NAME, 0)

        try:
            # Run the scan
            results = self._scanner.scan(text)
            
            # Process results into detections
            detections = self._process_results(results, config)
            
            elapsed_ms = int((time.perf_counter() - start_time) * 1000)
            
            if not detections:
                return DetectionResult.allowed(self.DETECTOR_NAME, elapsed_ms)

            # Determine verdict and severity from detections
            return self._build_result(detections, elapsed_ms)

        except Exception as e:
            if config.get("debug", False):
                print(f"NOVA scan error: {e}", file=sys.stderr)
            return DetectionResult.scan_failed(self.DETECTOR_NAME, str(e))

    def _get_rules_directory(self, config: Dict[str, Any]) -> Optional[Path]:
        """
        Find the rules directory.
        
        Checks multiple locations in order:
        1. Config-specified path
        2. Script's sibling rules directory
        3. Parent rules directory
        """
        # Check config first
        rules_path = config.get("rules_path")
        if rules_path:
            path = Path(rules_path)
            if path.exists() and path.is_dir():
                return path

        # Check relative to this file: hooks/lib/detectors/nova_detector.py
        # Rules are at: hooks/../rules = nova-tracer/rules
        detectors_dir = Path(__file__).parent
        lib_dir = detectors_dir.parent
        hooks_dir = lib_dir.parent
        project_dir = hooks_dir.parent

        rules_paths = [
            hooks_dir / "rules",           # hooks/rules
            project_dir / "rules",         # nova-tracer/rules
        ]

        for path in rules_paths:
            if path.exists() and path.is_dir():
                return path

        return None

    def _process_results(
        self,
        results: List[Dict[str, Any]],
        config: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        """
        Process NOVA scan results into detection dicts.
        
        Args:
            results: Raw results from NovaScanner.scan()
            config: Configuration dictionary
            
        Returns:
            List of detection dictionaries
        """
        detections = []

        for match in results:
            if not match.get("matched", False):
                continue

            meta = match.get("meta", {})
            detection = {
                "rule_name": match.get("rule_name", "unknown"),
                "severity": meta.get("severity", "medium"),
                "description": meta.get("description", ""),
                "category": meta.get("category", "unknown"),
                "matched_keywords": list(match.get("matching_keywords", {}).keys()),
                "matched_semantics": list(match.get("matching_semantics", {}).keys()),
                "llm_match": bool(match.get("matching_llm", {})),
                "confidence": 0.0,
            }
            
            # Calculate confidence based on match types
            confidence = 0.0
            if detection["matched_keywords"]:
                confidence = max(confidence, 0.7)
            if detection["matched_semantics"]:
                confidence = max(confidence, 0.8)
            if detection["llm_match"]:
                confidence = max(confidence, 0.9)
            detection["confidence"] = confidence
            
            detections.append(detection)

        return detections

    def _build_result(
        self,
        detections: List[Dict[str, Any]],
        scan_time_ms: int,
    ) -> DetectionResult:
        """
        Build a DetectionResult from processed detections.
        
        Args:
            detections: List of detection dictionaries
            scan_time_ms: Time taken for the scan
            
        Returns:
            Aggregated DetectionResult
        """
        # Get highest severity
        severities = [d.get("severity", "medium") for d in detections]
        
        if "high" in severities:
            verdict = "blocked"
            severity = "high"
        elif "medium" in severities:
            verdict = "warned"
            severity = "medium"
        else:
            verdict = "warned"
            severity = "low"

        # Collect rule names and max confidence
        rules_matched = [d.get("rule_name", "unknown") for d in detections]
        max_confidence = max((d.get("confidence", 0.0) for d in detections), default=0.0)

        return DetectionResult(
            verdict=verdict,
            severity=severity,
            rules_matched=rules_matched,
            confidence=max_confidence,
            scan_time_ms=scan_time_ms,
            detector_name=self.DETECTOR_NAME,
            raw_output={"detections": detections},
        )


def create_detector(config: Dict[str, Any]) -> DetectorInterface:
    """
    Factory function to create a NovaDetector instance.
    
    Required export for plugin discovery.
    
    Args:
        config: Configuration dictionary
        
    Returns:
        Instantiated NovaDetector
    """
    detector = NovaDetector()
    
    # Pre-load rules if path is specified in config
    rules_path = config.get("rules_path")
    if rules_path:
        detector.load_rules(Path(rules_path))
    
    return detector
