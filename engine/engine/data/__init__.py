"""Adapter-driven data layer."""

from .base import (
    Capability,
    DataSourceError,
    InternalsBar,
    MissingCredentials,
    SourceContext,
    VendorInfo,
)
from .registry import (
    KNOWN_VENDORS,
    build_congress_source,
    build_insider_source,
    build_ohlcv_source,
    build_option_source,
    vendor_info,
)
from .validation import ValidationIssue, validate

__all__ = [
    "Capability",
    "DataSourceError",
    "MissingCredentials",
    "InternalsBar",
    "SourceContext",
    "VendorInfo",
    "KNOWN_VENDORS",
    "vendor_info",
    "build_ohlcv_source",
    "build_option_source",
    "build_insider_source",
    "build_congress_source",
    "validate",
    "ValidationIssue",
]
