# Features

## Parsing

- Converts Markdown documents into a structured AST
- Extracts metadata tokens from parenthesized groups: due dates, priorities, estimates, progress states, and hashtags
- Supports multiple date formats: ISO (`YYYY-MM-DD`), US (`MM/DD/YYYY`, `MM/DD/YY`), and text dates
- `today` and `tomorrow` keywords resolve to concrete dates at parse time, using the configured timezone
- Relative offsets resolve to concrete dates: `2w`, `in 2 weeks`, `two months`, `twenty-one days`, etc. (1–31 number-words supported)
- Soft/flexible dates via `~` — point form (`~Apr 27`) for a soft target, span form (`Apr 24~Apr 27`) for a window during which the task should be on the user's radar
- Calendar-aware month/year arithmetic (Jan 31 + 1 month → Feb 28/29)
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

- `queryUpcoming()` — items with due dates, sorted by `due_start ?? due` (windows surface from when they start mattering) then priority then document order
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

## 2026-04-27
- Added `today` and `tomorrow` keyword resolution (timezone-aware, parse-time, never persisted as keywords)
- Added relative-date offsets: `2w`, `in 2 weeks`, `two months`, `twenty-one days`, etc. (number-words 1–31, calendar-aware month/year math)
- Added soft window span syntax: `start~end` between two dates carries soft-window semantics. Existing point form `~end` unchanged. New `due_start` field on `ItemMetadata`
- `parse()`, `format()`, `lint()`, `queryUpcoming()` now accept optional `now`/`settings` parameters for deterministic time-injection
- `queryUpcoming` sort key is now `due_start ?? due` so windows surface when they start mattering, not when they end
- Wired the previously-dangling `# Timezone` setting into "today" resolution; UTC is the default when no timezone is set

## v0.3.3
- Added sequence list support

## v0.3.0
- Updated parser exports

## v0.2.6
- Updated to settings format
