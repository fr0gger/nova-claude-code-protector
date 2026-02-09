"""
Nova-tracer Detector Base Classes
=================================

Defines the abstract interface and result dataclass for all detector implementations.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class DetectionResult:
    """
    Standardized detection result across all detector backends.
    
    Attributes:
        verdict: Detection outcome - "allowed", "warned", "blocked", or "scan_failed"
        severity: Detection severity - "low", "medium", "high", or None
        rules_matched: List of rule names that triggered
        confidence: Overall confidence score (0.0 to 1.0)
        scan_time_ms: Time taken for the scan in milliseconds
        detector_name: Name of the detector that produced this result
        raw_output: Original detector response for debugging
    """
    verdict: str  # "allowed", "warned", "blocked", "scan_failed"
    severity: Optional[str]  # "low", "medium", "high"
    rules_matched: List[str]
    confidence: float  # 0.0 to 1.0
    scan_time_ms: int
    detector_name: str
    raw_output: Optional[Dict[str, Any]] = field(default=None)

    def __post_init__(self):
        """Validate field values."""
        valid_verdicts = {"allowed", "warned", "blocked", "scan_failed"}
        if self.verdict not in valid_verdicts:
            raise ValueError(f"verdict must be one of {valid_verdicts}")
        
        valid_severities = {"low", "medium", "high", None}
        if self.severity not in valid_severities:
            raise ValueError(f"severity must be one of {valid_severities}")
        
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("confidence must be between 0.0 and 1.0")

    @classmethod
    def allowed(cls, detector_name: str, scan_time_ms: int = 0) -> "DetectionResult":
        """Create an 'allowed' result with no detections."""
        return cls(
            verdict="allowed",
            severity=None,
            rules_matched=[],
            confidence=0.0,
            scan_time_ms=scan_time_ms,
            detector_name=detector_name,
        )

    @classmethod
    def scan_failed(cls, detector_name: str, error: Optional[str] = None) -> "DetectionResult":
        """Create a 'scan_failed' result for error cases."""
        return cls(
            verdict="scan_failed",
            severity=None,
            rules_matched=[],
            confidence=0.0,
            scan_time_ms=0,
            detector_name=detector_name,
            raw_output={"error": error} if error else None,
        )


class DetectorInterface(ABC):
    """
    Abstract base class for all detector implementations.
    
    Each detector plugin must:
    1. Set DETECTOR_NAME class attribute to a unique identifier
    2. Implement scan() to analyze text for threats
    3. Implement load_rules() to load detection rules
    4. Implement is_available() to check dependencies
    """
    
    DETECTOR_NAME: str = ""  # Must be overridden by subclasses
    
    @abstractmethod
    def scan(self, text: str, config: Dict[str, Any]) -> DetectionResult:
        """
        Scan text for prompt injection or security issues.
        
        Args:
            text: The text content to scan
            config: Configuration dictionary with detector-specific settings
            
        Returns:
            DetectionResult with verdict, severity, and matched rules
        """
        pass
    
    @abstractmethod
    def load_rules(self, rules_path: Path) -> None:
        """
        Load detection rules from the specified path.
        
        Args:
            rules_path: Path to directory containing rule files
        """
        pass
    
    @abstractmethod
    def is_available(self) -> bool:
        """
        Check if this detector's dependencies are installed.
        
        Returns:
            True if the detector can be used, False otherwise
        """
        pass
