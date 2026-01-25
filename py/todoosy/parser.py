"""
Todoosy Parser
"""

import re
from dataclasses import dataclass, field
from typing import Optional

from .types import AST, ItemNode, ItemMetadata, ParsedToken, ParenGroup, Warning

from datetime import date
from dateutil.relativedelta import relativedelta

HEADING_REGEX = re.compile(r'^(#{1,6})\s+(.*)$')
LIST_ITEM_REGEX = re.compile(r'^(\s*)([-*]|\d+\.)\s+(.*)$')
PRIORITY_REGEX = re.compile(r'^p(\d+)$', re.IGNORECASE)
ESTIMATE_REGEX = re.compile(r'^(\d+)([mhd])$', re.IGNORECASE)
HASHTAG_REGEX = re.compile(r'^#([a-zA-Z][a-zA-Z0-9_-]*)$')

MONTH_NAMES: dict[str, int] = {
    'january': 1, 'jan': 1,
    'february': 2, 'feb': 2,
    'march': 3, 'mar': 3,
    'april': 4, 'apr': 4,
    'may': 5,
    'june': 6, 'jun': 6,
    'july': 7, 'jul': 7,
    'august': 8, 'aug': 8,
    'september': 9, 'sep': 9,
    'october': 10, 'oct': 10,
    'november': 11, 'nov': 11,
    'december': 12, 'dec': 12,
}

# Built-in progress states (normalized to lowercase)
PROGRESS_STATES = {'done', 'deleted', 'in progress', 'blocked'}


@dataclass
class ParseResult:
    ast: AST
    warnings: list[Warning] = field(default_factory=list)


def infer_year(month: int, day: int) -> int:
    """Infer the year for a date without a year. If the date is more than 3 months in the past, use next year."""
    today = date.today()
    current_year = today.year

    # Create the candidate date in the current year
    try:
        candidate_date = date(current_year, month, day)
    except ValueError:
        # Invalid date (e.g., Feb 30), just use current year
        return current_year

    # Calculate three months ago
    three_months_ago = today - relativedelta(months=3)

    # If the candidate date is more than 3 months in the past, use next year
    if candidate_date < three_months_ago:
        return current_year + 1

    return current_year


