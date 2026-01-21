/**
 * Todoosy Tests - Using golden test files
 */

import * as fs from 'node:fs';
import * as path from 'node:path';
import { parse, format, lint, queryUpcoming, queryMisc, parseScheme, parseSettings } from './index.js';
import { fileURLToPath } from 'node:url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const testDataDir = path.resolve(__dirname, '../../testdata');

// Get all test case directories
function getTestCases(): string[] {
  const dirs = fs.readdirSync(testDataDir);
  return dirs
    .filter(d => fs.statSync(path.join(testDataDir, d)).isDirectory())
    .sort();
}

function loadFile(testCase: string, filename: string): string | null {
  const filePath = path.join(testDataDir, testCase, filename);
  if (fs.existsSync(filePath)) {
    return fs.readFileSync(filePath, 'utf-8');
  }
  return null;
}

function loadJson(testCase: string, filename: string): unknown | null {
  const content = loadFile(testCase, filename);
  if (content) {
    return JSON.parse(content);
  }
  return null;
}

describe('Todoosy Golden Tests', () => {
  const testCases = getTestCases();

  describe('Parser', () => {
    test.each(testCases)('%s - parse', (testCase) => {
      const input = loadFile(testCase, 'input.md');
      const expectedAst = loadJson(testCase, 'expected_ast.json');

      if (!input || !expectedAst) {
        console.warn(`Skipping ${testCase} - missing input or expected_ast`);
        return;
      }

      const { ast } = parse(input);

      // Compare items count
      expect(ast.items.length).toBe((expectedAst as any).items.length);

      // Compare each item's essential properties
      for (let i = 0; i < ast.items.length; i++) {
        const actual = ast.items[i];
        const expected = (expectedAst as any).items[i];

        expect(actual.type).toBe(expected.type);
        expect(actual.title_text).toBe(expected.title_text);
        expect(actual.metadata.due).toBe(expected.metadata.due);
        expect(actual.metadata.priority).toBe(expected.metadata.priority);
        expect(actual.metadata.estimate_minutes).toBe(expected.metadata.estimate_minutes);
        expect(actual.metadata.progress).toBe(expected.metadata.progress);
        expect(actual.comments).toEqual(expected.comments);
        expect(actual.children.length).toBe(expected.children.length);
      }

      // Compare root_ids count
      expect(ast.root_ids.length).toBe((expectedAst as any).root_ids.length);
    });
  });

  describe('Formatter', () => {
    test.each(testCases)('%s - format', (testCase) => {
      const input = loadFile(testCase, 'input.md');
      const expectedFormatted = loadFile(testCase, 'expected_formatted.md');

      if (!input || !expectedFormatted) {
        console.warn(`Skipping ${testCase} - missing input or expected_formatted`);
        return;
      }

      const formatted = format(input);
      expect(formatted).toBe(expectedFormatted);
    });
  });

  describe('Linter', () => {
    test.each(testCases)('%s - lint', (testCase) => {
      const input = loadFile(testCase, 'input.md');
      const expectedWarnings = loadJson(testCase, 'expected_warnings.json');
      const schemeText = loadFile(testCase, 'settings.md');
      const scheme = schemeText ? parseScheme(schemeText) : undefined;

      if (!input || !expectedWarnings) {
        console.warn(`Skipping ${testCase} - missing input or expected_warnings`);
        return;
      }

      const result = lint(input, scheme);

      // Compare warning codes
      const actualCodes = result.warnings.map(w => w.code).sort();
      const expectedCodes = ((expectedWarnings as any).warnings || []).map((w: any) => w.code).sort();
      expect(actualCodes).toEqual(expectedCodes);
    });
  });

  describe('Query - Upcoming', () => {
    test.each(testCases)('%s - queryUpcoming', (testCase) => {
      const input = loadFile(testCase, 'input.md');
      const expectedUpcoming = loadJson(testCase, 'expected_upcoming.json');
      const schemeText = loadFile(testCase, 'settings.md');
      const scheme = schemeText ? parseScheme(schemeText) : undefined;

      if (!input || !expectedUpcoming) {
        console.warn(`Skipping ${testCase} - missing input or expected_upcoming`);
        return;
      }

      const result = queryUpcoming(input, scheme);

      // Compare items count
      expect(result.items.length).toBe((expectedUpcoming as any).items.length);

      // Compare each item
      for (let i = 0; i < result.items.length; i++) {
        const actual = result.items[i];
        const expected = (expectedUpcoming as any).items[i];

        expect(actual.due).toBe(expected.due);
        expect(actual.priority).toBe(expected.priority);
        if (expected.priority_label) {
          expect(actual.priority_label).toBe(expected.priority_label);
        }
      }
    });
  });

  describe('Query - Misc', () => {
    test.each(testCases)('%s - queryMisc', (testCase) => {
      const input = loadFile(testCase, 'input.md');
      const expectedMisc = loadJson(testCase, 'expected_misc.json');

      if (!input || !expectedMisc) {
        console.warn(`Skipping ${testCase} - missing input or expected_misc`);
        return;
      }

      const result = queryMisc(input);

      // Compare items count
      expect(result.items.length).toBe((expectedMisc as any).items.length);

      // Compare each item title
      for (let i = 0; i < result.items.length; i++) {
        const actual = result.items[i];
        const expected = (expectedMisc as any).items[i];

        expect(actual.title_text).toBe(expected.title_text);
      }
    });
  });

  describe('Settings Parser', () => {
    test.each(testCases)('%s - parseSettings', (testCase) => {
      const settingsText = loadFile(testCase, 'settings.md');
      const expectedSettings = loadJson(testCase, 'expected_settings.json');

      if (!settingsText || !expectedSettings) {
        // Settings are optional
        return;
      }

      const settings = parseSettings(settingsText);

      expect(settings.timezone).toBe((expectedSettings as any).timezone);
      expect(settings.priorities).toEqual((expectedSettings as any).priorities);
    });
  });
});

