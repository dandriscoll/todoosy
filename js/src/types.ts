/**
 * Todoosy Types
 */

export interface ItemMetadata {
  due: string | null;
  priority: number | null;
  estimate_minutes: number | null;
  progress: string | null;
}

export interface ItemNode {
  id: string;
  type: 'heading' | 'list';
  level?: number; // Only for headings
  raw_line: string;
  title_text: string;
  metadata: ItemMetadata;
  comments: string[];
  children: string[];
  item_span: [number, number];
  subtree_span: [number, number];
  line: number;
  column: number;
}

export interface AST {
  items: ItemNode[];
  root_ids: string[];
}

export interface Warning {
  code: string;
  message: string;
  line: number | null;
  column: number | null;
  span: [number, number] | null;
}

export interface LintResult {
  warnings: Warning[];
}

export interface UpcomingItem {
  id: string;
  due: string;
  priority: number | null;
  priority_label?: string;
  path: string;
  item_span: [number, number];
}

export interface UpcomingResult {
  items: UpcomingItem[];
}

export interface MiscItem {
  id: string;
  title_text: string;
  item_span: [number, number];
}

export interface MiscResult {
  items: MiscItem[];
}

export interface Scheme {
  timezone: string | null;
  priorities: Record<string, string>;
  misc: string; // format: "filename/headingname", default: "todoosy.md/Misc"
}

export interface ParsedToken {
  type: 'due' | 'priority' | 'estimate' | 'progress';
  value: string | number;
  raw: string;
  start: number;
  end: number;
}

export interface ParenGroup {
  start: number;
  end: number;
  content: string;
  tokens: ParsedToken[];
  hasRecognizedTokens: boolean;
}
