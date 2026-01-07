# Todoosy

A Markdown-based personal todo system with parser, formatter, linter, and query engine implementations in TypeScript and Python.

## Try Todoosy

- [Try it for free](https://todoosy.org)
- [Python package (PyPI)](https://pypi.org/project/todoosy)
- [JavaScript package (npm)](https://www.npmjs.com/package/todoosy)
- [Read the specification](docs/spec.md)

Or, read on to learn more about the format and tools.

## Format Overview

Todoosy is a personal Markdown-based todo system. Documents remain valid CommonMark while embedding structured task metadata through text conventions.

### Items

Items can be:
- **Heading-items**: ATX headings (`#`, `##`, etc.)
- **List-items**: List items (`-`, `*`, or `1.`)

### Metadata Tokens

Metadata is placed inside parentheses:

```markdown
- Task with all metadata (due 2026-01-15 p1 2h)
```

Supported tokens:
- **Due date**: `due YYYY-MM-DD`, `due MM/DD/YYYY`, or `due MM/DD/YY`
- **Priority**: `p0`, `p1`, `p2`, etc. (lower is higher priority)
- **Estimate**: `30m`, `2h`, `1d` (minutes, hours, days)

### Comments

Comments are text lines immediately following an item:

```markdown
# Project (p1)

This is a comment for the heading.

- Task
  This is a comment for the list item (must be indented).
```

### Misc Section

Every document should have a `# Misc` heading at the end for uncategorized items.

### Scheme File

Optional `todoosy.scheme.md` file for timezone and priority labels:

```markdown
# Timezone

America/New_York

# Priorities

P0 - Critical
P1 - High
P2 - Normal
```

## Repository Structure

```
/docs/           - Format specification
/js/             - TypeScript implementation
/py/             - Python implementation
/testdata/       - Shared golden test files
```

## APIs

Both implementations provide:

| Function | Description |
|----------|-------------|
| `parse(text)` | Parse document to AST |
| `format(text)` | Format document to canonical form |
| `lint(text, scheme?)` | Lint document and return warnings |
| `queryUpcoming(text, scheme?)` | Get items with due dates, sorted |
| `queryMisc(text)` | Get items under `# Misc` |
| `parseScheme(text)` | Parse scheme file |

## TypeScript (JavaScript)

### Installation

```bash
cd js
npm install
npm run build
```

### Usage

```typescript
import { parse, format, lint, queryUpcoming, queryMisc, parseScheme } from 'todoosy';

const text = `
# Work

- Important task (due 2026-01-15 p0 2h)

# Misc
`;

// Parse
const { ast } = parse(text);
console.log(ast.items);

// Format
const formatted = format(text);

// Lint
const { warnings } = lint(text);

// Query upcoming items
const upcoming = queryUpcoming(text);
for (const item of upcoming.items) {
  console.log(`${item.path}: ${item.due}`);
}

// Query misc items
const misc = queryMisc(text);

// Parse scheme
const scheme = parseScheme(schemeText);
```

### Running Tests

```bash
cd js
npm test
```

## Python

### Installation

```bash
cd py
pip install -e .
```

For development:
```bash
pip install -e ".[dev]"
```

### Usage

```python
from todoosy import parse, format, lint, query_upcoming, query_misc, parse_scheme

text = '''
# Work

- Important task (due 2026-01-15 p0 2h)

# Misc
'''

# Parse
result = parse(text)
for item in result.ast.items:
    print(f"{item.title_text}: {item.metadata.due}")

# Format
formatted = format(text)

# Lint
result = lint(text)
for w in result.warnings:
    print(f"{w.code}: {w.message}")

# Query upcoming items
upcoming = query_upcoming(text)
for item in upcoming.items:
    print(f"{item.path}: {item.due}")

# Query misc items
misc = query_misc(text)

# Parse scheme
scheme = parse_scheme(scheme_text)
```

### Running Tests

```bash
cd py
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
pytest
```

## Adding Test Cases

Test cases are shared golden files in `/testdata/`. Each test case is a directory containing:

| File | Description |
|------|-------------|
| `input.md` | Input document |
| `expected_ast.json` | Expected parsed AST |
| `expected_formatted.md` | Expected formatted output |
| `expected_warnings.json` | Expected linter warnings |
| `expected_upcoming.json` | Expected upcoming query results |
| `expected_misc.json` | Expected misc query results |
| `scheme.md` (optional) | Scheme file for the test |
| `expected_scheme.json` (optional) | Expected parsed scheme |

To add a new test case:

1. Create a new directory in `/testdata/` (e.g., `13-my-test/`)
2. Add `input.md` with the test input
3. Add expected output files
4. Run tests in both JS and Python to verify

## License

MIT