def parse_date(date_str: str) -> tuple[Optional[str], bool]:
    """Parse a date string and return (normalized_date, is_valid)."""
    # ISO format with dashes: YYYY-MM-DD or YYYY-M-D
    iso_match = re.match(r'^(\d{4})-(\d{1,2})-(\d{1,2})$', date_str)
    if iso_match:
        year = iso_match.group(1)
        month = iso_match.group(2).zfill(2)
        day = iso_match.group(3).zfill(2)
        return f"{year}-{month}-{day}", True

    # Short ISO format with dashes: YY-M-D or YY-MM-DD
    iso_short_match = re.match(r'^(\d{2})-(\d{1,2})-(\d{1,2})$', date_str)
    if iso_short_match:
        year = f"20{iso_short_match.group(1)}"
        month = iso_short_match.group(2).zfill(2)
        day = iso_short_match.group(3).zfill(2)
        return f"{year}-{month}-{day}", True

    # Year-first with slashes: YYYY/MM/DD
    ymd_slash_match = re.match(r'^(\d{4})/(\d{1,2})/(\d{1,2})$', date_str)
    if ymd_slash_match:
        year = ymd_slash_match.group(1)
        month = ymd_slash_match.group(2).zfill(2)
        day = ymd_slash_match.group(3).zfill(2)
        return f"{year}-{month}-{day}", True

    # Slash format: X/X/X where components are 1-2 digits each
    # Use heuristics to determine format
    slash_match = re.match(r'^(\d{1,2})/(\d{1,2})/(\d{1,2})$', date_str)
    if slash_match:
        first = int(slash_match.group(1))
        second = int(slash_match.group(2))
        third = int(slash_match.group(3))

        # Heuristics to determine format:
        # - If third > 31, it's a year -> XX/XX/YY
        # - If first > 31, it's a year -> YY/XX/XX (unusual but accept it)
        # - If first > 12 and third <= 31, first is day -> DD/MM/YY
        # - Otherwise, assume MM/DD/YY (US convention)

        if third > 31:
            # Third is year (e.g., 26/01/15 where 15 > 31? No, but 01/15/50)
            # Actually third > 31 means it can't be a day, so it must be year
            year = f"20{slash_match.group(3).zfill(2)}"
            if first > 12:  # DD/MM/YY
                day = str(first).zfill(2)
                month = str(second).zfill(2)
            else:  # MM/DD/YY
                month = str(first).zfill(2)
                day = str(second).zfill(2)
        elif first > 31:
            # First must be year (unusual format YY/MM/DD)
            year = f"20{slash_match.group(1).zfill(2)}"
            month = str(second).zfill(2)
            day = str(third).zfill(2)
        elif first > 12:
            # First > 12 but <= 31, so it's a day -> DD/MM/YY
            day = str(first).zfill(2)
            month = str(second).zfill(2)
            year = f"20{slash_match.group(3).zfill(2)}"
        else:
            # Default: MM/DD/YY (US convention)
            month = str(first).zfill(2)
            day = str(second).zfill(2)
            year = f"20{slash_match.group(3).zfill(2)}"
        return f"{year}-{month}-{day}", True

    # Slash format with 4-digit year at end: XX/XX/YYYY
    slash_4yr_match = re.match(r'^(\d{1,2})/(\d{1,2})/(\d{4})$', date_str)
    if slash_4yr_match:
        first = int(slash_4yr_match.group(1))
        second = int(slash_4yr_match.group(2))
        year = slash_4yr_match.group(3)
        if first > 12:  # Must be DD/MM/YYYY
            day = str(first).zfill(2)
            month = str(second).zfill(2)
        else:  # Treat as MM/DD/YYYY (US convention)
            month = str(first).zfill(2)
            day = str(second).zfill(2)
        return f"{year}-{month}-{day}", True

    return None, False


def parse_text_date(parts: list[str]) -> tuple[Optional[str], bool, int]:
    """Parse text date format (Month Day [Year] or Day Month [Year]). Returns (normalized_date, is_valid, parts_consumed)."""
    if len(parts) < 2:
        return None, False, 0

    # Try "Month Day [Year]" format first
    month_str = parts[0].lower()
    month = MONTH_NAMES.get(month_str)
    if month is not None:
        day_match = re.match(r'^(\d{1,2})$', parts[1])
        if day_match:
            day = int(day_match.group(1))
            if 1 <= day <= 31:
                # Check for year (4-digit or 2-digit)
                if len(parts) >= 3:
                    year_match = re.match(r'^(\d{4})$', parts[2])
                    if year_match:
                        year = int(year_match.group(1))
                        month_padded = str(month).zfill(2)
                        day_padded = str(day).zfill(2)
                        return f"{year}-{month_padded}-{day_padded}", True, 3
                    # Try 2-digit year
                    year_short_match = re.match(r'^(\d{2})$', parts[2])
                    if year_short_match:
                        year = 2000 + int(year_short_match.group(1))
                        month_padded = str(month).zfill(2)
                        day_padded = str(day).zfill(2)
                        return f"{year}-{month_padded}-{day_padded}", True, 3

                # No year provided, infer it
                year = infer_year(month, day)
                month_padded = str(month).zfill(2)
                day_padded = str(day).zfill(2)
                return f"{year}-{month_padded}-{day_padded}", True, 2

    # Try "Day Month [Year]" format
    day_match = re.match(r'^(\d{1,2})$', parts[0])
    if day_match:
        day = int(day_match.group(1))
        if 1 <= day <= 31:
            month_str = parts[1].lower()
            month = MONTH_NAMES.get(month_str)
            if month is not None:
                # Check for year (4-digit or 2-digit)
                if len(parts) >= 3:
                    year_match = re.match(r'^(\d{4})$', parts[2])
                    if year_match:
                        year = int(year_match.group(1))
                        month_padded = str(month).zfill(2)
                        day_padded = str(day).zfill(2)
                        return f"{year}-{month_padded}-{day_padded}", True, 3
                    # Try 2-digit year
                    year_short_match = re.match(r'^(\d{2})$', parts[2])
                    if year_short_match:
                        year = 2000 + int(year_short_match.group(1))
                        month_padded = str(month).zfill(2)
                        day_padded = str(day).zfill(2)
                        return f"{year}-{month_padded}-{day_padded}", True, 3

                # No year provided, infer it
                year = infer_year(month, day)
                month_padded = str(month).zfill(2)
                day_padded = str(day).zfill(2)
                return f"{year}-{month_padded}-{day_padded}", True, 2

    return None, False, 0


