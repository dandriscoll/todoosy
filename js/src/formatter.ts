/**
 * Todoosy Formatter
 */

import { parse } from './parser.js';
import type { ItemNode, ItemMetadata, Scheme } from './types.js';

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

function formatMetadata(metadata: ItemMetadata): string {
  const parts: string[] = [];

  if (metadata.due) {
    const softPrefix = metadata.due_soft ? '~' : '';
    parts.push(`due ${softPrefix}${metadata.due}`);
  }

  if (metadata.progress) {
    parts.push(metadata.progress);
  }

  if (metadata.priority !== null) {
    parts.push(`p${metadata.priority}`);
  }

  if (metadata.estimate_minutes !== null) {
    const minutes = metadata.estimate_minutes;
    if (minutes % 480 === 0 && minutes >= 480) {
      parts.push(`${minutes / 480}d`);
    } else if (minutes % 60 === 0 && minutes >= 60) {
      parts.push(`${minutes / 60}h`);
    } else {
      parts.push(`${minutes}m`);
    }
  }

  return parts.length > 0 ? `(${parts.join(' ')})` : '';
}

function formatItemLine(item: ItemNode, indent: number = 0): string {
  const indentStr = '  '.repeat(indent);
  const metaStr = formatMetadata(item.metadata);
  const titleWithMeta = metaStr ? `${item.title_text} ${metaStr}` : item.title_text;

  if (item.type === 'heading') {
    const hashes = '#'.repeat(item.level || 1);
    return `${hashes} ${titleWithMeta}`;
  }

  return `${indentStr}- ${titleWithMeta}`;
}

function formatComments(comments: string[], isListItem: boolean, indent: number): string[] {
  if (comments.length === 0) return [];

  if (isListItem) {
    // Indent is the list item's indent level; comments need +1 level
    const indentStr = '  '.repeat(indent + 1);
    return comments.map(c => `${indentStr}${c}`);
  }

  // Heading comments are not indented
  return comments;
}

export function format(text: string, scheme?: Scheme, filename?: string): string {
  const { ast } = parse(text);
  const lines: string[] = [];
  const itemMap = new Map<string, ItemNode>();

  for (const item of ast.items) {
    itemMap.set(item.id, item);
  }

  // Determine misc location from scheme or use default
  const miscLocation = parseMiscLocation(scheme?.misc ?? 'todoosy.md/Misc');
  // If no filename provided, assume it could be the misc file (backward compatibility)
  const isMiscFile = filename === undefined || filename === miscLocation.filename;

  // Determine formatting style: roomy (default), balanced, or tight
  const formattingStyle = scheme?.formatting_style ?? 'roomy';

  // Track Misc section
  let miscSectionId: string | null = null;

  // Find existing Misc section (using configured heading name)
  for (const item of ast.items) {
    if (item.type === 'heading' && item.title_text === miscLocation.heading && item.level === 1) {
      miscSectionId = item.id;
      break;
    }
  }

  // Helper to determine if we should add blank line before a heading
  function shouldAddBlankBefore(item: ItemNode): boolean {
    if (item.type !== 'heading') return false;
    if (formattingStyle === 'tight') return false;
    if (formattingStyle === 'balanced') return item.level === 1;
    return true; // roomy
  }

  // Helper to determine if we should add blank line after a heading
  function shouldAddBlankAfter(item: ItemNode): boolean {
    if (item.type !== 'heading') return false;
    if (formattingStyle === 'tight') return false;
    if (formattingStyle === 'balanced') return item.level === 1;
    return true; // roomy
  }

  // Helper to format an item and its subtree
  function formatItem(id: string, listIndent: number = 0, isUnderMisc: boolean = false): void {
    const item = itemMap.get(id)!;

    // Skip Misc section during normal iteration (we'll add it at the end)
    if (item.id === miscSectionId && !isUnderMisc) {
      return;
    }

    // Add blank line before headings (except at start), based on style
    if (shouldAddBlankBefore(item) && lines.length > 0) {
      if (lines[lines.length - 1] !== '') {
        lines.push('');
      }
    }

    lines.push(formatItemLine(item, listIndent));

    // Add blank line after heading before comments or children, based on style
    if (shouldAddBlankAfter(item)) {
      lines.push('');
    }

    // Add comments
    const formattedComments = formatComments(
      item.comments,
      item.type === 'list',
      listIndent
    );
    lines.push(...formattedComments);

    // Add blank line after heading comments before children
    if (item.type === 'heading' && item.comments.length > 0 && item.children.length > 0) {
      if (shouldAddBlankAfter(item)) {
        lines.push('');
      }
    }

    // Format children
    for (const childId of item.children) {
      const child = itemMap.get(childId)!;
      if (child.type === 'list') {
        // List items under a heading start at indent 0
        // Nested list items increment indent
        const nextIndent = item.type === 'heading' ? 0 : listIndent + 1;
        formatItem(childId, nextIndent, isUnderMisc);
      } else {
        formatItem(childId, 0, isUnderMisc);
      }
    }
  }

  // Format all root items except Misc
  for (const rootId of ast.root_ids) {
    if (rootId !== miscSectionId) {
      formatItem(rootId, 0, false);
    }
  }

  // Add Misc section at the end (only for the misc file)
  if (isMiscFile) {
    // Add blank line before Misc heading based on style
    const miscItem = miscSectionId ? itemMap.get(miscSectionId) : null;
    const shouldAddBlankBeforeMisc = formattingStyle !== 'tight' && (formattingStyle === 'roomy' || formattingStyle === 'balanced');
    if (lines.length > 0 && lines[lines.length - 1] !== '' && shouldAddBlankBeforeMisc) {
      lines.push('');
    }
    lines.push(`# ${miscLocation.heading}`);

    // Add blank line after Misc heading based on style
    const shouldAddBlankAfterMisc = formattingStyle !== 'tight' && (formattingStyle === 'roomy' || formattingStyle === 'balanced');

    // Add Misc items if they exist
    if (miscSectionId) {
      const miscItemNode = itemMap.get(miscSectionId)!;
      if (miscItemNode.comments.length > 0) {
        if (shouldAddBlankAfterMisc) {
          lines.push('');
        }
        lines.push(...miscItemNode.comments);
      }
      if (miscItemNode.children.length > 0) {
        if (shouldAddBlankAfterMisc) {
          lines.push('');
        }
        for (const childId of miscItemNode.children) {
          // Format misc children - they start at indent 0
          const child = itemMap.get(childId)!;
          lines.push(formatItemLine(child, 0));
          const formattedComments = formatComments(
            child.comments,
            child.type === 'list',
            0
          );
          lines.push(...formattedComments);
        }
      }
    }
  }

  return lines.join('\n') + '\n';
}
