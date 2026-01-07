"""
Todoosy Parser
"""

import re
from dataclasses import dataclass, field
from typing import Optional

from .types import AST, ItemNode, ItemMetadata, ParsedToken, ParenGroup, Warning

HEADING_REGEX = re.compile(r'^(#{1,6})\s+(.*)$')
LIST_ITEM_REGEX = re.compile(r'^(\s*)([-*]|\d+\.)\s+(.*)$')
PRIORITY_REGEX = re.compile(r'^p(\d+)$', re.IGNORECASE)
ESTIMATE_REGEX = re.compile(r'^(\d+)([mhd])$', re.IGNORECASE)


@dataclass
class ParseResult:
    ast: AST
    warnings: list[Warning] = field(default_factory=list)


def parse_date(date_str: str) -> tuple[Optional[str], bool]:
    """Parse a date string and return (normalized_date, is_valid)."""
    # ISO format: YYYY-MM-DD
    iso_match = re.match(r'^(\d{4})-(\d{2})-(\d{2})$', date_str)
    if iso_match:
        return date_str, True

    # US format: MM/DD/YYYY
    us_match = re.match(r'^(\d{1,2})/(\d{1,2})/(\d{4})$', date_str)
    if us_match:
        month = us_match.group(1).zfill(2)
        day = us_match.group(2).zfill(2)
        year = us_match.group(3)
        return f"{year}-{month}-{day}", True

    # US short format: MM/DD/YY
    us_short_match = re.match(r'^(\d{1,2})/(\d{1,2})/(\d{2})$', date_str)
    if us_short_match:
        month = us_short_match.group(1).zfill(2)
        day = us_short_match.group(2).zfill(2)
        year = f"20{us_short_match.group(3)}"
        return f"{year}-{month}-{day}", True

    return None, False


def parse_tokens_in_paren_group(content: str, group_start: int) -> ParenGroup:
    """Parse tokens within a parentheses group."""
    tokens: list[ParsedToken] = []
    parts = re.split(r'[,\s]+', content)
    parts = [p for p in parts if p]

    current_pos = 0
    for i, part in enumerate(parts):
        part_start = content.find(part, current_pos)
        absolute_start = group_start + 1 + part_start  # +1 for opening paren
        absolute_end = absolute_start + len(part)
        current_pos = part_start + len(part)

        # Check for 'due' keyword
        if part.lower() == 'due':
            continue

        # Check if previous part was 'due'
        if i > 0 and parts[i - 1].lower() == 'due':
            date, valid = parse_date(part)
            if valid and date:
                tokens.append(ParsedToken(
                    type='due',
                    value=date,
                    raw=f"due {part}",
                    start=absolute_start - 4,  # Include 'due '
                    end=absolute_end,
                ))
            continue

        # Check for priority
        priority_match = PRIORITY_REGEX.match(part)
        if priority_match:
            tokens.append(ParsedToken(
                type='priority',
                value=int(priority_match.group(1)),
                raw=part,
                start=absolute_start,
                end=absolute_end,
            ))
            continue

        # Check for estimate
        estimate_match = ESTIMATE_REGEX.match(part)
        if estimate_match:
            num = int(estimate_match.group(1))
            unit = estimate_match.group(2).lower()
            if unit == 'm':
                minutes = num
            elif unit == 'h':
                minutes = num * 60
            elif unit == 'd':
                minutes = num * 480
            else:
                minutes = num

            tokens.append(ParsedToken(
                type='estimate',
                value=minutes,
                raw=part,
                start=absolute_start,
                end=absolute_end,
            ))
            continue

    return ParenGroup(
        start=group_start,
        end=group_start + len(content) + 2,  # +2 for parens
        content=content,
        tokens=tokens,
        has_recognized_tokens=len(tokens) > 0,
    )


def extract_paren_groups(line: str, line_start: int) -> list[ParenGroup]:
    """Extract all parentheses groups from a line."""
    groups: list[ParenGroup] = []
    i = 0

    while i < len(line):
        if line[i] == '(':
            start = i
            depth = 1
            i += 1
            while i < len(line) and depth > 0:
                if line[i] == '(':
                    depth += 1
                elif line[i] == ')':
                    depth -= 1
                i += 1
            if depth == 0:
                content = line[start + 1:i - 1]
                group = parse_tokens_in_paren_group(content, start)
                group.start = start  # Store relative position
                group.end = i        # Store relative position
                groups.append(group)
        else:
            i += 1

    return groups


def build_title_text(raw_text: str, groups: list[ParenGroup]) -> str:
    """Build title text by removing recognized metadata groups."""
    sorted_groups = sorted(
        [g for g in groups if g.has_recognized_tokens],
        key=lambda g: g.start,
        reverse=True
    )

    result = raw_text
    for group in sorted_groups:
        result = result[:group.start] + result[group.end:]

    # Clean up extra whitespace
    return ' '.join(result.split()).strip()


