# Todoosy Format Specification

**Version:** 0.2
**Status:** Draft

## Overview

Todoosy is a personal Markdown-based todo system. This specification defines a format that remains valid CommonMark Markdown while embedding structured task metadata through text conventions.

The format is designed to be:
- Human-readable and editable in any text editor
- Valid CommonMark that renders meaningfully
- Machine-parseable for tooling (parser, formatter, linter, query engine)

---

## Normative Specification

### 1. Items

An **item** is defined as:

1. Any ATX heading line (`#`, `##`, `###`, etc.) — called a **heading-item**
2. Any list item line (`- `, `* `, or `N. ` where N is a number) — called a **list-item**

Items MAY have:
- Children (nested items per hierarchy rules)
- Comments (descriptive text)
- Metadata tokens (structured data in parentheses)

### 2. Hierarchy Rules

#### 2.1 Heading-Items

A heading-item's **region** is defined as all content from the heading line up to (but not including):
- The next heading line of any level, OR
- End of file (EOF)

Within a heading region:
- All list-items are descendants of the heading-item
- List-item parent/child relationships follow list indentation rules (Section 2.2)
- A heading-item is NEVER a child of a list-item

A new heading MUST terminate any currently active list subtree. Parsers MUST close all open list contexts when encountering a heading.

#### 2.2 List-Items

List indentation defines parent/child relationships:

- A list-item indented further than the previous list-item is a **child** of that item
- A list-item at the same indentation level as a previous list-item is a **sibling**
- A list-item at reduced indentation (dedenting) **closes** the current subtree and becomes a sibling of an ancestor

Indentation MUST be measured in spaces. Parsers SHOULD treat 2-4 spaces as one indentation level for flexibility, but formatters MUST output exactly 2 spaces per level.

List-items within a heading region are children of that heading-item, either directly (top-level list-items) or indirectly (nested list-items).

### 3. Comments (Commentary)

Comments are plain text lines that provide additional context for an item.

#### 3.1 General Rules

- Comments are lines immediately following an item
- Comments stop at:
  1. The first blank line, OR
  2. The next item (heading or list-item)

#### 3.2 Heading-Item Comments

Comments under heading-items:
- MUST be unindented (standard paragraphs)
- Appear within the heading's region
- End at the first blank line or next item

#### 3.3 List-Item Comments

Comments under list-items:
- MUST be indented to align with the list item's text content
- This indentation is REQUIRED for valid CommonMark rendering
- The formatter MUST enforce correct indentation
- The linter MUST warn if comment indentation is violated

### 4. Metadata Tokens

#### 4.1 Token Recognition

Metadata tokens are ONLY recognized inside parentheses `( … )`.

Rules:
- Tokens are **case-insensitive**
- Tokens within parentheses are **whitespace and/or comma separated**
- Multiple parentheses groups in a single item are combined into a **token bag**
- Parentheses containing NO recognized tokens are treated as normal text
- Parsers MUST NOT modify or strip non-metadata parentheses

#### 4.2 Recognized Token Forms

##### Due Date

Format: `due <date>`

Accepted date formats:
| Format | Example | Notes |
|--------|---------|-------|
| `YYYY-MM-DD` | `due 2026-01-10` | ISO 8601 (preferred) |
| `MM/DD/YYYY` | `due 01/10/2026` | US format, 4-digit year |
| `MM/DD/YY` | `due 01/10/26` | US format, 2-digit year |
| `Month D` | `due January 7` | Full month name, no year |
| `Mon D` | `due Jan 7` | 3-letter month abbreviation, no year |
| `Month D YYYY` | `due January 7 2028` | Full month name with year |
| `Mon D YYYY` | `due Jan 7 2028` | 3-letter month abbreviation with year |

Month names and abbreviations are case-insensitive.

Two-digit year interpretation:
- Years 00-99 map to 2000-2099

Year inference for text dates without year:
- If the date (in the current year) is more than 3 months in the past, the next year is assumed
- Example: If today is October 7, 2026, "due Aug 1" (about 2 months ago) is interpreted as August 1, 2026, but "due Jun 1" (more than 3 months ago) is interpreted as June 1, 2027

Parsers MUST normalize all date formats to ISO 8601 (`YYYY-MM-DD`) internally

##### Priority

Format: `pN` where N is a non-negative integer

Examples: `p0`, `p1`, `p10`, `p99`

- Lower numbers indicate higher priority
- `p0` is the highest priority
- Parsers MUST normalize to integer internally

##### Estimate

Format: `N<unit>` where:
- N is a positive integer
- Unit is one of: `m` (minutes), `h` (hours), `d` (days)

Examples: `30m`, `2h`, `1d`

Normalization:
- Parsers MUST normalize to minutes internally
- Conversion: 1h = 60m, 1d = 480m (8 working hours)

##### Progress

Format: Progress state name (case-insensitive)

Built-in progress states:
- `done` - Task is complete
- `deleted` - Task has been deleted/cancelled
- `in progress` - Task is currently being worked on
- `blocked` - Task is blocked by something

