"""
Todoosy Settings Parser

Parses todoosy.settings.md files using a canonical Markdown-compatible format.

## Canonical Format

Settings files use standard Markdown with level-1 headings as setting names:

    # Setting Name

    value

## Value Types

1. **Single Value** - First non-empty line after heading

       # Timezone

       America/Denver

2. **List Value** - Bulleted list items (- or *)

       # Tags

       - work
       - personal

3. **Key-Value Map** - Lines with `key - value` format

       # Priorities

       P0 - Critical
       P1 - High

## Known Settings

- Timezone: Single value (IANA timezone identifier)
- Priorities: Key-value map (P0 - Label)
- Misc: Single value (filename/headingname)
- Calendar Format: Single value (yyyy-mm-dd, mm/dd/yyyy, etc.)
- Formatting Style: Single value (roomy, balanced, tight)

## Extended Settings

Any heading not matching known settings is captured as an extended setting,
with automatic value type inference.
"""

import re
from dataclasses import dataclass
from typing import Union

from .types import Settings, Scheme, SettingValue

# Heading pattern
HEADING_REGEX = re.compile(r'^#\s+(.+?)\s*$')

# Known settings mapping (normalized name -> field name)
KNOWN_SETTINGS = {
    'timezone': 'timezone',
    'priorities': 'priorities',
    'misc': 'misc',
    'calendar format': 'calendar_format',
    'formatting style': 'formatting_style',
}

# Value parsing patterns
BULLET_LINE_REGEX = re.compile(r'^[*\-]\s+(.+)$')
KEY_VALUE_REGEX = re.compile(r'^([^-–—]+?)\s*[-–—]\s+(.+)$')
PRIORITY_KEY_REGEX = re.compile(r'^[Pp](\d+)$')

VALID_CALENDAR_FORMATS = {'yyyy-mm-dd', 'yyyy/mm/dd', 'mm/dd/yyyy', 'dd/mm/yyyy'}
VALID_FORMATTING_STYLES = {'roomy', 'balanced', 'tight'}


@dataclass
class ParsedSection:
    """Represents a parsed section from the settings file"""

    name: str
    normalized_name: str
    lines: list[str]


def normalize_name(name: str) -> str:
    """Normalize a setting name for comparison with known settings"""
    return name.lower().strip()


def parse_sections(text: str) -> list[ParsedSection]:
    """Parse the file into sections based on level-1 headings"""
    lines = text.split('\n')
    sections: list[ParsedSection] = []
    current_section: ParsedSection | None = None

    for line in lines:
        heading_match = HEADING_REGEX.match(line)

        if heading_match:
            # Save previous section
            if current_section:
                sections.append(current_section)
            # Start new section
            name = heading_match.group(1)
            current_section = ParsedSection(
                name=name, normalized_name=normalize_name(name), lines=[]
            )
        elif current_section:
            current_section.lines.append(line)

    # Don't forget the last section
    if current_section:
        sections.append(current_section)

    return sections


def parse_value(lines: list[str]) -> SettingValue:
    """Infer the value type and parse accordingly"""
    non_empty_lines: list[str] = []
    bullet_items: list[str] = []
    key_value_pairs: dict[str, str] = {}
    has_bullets = False
    has_key_values = False

    for line in lines:
        trimmed = line.strip()
        if not trimmed:
            continue

        # Check for bullet
        bullet_match = BULLET_LINE_REGEX.match(trimmed)
        if bullet_match:
            bullet_items.append(bullet_match.group(1).strip())
            has_bullets = True
            continue

        # Check for key-value
        kv_match = KEY_VALUE_REGEX.match(trimmed)
        if kv_match:
            key = kv_match.group(1).strip()
            value = kv_match.group(2).strip()
            key_value_pairs[key] = value
            has_key_values = True
            continue

        non_empty_lines.append(trimmed)

    # Determine value type based on what we found
    if has_bullets and bullet_items:
        return bullet_items

    if has_key_values and key_value_pairs:
        return key_value_pairs

    # Single value - return first non-empty line
    return non_empty_lines[0] if non_empty_lines else ''


def parse_priorities(lines: list[str]) -> dict[str, str]:
    """Parse priorities section specifically (handles P0, P1, etc. format)"""
    priorities: dict[str, str] = {}

    for line in lines:
        trimmed = line.strip()
        if not trimmed:
            continue

        # Handle bullet prefix
        content = trimmed
        bullet_match = BULLET_LINE_REGEX.match(trimmed)
        if bullet_match:
            content = bullet_match.group(1)

        # Parse key-value
        kv_match = KEY_VALUE_REGEX.match(content)
        if kv_match:
            key = kv_match.group(1).strip()
            value = kv_match.group(2).strip()

            # Extract priority number from P0, P1, etc.
            priority_match = PRIORITY_KEY_REGEX.match(key)
            if priority_match:
                priorities[priority_match.group(1)] = value

    return priorities


def parse_settings(text: str) -> Settings:
    """Parse a settings file and return structured settings"""
    sections = parse_sections(text)

    settings = Settings(
        timezone=None,
        priorities={},
        misc='todoosy.md/Misc',
        calendar_format='yyyy-mm-dd',
        formatting_style='roomy',
        extended={},
    )

    for section in sections:
        known_key = KNOWN_SETTINGS.get(section.normalized_name)

        if known_key:
            # Handle known settings
            if known_key == 'timezone':
                value = parse_value(section.lines)
                if isinstance(value, str) and value:
                    settings.timezone = value

            elif known_key == 'priorities':
                settings.priorities = parse_priorities(section.lines)

            elif known_key == 'misc':
                value = parse_value(section.lines)
                if isinstance(value, str) and value:
                    settings.misc = value

            elif known_key == 'calendar_format':
                value = parse_value(section.lines)
                if isinstance(value, str) and value:
                    settings.calendar_format = value.lower()

            elif known_key == 'formatting_style':
                value = parse_value(section.lines)
                if isinstance(value, str) and value:
                    settings.formatting_style = value.lower()

        else:
            # Extended setting - use original name as key
            value = parse_value(section.lines)
            if value != '':
                settings.extended[section.name] = value

    return settings


def parse_scheme(text: str) -> Scheme:
    """
    Parse a settings file and return legacy Scheme format.

    Deprecated: Use parse_settings instead.
    """
    settings = parse_settings(text)
    return Scheme(
        timezone=settings.timezone,
        priorities=settings.priorities,
        misc=settings.misc,
        calendar_format=settings.calendar_format,
        formatting_style=settings.formatting_style,
    )