def parse_tokens_in_paren_group(content: str, group_start: int) -> ParenGroup:
    """Parse tokens within a parentheses group."""
    tokens: list[ParsedToken] = []
    parts = re.split(r'[,\s]+', content)
    parts = [p for p in parts if p]

    current_pos = 0
    skip_indices: set[int] = set()

    for i, part in enumerate(parts):
        if i in skip_indices:
            continue

        part_start = content.find(part, current_pos)
        absolute_start = group_start + 1 + part_start  # +1 for opening paren
        absolute_end = absolute_start + len(part)
        current_pos = part_start + len(part)

        # Check for 'due' keyword
        if part.lower() == 'due':
            remaining_parts = parts[i + 1:]
            if remaining_parts:
                # Check for soft date prefix (~)
                is_soft = False
                date_parts_to_check = remaining_parts
                if remaining_parts[0].startswith('~'):
                    is_soft = True
                    date_parts_to_check = [remaining_parts[0][1:]] + remaining_parts[1:]

                # First try standard date formats (single part)
                date_result, valid = parse_date(date_parts_to_check[0])
                if valid and date_result:
                    next_part_start = content.find(remaining_parts[0], current_pos)
                    next_absolute_end = group_start + 1 + next_part_start + len(remaining_parts[0])
                    tokens.append(ParsedToken(
                        type='due',
                        value=date_result,
                        raw=f"due {remaining_parts[0]}",
                        start=absolute_start,
                        end=next_absolute_end,
                        soft=is_soft if is_soft else None,
                    ))
                    skip_indices.add(i + 1)
                    continue

                # Try text date formats (multiple parts: Month Day [Year])
                text_date_result, text_valid, parts_consumed = parse_text_date(date_parts_to_check)
                if text_valid and text_date_result:
                    raw_parts = ['due']
                    end_pos = current_pos
                    for j in range(parts_consumed):
                        raw_parts.append(remaining_parts[j])
                        skip_indices.add(i + 1 + j)
                        end_pos = content.find(remaining_parts[j], end_pos) + len(remaining_parts[j])
                    final_absolute_end = group_start + 1 + end_pos
                    tokens.append(ParsedToken(
                        type='due',
                        value=text_date_result,
                        raw=' '.join(raw_parts),
                        start=absolute_start,
                        end=final_absolute_end,
                        soft=is_soft if is_soft else None,
                    ))
                    continue
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

        # Check for progress states
        part_lower = part.lower()

        # Check for single-word progress states: done, deleted, blocked
        if part_lower in PROGRESS_STATES:
            tokens.append(ParsedToken(
                type='progress',
                value=part_lower,
                raw=part,
                start=absolute_start,
                end=absolute_end,
            ))
            continue

        # Check for multi-word progress state: "in progress"
        if part_lower == 'in':
            remaining_parts = parts[i + 1:]
            if remaining_parts and remaining_parts[0].lower() == 'progress':
                next_part_start = content.find(remaining_parts[0], current_pos)
                next_absolute_end = group_start + 1 + next_part_start + len(remaining_parts[0])
                tokens.append(ParsedToken(
                    type='progress',
                    value='in progress',
                    raw=f'{part} {remaining_parts[0]}',
                    start=absolute_start,
                    end=next_absolute_end,
                ))
                skip_indices.add(i + 1)
                continue

        # Check for hashtags
        hashtag_match = HASHTAG_REGEX.match(part)
        if hashtag_match:
            tokens.append(ParsedToken(
                type='hashtag',
                value=hashtag_match.group(1).lower(),
                raw=part,
                start=absolute_start,
                end=absolute_end,
            ))
            continue

        # Check for soft date prefix (~) on standalone dates
        is_soft_standalone = False
        part_to_check = part
        if part.startswith('~'):
            is_soft_standalone = True
            part_to_check = part[1:]

        # Try standalone date formats (single part: ISO dates)
        date_result, valid = parse_date(part_to_check)
        if valid and date_result:
            tokens.append(ParsedToken(
                type='due',
                value=date_result,
                raw=part,
                start=absolute_start,
                end=absolute_end,
                soft=is_soft_standalone if is_soft_standalone else None,
            ))
            continue

        # Try standalone text date formats (multiple parts: Month Day [Year] or Day Month [Year])
        remaining_parts = [part] + parts[i + 1:]
        # For text dates, use stripped version if soft
        date_parts_for_text = [part_to_check] + parts[i + 1:] if is_soft_standalone else remaining_parts
        text_date_result, text_valid, parts_consumed = parse_text_date(date_parts_for_text)
        if text_valid and text_date_result:
            raw_parts = [part]
            end_pos = part_start + len(part)
            for j in range(1, parts_consumed):
                raw_parts.append(parts[i + j])
                skip_indices.add(i + j)
                end_pos = content.find(parts[i + j], end_pos) + len(parts[i + j])
            final_absolute_end = group_start + 1 + end_pos
            tokens.append(ParsedToken(
                type='due',
                value=text_date_result,
                raw=' '.join(raw_parts),
                start=absolute_start,
                end=final_absolute_end,
                soft=is_soft_standalone if is_soft_standalone else None,
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

    # Collect unique hashtags
    hashtag_set: set[str] = set()

    # Last occurrence wins for non-hashtag tokens
    for token in all_tokens:
        if token.type == 'due':
            metadata.due = str(token.value)
            metadata.due_soft = token.soft
        elif token.type == 'priority':
            metadata.priority = int(token.value)
        elif token.type == 'estimate':
            metadata.estimate_minutes = int(token.value)
        elif token.type == 'progress':
            metadata.progress = str(token.value)
        elif token.type == 'hashtag':
            hashtag_set.add(str(token.value))

    # Store sorted unique hashtags
    metadata.hashtags = sorted(hashtag_set)

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

            # Determine marker type and sequence number
            is_numbered = bool(re.match(r'^\d+\.$', marker))
            marker_type = 'numbered' if is_numbered else 'bullet'
            sequence_number = int(marker[:-1]) if is_numbered else None

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
                marker_type=marker_type,
                sequence_number=sequence_number,
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

    # Compute effective_hashtags through inheritance (pre-order traversal)
    item_map = {item.id: item for item in items}

    def compute_effective_hashtags(item_id: str, parent_effective_hashtags: list[str]) -> None:
        item = item_map[item_id]
        # Merge parent's effective_hashtags with own hashtags, deduplicate and sort
        combined = set(parent_effective_hashtags) | set(item.metadata.hashtags)
        item.metadata.effective_hashtags = sorted(combined)

        for child_id in item.children:
            compute_effective_hashtags(child_id, item.metadata.effective_hashtags)

    for root_id in actual_root_ids:
        compute_effective_hashtags(root_id, [])

    return ParseResult(
        ast=AST(items=items, root_ids=actual_root_ids),
        warnings=warnings,
    )
