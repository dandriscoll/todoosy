/**
 * Todoosy Scheme Parser
 */

import type { Scheme } from './types.js';

const TIMEZONE_HEADING_REGEX = /^#\s+Timezone\s*$/i;
const PRIORITIES_HEADING_REGEX = /^#\s+Priorities\s*$/i;
const PRIORITY_LINE_REGEX = /^[*\-]?\s*P(\d+)\s*[-–—]\s*(.+)$/i;

export function parseScheme(text: string): Scheme {
  const lines = text.split('\n');
  const scheme: Scheme = {
    timezone: null,
    priorities: {},
  };

  let currentSection: 'none' | 'timezone' | 'priorities' = 'none';

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
    }
  }

  return scheme;
}
