/**
 * Todoosy Types
 */

export interface ItemMetadata {
  due: string | null;
  due_soft: boolean | null;
  priority: number | null;
  estimate_minutes: number | null;
  progress: string | null;
  hashtags: string[];           // Direct hashtags (without # prefix, lowercase)
  effective_hashtags: string[]; // All hashtags including inherited from ancestors
}

export interface ItemNode {
  id: string;
  type: 'heading' | 'list';
  level?: number; // Only for headings
  marker_type?: 'bullet' | 'numbered'; // Only for list items
  sequence_number?: number; // Original number for numbered items
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
  calendar_format: string; // Valid: yyyy-mm-dd, yyyy/mm/dd, mm/dd/yyyy, dd/mm/yyyy
  formatting_style: string; // Valid: roomy, balanced, tight
}

/**
 * Represents the value of a setting in the settings file.
 * - string: Single value (e.g., timezone, calendar format)
 * - string[]: List of values (e.g., tags, categories)
 * - Record<string, string>: Key-value pairs (e.g., priorities, colors)
 */
export type SettingValue = string | string[] | Record<string, string>;

/**
 * Extended settings interface that supports both known and custom settings.
 * Known settings are typed explicitly, custom settings are captured in `extended`.
 */
export interface Settings {
  // Known settings with typed values
  timezone: string | null;
  priorities: Record<string, string>;
  misc: string;
  calendar_format: string;
  formatting_style: string;

  // Extended settings for custom user-defined settings
  extended: Record<string, SettingValue>;
}

export interface ParsedToken {
  type: 'due' | 'priority' | 'estimate' | 'progress' | 'hashtag';
  value: string | number;
  raw: string;
  start: number;
  end: number;
  soft?: boolean; // Only for 'due' tokens - indicates a soft/flexible date
}

export interface ParenGroup {
  start: number;
  end: number;
  content: string;
  tokens: ParsedToken[];
  hasRecognizedTokens: boolean;
}
