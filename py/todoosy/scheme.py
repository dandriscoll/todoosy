"""
Todoosy Scheme Parser
"""

import re
from .types import Scheme

TIMEZONE_HEADING_REGEX = re.compile(r'^#\s+Timezone\s*$', re.IGNORECASE)
PRIORITIES_HEADING_REGEX = re.compile(r'^#\s+Priorities\s*$', re.IGNORECASE)
PRIORITY_LINE_REGEX = re.compile(r'^[*\-]?\s*P(\d+)\s*[-–—]\s*(.+)$', re.IGNORECASE)


def parse_scheme(text: str) -> Scheme:
    """Parse a todoosy scheme file."""
    lines = text.split('\n')
    scheme = Scheme(timezone=None, priorities={})

    current_section = 'none'

    for line in lines:
        trimmed = line.strip()

        # Check for section headers
        if TIMEZONE_HEADING_REGEX.match(trimmed):
            current_section = 'timezone'
            continue

        if PRIORITIES_HEADING_REGEX.match(trimmed):
            current_section = 'priorities'
            continue

        # Check if we hit another heading (any level)
        if re.match(r'^#+\s+', trimmed) and current_section != 'none':
            current_section = 'none'
            continue

        # Skip empty lines
        if not trimmed:
            continue

        # Process content based on current section
        if current_section == 'timezone':
            if scheme.timezone is None:
                scheme.timezone = trimmed

        elif current_section == 'priorities':
            match = PRIORITY_LINE_REGEX.match(trimmed)
            if match:
                level = match.group(1)
                label = match.group(2).strip()
                scheme.priorities[level] = label
            else:
                # Try format without bullet
                alt_match = re.match(r'^P(\d+)\s*[-–—]\s*(.+)$', trimmed, re.IGNORECASE)
                if alt_match:
                    level = alt_match.group(1)
                    label = alt_match.group(2).strip()
                    scheme.priorities[level] = label

    return scheme
