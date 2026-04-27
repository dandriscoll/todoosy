/**
 * Todoosy Tests - Using golden test files
 */

import * as fs from 'node:fs';
import * as path from 'node:path';
import { parse, format, lint, queryUpcoming, queryMisc, parseScheme, parseSettings, parseTokensInParenGroup, extractParenGroups } from './index.js';
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
        if ('due_start' in expected.metadata) {
          expect(actual.metadata.due_start).toBe(expected.metadata.due_start);
        }
        if ('due_soft' in expected.metadata) {
          expect(actual.metadata.due_soft).toBe(expected.metadata.due_soft);
        }
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

describe('parseTokensInParenGroup', () => {
  test('parses priority token', () => {
    const result = parseTokensInParenGroup('p1', 0);
    expect(result.tokens).toHaveLength(1);
    expect(result.tokens[0].type).toBe('priority');
    expect(result.tokens[0].value).toBe(1);
    expect(result.hasRecognizedTokens).toBe(true);
  });

  test('parses due date with ISO format', () => {
    const result = parseTokensInParenGroup('due 2026-01-20', 0);
    expect(result.tokens).toHaveLength(1);
    expect(result.tokens[0].type).toBe('due');
    expect(result.tokens[0].value).toBe('2026-01-20');
  });

  test('parses soft due date with tilde', () => {
    const result = parseTokensInParenGroup('due ~2026-01-25', 0);
    expect(result.tokens).toHaveLength(1);
    expect(result.tokens[0].type).toBe('due');
    expect(result.tokens[0].value).toBe('2026-01-25');
    expect(result.tokens[0].soft).toBe(true);
  });

  test('parses estimate in minutes', () => {
    const result = parseTokensInParenGroup('30m', 0);
    expect(result.tokens).toHaveLength(1);
    expect(result.tokens[0].type).toBe('estimate');
    expect(result.tokens[0].value).toBe(30);
  });

  test('parses estimate in hours', () => {
    const result = parseTokensInParenGroup('2h', 0);
    expect(result.tokens).toHaveLength(1);
    expect(result.tokens[0].type).toBe('estimate');
    expect(result.tokens[0].value).toBe(120);
  });

  test('parses estimate in days', () => {
    const result = parseTokensInParenGroup('1d', 0);
    expect(result.tokens).toHaveLength(1);
    expect(result.tokens[0].type).toBe('estimate');
    expect(result.tokens[0].value).toBe(480);
  });

  test('parses progress state done', () => {
    const result = parseTokensInParenGroup('done', 0);
    expect(result.tokens).toHaveLength(1);
    expect(result.tokens[0].type).toBe('progress');
    expect(result.tokens[0].value).toBe('done');
  });

  test('parses progress state in progress', () => {
    const result = parseTokensInParenGroup('in progress', 0);
    expect(result.tokens).toHaveLength(1);
    expect(result.tokens[0].type).toBe('progress');
    expect(result.tokens[0].value).toBe('in progress');
  });

  test('parses progress state blocked', () => {
    const result = parseTokensInParenGroup('blocked', 0);
    expect(result.tokens).toHaveLength(1);
    expect(result.tokens[0].type).toBe('progress');
    expect(result.tokens[0].value).toBe('blocked');
  });

  test('parses multiple tokens', () => {
    const result = parseTokensInParenGroup('due 2026-01-20, p1, 2h', 0);
    expect(result.tokens).toHaveLength(3);
    expect(result.tokens[0].type).toBe('due');
    expect(result.tokens[1].type).toBe('priority');
    expect(result.tokens[2].type).toBe('estimate');
    expect(result.hasRecognizedTokens).toBe(true);
  });

  test('parses text date format Month Day', () => {
    const result = parseTokensInParenGroup('due Jan 15', 0);
    expect(result.tokens).toHaveLength(1);
    expect(result.tokens[0].type).toBe('due');
    expect(result.tokens[0].value).toMatch(/^\d{4}-01-15$/);
  });

  test('parses text date format Day Month', () => {
    const result = parseTokensInParenGroup('due 15 Jan', 0);
    expect(result.tokens).toHaveLength(1);
    expect(result.tokens[0].type).toBe('due');
    expect(result.tokens[0].value).toMatch(/^\d{4}-01-15$/);
  });

  test('parses standalone date without due prefix', () => {
    const result = parseTokensInParenGroup('2026-02-01', 0);
    expect(result.tokens).toHaveLength(1);
    expect(result.tokens[0].type).toBe('due');
    expect(result.tokens[0].value).toBe('2026-02-01');
  });

  test('parses standalone soft date without due prefix', () => {
    const result = parseTokensInParenGroup('~2026-02-01', 0);
    expect(result.tokens).toHaveLength(1);
    expect(result.tokens[0].type).toBe('due');
    expect(result.tokens[0].value).toBe('2026-02-01');
    expect(result.tokens[0].soft).toBe(true);
  });

  test('returns empty tokens for unrecognized content', () => {
    const result = parseTokensInParenGroup('CEO', 0);
    expect(result.tokens).toHaveLength(0);
    expect(result.hasRecognizedTokens).toBe(false);
  });

  test('preserves content in result', () => {
    const result = parseTokensInParenGroup('p2, 1h', 0);
    expect(result.content).toBe('p2, 1h');
  });

  test('calculates correct positions with groupStart offset', () => {
    const result = parseTokensInParenGroup('p1', 10);
    expect(result.tokens[0].start).toBe(11); // groupStart + 1 for opening paren
    expect(result.tokens[0].end).toBe(13);
  });
});

