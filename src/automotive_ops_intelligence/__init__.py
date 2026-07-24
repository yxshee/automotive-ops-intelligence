"""Ranked, costed automation opportunity briefs for a business unit.

Agents supply assumptions. Deterministic code computes the return.
"""

from automotive_ops_intelligence.models import (
    AutomationDesign,
    Brief,
    Confidence,
    Evidence,
    Opportunity,
    OrganisationScope,
    ProcessProfile,
    ROIResult,
    SensitivityBand,
)
from automotive_ops_intelligence.roi import compute_roi, compute_sensitivity

__version__ = "0.1.0"

__all__ = [
    "AutomationDesign",
    "Brief",
    "Confidence",
    "Evidence",
    "Opportunity",
    "OrganisationScope",
    "ProcessProfile",
    "ROIResult",
    "SensitivityBand",
    "compute_roi",
    "compute_sensitivity",
]
