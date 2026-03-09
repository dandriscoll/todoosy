/**
 * Todoosy Settings Parser
 *
 * Parses todoosy.settings.md files using a canonical Markdown-compatible format.
 *
 * ## Canonical Format
 *
 * Settings files use standard Markdown with level-1 headings as setting names:
 *
 * ```markdown
 * # Setting Name
 *
 * value
 * ```
 *
 * ## Value Types
 *
 * 1. **Single Value** - First non-empty line after heading
 *    ```markdown
 *    # Timezone
 *
 *    America/Denver
 *    ```
 *
 * 2. **List Value** - Bulleted list items (- or *)
 *    ```markdown
 *    # Tags
 *
 *    - work
 *    - personal
 *    ```
 *
 * 3. **Key-Value Map** - Lines with `key - value` format
 *    ```markdown
 *    # Priorities
 *
 *    P0 - Critical
 *    P1 - High
 *    ```
 *
 * ## Known Settings
 *
 * - Timezone: Single value (IANA timezone identifier)
 * - Priorities: Key-value map (P0 - Label)
 * - Misc: Single value (filename/headingname)
 * - Calendar Format: Single value (yyyy-mm-dd, mm/dd/yyyy, etc.)
 * - Formatting Style: Single value (roomy, balanced, tight)
 *
 * ## Extended Settings
 *
 * Any heading not matching known settings is captured as an extended setting,
 * with automatic value type inference.
 */

import type { Settings, SettingValue, Scheme } from './types.js';

// Heading patterns for known settings
const HEADING_REGEX = /^#{1,6}\s+(.+?)\s*$/;
const KNOWN_SETTINGS: Record<string, string> = {
  timezone: 'timezone',
  priorities: 'priorities',
  misc: 'misc',
  'calendar format': 'calendar_format',
  'formatting style': 'formatting_style',
};

// Value parsing patterns
const BULLET_LINE_REGEX = /^[*\-]\s+(.+)$/;
const KEY_VALUE_REGEX = /^([^-–—]+?)\s*[-–—]\s+(.+)$/;
const PRIORITY_KEY_REGEX = /^[Pp](\d+)$/;

export const VALID_CALENDAR_FORMATS = new Set([
  'yyyy-mm-dd',
  'yyyy/mm/dd',
  'mm/dd/yyyy',
  'dd/mm/yyyy',
]);
export const VALID_FORMATTING_STYLES = new Set(['roomy', 'balanced', 'tight']);

/**
 * Represents a parsed section from the settings file
 */
interface ParsedSection {
  name: string;
  normalizedName: string;
  lines: string[];
}

/**
 * Normalize a setting name for comparison with known settings
 */
function normalizeName(name: string): string {
  return name.toLowerCase().trim();
}

/**
 * Parse the file into sections based on level-1 headings
 */
function parseSections(text: string): ParsedSection[] {
  const lines = text.split('\n');
  const sections: ParsedSection[] = [];
  let currentSection: ParsedSection | null = null;

  for (const line of lines) {
    const headingMatch = line.match(HEADING_REGEX);

    if (headingMatch) {
      // Save previous section
      if (currentSection) {
        sections.push(currentSection);
      }
      // Start new section
      const name = headingMatch[1];
      currentSection = {
        name,
        normalizedName: normalizeName(name),
        lines: [],
      };
    } else if (currentSection) {
      currentSection.lines.push(line);
    }
  }

  // Don't forget the last section
  if (currentSection) {
    sections.push(currentSection);
  }

  return sections;
}

/**
 * Infer the value type and parse accordingly
 */
function parseValue(lines: string[]): SettingValue {
  const nonEmptyLines: string[] = [];
  const bulletItems: string[] = [];
  const keyValuePairs: Record<string, string> = {};
  let hasBullets = false;
  let hasKeyValues = false;

  for (const line of lines) {
    const trimmed = line.trim();
    if (!trimmed) continue;

    // Check for bullet
    const bulletMatch = trimmed.match(BULLET_LINE_REGEX);
    if (bulletMatch) {
      bulletItems.push(bulletMatch[1].trim());
      hasBullets = true;
      continue;
    }

    // Check for key-value
    const kvMatch = trimmed.match(KEY_VALUE_REGEX);
    if (kvMatch) {
      const key = kvMatch[1].trim();
      const value = kvMatch[2].trim();
      keyValuePairs[key] = value;
      hasKeyValues = true;
      continue;
    }

    nonEmptyLines.push(trimmed);
  }

  // Determine value type based on what we found
  if (hasBullets && bulletItems.length > 0) {
    return bulletItems;
  }

  if (hasKeyValues && Object.keys(keyValuePairs).length > 0) {
    return keyValuePairs;
  }

  // Single value - return first non-empty line
  return nonEmptyLines.length > 0 ? nonEmptyLines[0] : '';
}

/**
 * Parse priorities section specifically (handles P0, P1, etc. format)
 */
function parsePriorities(lines: string[]): Record<string, string> {
  const priorities: Record<string, string> = {};

  for (const line of lines) {
    const trimmed = line.trim();
    if (!trimmed) continue;

    // Handle bullet prefix
    let content = trimmed;
    const bulletMatch = trimmed.match(BULLET_LINE_REGEX);
    if (bulletMatch) {
      content = bulletMatch[1];
    }

    // Parse key-value
    const kvMatch = content.match(KEY_VALUE_REGEX);
    if (kvMatch) {
      const key = kvMatch[1].trim();
      const value = kvMatch[2].trim();

      // Extract priority number from P0, P1, etc.
      const priorityMatch = key.match(PRIORITY_KEY_REGEX);
      if (priorityMatch) {
        priorities[priorityMatch[1]] = value;
      }
    }
  }

  return priorities;
}

/**
 * Parse a settings file and return structured settings
 */
export function parseSettings(text: string): Settings {
  const sections = parseSections(text);

  const settings: Settings = {
    timezone: null,
    priorities: {},
    misc: 'todoosy.md/Misc',
    calendar_format: 'yyyy-mm-dd',
    formatting_style: 'roomy',
    extended: {},
  };

  for (const section of sections) {
    const knownKey = KNOWN_SETTINGS[section.normalizedName];

    if (knownKey) {
      // Handle known settings
      switch (knownKey) {
        case 'timezone': {
          const value = parseValue(section.lines);
          if (typeof value === 'string' && value) {
            settings.timezone = value;
          }
          break;
        }
        case 'priorities': {
          settings.priorities = parsePriorities(section.lines);
          break;
        }
        case 'misc': {
          const value = parseValue(section.lines);
          if (typeof value === 'string' && value) {
            settings.misc = value;
          }
          break;
        }
        case 'calendar_format': {
          const value = parseValue(section.lines);
          if (typeof value === 'string' && value) {
            settings.calendar_format = value.toLowerCase();
          }
          break;
        }
        case 'formatting_style': {
          const value = parseValue(section.lines);
          if (typeof value === 'string' && value) {
            settings.formatting_style = value.toLowerCase();
          }
          break;
        }
      }
    } else {
      // Extended setting - use original name as key
      const value = parseValue(section.lines);
      if (value !== '') {
        settings.extended[section.name] = value;
      }
    }
  }

  return settings;
}

/**
 * Parse a settings file and return legacy Scheme format
 * @deprecated Use parseSettings instead
 */
export function parseScheme(text: string): Scheme {
  const settings = parseSettings(text);
  return {
    timezone: settings.timezone,
    priorities: settings.priorities,
    misc: settings.misc,
    calendar_format: settings.calendar_format,
    formatting_style: settings.formatting_style,
  };
}