Examples: `done`, `deleted`, `in progress`, `blocked`

Progress tokens can appear anywhere within a parentheses group alongside other tokens:
- `(due Jan 6, in progress, 3h)` - Task due Jan 6, in progress, estimate 3 hours
- `(done, p1)` - Completed task with priority 1
- `(blocked)` - Blocked task

Parsers MUST normalize progress state names to lowercase internally.

Additional progress states MAY be defined in the scheme file (Section 7.4).

#### 4.3 Token Bag Combination

When multiple parentheses groups exist, all recognized tokens are merged:

```markdown
- Task (p1, in progress) with details (due 2026-01-15, 2h)
```

Results in token bag: `{priority: 1, progress: "in progress", due: "2026-01-15", estimate: 120}`

If duplicate token types appear, the **last occurrence wins**.

#### 4.4 Canonical Examples

```markdown
- Fix bug (due 2026-01-10 p0 2h)
# Project Alpha (p2)
- Call vendor (due 01/31/26)
- Review docs (p1, 30m) and notes (due 2026-02-01)
```

### 5. Reserved Misc Section

#### 5.1 Definition

A heading with the exact text `# Misc` (case-sensitive) is the **reserved misc section**.

- Items under `# Misc` are called **misc items**
- The misc section is intended for uncategorized or quick-capture items
- The misc section SHOULD contain a flat list (no deep nesting)

#### 5.2 Position Requirements

- The `# Misc` heading MUST be the final heading in the document
- No other headings MAY appear after `# Misc`
- The formatter MUST move `# Misc` to EOF if it appears elsewhere
- The linter MUST warn if any heading appears after `# Misc`

### 6. Views

Views are logical presentations of items filtered and sorted by criteria.

#### 6.1 Upcoming View

The **Upcoming** view includes all items with a due date.

Sort order (stable sort):
1. Due date ascending (earliest first)
2. Priority ascending within same date (p0 before p1; uses scheme file labels if defined)
3. Document order as tie-breaker (items appearing earlier in source come first)

Items without a due date are EXCLUDED from the Upcoming view.

### 7. Scheme File

#### 7.1 File Definition

The scheme file MUST be named exactly `todoosy.scheme.md` and located in the same directory as the todoosy document (or a configured location).

The scheme file is valid Markdown and defines:
- Timezone for date interpretation
- Priority labels and ordering

#### 7.2 Timezone Section

A heading `# Timezone` followed by a single line containing an IANA timezone identifier.

```markdown
# Timezone

America/Denver
```

- The timezone string MUST be a valid IANA Time Zone Database identifier
- If omitted, parsers SHOULD default to UTC

#### 7.3 Priorities Section

A heading `# Priorities` followed by priority definitions, one per line.

Format: `p<N> - <label>`

```markdown
# Priorities

p0 - Critical
p1 - High
p2 - Medium
p3 - Low
```

Rules:
- Each line explicitly defines a priority number and its label
- Priority order is determined by position (first line is highest priority)
- `N` MUST be a non-negative integer
- Label is freeform text after the ` - ` separator
- Priority numbers used in documents (`p0`, `p1`, etc.) map to these labels

#### 7.4 Progress Section

A heading `# Progress` followed by additional progress state definitions, one per line.

```markdown
# Progress

waiting
deferred
cancelled
```

Rules:
- Each line defines an additional progress state name
- Progress states are case-insensitive when matching tokens
- Custom progress states extend (do not replace) the built-in states: `done`, `deleted`, `in progress`, `blocked`
- If omitted, only the built-in progress states are recognized

---

## Examples

### Example 1: Headings and Lists Mixed

```markdown
# Work Tasks

- Review PR #123
- Update documentation
  - API reference
  - Getting started guide

# Personal

- Buy groceries
- Call mom
```

**Interpretation:**
- `# Work Tasks` is a heading-item with 2 direct children and 2 grandchildren
- `# Personal` is a heading-item with 2 direct children
- The `# Personal` heading terminates the `# Work Tasks` region

### Example 2: Heading Terminating a List Subtree

```markdown
# Project A

- Task 1
  - Subtask 1.1
  - Subtask 1.2
    - Deep task

# Project B

- Task 2
```

**Interpretation:**
- When `# Project B` is encountered, the entire nested list under `# Project A` is closed
- `- Task 2` is a child of `# Project B`, not a sibling of the deep task

### Example 3: Comments Under List Items (Indented)

```markdown
- Fix login bug (p0)
  The bug occurs when users have special characters in passwords.
  Affects approximately 5% of users.
- Update tests
  Need to add edge cases for the login fix.
```

**Interpretation:**
- Lines 2-3 are comments for "Fix login bug"
- Line 5 is a comment for "Update tests"
- All comment lines are indented to align with list text

### Example 4: Comments Under Headings (Unindented)

```markdown
# Q1 Goals (p1)

These are the primary objectives for Q1 2026.
Focus on customer retention and new feature development.

- Reduce churn by 10%
- Launch feature X
```

