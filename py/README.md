# Todoosy Python Library

Python implementation of the Todoosy format parser, formatter, linter, and query engine.

## Installation

```bash
pip install -e .
```

For development:
```bash
pip install -e ".[dev]"
```

## Usage

```python
from todoosy import parse, format, lint, query_upcoming, query_misc, parse_scheme

# Parse a document
result = parse('''
# Work

- Task (due 2026-01-15 p1 2h)

# Misc
''')

# Access the AST
for item in result.ast.items:
    print(f"{item.title_text}: due={item.metadata.due}")

# Format a document
formatted = format(input_text)

# Lint a document
warnings = lint(input_text)
for w in warnings.warnings:
    print(f"{w.code}: {w.message}")

# Query upcoming items
scheme = parse_scheme(scheme_text)
upcoming = query_upcoming(input_text, scheme)
for item in upcoming.items:
    print(f"{item.path}: {item.due}")

# Query misc items
misc = query_misc(input_text)
for item in misc.items:
    print(item.title_text)
```

## Running Tests

```bash
pytest
```