// Additional unit tests for edge cases
describe('Parser Edge Cases', () => {
  test('handles empty document', () => {
    const { ast } = parse('');
    expect(ast.items).toHaveLength(0);
    expect(ast.root_ids).toHaveLength(0);
  });

  test('handles document with only whitespace', () => {
    const { ast } = parse('   \n\n   ');
    expect(ast.items).toHaveLength(0);
  });

  test('parses numbered lists', () => {
    const { ast } = parse('# Tasks\n\n1. First task\n2. Second task');
    expect(ast.items).toHaveLength(3);
    expect(ast.items[1].title_text).toBe('First task');
    expect(ast.items[2].title_text).toBe('Second task');
  });

  test('parses asterisk lists', () => {
    const { ast } = parse('# Tasks\n\n* Task one\n* Task two');
    expect(ast.items).toHaveLength(3);
    expect(ast.items[1].title_text).toBe('Task one');
  });

  test('normalizes 2-digit year dates', () => {
    const { ast } = parse('- Task (due 01/15/26)');
    expect(ast.items[0].metadata.due).toBe('2026-01-15');
  });

  test('handles estimate with days', () => {
    const { ast } = parse('- Task (2d)');
    expect(ast.items[0].metadata.estimate_minutes).toBe(960);
  });

  test('parses soft dates with tilde prefix', () => {
    const { ast } = parse('- Task (due ~2026-01-25)');
    expect(ast.items[0].metadata.due).toBe('2026-01-25');
    expect(ast.items[0].metadata.due_soft).toBe(true);
  });

  test('parses soft text dates with tilde prefix', () => {
    const { ast } = parse('- Task (due ~Jan 30)');
    expect(ast.items[0].metadata.due).toBe('2026-01-30');
    expect(ast.items[0].metadata.due_soft).toBe(true);
  });

  test('parses standalone soft dates with tilde prefix', () => {
    const { ast } = parse('- Task (~2026-02-10)');
    expect(ast.items[0].metadata.due).toBe('2026-02-10');
    expect(ast.items[0].metadata.due_soft).toBe(true);
  });

  test('parses standalone soft text dates with tilde prefix', () => {
    const { ast } = parse('- Task (~Feb 15)');
    expect(ast.items[0].metadata.due).toBe('2026-02-15');
    expect(ast.items[0].metadata.due_soft).toBe(true);
  });

  test('non-soft dates have null due_soft', () => {
    const { ast } = parse('- Task (due 2026-01-20)');
    expect(ast.items[0].metadata.due).toBe('2026-01-20');
    expect(ast.items[0].metadata.due_soft).toBeNull();
  });
});

