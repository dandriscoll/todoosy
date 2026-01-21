"""
Todoosy Scheme Parser

Deprecated: This module is deprecated. Use settings.py instead.
This file is maintained for backwards compatibility.
"""

from .settings import (
    parse_scheme,
    parse_settings,
    VALID_CALENDAR_FORMATS,
    VALID_FORMATTING_STYLES,
)

__all__ = [
    'parse_scheme',
    'parse_settings',
    'VALID_CALENDAR_FORMATS',
    'VALID_FORMATTING_STYLES',
]