def build_metadata(groups: list[ParenGroup]) -> ItemMetadata:
    """Build metadata from all paren groups."""
    metadata = ItemMetadata()

    # Collect all tokens from all groups
    all_tokens = [token for group in groups for token in group.tokens]

    # Last occurrence wins
    for token in all_tokens:
        if token.type == 'due':
            metadata.due = str(token.value)
        elif token.type == 'priority':
            metadata.priority = int(token.value)
        elif token.type == 'estimate':
            metadata.estimate_minutes = int(token.value)

    return metadata


def parse(text: str) -> ParseResult:
    """Parse a todoosy document."""
    lines = text.split('\n')
    items: list[ItemNode] = []
    warnings: list[Warning] = []
    next_id = 0
    offset = 0

    # Stack to track current context
    list_stack: list[tuple[str, int]] = []  # (id, indent)
    current_heading_id: Optional[str] = None
    root_ids: list[str] = []

    # Map id -> children
    children_map: dict[str, list[str]] = {}

    # First pass: identify all items
    for line_num, line in enumerate(lines):
        line_start = offset
        line_end = offset + len(line)

        # Check for heading
        heading_match = HEADING_REGEX.match(line)
        if heading_match:
            level = len(heading_match.group(1))
            content = heading_match.group(2)

            # Close any open list context
            list_stack.clear()

            groups = extract_paren_groups(content, line_start + level + 1)
            title_text = build_title_text(content, groups)
            metadata = build_metadata(groups)

            item_id = str(next_id)
            next_id += 1

            item = ItemNode(
                id=item_id,
                type='heading',
                level=level,
                raw_line=line,
                title_text=title_text,
                metadata=metadata,
                comments=[],
                children=[],
                item_span=(line_start, line_end),
                subtree_span=(line_start, line_end),
                line=line_num + 1,
                column=1,
            )

            items.append(item)
            children_map[item_id] = []
            root_ids.append(item_id)
            current_heading_id = item_id

            offset = line_end + 1
            continue

        # Check for list item
        list_match = LIST_ITEM_REGEX.match(line)
        if list_match:
            indent = len(list_match.group(1))
            marker = list_match.group(2)
            content = list_match.group(3)

            content_start = line_start + indent + len(marker) + 1
            groups = extract_paren_groups(content, content_start)
            title_text = build_title_text(content, groups)
            metadata = build_metadata(groups)

            item_id = str(next_id)
            next_id += 1

            item = ItemNode(
                id=item_id,
                type='list',
                raw_line=line,
                title_text=title_text,
                metadata=metadata,
                comments=[],
                children=[],
                item_span=(line_start, line_end),
                subtree_span=(line_start, line_end),
                line=line_num + 1,
                column=1,
            )

            items.append(item)
            children_map[item_id] = []

            # Determine parent
            while list_stack and list_stack[-1][1] >= indent:
                list_stack.pop()

            if list_stack:
                parent_id = list_stack[-1][0]
                children_map[parent_id].append(item_id)
            elif current_heading_id is not None:
                children_map[current_heading_id].append(item_id)
            else:
                root_ids.append(item_id)

            list_stack.append((item_id, indent))

            offset = line_end + 1
            continue

        # Not a heading or list item
        offset = line_end + 1

    # Second pass: collect comments
    offset = 0
    current_item_index = -1
    has_started_comments = False
    blank_after_comment_start = False

    for line_num, line in enumerate(lines):
        line_start = offset
        line_end = offset + len(line)

        # Check if this line starts a new item
        heading_match = HEADING_REGEX.match(line)
        list_match = LIST_ITEM_REGEX.match(line)

        if heading_match or list_match:
            current_item_index = next(
                (i for i, item in enumerate(items) if item.item_span[0] == line_start),
                -1
            )
            has_started_comments = False
            blank_after_comment_start = False
            offset = line_end + 1
            continue

        # Check for blank line
        if not line.strip():
            if has_started_comments:
                blank_after_comment_start = True
            offset = line_end + 1
            continue

        # Non-blank, non-item line - potential comment
        if current_item_index >= 0 and not blank_after_comment_start:
            current_item = items[current_item_index]
            current_item.comments.append(line.strip())
            current_item.item_span = (current_item.item_span[0], line_end)
            has_started_comments = True

        offset = line_end + 1

    # Build children arrays
    for item in items:
        item.children = children_map.get(item.id, [])

    # Compute subtree spans
    def compute_subtree_span(item_id: str) -> tuple[int, int]:
        item = next(i for i in items if i.id == item_id)
        end = item.item_span[1]

        for child_id in item.children:
            child_span = compute_subtree_span(child_id)
            end = max(end, child_span[1])

        item.subtree_span = (item.item_span[0], end)
        return item.subtree_span

    for root_id in root_ids:
        compute_subtree_span(root_id)

    # Update root_ids to only include top-level items
    actual_root_ids = [
        item.id for item in items
        if not any(item.id in other.children for other in items)
    ]

    return ParseResult(
        ast=AST(items=items, root_ids=actual_root_ids),
        warnings=warnings,
    )