**Interpretation:**
- Lines 3-4 are comments for `# Q1 Goals`
- Comments are unindented paragraphs
- The blank line after comments separates them from the list

### Example 5: Multiple Parentheses Groups

```markdown
- Prepare presentation (p2) for Monday meeting (due 2026-01-13, 4h)
```

**Interpretation:**
- Token bag: `{priority: 2, due: "2026-01-13", estimate: 240}`
- "for Monday meeting" is not in parentheses with tokens, treated as normal text
- All recognized tokens from both groups are combined

### Example 6: Parentheses That Are NOT Metadata

```markdown
- Call John (CEO) about the project
- Fix bug in parser (see issue #45)
- Review the Smith (and Jones) proposal (p1)
```

**Interpretation:**
- Line 1: `(CEO)` contains no recognized tokens → normal text
- Line 2: `(see issue #45)` contains no recognized tokens → normal text
- Line 3: `(and Jones)` is normal text; `(p1)` is metadata → token bag: `{priority: 1}`

### Example 7: Misc Section at EOF

```markdown
# Active Projects

- Project Alpha (p1)
- Project Beta (p2)

# Misc

- Random thought to process later
- Quick idea from meeting
- Someday/maybe item
```

**Interpretation:**
- `# Misc` is the reserved misc section
- Items under it are misc items (flat list)
- Linter passes because `# Misc` is the final heading

### Example 8: Due Dates in Multiple Formats

```markdown
- Tax filing (due 2026-04-15, p0)
- Dentist appointment (due 03/20/2026)
- Renew license (due 06/15/26)
- Submit report (due 01/10/26, p1, 2h)
```

**Interpretation:**
| Item | Normalized Due Date | Priority | Estimate |
|------|---------------------|----------|----------|
| Tax filing | 2026-04-15 | 0 | - |
| Dentist appointment | 2026-03-20 | - | - |
| Renew license | 2026-06-15 | - | - |
| Submit report | 2026-01-10 | 1 | 120 min |

All dates normalized to ISO 8601 internally.

### Example 9: Complete Document with Scheme

**todoosy.scheme.md:**
```markdown
# Timezone

America/New_York

# Priorities

p0 - Urgent
p1 - High
p2 - Normal
p3 - Backlog
```

**tasks.md:**
```markdown
# Work

Sprint tasks for this week.

- Deploy hotfix (due 2026-01-07, p0, 1h)
  Critical security patch.
- Code review (p2, 2h)
  Review Sarah's PR.

## Backend

- Optimize database queries (p2, 4h)
- Add caching layer (p3, 1d)

# Personal

- Gym (due 01/08/26)
- Read book (p3)

# Misc

- Look into new todo apps
- Random idea from shower
```

---

## Ambiguities and Non-Goals

The following are explicitly **out of scope** for version 0.1:

### Recurrence

Recurring tasks (e.g., "every Monday", "daily") are not supported. Each task instance must be created manually.

**Rationale:** Recurrence rules add significant complexity to parsing and require decisions about instance generation timing.

### Workflow States Beyond Progress

The built-in progress states (`done`, `deleted`, `in progress`, `blocked`) cover basic task tracking. Advanced workflow states (e.g., "waiting for review", "in QA") are not specified beyond the extensibility provided by the scheme file's Progress section.

**Rationale:** Workflow semantics vary widely between users. Basic progress tracking is supported via progress tokens.

### Multi-File Vaults

The specification defines single-file behavior only. Linking between files, vault-wide queries, or file organization conventions are not specified.

**Rationale:** Multi-file support requires decisions about file discovery, relative paths, and cross-file references.

### Conflict-Free Merges

When todoosy files are synced via cloud storage (e.g., Google Drive), conflicts are resolved by last-write-wins at the file level. There is no line-level or item-level merge strategy.

**Rationale:** Robust merging requires either CRDT-based approaches or operational transforms, which are beyond the scope of a file format spec.

### Tags and Labels

Arbitrary tagging (e.g., `#context`, `@person`) is not specified. Priority levels serve as the primary categorization mechanism.

**Rationale:** Tag syntax could conflict with Markdown headings. This may be addressed in a future version.

### Time-of-Day

Due dates do not include time components. All due dates are day-level granularity interpreted in the scheme file's timezone.

**Rationale:** Time-of-day adds complexity and is often unnecessary for personal task management.

---

## Conformance

A conforming **parser** MUST:
- Correctly identify all items (headings and list-items)
- Build the hierarchy according to Section 2
- Extract comments according to Section 3
- Parse and normalize all metadata tokens according to Section 4
- Recognize the `# Misc` section according to Section 5

A conforming **formatter** MUST:
- Output valid CommonMark
- Indent list-item comments correctly
- Use 2 spaces per indentation level
- Position `# Misc` at EOF

A conforming **linter** MUST:
- Warn on incorrectly indented list-item comments
- Warn on content appearing after `# Misc`
- Warn on unrecognized date formats in `due` tokens

A conforming **query engine** MUST:
- Implement the Upcoming view per Section 6.1
- Respect scheme file priority ordering when present