describe('extractParenGroups', () => {
  test('extracts single parenthetical group', () => {
    const result = extractParenGroups('Task (p1)', 0);
    expect(result).toHaveLength(1);
    expect(result[0].content).toBe('p1');
    expect(result[0].hasRecognizedTokens).toBe(true);
  });

  test('extracts multiple parenthetical groups', () => {
    const result = extractParenGroups('Task (p1) (2h)', 0);
    expect(result).toHaveLength(2);
    expect(result[0].content).toBe('p1');
    expect(result[1].content).toBe('2h');
  });

  test('handles nested parentheses', () => {
    const result = extractParenGroups('Task (outer (inner))', 0);
    expect(result).toHaveLength(1);
    expect(result[0].content).toBe('outer (inner)');
  });

  test('handles unmatched opening paren', () => {
    const result = extractParenGroups('Task (incomplete', 0);
    expect(result).toHaveLength(0);
  });

  test('returns empty array for no parentheses', () => {
    const result = extractParenGroups('Task without parens', 0);
    expect(result).toHaveLength(0);
  });

  test('correctly identifies non-metadata parentheses', () => {
    const result = extractParenGroups('Call John (CEO)', 0);
    expect(result).toHaveLength(1);
    expect(result[0].content).toBe('CEO');
    expect(result[0].hasRecognizedTokens).toBe(false);
  });

  test('tracks correct start and end positions', () => {
    const result = extractParenGroups('Task (p1)', 0);
    expect(result[0].start).toBe(5); // position of opening paren
    expect(result[0].end).toBe(9); // position after closing paren
  });

  test('handles empty parentheses', () => {
    const result = extractParenGroups('Task ()', 0);
    expect(result).toHaveLength(1);
    expect(result[0].content).toBe('');
    expect(result[0].hasRecognizedTokens).toBe(false);
  });

  test('parses complex metadata in group', () => {
    const result = extractParenGroups('Task (due 2026-01-20, p1, 2h, in progress)', 0);
    expect(result).toHaveLength(1);
    expect(result[0].tokens).toHaveLength(4);
    expect(result[0].tokens.map(t => t.type)).toEqual(['due', 'priority', 'estimate', 'progress']);
  });

  test('handles adjacent parenthetical groups', () => {
    const result = extractParenGroups('(p1)(2h)', 0);
    expect(result).toHaveLength(2);
    expect(result[0].content).toBe('p1');
    expect(result[1].content).toBe('2h');
  });
});

