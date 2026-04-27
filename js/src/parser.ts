/**
 * Todoosy Parser
 */

import type { AST, ItemNode, ItemMetadata, ParsedToken, ParenGroup, Warning, Settings } from './types.js';
import { resolveNow, resolveKeyword, tryParseRelative, type ResolvedNow } from './relative-date.js';

const HEADING_REGEX = /^(#{1,6})\s+(.*)$/;
const LIST_ITEM_REGEX = /^(\s*)([-*]|\d+\.)\s+(.*)$/;
const PRIORITY_REGEX = /^p(\d+)$/i;
const ESTIMATE_REGEX = /^(\d+)([mhd])$/i;
const HASHTAG_REGEX = /^#([a-zA-Z][a-zA-Z0-9_-]*)$/;

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

export interface ParseOptions {
  /** Override "now" for deterministic tests. */
  now?: Date;
  /** Settings (timezone) used when resolving relative dates. */
  settings?: Settings;
}

export interface ParseResult {
  ast: AST;
  warnings: Warning[];
}

function inferYear(month: number, day: number, now: ResolvedNow): number {
  const [todayY, todayM, todayD] = now.todayIso.split('-').map(n => parseInt(n, 10));
  const candidate = new Date(Date.UTC(todayY, month - 1, day));
  // Three months ago in UTC
  const threeMonthsAgo = new Date(Date.UTC(todayY, todayM - 1 - 3, todayD));
  if (candidate < threeMonthsAgo) {
    return todayY + 1;
  }
  return todayY;
}

function parseISODate(dateStr: string): string | null {
  // ISO format: YYYY-MM-DD or YYYY-M-D
  const isoMatch = dateStr.match(/^(\d{4})-(\d{1,2})-(\d{1,2})$/);
  if (isoMatch) {
    const year = isoMatch[1];
    const month = isoMatch[2].padStart(2, '0');
    const day = isoMatch[3].padStart(2, '0');
    return `${year}-${month}-${day}`;
  }

  // Short ISO format: YY-MM-DD or YY-M-D
  const isoShortMatch = dateStr.match(/^(\d{2})-(\d{1,2})-(\d{1,2})$/);
  if (isoShortMatch) {
    const year = `20${isoShortMatch[1]}`;
    const month = isoShortMatch[2].padStart(2, '0');
    const day = isoShortMatch[3].padStart(2, '0');
    return `${year}-${month}-${day}`;
  }

  // Year-first with slashes: YYYY/MM/DD
  const ymdSlashMatch = dateStr.match(/^(\d{4})\/(\d{1,2})\/(\d{1,2})$/);
  if (ymdSlashMatch) {
    const year = ymdSlashMatch[1];
    const month = ymdSlashMatch[2].padStart(2, '0');
    const day = ymdSlashMatch[3].padStart(2, '0');
    return `${year}-${month}-${day}`;
  }

  // Slash format with heuristics
  const slashMatch = dateStr.match(/^(\d{1,4})\/(\d{1,2})\/(\d{1,4})$/);
  if (slashMatch) {
    const first = parseInt(slashMatch[1], 10);
    const second = parseInt(slashMatch[2], 10);
    const third = parseInt(slashMatch[3], 10);
    const firstLen = slashMatch[1].length;
    const thirdLen = slashMatch[3].length;

    let year: number, month: number, day: number;
    if (firstLen === 4) {
      year = first; month = second; day = third;
    } else if (thirdLen === 4) {
      year = third;
      if (first > 12) { day = first; month = second; }
      else { month = first; day = second; }
    } else if (firstLen === 2 && thirdLen === 2) {
      if (first > 31) { year = 2000 + first; month = second; day = third; }
      else if (first > 12) { day = first; month = second; year = 2000 + third; }
      else { month = first; day = second; year = 2000 + third; }
    } else {
      if (thirdLen <= 2) {
        if (first > 12) { day = first; month = second; }
        else { month = first; day = second; }
        year = 2000 + third;
      } else {
        year = first; month = second; day = third;
      }
    }
    return `${year}-${String(month).padStart(2, '0')}-${String(day).padStart(2, '0')}`;
  }
  return null;
}

function parseTextDate(parts: string[], startIdx: number, now: ResolvedNow): { date: string; partsConsumed: number } | null {
  if (startIdx + 1 >= parts.length) return null;

  // "Month Day [Year]"
  const monthStr = parts[startIdx].toLowerCase();
  const monthFromName = MONTH_NAMES[monthStr];
  if (monthFromName !== undefined) {
    const dayMatch = parts[startIdx + 1].match(/^(\d{1,2})$/);
    if (dayMatch) {
      const day = parseInt(dayMatch[1], 10);
      if (day >= 1 && day <= 31) {
        if (startIdx + 2 < parts.length) {
          const yearStr = parts[startIdx + 2];
          const yMatch4 = yearStr.match(/^(\d{4})$/);
          if (yMatch4) {
            return { date: `${yMatch4[1]}-${String(monthFromName).padStart(2, '0')}-${String(day).padStart(2, '0')}`, partsConsumed: 3 };
          }
          const yMatch2 = yearStr.match(/^(\d{2})$/);
          if (yMatch2) {
            return { date: `${2000 + parseInt(yMatch2[1], 10)}-${String(monthFromName).padStart(2, '0')}-${String(day).padStart(2, '0')}`, partsConsumed: 3 };
          }
        }
        const year = inferYear(monthFromName, day, now);
        return { date: `${year}-${String(monthFromName).padStart(2, '0')}-${String(day).padStart(2, '0')}`, partsConsumed: 2 };
      }
    }
  }

  // "Day Month [Year]"
  const dayFirstMatch = parts[startIdx].match(/^(\d{1,2})$/);
  if (dayFirstMatch) {
    const day = parseInt(dayFirstMatch[1], 10);
    if (day >= 1 && day <= 31) {
      const monthStr2 = parts[startIdx + 1].toLowerCase();
      const monthFromName2 = MONTH_NAMES[monthStr2];
      if (monthFromName2 !== undefined) {
        if (startIdx + 2 < parts.length) {
          const yearStr = parts[startIdx + 2];
          const yMatch4 = yearStr.match(/^(\d{4})$/);
          if (yMatch4) {
            return { date: `${yMatch4[1]}-${String(monthFromName2).padStart(2, '0')}-${String(day).padStart(2, '0')}`, partsConsumed: 3 };
          }
          const yMatch2 = yearStr.match(/^(\d{2})$/);
          if (yMatch2) {
            return { date: `${2000 + parseInt(yMatch2[1], 10)}-${String(monthFromName2).padStart(2, '0')}-${String(day).padStart(2, '0')}`, partsConsumed: 3 };
          }
        }
        const year = inferYear(monthFromName2, day, now);
        return { date: `${year}-${String(monthFromName2).padStart(2, '0')}-${String(day).padStart(2, '0')}`, partsConsumed: 2 };
      }
    }
  }

  return null;
}

/**
 * Try to parse a single date (keyword | ISO/slash | text date | relative offset)
 * starting at parts[startIdx]. Returns the date and parts consumed, or null.
 */
function tryParseSingleDate(parts: string[], startIdx: number, now: ResolvedNow): { date: string; partsConsumed: number } | null {
  if (startIdx >= parts.length) return null;

  // Keywords
  const kw = resolveKeyword(parts[startIdx], now);
  if (kw !== null) return { date: kw, partsConsumed: 1 };

  // ISO/slash single-token
  const iso = parseISODate(parts[startIdx]);
  if (iso !== null) return { date: iso, partsConsumed: 1 };

  // Text date (multi-token)
  const textDate = parseTextDate(parts, startIdx, now);
  if (textDate !== null) return textDate;

  // Relative offset
  const rel = tryParseRelative(parts, startIdx, now);
  if (rel !== null) return rel;

  return null;
}

/**
 * Pre-tokenize parens content. The base split is by commas/whitespace; then
 * each part is further split on `~` so that `~` always appears as its own
 * delimiter token. Examples:
 *   `~Apr`              → [`~`, `Apr`]
 *   `Apr 24~Apr 27`     → [`Apr`, `24`, `~`, `Apr`, `27`]  (input parts: [`Apr`, `24~Apr`, `27`])
 *   `2026-04-24~2026-04-27` → [`2026-04-24`, `~`, `2026-04-27`]
 */
function tokenizeContent(content: string): { parts: string[]; partOffsets: number[] } {
  const parts: string[] = [];
  const partOffsets: number[] = [];
  let i = 0;
  while (i < content.length) {
    // Skip separators (commas + whitespace)
    while (i < content.length && (content[i] === ',' || /\s/.test(content[i]))) i++;
    if (i >= content.length) break;

    // Read until next separator
    const tokenStart = i;
    while (i < content.length && content[i] !== ',' && !/\s/.test(content[i])) i++;
    const raw = content.slice(tokenStart, i);

    // Split this token on `~`, emitting `~` as its own part. Preserve offsets.
    let cursor = 0;
    while (cursor < raw.length) {
      const tildeIdx = raw.indexOf('~', cursor);
      if (tildeIdx === -1) {
        const seg = raw.slice(cursor);
        if (seg.length > 0) {
          parts.push(seg);
          partOffsets.push(tokenStart + cursor);
        }
        break;
      }
      // Pre-tilde segment (may be empty)
      if (tildeIdx > cursor) {
        parts.push(raw.slice(cursor, tildeIdx));
        partOffsets.push(tokenStart + cursor);
      }
      // The tilde itself
      parts.push('~');
      partOffsets.push(tokenStart + tildeIdx);
      cursor = tildeIdx + 1;
    }
  }
  return { parts, partOffsets };
}

export function parseTokensInParenGroup(content: string, groupStart: number, now?: ResolvedNow): ParenGroup {
  if (!now) now = resolveNow(undefined, undefined);
  return parseTokensInParenGroupImpl(content, groupStart, now);
}

function parseTokensInParenGroupImpl(content: string, groupStart: number, now: ResolvedNow): ParenGroup {
  const tokens: ParsedToken[] = [];
  const { parts, partOffsets } = tokenizeContent(content);

  // Compute the absolute end of part i.
  const partEndOffset = (i: number) => partOffsets[i] + parts[i].length;
  const absStart = (i: number) => groupStart + 1 + partOffsets[i];
  const absEnd = (i: number) => groupStart + 1 + partEndOffset(i);

  const skipIndices = new Set<number>();

  for (let i = 0; i < parts.length; i++) {
    if (skipIndices.has(i)) continue;
    const part = parts[i];

    // Standalone `~` here means we encountered a tilde without a leading date —
    // either a soft-prefix introducer (`~<date>`) or an orphan. Try as soft prefix.
    if (part === '~') {
      // Soft prefix: try to consume a single date (no span — span would have a leading date).
      const inner = tryParseSingleDate(parts, i + 1, now);
      if (inner !== null) {
        const startIndex = i;
        const endIndex = i + inner.partsConsumed; // last consumed index = endIndex
        // Mark consumed
        for (let j = i + 1; j <= endIndex; j++) skipIndices.add(j);
        const raw = content.slice(partOffsets[startIndex], partEndOffset(endIndex));
        tokens.push({
          type: 'due',
          value: inner.date,
          raw,
          start: absStart(startIndex),
          end: absEnd(endIndex),
          soft: true,
        });
        continue;
      }
      // Orphan `~` — drop silently.
      continue;
    }

    // 'due' keyword
    if (part.toLowerCase() === 'due') {
      // Look ahead. After `due` we may have `~<date>`, `<date>~<date>`, or `<date>`.
      let cursor = i + 1;
      let isSoftPrefix = false;
      if (cursor < parts.length && parts[cursor] === '~') {
        isSoftPrefix = true;
        cursor++;
      }
      const first = tryParseSingleDate(parts, cursor, now);
      if (first === null) continue;

      let endIndex = cursor + first.partsConsumed - 1;
      let dateStart: string | null = null;
      let dueDate = first.date;
      let isSoft = isSoftPrefix;

      // Span continuation: `<date>~<date>`
      if (endIndex + 1 < parts.length && parts[endIndex + 1] === '~') {
        const second = tryParseSingleDate(parts, endIndex + 2, now);
        if (second !== null) {
          if (isSoftPrefix) {
            // `due ~start~end` is malformed; reject (treat as if span didn't parse).
            // Fall through with the first date only.
          } else {
            dateStart = first.date;
            dueDate = second.date;
            endIndex = endIndex + 1 + second.partsConsumed; // skip the `~` and the second date's parts
            isSoft = true; // span implies soft
          }
        }
      }

      // Mark all consumed including 'due' and optional leading '~'
      for (let j = i; j <= endIndex; j++) skipIndices.add(j);

      const raw = content.slice(partOffsets[i], partEndOffset(endIndex));
      tokens.push({
        type: 'due',
        value: dueDate,
        raw,
        start: absStart(i),
        end: absEnd(endIndex),
        soft: isSoft || undefined,
        dateStart: dateStart ?? undefined,
      });
      continue;
    }

    // priority
    const priorityMatch = part.match(PRIORITY_REGEX);
    if (priorityMatch) {
      tokens.push({
        type: 'priority',
        value: parseInt(priorityMatch[1], 10),
        raw: part,
        start: absStart(i),
        end: absEnd(i),
      });
      continue;
    }

    // estimate (must run before relative-date so bare 2d/2h/2m stay as estimates)
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
        start: absStart(i),
        end: absEnd(i),
      });
      continue;
    }

    // progress (single word)
    const partLower = part.toLowerCase();
    if (PROGRESS_STATES.has(partLower)) {
      tokens.push({
        type: 'progress',
        value: partLower,
        raw: part,
        start: absStart(i),
        end: absEnd(i),
      });
      continue;
    }

    // progress: "in progress" — but `in` also introduces relative dates.
    // Disambiguate by lookahead: if next part is "progress", it's a progress state.
    if (partLower === 'in' && i + 1 < parts.length && parts[i + 1].toLowerCase() === 'progress') {
      tokens.push({
        type: 'progress',
        value: 'in progress',
        raw: `${part} ${parts[i + 1]}`,
        start: absStart(i),
        end: absEnd(i + 1),
      });
      skipIndices.add(i + 1);
      continue;
    }

    // hashtag
    const hashtagMatch = part.match(HASHTAG_REGEX);
    if (hashtagMatch) {
      tokens.push({
        type: 'hashtag',
        value: hashtagMatch[1].toLowerCase(),
        raw: part,
        start: absStart(i),
        end: absEnd(i),
      });
      continue;
    }

    // Standalone date / relative / span
    const first = tryParseSingleDate(parts, i, now);
    if (first !== null) {
      let endIndex = i + first.partsConsumed - 1;
      let dateStart: string | null = null;
      let dueDate = first.date;
      let isSoft = false;

      if (endIndex + 1 < parts.length && parts[endIndex + 1] === '~') {
        const second = tryParseSingleDate(parts, endIndex + 2, now);
        if (second !== null) {
          dateStart = first.date;
          dueDate = second.date;
          endIndex = endIndex + 1 + second.partsConsumed;
          isSoft = true;
        }
      }

      for (let j = i; j <= endIndex; j++) skipIndices.add(j);
      const raw = content.slice(partOffsets[i], partEndOffset(endIndex));
      tokens.push({
        type: 'due',
        value: dueDate,
        raw,
        start: absStart(i),
        end: absEnd(endIndex),
        soft: isSoft || undefined,
        dateStart: dateStart ?? undefined,
      });
      continue;
    }
  }

  return {
    start: groupStart,
    end: groupStart + content.length + 2,
    content,
    tokens,
    hasRecognizedTokens: tokens.length > 0,
  };
}

