# Features

## Parsing

- Converts Markdown documents into a structured AST
- Extracts metadata tokens from parenthesized groups: due dates, priorities, estimates, progress states, and hashtags
- Supports multiple date formats: ISO (`YYYY-MM-DD`), US (`MM/DD/YYYY`, `MM/DD/YY`), and text dates
- Soft/flexible dates via `~` prefix
- Builds item hierarchy from heading levels and list indentation
- Associates indented comments with their parent items
- Tracks line and column positions

## Formatting

- Normalizes documents to a canonical form with consistent spacing and indentation
- Orders metadata tokens consistently (due date, progress, priority, estimate, hashtags)
- Supports formatting styles: roomy, balanced, and tight
- Preserves non-metadata parentheses

## Linting

- Validates date formats, priority syntax, estimate syntax, and hashtag format
- Detects missing Misc sections
- Validates calendar format and custom priority labels
- Returns structured warnings with line numbers

## Query Engine

- `queryUpcoming()` — items with due dates, sorted by date then priority then document order
- `queryMisc()` — items under the Misc heading
- `queryByHashtag()` — filter items by hashtag
- `listHashtags()` — all hashtags with occurrence counts
- Builds hierarchical paths (e.g., "Work > Backend > Database")

## Sequence Management

- Analyze numbered list sequences for gaps and duplicates
- Renumber children consecutively
- Insert and remove items while maintaining sequence integrity
- Convert between bullet lists and numbered sequences

## Settings

- Parse `todoosy.settings.md` configuration files
- Known settings: timezone, priorities, misc, calendar_format, formatting_style
- Supports single values, lists, and key-value maps
- Legacy Scheme format support

---

# Changelog

## v0.3.3
- Added sequence list support

## v0.3.0
- Updated parser exports

## v0.2.6
- Updated to settings format