describe('Today/tomorrow keyword resolution', () => {
  // 2026-04-27 is a Monday. Anchored UTC instant.
  const fixedNow = new Date('2026-04-27T12:00:00Z');

  test('today resolves after due', () => {
    const { ast } = parse('- Task (due today)\n# Misc\n', { now: fixedNow });
    expect(ast.items[0].metadata.due).toBe('2026-04-27');
    expect(ast.items[0].metadata.due_soft).toBeNull();
  });

  test('tomorrow resolves after due', () => {
    const { ast } = parse('- Task (due tomorrow)\n# Misc\n', { now: fixedNow });
    expect(ast.items[0].metadata.due).toBe('2026-04-28');
  });

  test('soft tomorrow resolves with prefix', () => {
    const { ast } = parse('- Task (~tomorrow)\n# Misc\n', { now: fixedNow });
    expect(ast.items[0].metadata.due).toBe('2026-04-28');
    expect(ast.items[0].metadata.due_soft).toBe(true);
  });

  test('today is case-insensitive', () => {
    const { ast } = parse('- Task (TODAY)\n# Misc\n', { now: fixedNow });
    expect(ast.items[0].metadata.due).toBe('2026-04-27');
  });

  test('formatter emits concrete dates, never keywords', () => {
    const out = format('- Task (due today)\n# Misc\n', undefined, undefined, { now: fixedNow });
    expect(out).toContain('due 2026-04-27');
    expect(out).not.toContain('today');
  });
});

describe('Relative-date offsets', () => {
  const fixedNow = new Date('2026-04-27T12:00:00Z');

  test('digit + week short form', () => {
    const { ast } = parse('- Task (due 2w)\n# Misc\n', { now: fixedNow });
    expect(ast.items[0].metadata.due).toBe('2026-05-11');
  });

  test('digit + days long form', () => {
    const { ast } = parse('- Task (due 3 days)\n# Misc\n', { now: fixedNow });
    expect(ast.items[0].metadata.due).toBe('2026-04-30');
  });

  test('"in" prefix is optional', () => {
    const a = parse('- A (due in 2 weeks)\n# Misc\n', { now: fixedNow });
    const b = parse('- B (due 2 weeks)\n# Misc\n', { now: fixedNow });
    expect(a.ast.items[0].metadata.due).toBe(b.ast.items[0].metadata.due);
  });

  test('"from now" suffix is optional', () => {
    const a = parse('- A (due 2 weeks from now)\n# Misc\n', { now: fixedNow });
    const b = parse('- B (due 2 weeks)\n# Misc\n', { now: fixedNow });
    expect(a.ast.items[0].metadata.due).toBe(b.ast.items[0].metadata.due);
  });

  test('number-words 1-31', () => {
    const { ast: a } = parse('- A (due in two weeks)\n# Misc\n', { now: fixedNow });
    expect(a.items[0].metadata.due).toBe('2026-05-11');
    const { ast: b } = parse('- B (due in twenty-one days)\n# Misc\n', { now: fixedNow });
    expect(b.items[0].metadata.due).toBe('2026-05-18');
    const { ast: c } = parse('- C (due in thirty-one days)\n# Misc\n', { now: fixedNow });
    expect(c.items[0].metadata.due).toBe('2026-05-28');
  });

  test('compound number-word "twenty one" with space', () => {
    const { ast } = parse('- Task (due in twenty one days)\n# Misc\n', { now: fixedNow });
    expect(ast.items[0].metadata.due).toBe('2026-05-18');
  });

  test('months are calendar-aware (Jan 31 + 1 month clips to Feb 28/29)', () => {
    const jan31 = new Date('2026-01-31T12:00:00Z');
    const { ast } = parse('- Task (due in 1 month)\n# Misc\n', { now: jan31 });
    expect(ast.items[0].metadata.due).toBe('2026-02-28');
  });

  test('bare 2d remains an estimate, not a relative date', () => {
    const { ast } = parse('- Task (2d)\n# Misc\n', { now: fixedNow });
    expect(ast.items[0].metadata.due).toBeNull();
    expect(ast.items[0].metadata.estimate_minutes).toBe(960); // 2 * 480
  });

  test('"in progress" still parses as progress, not relative date', () => {
    const { ast } = parse('- Task (in progress)\n# Misc\n', { now: fixedNow });
    expect(ast.items[0].metadata.progress).toBe('in progress');
    expect(ast.items[0].metadata.due).toBeNull();
  });
});

