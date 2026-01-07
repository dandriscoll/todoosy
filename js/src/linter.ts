/**
 * Todoosy Linter
 */

import { parse } from './parser.js';
import type { Warning, LintResult, Scheme } from './types.js';

const VALID_DATE_FORMATS = [
  /^\d{4}-\d{2}-\d{2}$/,           // YYYY-MM-DD
  /^\d{1,2}\/\d{1,2}\/\d{4}$/,     // MM/DD/YYYY
  /^\d{1,2}\/\d{1,2}\/\d{2}$/,     // MM/DD/YY
];

const MONTH_NAMES = new Set([
  'january', 'jan',
  'february', 'feb',
  'march', 'mar',
  'april', 'apr',
  'may',
  'june', 'jun',
  'july', 'jul',
  'august', 'aug',
  'september', 'sep',
  'october', 'oct',
  'november', 'nov',
  'december', 'dec',
]);

// Regex for text dates: Month Day or Month Day Year
const TEXT_DATE_REGEX = /^(january|jan|february|feb|march|mar|april|apr|may|june|jun|july|jul|august|aug|september|sep|october|oct|november|nov|december|dec)\s+(\d{1,2})(?:\s+(\d{4}))?$/i;

const PRIORITY_REGEX = /\bp(\d+)\b/gi;
const ESTIMATE_REGEX = /\b(\d+)([mhd])\b/gi;
const INVALID_PRIORITY_REGEX = /\bp([^0-9\s)][^\s)]*)\b/gi;
const INVALID_ESTIMATE_REGEX = /\b(\d+)([^mhd\s)0-9][^\s)]*)\b/gi;

function isValidDate(dateStr: string): boolean {
  // Check standard formats
  if (VALID_DATE_FORMATS.some(regex => regex.test(dateStr))) {
    return true;
  }
  // Check text date format
  if (TEXT_DATE_REGEX.test(dateStr)) {
    const match = dateStr.match(TEXT_DATE_REGEX);
    if (match) {
      const day = parseInt(match[2], 10);
      return day >= 1 && day <= 31;
    }
  }
  return false;
}

