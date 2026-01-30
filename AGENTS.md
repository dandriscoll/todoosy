# AGENTS.md

## Project Overview

Todoosy is a Markdown-based personal todo system with dual TypeScript and Python implementations. It provides a parser, formatter, linter, query engine, and sequence manager that operate on structured Markdown documents containing embedded metadata tokens.

## Codebase Structure

```
js/src/          TypeScript implementation
py/todoosy/      Python implementation
testdata/        Shared golden test cases (input.md → expected outputs)
docs/            Format specification
```

Both implementations expose the same public API surface: `parse`, `format`, `lint`, `queryUpcoming`, `queryMisc`, `queryByHashtag`, `listHashtags`, and sequence operations.

### Key Modules

| Module       | Purpose                                              |
|--------------|------------------------------------------------------|
| parser       | Converts Markdown text into an AST                   |
| formatter    | Normalizes documents to canonical form               |
| linter       | Validates documents and returns warnings             |
| query        | Searches/filters items by date, hashtag, misc status |
| sequence     | Manages numbered/sequenced lists                     |
| settings     | Parses todoosy.settings.md configuration files       |
| scheme       | Legacy scheme format parser                          |
| types        | Core data structures (ItemNode, AST, Metadata, etc.) |

### Metadata Token Format

Items can contain metadata in parentheses:

```markdown
- Task name (due 2026-01-15 p1 2h #work)
```

Supported tokens: `due DATE`, `~` (soft date prefix), `p0`–`pN` (priority), time estimates (`30m`, `2h`, `1d`), progress states (`done`, `deleted`, `in progress`, `blocked`), and `#hashtags`.

## Testing

Both implementations share golden test cases in `testdata/`. Each case has `input.md` and expected output files for AST, formatting, warnings, and queries.

- JS: `cd js && npm test`
- Python: `cd py && pytest`

## Feature Documentation

All features are documented in `FEATURES.md`, which also contains a changelog of major changes. When adding, removing, or modifying any feature, you **must** update `FEATURES.md` accordingly:

1. Add or update the feature entry in the appropriate section.
2. Add a dated entry to the Changelog section at the top of the changelog, describing what changed.
3. Keep entries concise and factual.