describe('Window span syntax', () => {
  const fixedNow = new Date('2026-04-27T12:00:00Z');

  test('ISO span standalone', () => {
    const { ast } = parse('- Task (2026-04-24~2026-05-08)\n# Misc\n', { now: fixedNow });
    expect(ast.items[0].metadata.due_start).toBe('2026-04-24');
    expect(ast.items[0].metadata.due).toBe('2026-05-08');
    expect(ast.items[0].metadata.due_soft).toBe(true);
  });

  test('ISO span after due', () => {
    const { ast } = parse('- Task (due 2026-04-24~2026-05-08)\n# Misc\n', { now: fixedNow });
    expect(ast.items[0].metadata.due_start).toBe('2026-04-24');
    expect(ast.items[0].metadata.due).toBe('2026-05-08');
  });

  test('keyword + relative span', () => {
    const { ast } = parse('- Task (today~2w)\n# Misc\n', { now: fixedNow });
    expect(ast.items[0].metadata.due_start).toBe('2026-04-27');
    expect(ast.items[0].metadata.due).toBe('2026-05-11');
  });

  test('text-date span', () => {
    const { ast } = parse('- Task (Apr 24 2026~May 8 2026)\n# Misc\n', { now: fixedNow });
    expect(ast.items[0].metadata.due_start).toBe('2026-04-24');
    expect(ast.items[0].metadata.due).toBe('2026-05-08');
  });

  test('formatter emits start~end form', () => {
    const out = format('- Task (Apr 24 2026~May 8 2026)\n# Misc\n', undefined, undefined, { now: fixedNow });
    expect(out).toContain('due 2026-04-24~2026-05-08');
  });

  test('queryUpcoming sorts spans by due_start', () => {
    const text = '# Tasks\n- Span (2026-05-01~2026-06-01)\n- Hard (due 2026-05-15)\n# Misc\n';
    const result = queryUpcoming(text, undefined, { now: fixedNow });
    // Span starts 2026-05-01, hard is 2026-05-15. Span should sort first.
    expect(result.items[0].id).toBe(ast0Id(text));
    function ast0Id(t: string) { return parse(t).ast.items[1].id; }
  });
});

describe('Timezone-aware "today"', () => {
  test('settings timezone affects today resolution', () => {
    // Same UTC instant: 2026-04-27 23:00 UTC. In America/Los_Angeles that's still 2026-04-27 16:00.
    // In Asia/Tokyo it's 2026-04-28 08:00.
    const instant = new Date('2026-04-27T23:00:00Z');
    const settingsLA = { timezone: 'America/Los_Angeles', priorities: {}, misc: 'todoosy.md/Misc', calendar_format: 'yyyy-mm-dd', formatting_style: 'roomy', extended: {} };
    const settingsTokyo = { timezone: 'Asia/Tokyo', priorities: {}, misc: 'todoosy.md/Misc', calendar_format: 'yyyy-mm-dd', formatting_style: 'roomy', extended: {} };

    const a = parse('- Task (due today)\n# Misc\n', { now: instant, settings: settingsLA });
    const b = parse('- Task (due today)\n# Misc\n', { now: instant, settings: settingsTokyo });

    expect(a.ast.items[0].metadata.due).toBe('2026-04-27');
    expect(b.ast.items[0].metadata.due).toBe('2026-04-28');
  });

  test('UTC default when no timezone setting', () => {
    const instant = new Date('2026-04-27T23:30:00Z');
    const { ast } = parse('- Task (due today)\n# Misc\n', { now: instant });
    expect(ast.items[0].metadata.due).toBe('2026-04-27');
  });
});
