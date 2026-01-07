/**
 * Todoosy Parser
 */

import type { AST, ItemNode, ItemMetadata, ParsedToken, ParenGroup, Warning } from './types.js';

const HEADING_REGEX = /^(#{1,6})\s+(.*)$/;
const LIST_ITEM_REGEX = /^(\s*)([-*]|\d+\.)\s+(.*)$/;
const DUE_ISO_REGEX = /^due\s+(\d{4})-(\d{2})-(\d{2})$/i;
const DUE_US_REGEX = /^due\s+(\d{1,2})\/(\d{1,2})\/(\d{4})$/i;
const DUE_US_SHORT_REGEX = /^due\s+(\d{1,2})\/(\d{1,2})\/(\d{2})$/i;
const PRIORITY_REGEX = /^p(\d+)$/i;
const ESTIMATE_REGEX = /^(\d+)([mhd])$/i;

const MONTH_NAMES: Record<string, number> = {
  january: 1, jan: 1,
  february: 2, feb: 2,
  march: 3, mar: 3,
  april: 4, apr: 4,
  may: 5,
  june: 6, jun: 6,
  july: 7, jul: 7,
  august: 8, aug: 8,
  september: 9, sep: 9,
  october: 10, oct: 10,
  november: 11, nov: 11,
  december: 12, dec: 12,
};

// Built-in progress states (normalized to lowercase)
const PROGRESS_STATES = new Set(['done', 'deleted', 'in progress', 'blocked']);

export interface ParseResult {
  ast: AST;
  warnings: Warning[];
}

function inferYear(month: number, day: number): number {
  const now = new Date();
  const currentYear = now.getFullYear();
  const currentMonth = now.getMonth() + 1;
  const currentDay = now.getDate();

  // Calculate months difference
  let monthsDiff = (currentMonth - month) + (currentDay > day ? 0 : 0);
  if (currentMonth > month || (currentMonth === month && currentDay > day)) {
    monthsDiff = (currentMonth - month) + (currentDay > day ? 0 : -1);
    // More precise: is the date more than 3 months in the past?
    const candidateDate = new Date(currentYear, month - 1, day);
    const threeMonthsAgo = new Date(now);
    threeMonthsAgo.setMonth(threeMonthsAgo.getMonth() - 3);

    if (candidateDate < threeMonthsAgo) {
      return currentYear + 1;
    }
  }
  return currentYear;
}

function parseDate(dateStr: string): { date: string | null; valid: boolean; raw: string } {
  const isoMatch = dateStr.match(/^(\d{4})-(\d{2})-(\d{2})$/);
  if (isoMatch) {
    return { date: dateStr, valid: true, raw: dateStr };
  }

  const usMatch = dateStr.match(/^(\d{1,2})\/(\d{1,2})\/(\d{4})$/);
  if (usMatch) {
    const month = usMatch[1].padStart(2, '0');
    const day = usMatch[2].padStart(2, '0');
    const year = usMatch[3];
    return { date: `${year}-${month}-${day}`, valid: true, raw: dateStr };
  }

  const usShortMatch = dateStr.match(/^(\d{1,2})\/(\d{1,2})\/(\d{2})$/);
  if (usShortMatch) {
    const month = usShortMatch[1].padStart(2, '0');
    const day = usShortMatch[2].padStart(2, '0');
    const year = `20${usShortMatch[3]}`;
    return { date: `${year}-${month}-${day}`, valid: true, raw: dateStr };
  }

  return { date: null, valid: false, raw: dateStr };
}

function parseTextDate(parts: string[]): { date: string | null; valid: boolean; partsConsumed: number } {
  if (parts.length < 2) {
    return { date: null, valid: false, partsConsumed: 0 };
  }

  const monthStr = parts[0].toLowerCase();
  const month = MONTH_NAMES[monthStr];
  if (month === undefined) {
    return { date: null, valid: false, partsConsumed: 0 };
  }

  const dayStr = parts[1];
  const dayMatch = dayStr.match(/^(\d{1,2})$/);
  if (!dayMatch) {
    return { date: null, valid: false, partsConsumed: 0 };
  }
  const day = parseInt(dayMatch[1], 10);
  if (day < 1 || day > 31) {
    return { date: null, valid: false, partsConsumed: 0 };
  }

  // Check for year
  if (parts.length >= 3) {
    const yearStr = parts[2];
    const yearMatch = yearStr.match(/^(\d{4})$/);
    if (yearMatch) {
      const year = parseInt(yearMatch[1], 10);
      const monthPadded = String(month).padStart(2, '0');
      const dayPadded = String(day).padStart(2, '0');
      return { date: `${year}-${monthPadded}-${dayPadded}`, valid: true, partsConsumed: 3 };
    }
  }

  // No year provided, infer it
  const year = inferYear(month, day);
  const monthPadded = String(month).padStart(2, '0');
  const dayPadded = String(day).padStart(2, '0');
  return { date: `${year}-${monthPadded}-${dayPadded}`, valid: true, partsConsumed: 2 };
}

function parseTokensInParenGroup(content: string, groupStart: number): ParenGroup {
  const tokens: ParsedToken[] = [];
  // Split by comma and/or whitespace
  const parts = content.split(/[,\s]+/).filter(p => p.length > 0);

  let currentPos = 0;
  const skipIndices = new Set<number>();

  for (let i = 0; i < parts.length; i++) {
    if (skipIndices.has(i)) continue;

    const part = parts[i];
    const partStart = content.indexOf(part, currentPos);
    const absoluteStart = groupStart + 1 + partStart; // +1 for opening paren
    const absoluteEnd = absoluteStart + part.length;
    currentPos = partStart + part.length;

    // Check for due date
    if (part.toLowerCase() === 'due') {
      // Look for the next part(s) as the date
      const remainingParts = parts.slice(i + 1);
      if (remainingParts.length > 0) {
        // First try standard date formats (single part)
        const dateResult = parseDate(remainingParts[0]);
        if (dateResult.valid) {
          const nextPartStart = content.indexOf(remainingParts[0], currentPos);
          const nextAbsoluteEnd = groupStart + 1 + nextPartStart + remainingParts[0].length;
          tokens.push({
            type: 'due',
            value: dateResult.date!,
            raw: `due ${remainingParts[0]}`,
            start: absoluteStart,
            end: nextAbsoluteEnd,
          });
          skipIndices.add(i + 1);
          continue;
        }

        // Try text date formats (multiple parts: Month Day [Year])
        const textDateResult = parseTextDate(remainingParts);
        if (textDateResult.valid) {
          // Calculate the end position
          let rawParts = [`due`];
          let endPos = currentPos;
          for (let j = 0; j < textDateResult.partsConsumed; j++) {
            rawParts.push(remainingParts[j]);
            skipIndices.add(i + 1 + j);
            endPos = content.indexOf(remainingParts[j], endPos) + remainingParts[j].length;
          }
          const finalAbsoluteEnd = groupStart + 1 + endPos;
          tokens.push({
            type: 'due',
            value: textDateResult.date!,
            raw: rawParts.join(' '),
            start: absoluteStart,
            end: finalAbsoluteEnd,
          });
          continue;
        }
      }
      continue;
    }

    // Check for priority
    const priorityMatch = part.match(PRIORITY_REGEX);
    if (priorityMatch) {
      tokens.push({
        type: 'priority',
        value: parseInt(priorityMatch[1], 10),
        raw: part,
        start: absoluteStart,
        end: absoluteEnd,
      });
      continue;
    }

    // Check for estimate
    const estimateMatch = part.match(ESTIMATE_REGEX);
    if (estimateMatch) {
      const num = parseInt(estimateMatch[1], 10);
      const unit = estimateMatch[2].toLowerCase();
      let minutes: number;
      switch (unit) {
        case 'm': minutes = num; break;
        case 'h': minutes = num * 60; break;
        case 'd': minutes = num * 480; break;
        default: minutes = num;
      }
      tokens.push({
        type: 'estimate',
        value: minutes,
        raw: part,
        start: absoluteStart,
        end: absoluteEnd,
      });
      continue;
    }

    // Check for progress states
    const partLower = part.toLowerCase();

    // Check for single-word progress states: done, deleted, blocked
    if (PROGRESS_STATES.has(partLower)) {
      tokens.push({
        type: 'progress',
        value: partLower,
        raw: part,
        start: absoluteStart,
        end: absoluteEnd,
      });
      continue;
    }

    // Check for multi-word progress state: "in progress"
    if (partLower === 'in') {
      const remainingParts = parts.slice(i + 1);
      if (remainingParts.length > 0 && remainingParts[0].toLowerCase() === 'progress') {
        const nextPartStart = content.indexOf(remainingParts[0], currentPos);
        const nextAbsoluteEnd = groupStart + 1 + nextPartStart + remainingParts[0].length;
        tokens.push({
          type: 'progress',
          value: 'in progress',
          raw: `${part} ${remainingParts[0]}`,
          start: absoluteStart,
          end: nextAbsoluteEnd,
        });
        skipIndices.add(i + 1);
        continue;
      }
    }
  }

  return {
    start: groupStart,
    end: groupStart + content.length + 2, // +2 for parens
    content,
    tokens,
    hasRecognizedTokens: tokens.length > 0,
  };
}

function extractParenGroups(line: string, lineStart: number): ParenGroup[] {
  const groups: ParenGroup[] = [];
  let i = 0;

  while (i < line.length) {
    if (line[i] === '(') {
      const start = i;  // Position within the line (content)
      let depth = 1;
      i++;
      while (i < line.length && depth > 0) {
        if (line[i] === '(') depth++;
        else if (line[i] === ')') depth--;
        i++;
      }
      if (depth === 0) {
        const content = line.slice(start + 1, i - 1);
        // Pass the relative position within content string
        const group = parseTokensInParenGroup(content, start);
        group.start = start;  // Store relative position
        group.end = i;        // Store relative position
        groups.push(group);
      }
    } else {
      i++;
    }
  }

  return groups;
}

function buildTitleText(rawText: string, groups: ParenGroup[]): string {
  // Remove groups that have recognized tokens
  // Process in reverse order to maintain correct positions
  const sortedGroups = [...groups]
    .filter(g => g.hasRecognizedTokens)
    .sort((a, b) => b.start - a.start);

  let result = rawText;
  for (const group of sortedGroups) {
    const before = result.slice(0, group.start);
    const after = result.slice(group.end);
    result = before + after;
  }

  // Clean up extra whitespace
  return result.replace(/\s+/g, ' ').trim();
}

function buildMetadata(groups: ParenGroup[]): ItemMetadata {
  const metadata: ItemMetadata = {
    due: null,
    priority: null,
    estimate_minutes: null,
    progress: null,
  };

  // Collect all tokens from all groups
  const allTokens = groups.flatMap(g => g.tokens);

  // Last occurrence wins
  for (const token of allTokens) {
    switch (token.type) {
      case 'due':
        metadata.due = token.value as string;
        break;
      case 'priority':
        metadata.priority = token.value as number;
        break;
      case 'estimate':
        metadata.estimate_minutes = token.value as number;
        break;
      case 'progress':
        metadata.progress = token.value as string;
        break;
    }
  }

  return metadata;
}

export function parse(text: string): ParseResult {
  const lines = text.split('\n');
  const items: ItemNode[] = [];
  const warnings: Warning[] = [];
  let nextId = 0;
  let offset = 0;

  // Stack to track current context: [itemId, indentLevel]
  const listStack: { id: string; indent: number }[] = [];
  let currentHeadingId: string | null = null;
  const rootIds: string[] = [];

  // Map id -> children for building the tree
  const childrenMap: Map<string, string[]> = new Map();

  // First pass: identify all items and their basic info
  for (let lineNum = 0; lineNum < lines.length; lineNum++) {
    const line = lines[lineNum];
    const lineStart = offset;
    const lineEnd = offset + line.length;

    // Check for heading
    const headingMatch = line.match(HEADING_REGEX);
    if (headingMatch) {
      const level = headingMatch[1].length;
      const content = headingMatch[2];

      // Close any open list context
      listStack.length = 0;

      const groups = extractParenGroups(content, lineStart + headingMatch[1].length + 1);
      const titleText = buildTitleText(content, groups);
      const metadata = buildMetadata(groups);

      const id = String(nextId++);
      const item: ItemNode = {
        id,
        type: 'heading',
        level,
        raw_line: line,
        title_text: titleText,
        metadata,
        comments: [],
        children: [],
        item_span: [lineStart, lineEnd],
        subtree_span: [lineStart, lineEnd],
        line: lineNum + 1,
        column: 1,
      };

      items.push(item);
      childrenMap.set(id, []);
      rootIds.push(id);
      currentHeadingId = id;

      offset = lineEnd + 1;
      continue;
    }

    // Check for list item
    const listMatch = line.match(LIST_ITEM_REGEX);
    if (listMatch) {
      const indent = listMatch[1].length;
      const marker = listMatch[2];
      const content = listMatch[3];

      const contentStart = lineStart + indent + marker.length + 1;
      const groups = extractParenGroups(content, contentStart);
      const titleText = buildTitleText(content, groups);
      const metadata = buildMetadata(groups);

      const id = String(nextId++);
      const item: ItemNode = {
        id,
        type: 'list',
        raw_line: line,
        title_text: titleText,
        metadata,
        comments: [],
        children: [],
        item_span: [lineStart, lineEnd],
        subtree_span: [lineStart, lineEnd],
        line: lineNum + 1,
        column: 1,
      };

      items.push(item);
      childrenMap.set(id, []);

      // Determine parent
      // Pop items from stack that are at same or greater indent
      while (listStack.length > 0 && listStack[listStack.length - 1].indent >= indent) {
        listStack.pop();
      }

      if (listStack.length > 0) {
        // Parent is the top of the stack
        const parentId = listStack[listStack.length - 1].id;
        childrenMap.get(parentId)!.push(id);
      } else if (currentHeadingId !== null) {
        // Parent is current heading
        childrenMap.get(currentHeadingId)!.push(id);
      } else {
        // No parent, it's a root
        rootIds.push(id);
      }

      listStack.push({ id, indent });

      offset = lineEnd + 1;
      continue;
    }

    // Not a heading or list item - could be a comment or blank line
    offset = lineEnd + 1;
  }

  // Second pass: collect comments
  offset = 0;
  let currentItemIndex = -1;
  let hasStartedComments = false;
  let blankAfterCommentStart = false;

  for (let lineNum = 0; lineNum < lines.length; lineNum++) {
    const line = lines[lineNum];
    const lineStart = offset;
    const lineEnd = offset + line.length;

    // Check if this line starts a new item
    const headingMatch = line.match(HEADING_REGEX);
    const listMatch = line.match(LIST_ITEM_REGEX);

    if (headingMatch || listMatch) {
      currentItemIndex = items.findIndex(
        item => item.item_span[0] === lineStart
      );
      hasStartedComments = false;
      blankAfterCommentStart = false;
      offset = lineEnd + 1;
      continue;
    }

    // Check for blank line
    if (line.trim() === '') {
      if (hasStartedComments) {
        // Blank line after comments started = stop collecting
        blankAfterCommentStart = true;
      }
      // Blank line before comments started (e.g., after heading) = ignore
      offset = lineEnd + 1;
      continue;
    }

    // Non-blank, non-item line - potential comment
    if (currentItemIndex >= 0 && !blankAfterCommentStart) {
      const currentItem = items[currentItemIndex];
      currentItem.comments.push(line.trim());
      currentItem.item_span[1] = lineEnd;
      hasStartedComments = true;
    }

    offset = lineEnd + 1;
  }

  // Build children arrays and compute subtree spans
  for (const item of items) {
    item.children = childrenMap.get(item.id) || [];
  }

  // Compute subtree spans (post-order traversal)
  function computeSubtreeSpan(id: string): [number, number] {
    const item = items.find(i => i.id === id)!;
    let end = item.item_span[1];

    for (const childId of item.children) {
      const childSpan = computeSubtreeSpan(childId);
      end = Math.max(end, childSpan[1]);
    }

    item.subtree_span = [item.item_span[0], end];
    return item.subtree_span;
  }

  for (const rootId of rootIds) {
    computeSubtreeSpan(rootId);
  }

  // Update root_ids to only include top-level items
  const actualRootIds = items
    .filter(item => {
      // Check if this item is a child of any other item
      return !items.some(other => other.children.includes(item.id));
    })
    .map(item => item.id);

  return {
    ast: {
      items,
      root_ids: actualRootIds,
    },
    warnings,
  };
}
