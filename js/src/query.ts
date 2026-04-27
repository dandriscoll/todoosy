/**
 * Todoosy Query Engine
 */

import { parse, type ParseOptions } from './parser.js';
import type {
  AST,
  ItemNode,
  UpcomingItem,
  UpcomingResult,
  MiscItem,
  MiscResult,
  Scheme,
} from './types.js';

function buildPath(itemId: string, ast: AST): string {
  const itemMap = new Map<string, ItemNode>();
  const parentMap = new Map<string, string>();

  for (const item of ast.items) {
    itemMap.set(item.id, item);
    for (const childId of item.children) {
      parentMap.set(childId, item.id);
    }
  }

  const parts: string[] = [];
  let currentId: string | undefined = itemId;

  while (currentId !== undefined) {
    const item = itemMap.get(currentId);
    if (item) {
      parts.unshift(item.title_text);
    }
    currentId = parentMap.get(currentId);
  }

  return parts.join(' > ');
}

export function queryUpcoming(text: string, scheme?: Scheme, options?: ParseOptions): UpcomingResult {
  const { ast } = parse(text, options);
  const items: UpcomingItem[] = [];

  // Find all items with due dates
  for (const item of ast.items) {
    if (item.metadata.due) {
      const upcomingItem: UpcomingItem = {
        id: item.id,
        due: item.metadata.due,
        priority: item.metadata.priority,
        path: buildPath(item.id, ast),
        item_span: item.item_span,
      };

      // Add priority label if scheme is provided
      if (scheme && item.metadata.priority !== null) {
        const label = scheme.priorities[String(item.metadata.priority)];
        if (label) {
          upcomingItem.priority_label = label;
        }
      }

      items.push(upcomingItem);
    }
  }

  // Map id -> sort-anchor (due_start if present, else due). Span items sort by
  // when they start mattering; point items sort by their date as before.
  const sortAnchor = new Map<string, string>();
  for (const item of ast.items) {
    if (item.metadata.due) {
      sortAnchor.set(item.id, item.metadata.due_start ?? item.metadata.due);
    }
  }

  // Sort by:
  // 1. due_start ?? due ascending (windows surface from when they start)
  // 2. Priority ascending (lower is higher priority, nulls last)
  // 3. Document order (by item_span start)
  items.sort((a, b) => {
    const dateCompare = sortAnchor.get(a.id)!.localeCompare(sortAnchor.get(b.id)!);
    if (dateCompare !== 0) return dateCompare;

    // Priority comparison (null treated as infinity)
    const aPri = a.priority ?? Infinity;
    const bPri = b.priority ?? Infinity;
    if (aPri !== bPri) return aPri - bPri;

    // Document order
    return a.item_span[0] - b.item_span[0];
  });

  return { items };
}

function parseMiscLocation(misc: string): { filename: string; heading: string } {
  const slashIndex = misc.indexOf('/');
  if (slashIndex === -1) {
    return { filename: misc, heading: 'Misc' };
  }
  return {
    filename: misc.substring(0, slashIndex),
    heading: misc.substring(slashIndex + 1),
  };
}

export function queryMisc(text: string, scheme?: Scheme): MiscResult {
  const { ast } = parse(text);
  const items: MiscItem[] = [];

  // Determine the heading name from scheme or use default
  const miscLocation = parseMiscLocation(scheme?.misc ?? 'todoosy.md/Misc');

  // Find the Misc section
  let miscSectionId: string | null = null;
  for (const item of ast.items) {
    if (item.type === 'heading' && item.title_text === miscLocation.heading && item.level === 1) {
      miscSectionId = item.id;
      break;
    }
  }

  if (miscSectionId === null) {
    return { items };
  }

  // Get all direct children of the Misc section
  const miscSection = ast.items.find(i => i.id === miscSectionId);
  if (!miscSection) {
    return { items };
  }

  const itemMap = new Map<string, ItemNode>();
  for (const item of ast.items) {
    itemMap.set(item.id, item);
  }

  for (const childId of miscSection.children) {
    const child = itemMap.get(childId);
    if (child) {
      items.push({
        id: child.id,
        title_text: child.title_text,
        item_span: child.item_span,
      });
    }
  }

  return { items };
}

export interface HashtagItem {
  id: string;
  title_text: string;
  path: string;
  item_span: [number, number];
  hashtags: string[];           // Direct hashtags
  effective_hashtags: string[]; // Including inherited
}

export interface HashtagResult {
  items: HashtagItem[];
}

export interface HashtagListResult {
  hashtags: string[];
}

export function queryByHashtag(text: string, hashtag: string): HashtagResult {
  const { ast } = parse(text);
  const items: HashtagItem[] = [];

  // Normalize hashtag (lowercase, remove # if present)
  const normalizedHashtag = hashtag.replace(/^#/, '').toLowerCase();

  // Find all items with the hashtag (using effective_hashtags for inheritance)
  for (const item of ast.items) {
    if (item.metadata.effective_hashtags.includes(normalizedHashtag)) {
      items.push({
        id: item.id,
        title_text: item.title_text,
        path: buildPath(item.id, ast),
        item_span: item.item_span,
        hashtags: item.metadata.hashtags,
        effective_hashtags: item.metadata.effective_hashtags,
      });
    }
  }

  // Sort by document order
  items.sort((a, b) => a.item_span[0] - b.item_span[0]);

  return { items };
}

export function listHashtags(text: string): HashtagListResult {
  const { ast } = parse(text);
  const hashtagSet = new Set<string>();

  // Collect all unique hashtags from all items
  for (const item of ast.items) {
    for (const tag of item.metadata.hashtags) {
      hashtagSet.add(tag);
    }
  }

  // Return sorted list
  return { hashtags: [...hashtagSet].sort() };
}
