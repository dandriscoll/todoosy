/**
 * Todoosy Scheme Parser
 */

import type { Scheme } from './types.js';

const TIMEZONE_HEADING_REGEX = /^#\s+Timezone\s*$/i;
const PRIORITIES_HEADING_REGEX = /^#\s+Priorities\s*$/i;
const MISC_HEADING_REGEX = /^#\s+Misc\s*$/i;
const CALENDAR_FORMAT_HEADING_REGEX = /^#\s+Calendar\s+Format\s*$/i;
const FORMATTING_STYLE_HEADING_REGEX = /^#\s+Formatting\s+Style\s*$/i;
const PRIORITY_LINE_REGEX = /^[*\-]?\s*P(\d+)\s*[-–—]\s*(.+)$/i;

export const VALID_CALENDAR_FORMATS = new Set(['yyyy-mm-dd', 'yyyy/mm/dd', 'mm/dd/yyyy', 'dd/mm/yyyy']);
export const VALID_FORMATTING_STYLES = new Set(['roomy', 'balanced', 'tight']);

export function parseScheme(text: string): Scheme {
  const lines = text.split('\n');
  const scheme: Scheme = {
    timezone: null,
    priorities: {},
    misc: 'todoosy.md/Misc',
    calendar_format: 'yyyy-mm-dd',
    formatting_style: 'roomy',
  };

  let currentSection: 'none' | 'timezone' | 'priorities' | 'misc' | 'calendar_format' | 'formatting_style' = 'none';
  let calendarFormatSet = false;
  let formattingStyleSet = false;

  for (const line of lines) {
    const trimmed = line.trim();

    // Check for section headers
    if (TIMEZONE_HEADING_REGEX.test(trimmed)) {
      currentSection = 'timezone';
      continue;
    }

    if (PRIORITIES_HEADING_REGEX.test(trimmed)) {
      currentSection = 'priorities';
      continue;
    }

    if (MISC_HEADING_REGEX.test(trimmed)) {
      currentSection = 'misc';
      continue;
    }

    if (CALENDAR_FORMAT_HEADING_REGEX.test(trimmed)) {
      currentSection = 'calendar_format';
      continue;
    }

    if (FORMATTING_STYLE_HEADING_REGEX.test(trimmed)) {
      currentSection = 'formatting_style';
      continue;
    }

    // Check if we hit another heading (any level)
    if (/^#+\s+/.test(trimmed) && currentSection !== 'none') {
      currentSection = 'none';
      continue;
    }

    // Skip empty lines
    if (trimmed === '') {
      continue;
    }

    // Process content based on current section
    if (currentSection === 'timezone') {
      // First non-empty line after Timezone heading is the timezone
      if (scheme.timezone === null) {
        scheme.timezone = trimmed;
      }
    } else if (currentSection === 'priorities') {
      // Try to parse priority line
      const match = trimmed.match(PRIORITY_LINE_REGEX);
      if (match) {
        const level = match[1];
        const label = match[2].trim();
        scheme.priorities[level] = label;
      } else if (!trimmed.startsWith('#')) {
        // Also try format without bullet: "P0 - Label"
        const altMatch = trimmed.match(/^P(\d+)\s*[-–—]\s*(.+)$/i);
        if (altMatch) {
          const level = altMatch[1];
          const label = altMatch[2].trim();
          scheme.priorities[level] = label;
        }
      }
    } else if (currentSection === 'misc') {
      // First non-empty line after Misc heading is the misc location (filename/headingname)
      if (trimmed && !trimmed.startsWith('#')) {
        scheme.misc = trimmed;
      }
    } else if (currentSection === 'calendar_format') {
      // First non-empty line after Calendar Format heading is the format
      if (!calendarFormatSet && trimmed && !trimmed.startsWith('#')) {
        scheme.calendar_format = trimmed.toLowerCase();
        calendarFormatSet = true;
      }
    } else if (currentSection === 'formatting_style') {
      // First non-empty line after Formatting Style heading is the style
      if (!formattingStyleSet && trimmed && !trimmed.startsWith('#')) {
        scheme.formatting_style = trimmed.toLowerCase();
        formattingStyleSet = true;
      }
    }
  }

  return scheme;
}