describe('Formatter Edge Cases', () => {
  test('adds Misc section if missing', () => {
    const formatted = format('# Work\n\n- Task');
    expect(formatted).toContain('# Misc');
  });

  test('preserves non-metadata parentheses', () => {
    const input = '# Work\n\n- Call John (CEO)\n\n# Misc\n';
    const formatted = format(input);
    expect(formatted).toContain('(CEO)');
  });

  test('preserves soft date tilde prefix', () => {
    const input = '# Work\n\n- Task (due ~2026-01-25)\n\n# Misc\n';
    const formatted = format(input);
    expect(formatted).toContain('(due ~2026-01-25)');
  });

  test('roomy style adds blank lines around all headings', () => {
    const input = '# Work\n\n## Sub\n\n- Task\n\n# Misc\n';
    const scheme = { timezone: null, priorities: {}, misc: 'todoosy.md/Misc', calendar_format: 'yyyy-mm-dd', formatting_style: 'roomy' };
    const formatted = format(input, scheme);
    // Should have blank line after ## Sub
    expect(formatted).toContain('## Sub\n\n- Task');
  });

  test('balanced style adds blank lines only around top-level headings', () => {
    const input = '# Work\n\n## Sub\n\n- Task\n\n# Misc\n';
    const scheme = { timezone: null, priorities: {}, misc: 'todoosy.md/Misc', calendar_format: 'yyyy-mm-dd', formatting_style: 'balanced' };
    const formatted = format(input, scheme);
    // Should NOT have blank line after ## Sub
    expect(formatted).toContain('## Sub\n- Task');
  });

  test('tight style removes all blank lines around headings', () => {
    const input = '# Work\n\n## Sub\n\n- Task\n\n# Misc\n';
    const scheme = { timezone: null, priorities: {}, misc: 'todoosy.md/Misc', calendar_format: 'yyyy-mm-dd', formatting_style: 'tight' };
    const formatted = format(input, scheme);
    // Should NOT have blank lines around headings
    expect(formatted).toContain('# Work\n## Sub\n- Task');
  });
});

describe('Linter Edge Cases', () => {
  test('warns on missing Misc section', () => {
    const result = lint('# Work\n\n- Task');
    expect(result.warnings.some(w => w.code === 'MISC_MISSING')).toBe(true);
  });

  test('no warnings on valid document', () => {
    const result = lint('# Work\n\n- Task (due 2026-01-15 p1 2h)\n\n# Misc\n');
    expect(result.warnings).toHaveLength(0);
  });
});

describe('Scheme Parser Edge Cases', () => {
  test('handles empty scheme', () => {
    const scheme = parseScheme('');
    expect(scheme.timezone).toBeNull();
    expect(scheme.priorities).toEqual({});
  });

  test('handles scheme with only timezone', () => {
    const scheme = parseScheme('# Timezone\n\nEurope/London');
    expect(scheme.timezone).toBe('Europe/London');
    expect(scheme.priorities).toEqual({});
  });

  test('handles various bullet formats', () => {
    const scheme = parseScheme(`
# Priorities

- P0 - Critical
* P1 - High
P2 - Medium
`);
    expect(scheme.priorities['0']).toBe('Critical');
    expect(scheme.priorities['1']).toBe('High');
    expect(scheme.priorities['2']).toBe('Medium');
  });

  test('parses formatting_style', () => {
    const scheme = parseScheme(`
# Formatting Style

balanced
`);
    expect(scheme.formatting_style).toBe('balanced');
  });

  test('defaults formatting_style to roomy', () => {
    const scheme = parseScheme('');
    expect(scheme.formatting_style).toBe('roomy');
  });
});

describe('Settings Parser Extended Settings', () => {
  test('parses single value extended setting', () => {
    const settings = parseSettings(`
# Timezone

America/Denver

# UI Color

blue
`);
    expect(settings.timezone).toBe('America/Denver');
    expect(settings.extended['UI Color']).toBe('blue');
  });

  test('parses list extended setting', () => {
    const settings = parseSettings(`
# Tags

- work
- personal
- urgent
`);
    expect(settings.extended['Tags']).toEqual(['work', 'personal', 'urgent']);
  });

  test('parses key-value extended setting', () => {
    const settings = parseSettings(`
# Theme Colors

background - #ffffff
foreground - #000000
accent - #0066cc
`);
    expect(settings.extended['Theme Colors']).toEqual({
      background: '#ffffff',
      foreground: '#000000',
      accent: '#0066cc',
    });
  });

  test('preserves original capitalization in extended setting names', () => {
    const settings = parseSettings(`
# My Custom Setting

value
`);
    expect(settings.extended['My Custom Setting']).toBe('value');
    expect(settings.extended['my custom setting']).toBeUndefined();
  });

  test('ignores empty extended settings', () => {
    const settings = parseSettings(`
# Empty Setting

# Non-empty Setting

value
`);
    expect(settings.extended['Empty Setting']).toBeUndefined();
    expect(settings.extended['Non-empty Setting']).toBe('value');
  });
});