export function extractParenGroups(line: string, _lineStart: number, now?: ResolvedNow): ParenGroup[] {
  if (!now) now = resolveNow(undefined, undefined);
  return extractParenGroupsImpl(line, _lineStart, now);
}

function extractParenGroupsImpl(line: string, _lineStart: number, now: ResolvedNow): ParenGroup[] {
  const groups: ParenGroup[] = [];
  let i = 0;

  while (i < line.length) {
    if (line[i] === '(') {
      const start = i;
      let depth = 1;
      i++;
      while (i < line.length && depth > 0) {
        if (line[i] === '(') depth++;
        else if (line[i] === ')') depth--;
        i++;
      }
      if (depth === 0) {
        const content = line.slice(start + 1, i - 1);
        const group = parseTokensInParenGroup(content, start, now);
        group.start = start;
        group.end = i;
        groups.push(group);
      }
    } else {
      i++;
    }
  }

  return groups;
}

function buildTitleText(rawText: string, groups: ParenGroup[]): string {
  const sortedGroups = [...groups]
    .filter(g => g.hasRecognizedTokens)
    .sort((a, b) => b.start - a.start);

  let result = rawText;
  for (const group of sortedGroups) {
    result = result.slice(0, group.start) + result.slice(group.end);
  }
  return result.replace(/\s+/g, ' ').trim();
}

