/**
 * Todoosy Sequence Utilities
 *
 * Functions for working with sequenced (numbered) task lists.
 */

import type { AST, ItemNode } from './types.js';

export interface SequenceInfo {
  parentId: string;
  hasSequence: boolean;
  numberedChildren: { id: string; sequenceNumber: number }[];
  gaps: { position: number; expected: number; actual: number }[];
  duplicates: { number: number; ids: string[] }[];
}

/**
 * Analyze the sequence of numbered children under a parent item.
 * Returns information about gaps and duplicates in the sequence.
 */
export function analyzeSequence(ast: AST, parentId: string): SequenceInfo {
  const itemMap = new Map<string, ItemNode>();
  for (const item of ast.items) {
    itemMap.set(item.id, item);
  }

  const parent = itemMap.get(parentId);
  if (!parent) {
    return {
      parentId,
      hasSequence: false,
      numberedChildren: [],
      gaps: [],
      duplicates: [],
    };
  }

  // Collect numbered children
  const numberedChildren: { id: string; sequenceNumber: number }[] = [];
  for (const childId of parent.children) {
    const child = itemMap.get(childId);
    if (child && child.marker_type === 'numbered' && child.sequence_number !== undefined) {
      numberedChildren.push({ id: childId, sequenceNumber: child.sequence_number });
    }
  }

  if (numberedChildren.length === 0) {
    return {
      parentId,
      hasSequence: false,
      numberedChildren: [],
      gaps: [],
      duplicates: [],
    };
  }

  // Find gaps - numbers should be consecutive starting from 1
  const gaps: { position: number; expected: number; actual: number }[] = [];
  for (let i = 0; i < numberedChildren.length; i++) {
    const expected = i + 1;
    const actual = numberedChildren[i].sequenceNumber;
    if (actual !== expected) {
      gaps.push({ position: i, expected, actual });
    }
  }

  // Find duplicates
  const numberCounts = new Map<number, string[]>();
  for (const child of numberedChildren) {
    const ids = numberCounts.get(child.sequenceNumber) || [];
    ids.push(child.id);
    numberCounts.set(child.sequenceNumber, ids);
  }

  const duplicates: { number: number; ids: string[] }[] = [];
  for (const [num, ids] of numberCounts) {
    if (ids.length > 1) {
      duplicates.push({ number: num, ids });
    }
  }

  return {
    parentId,
    hasSequence: true,
    numberedChildren,
    gaps,
    duplicates,
  };
}

/**
 * Renumber children of a parent to have consecutive sequence numbers starting from 1.
 * Returns a new AST with the renumbered items.
 */
export function renumberChildren(ast: AST, parentId: string): AST {
  const itemMap = new Map<string, ItemNode>();
  for (const item of ast.items) {
    itemMap.set(item.id, { ...item });
  }

  const parent = itemMap.get(parentId);
  if (!parent) {
    return ast;
  }

  // Renumber numbered children
  let nextNum = 1;
  for (const childId of parent.children) {
    const child = itemMap.get(childId);
    if (child && child.marker_type === 'numbered') {
      child.sequence_number = nextNum++;
    }
  }

  return {
    items: Array.from(itemMap.values()),
    root_ids: [...ast.root_ids],
  };
}

/**
 * Insert a new item into a sequenced list at a specific position and renumber.
 * Position is 0-indexed. Returns a new AST with the inserted and renumbered items.
 */
export function insertSequencedItem(
  ast: AST,
  parentId: string,
  position: number,
  newItem: Omit<ItemNode, 'id' | 'sequence_number'>
): AST {
  const itemMap = new Map<string, ItemNode>();
  for (const item of ast.items) {
    itemMap.set(item.id, { ...item });
  }

  const parent = itemMap.get(parentId);
  if (!parent) {
    return ast;
  }

  // Generate new ID
  const maxId = Math.max(...ast.items.map(item => parseInt(item.id, 10)));
  const newId = String(maxId + 1);

  // Create new item
  const item: ItemNode = {
    ...newItem,
    id: newId,
    sequence_number: position + 1,
    children: newItem.children || [],
  };

  // Insert into parent's children
  const newChildren = [...parent.children];
  newChildren.splice(position, 0, newId);
  parent.children = newChildren;

  // Add to items
  itemMap.set(newId, item);

  // Renumber all numbered children
  let nextNum = 1;
  for (const childId of parent.children) {
    const child = itemMap.get(childId);
    if (child && child.marker_type === 'numbered') {
      child.sequence_number = nextNum++;
    }
  }

  return {
    items: Array.from(itemMap.values()),
    root_ids: [...ast.root_ids],
  };
}

/**
 * Remove an item from a sequenced list and renumber siblings.
 * Returns a new AST with the item removed and siblings renumbered.
 */
export function removeSequencedItem(ast: AST, itemId: string): AST {
  const itemMap = new Map<string, ItemNode>();
  for (const item of ast.items) {
    if (item.id !== itemId) {
      itemMap.set(item.id, { ...item });
    }
  }

  // Find and update parent
  for (const [id, item] of itemMap) {
    if (item.children.includes(itemId)) {
      item.children = item.children.filter(c => c !== itemId);

      // Renumber numbered children
      let nextNum = 1;
      for (const childId of item.children) {
        const child = itemMap.get(childId);
        if (child && child.marker_type === 'numbered') {
          child.sequence_number = nextNum++;
        }
      }
      break;
    }
  }

  // Update root_ids if necessary
  const newRootIds = ast.root_ids.filter(id => id !== itemId);

  return {
    items: Array.from(itemMap.values()),
    root_ids: newRootIds,
  };
}

/**
 * Convert bullet children of a parent to numbered items.
 * Returns a new AST with bullet items converted to numbered.
 */
export function convertToSequence(ast: AST, parentId: string): AST {
  const itemMap = new Map<string, ItemNode>();
  for (const item of ast.items) {
    itemMap.set(item.id, { ...item });
  }

  const parent = itemMap.get(parentId);
  if (!parent) {
    return ast;
  }

  // Convert bullet children to numbered
  let nextNum = 1;
  for (const childId of parent.children) {
    const child = itemMap.get(childId);
    if (child && child.type === 'list') {
      child.marker_type = 'numbered';
      child.sequence_number = nextNum++;
    }
  }

  return {
    items: Array.from(itemMap.values()),
    root_ids: [...ast.root_ids],
  };
}

/**
 * Convert numbered children of a parent to bullet items.
 * Returns a new AST with numbered items converted to bullets.
 */
export function convertToBullets(ast: AST, parentId: string): AST {
  const itemMap = new Map<string, ItemNode>();
  for (const item of ast.items) {
    itemMap.set(item.id, { ...item });
  }

  const parent = itemMap.get(parentId);
  if (!parent) {
    return ast;
  }

  // Convert numbered children to bullets
  for (const childId of parent.children) {
    const child = itemMap.get(childId);
    if (child && child.marker_type === 'numbered') {
      child.marker_type = 'bullet';
      child.sequence_number = undefined;
    }
  }

  return {
    items: Array.from(itemMap.values()),
    root_ids: [...ast.root_ids],
  };
}
