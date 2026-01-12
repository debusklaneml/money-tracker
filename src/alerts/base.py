"""Base alert framework and registry."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional, Any


class AlertSeverity(Enum):
    """Alert severity levels."""
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class AlertType(Enum):
    """Types of alerts the system can generate."""
    UNUSUAL_SPENDING = "unusual_spending"
    BUDGET_OVERSPENDING = "budget_overspending"
    RECURRING_CHANGE = "recurring_change"
    RECURRING_MISSING = "recurring_missing"


@dataclass
class Alert:
    """Represents a detected alert."""
    alert_type: AlertType
    severity: AlertSeverity
    title: str
    description: str
    related_entity_id: Optional[str] = None
    related_entity_type: Optional[str] = None
    metadata: Optional[dict[str, Any]] = None
    created_at: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> dict:
        """Convert alert to dictionary for storage."""
        return {
            'alert_type': self.alert_type.value,
            'severity': self.severity.value,
            'title': self.title,
            'description': self.description,
            'related_entity_id': self.related_entity_id,
            'related_entity_type': self.related_entity_type,
            'metadata': self.metadata,
            'created_at': self.created_at.isoformat()
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'Alert':
        """Create alert from dictionary."""
        return cls(
            alert_type=AlertType(data['alert_type']),
            severity=AlertSeverity(data['severity']),
            title=data['title'],
            description=data['description'],
            related_entity_id=data.get('related_entity_id'),
            related_entity_type=data.get('related_entity_type'),
            metadata=data.get('metadata'),
            created_at=datetime.fromisoformat(data['created_at']) if data.get('created_at') else datetime.utcnow()
        )


class AlertDetector(ABC):
    """Base class for alert detection algorithms."""

    def __init__(self, db, config: Optional[dict] = None):
        self.db = db
        self.config = config or {}

    @abstractmethod
    def detect(self, budget_id: str) -> list[Alert]:
        """Run detection and return any alerts found."""
        pass

    @abstractmethod
    def get_config_schema(self) -> dict[str, Any]:
        """Return configuration schema for this detector."""
        pass

    @property
    @abstractmethod
    def alert_type(self) -> AlertType:
        """Return the type of alerts this detector produces."""
        pass


class AlertRegistry:
    """Registry of all alert detectors."""

    _detectors: dict[AlertType, type[AlertDetector]] = {}

    @classmethod
    def register(cls, detector_class: type[AlertDetector]) -> type[AlertDetector]:
        """Register a detector class. Can be used as a decorator."""
        # We'll instantiate later when we have db and config
        cls._detectors[detector_class.alert_type.fget(None)] = detector_class
        return detector_class

    @classmethod
    def get_detector(cls, alert_type: AlertType, db, config: Optional[dict] = None) -> AlertDetector:
        """Get an instance of a detector."""
        if alert_type not in cls._detectors:
            raise ValueError(f"No detector registered for {alert_type}")
        return cls._detectors[alert_type](db, config)

    @classmethod
    def run_all(cls, budget_id: str, db, config: Optional[dict] = None) -> list[Alert]:
        """Run all registered detectors and return combined alerts."""
        alerts = []
        for alert_type, detector_class in cls._detectors.items():
            try:
                detector = detector_class(db, config)
                detected = detector.detect(budget_id)
                alerts.extend(detected)
            except Exception as e:
                # Log error but continue with other detectors
                print(f"Error running {alert_type} detector: {e}")
        return alerts

    @classmethod
    def get_registered_types(cls) -> list[AlertType]:
        """Get list of registered alert types."""
        return list(cls._detectors.keys())


def save_alerts_to_db(db, budget_id: str, alerts: list[Alert]) -> int:
    """Save alerts to database, avoiding duplicates. Returns count saved."""
    saved = 0
    for alert in alerts:
        # Check if similar alert already exists
        if alert.related_entity_id:
            exists = db.alert_exists(budget_id, alert.alert_type.value, alert.related_entity_id)
            if exists:
                continue

        db.save_alert(
            budget_id=budget_id,
            alert_type=alert.alert_type.value,
            severity=alert.severity.value,
            title=alert.title,
            description=alert.description,
            related_entity_id=alert.related_entity_id,
            related_entity_type=alert.related_entity_type,
            metadata=alert.metadata
        )
        saved += 1

    return saved
