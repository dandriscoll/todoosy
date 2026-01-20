"""
Todoosy Scheme Parser
"""

import re
from .types import Scheme

TIMEZONE_HEADING_REGEX = re.compile(r'^#\s+Timezone\s*$', re.IGNORECASE)
PRIORITIES_HEADING_REGEX = re.compile(r'^#\s+Priorities\s*$', re.IGNORECASE)
MISC_HEADING_REGEX = re.compile(r'^#\s+Misc\s*$', re.IGNORECASE)
CALENDAR_FORMAT_HEADING_REGEX = re.compile(r'^#\s+Calendar\s+Format\s*$', re.IGNORECASE)
FORMATTING_STYLE_HEADING_REGEX = re.compile(r'^#\s+Formatting\s+Style\s*$', re.IGNORECASE)
PRIORITY_LINE_REGEX = re.compile(r'^[*\-]?\s*P(\d+)\s*[-–—]\s*(.+)$', re.IGNORECASE)

VALID_CALENDAR_FORMATS = {'yyyy-mm-dd', 'yyyy/mm/dd', 'mm/dd/yyyy', 'dd/mm/yyyy'}
VALID_FORMATTING_STYLES = {'roomy', 'balanced', 'tight'}


def parse_scheme(text: str) -> Scheme:
    """Parse a todoosy scheme file."""
    lines = text.split('\n')
    scheme = Scheme(timezone=None, priorities={}, misc='todoosy.md/Misc', calendar_format='yyyy-mm-dd', formatting_style='roomy')

    current_section = 'none'
    calendar_format_set = False
    formatting_style_set = False

    for line in lines:
        trimmed = line.strip()

        # Check for section headers
        if TIMEZONE_HEADING_REGEX.match(trimmed):
            current_section = 'timezone'
            continue

        if PRIORITIES_HEADING_REGEX.match(trimmed):
            current_section = 'priorities'
            continue

        if MISC_HEADING_REGEX.match(trimmed):
            current_section = 'misc'
            continue

        if CALENDAR_FORMAT_HEADING_REGEX.match(trimmed):
            current_section = 'calendar_format'
            continue

        if FORMATTING_STYLE_HEADING_REGEX.match(trimmed):
            current_section = 'formatting_style'
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

        elif current_section == 'misc':
            # First non-empty line after Misc heading is the misc location (filename/headingname)
            if trimmed and not trimmed.startswith('#'):
                scheme.misc = trimmed

        elif current_section == 'calendar_format':
            # First non-empty line after Calendar Format heading is the format
            if not calendar_format_set and trimmed and not trimmed.startswith('#'):
                scheme.calendar_format = trimmed.lower()
                calendar_format_set = True

        elif current_section == 'formatting_style':
            # First non-empty line after Formatting Style heading is the style
            if not formatting_style_set and trimmed and not trimmed.startswith('#'):
                scheme.formatting_style = trimmed.lower()
                formatting_style_set = True

    return scheme