function buildMetadata(groups: ParenGroup[]): ItemMetadata {
  const metadata: ItemMetadata = {
    due: null,
    due_start: null,
    due_soft: null,
    priority: null,
    estimate_minutes: null,
    progress: null,
    hashtags: [],
    effective_hashtags: [],
  };

  const allTokens = groups.flatMap(g => g.tokens);
  const hashtagSet = new Set<string>();

  for (const token of allTokens) {
    switch (token.type) {
      case 'due':
        metadata.due = token.value as string;
        metadata.due_start = token.dateStart ?? null;
        metadata.due_soft = token.soft ?? null;
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
      case 'hashtag':
        hashtagSet.add(token.value as string);
        break;
    }
  }

  metadata.hashtags = [...hashtagSet].sort();
  return metadata;
}

export function parse(text: string, options?: ParseOptions): ParseResult {
  const now = resolveNow(options?.now, options?.settings);
  const lines = text.split('\n');
  const items: ItemNode[] = [];
  const warnings: Warning[] = [];
  let nextId = 0;
  let offset = 0;

  const listStack: { id: string; indent: number }[] = [];
  let currentHeadingId: string | null = null;
  const rootIds: string[] = [];
  const childrenMap: Map<string, string[]> = new Map();

  for (let lineNum = 0; lineNum < lines.length; lineNum++) {
    const line = lines[lineNum];
    const lineStart = offset;
    const lineEnd = offset + line.length;

    const headingMatch = line.match(HEADING_REGEX);
    if (headingMatch) {
      const level = headingMatch[1].length;
      const content = headingMatch[2];

      listStack.length = 0;

      const groups = extractParenGroups(content, lineStart + headingMatch[1].length + 1, now);
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

    const listMatch = line.match(LIST_ITEM_REGEX);
    if (listMatch) {
      const indent = listMatch[1].length;
      const marker = listMatch[2];
      const content = listMatch[3];

      const contentStart = lineStart + indent + marker.length + 1;
      const groups = extractParenGroups(content, contentStart, now);
      const titleText = buildTitleText(content, groups);
      const metadata = buildMetadata(groups);

      const isNumbered = /^\d+\.$/.test(marker);
      const markerType: 'bullet' | 'numbered' = isNumbered ? 'numbered' : 'bullet';
      const sequenceNumber = isNumbered ? parseInt(marker.slice(0, -1), 10) : undefined;

      const id = String(nextId++);
      const item: ItemNode = {
        id,
        type: 'list',
        marker_type: markerType,
        sequence_number: sequenceNumber,
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

      while (listStack.length > 0 && listStack[listStack.length - 1].indent >= indent) {
        listStack.pop();
      }

      if (listStack.length > 0) {
        const parentId = listStack[listStack.length - 1].id;
        childrenMap.get(parentId)!.push(id);
      } else if (currentHeadingId !== null) {
        childrenMap.get(currentHeadingId)!.push(id);
      } else {
        rootIds.push(id);
      }

      listStack.push({ id, indent });

      offset = lineEnd + 1;
      continue;
    }

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

    const headingMatch = line.match(HEADING_REGEX);
    const listMatch = line.match(LIST_ITEM_REGEX);

    if (headingMatch || listMatch) {
      currentItemIndex = items.findIndex(item => item.item_span[0] === lineStart);
      hasStartedComments = false;
      blankAfterCommentStart = false;
      offset = lineEnd + 1;
      continue;
    }

    if (line.trim() === '') {
      if (hasStartedComments) blankAfterCommentStart = true;
      offset = lineEnd + 1;
      continue;
    }

    if (currentItemIndex >= 0 && !blankAfterCommentStart) {
      const currentItem = items[currentItemIndex];
      currentItem.comments.push(line.trim());
      currentItem.item_span[1] = lineEnd;
      hasStartedComments = true;
    }

    offset = lineEnd + 1;
  }

  for (const item of items) {
    item.children = childrenMap.get(item.id) || [];
  }

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

  const actualRootIds = items
    .filter(item => !items.some(other => other.children.includes(item.id)))
    .map(item => item.id);

  function computeEffectiveHashtags(id: string, parentEffectiveHashtags: string[]): void {
    const item = items.find(i => i.id === id)!;
    const combined = new Set([...parentEffectiveHashtags, ...item.metadata.hashtags]);
    item.metadata.effective_hashtags = [...combined].sort();

    for (const childId of item.children) {
      computeEffectiveHashtags(childId, item.metadata.effective_hashtags);
    }
  }

  for (const rootId of actualRootIds) {
    computeEffectiveHashtags(rootId, []);
  }

  return {
    ast: { items, root_ids: actualRootIds },
    warnings,
  };
}