export function lint(text: string, scheme?: Scheme): LintResult {
  const { ast } = parse(text);
  const warnings: Warning[] = [];
  const lines = text.split('\n');

  let miscSectionLine: number | null = null;
  let miscSectionSpan: [number, number] | null = null;
  const headingsAfterMisc: { line: number; span: [number, number] }[] = [];

  // Check each item
  for (const item of ast.items) {
    const lineIndex = item.line - 1;
    const rawLine = item.raw_line;

    // Check for Misc section
    if (item.type === 'heading') {
      if (miscSectionLine !== null) {
        // Any heading after Misc (including duplicate Misc) is an error
        headingsAfterMisc.push({ line: item.line, span: item.item_span });
      } else if (item.title_text === 'Misc' && item.level === 1) {
        miscSectionLine = item.line;
        miscSectionSpan = item.item_span;
      }
    }

    // Check for invalid date formats in parentheses
    const parenMatches = rawLine.matchAll(/\(([^)]+)\)/g);
    for (const match of parenMatches) {
      const content = match[1];
      const parenStart = item.item_span[0] + (match.index || 0);

      // Check for due dates - try text date format first (captures more), then standard format
      // Text date: due Month Day [Year]
      const textDueMatches = content.matchAll(/\bdue\s+((?:january|jan|february|feb|march|mar|april|apr|may|june|jun|july|jul|august|aug|september|sep|october|oct|november|nov|december|dec)\s+\d{1,2}(?:\s+\d{4})?)/gi);
      const textDueIndices = new Set<number>();
      for (const textDueMatch of textDueMatches) {
        textDueIndices.add(textDueMatch.index || 0);
        const dateStr = textDueMatch[1];
        if (!isValidDate(dateStr)) {
          const tokenStart = parenStart + 1 + (textDueMatch.index || 0);
          warnings.push({
            code: 'INVALID_DATE_FORMAT',
            message: `Invalid due date format: ${dateStr}`,
            line: item.line,
            column: tokenStart - item.item_span[0] + 1,
            span: [tokenStart + 4, tokenStart + 4 + dateStr.length],
          });
        }
      }

      // Standard date formats (single token)
      const dueMatches = content.matchAll(/\bdue\s+([^\s,)]+)/gi);
      for (const dueMatch of dueMatches) {
        // Skip if this was already matched as a text date
        if (textDueIndices.has(dueMatch.index || 0)) continue;

        const dateStr = dueMatch[1];
        // Skip if this looks like the start of a text date (month name)
        if (MONTH_NAMES.has(dateStr.toLowerCase())) continue;

        if (!isValidDate(dateStr)) {
          const tokenStart = parenStart + 1 + (dueMatch.index || 0);
          warnings.push({
            code: 'INVALID_DATE_FORMAT',
            message: `Invalid due date format: ${dateStr}`,
            line: item.line,
            column: tokenStart - item.item_span[0] + 1,
            span: [tokenStart + 4, tokenStart + 4 + dateStr.length], // Skip 'due '
          });
        }
      }

      // Check for multiple due dates across all paren groups
      const allDueDates: { dateStr: string; span: [number, number] }[] = [];
      const allParenMatches = rawLine.matchAll(/\(([^)]+)\)/g);
      for (const pMatch of allParenMatches) {
        const pContent = pMatch[1];
        const pStart = item.item_span[0] + (pMatch.index || 0);

        // Check text dates first
        const textDueDatesInGroup = pContent.matchAll(/\bdue\s+((?:january|jan|february|feb|march|mar|april|apr|may|june|jun|july|jul|august|aug|september|sep|october|oct|november|nov|december|dec)\s+\d{1,2}(?:\s+\d{4})?)/gi);
        const textDuePositions = new Set<number>();
        for (const tdm of textDueDatesInGroup) {
          const ds = tdm[1];
          if (isValidDate(ds)) {
            textDuePositions.add(tdm.index || 0);
            const dStart = pStart + 1 + (tdm.index || 0);
            allDueDates.push({
              dateStr: ds,
              span: [dStart, dStart + tdm[0].length],
            });
          }
        }

        // Check standard dates
        const dueDatesInGroup = pContent.matchAll(/\bdue\s+([^\s,)]+)/gi);
        for (const dm of dueDatesInGroup) {
          // Skip if already matched as text date
          if (textDuePositions.has(dm.index || 0)) continue;
          const ds = dm[1];
          // Skip if it's a month name (part of text date)
          if (MONTH_NAMES.has(ds.toLowerCase())) continue;
          if (isValidDate(ds)) {
            const dStart = pStart + 1 + (dm.index || 0);
            allDueDates.push({
              dateStr: ds,
              span: [dStart, dStart + dm[0].length],
            });
          }
        }
      }
      if (allDueDates.length > 1) {
        // Warn for the second and subsequent ones
        for (let i = 1; i < allDueDates.length; i++) {
          warnings.push({
            code: 'DUPLICATE_DUE_DATE',
            message: 'Multiple due dates found, using last value',
            line: item.line,
            column: allDueDates[i].span[0] - item.item_span[0] + 1,
            span: allDueDates[i].span,
          });
        }
        break; // Only warn once per item
      }

      // Check for invalid priority tokens (e.g., pX)
      const invalidPriorities = content.matchAll(/\bp([a-zA-Z][^\s,)]*)/gi);
      for (const ipMatch of invalidPriorities) {
        const tokenStart = parenStart + 1 + (ipMatch.index || 0);
        warnings.push({
          code: 'INVALID_TOKEN',
          message: `Unrecognized token in parentheses: ${ipMatch[0]}`,
          line: item.line,
          column: tokenStart - item.item_span[0] + 1,
          span: [tokenStart, tokenStart + ipMatch[0].length],
        });
      }

      // Check for invalid estimate tokens (e.g., 5q)
      const invalidEstimates = content.matchAll(/\b(\d+)([a-zA-Z])(?![mhdMHD])\b/gi);
      for (const ieMatch of invalidEstimates) {
        const unit = ieMatch[2].toLowerCase();
        if (unit !== 'm' && unit !== 'h' && unit !== 'd') {
          const tokenStart = parenStart + 1 + (ieMatch.index || 0);
          warnings.push({
            code: 'INVALID_TOKEN',
            message: `Unrecognized token in parentheses: ${ieMatch[0]}`,
            line: item.line,
            column: tokenStart - item.item_span[0] + 1,
            span: [tokenStart, tokenStart + ieMatch[0].length],
          });
        }
      }
    }

    // Check for comment indentation (list items only)
    if (item.type === 'list' && item.comments.length > 0) {
      const listMatch = rawLine.match(/^(\s*)([-*]|\d+\.)\s/);
      const expectedIndent = listMatch ? listMatch[1].length + listMatch[2].length + 1 : 2;

      // Find comment lines in the original text
      let currentOffset = item.item_span[0] + rawLine.length + 1;
      for (let i = 0; i < item.comments.length; i++) {
        const commentLineIndex = item.line + i;
        if (commentLineIndex < lines.length) {
          const commentLine = lines[commentLineIndex];
          const leadingSpaces = commentLine.match(/^(\s*)/)?.[1].length || 0;

          if (leadingSpaces < expectedIndent && commentLine.trim().length > 0) {
            warnings.push({
              code: 'COMMENT_INDENTATION',
              message: 'List item comment should be indented',
              line: commentLineIndex + 1,
              column: 1,
              span: [currentOffset, currentOffset + commentLine.length],
            });
          }
        }
        currentOffset += (lines[commentLineIndex]?.length || 0) + 1;
      }
    }
  }

  // Check for Misc section issues
  if (miscSectionLine === null) {
    warnings.push({
      code: 'MISC_MISSING',
      message: "Document is missing required '# Misc' section",
      line: null,
      column: null,
      span: null,
    });
  } else if (headingsAfterMisc.length > 0) {
    // Misc is not at EOF
    warnings.push({
      code: 'MISC_NOT_AT_EOF',
      message: "'# Misc' section must be at end of file",
      line: miscSectionLine,
      column: 1,
      span: miscSectionSpan,
    });

    // Content after Misc warning for each heading
    for (const heading of headingsAfterMisc) {
      warnings.push({
        code: 'CONTENT_AFTER_MISC',
        message: "Heading found after '# Misc' section",
        line: heading.line,
        column: 1,
        span: heading.span,
      });
    }
  }

  return { warnings };
}
