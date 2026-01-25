"""
Todoosy Formatter
"""

from typing import Optional
from .parser import parse
from .types import ItemNode, ItemMetadata, Scheme


def parse_misc_location(misc: str) -> tuple[str, str]:
    """Parse misc location string into (filename, heading)."""
    slash_index = misc.find('/')
    if slash_index == -1:
        return (misc, 'Misc')
    return (misc[:slash_index], misc[slash_index + 1:])


def format_metadata(metadata: ItemMetadata) -> str:
    """Format metadata as a canonical string."""
    parts: list[str] = []

    if metadata.due:
        soft_prefix = '~' if metadata.due_soft else ''
        parts.append(f"due {soft_prefix}{metadata.due}")

    if metadata.progress:
        parts.append(metadata.progress)

    if metadata.priority is not None:
        parts.append(f"p{metadata.priority}")

    if metadata.estimate_minutes is not None:
        minutes = metadata.estimate_minutes
        if minutes % 480 == 0 and minutes >= 480:
            parts.append(f"{minutes // 480}d")
        elif minutes % 60 == 0 and minutes >= 60:
            parts.append(f"{minutes // 60}h")
        else:
            parts.append(f"{minutes}m")

    # Output direct hashtags (not effective_hashtags) at end
    for tag in metadata.hashtags:
        parts.append(f"#{tag}")

    return f"({' '.join(parts)})" if parts else ''


def format_item_line(item: ItemNode, indent: int = 0, sequence_num: Optional[int] = None) -> str:
    """Format a single item line."""
    indent_str = '  ' * indent
    meta_str = format_metadata(item.metadata)
    title_with_meta = f"{item.title_text} {meta_str}" if meta_str else item.title_text

    if item.type == 'heading':
        hashes = '#' * (item.level or 1)
        return f"{hashes} {title_with_meta}"

    # Use numbered marker if item is numbered
    if item.marker_type == 'numbered' and sequence_num is not None:
        return f"{indent_str}{sequence_num}. {title_with_meta}"

    return f"{indent_str}- {title_with_meta}"


def format_comments(comments: list[str], is_list_item: bool, indent: int) -> list[str]:
    """Format comments with proper indentation."""
    if not comments:
        return []

    if is_list_item:
        indent_str = '  ' * (indent + 1)
        return [f"{indent_str}{c}" for c in comments]

    return list(comments)


def format(text: str, scheme: Optional[Scheme] = None, filename: Optional[str] = None) -> str:
    """Format a todoosy document."""
    result = parse(text)
    ast = result.ast
    lines: list[str] = []
    item_map = {item.id: item for item in ast.items}

    # Determine misc location from scheme or use default
    misc_filename, misc_heading = parse_misc_location(scheme.misc if scheme else 'todoosy.md/Misc')
    # If no filename provided, assume it could be the misc file (backward compatibility)
    is_misc_file = filename is None or filename == misc_filename

    # Determine formatting style: roomy (default), balanced, or tight
    formatting_style = scheme.formatting_style if scheme else 'roomy'

    # Track Misc section
    misc_section_id = None
    for item in ast.items:
        if item.type == 'heading' and item.title_text == misc_heading and item.level == 1:
            misc_section_id = item.id
            break

    def should_add_blank_before(item: ItemNode) -> bool:
        """Determine if we should add blank line before a heading."""
        if item.type != 'heading':
            return False
        if formatting_style == 'tight':
            return False
        if formatting_style == 'balanced':
            return item.level == 1
        return True  # roomy

    def should_add_blank_after(item: ItemNode) -> bool:
        """Determine if we should add blank line after a heading."""
        if item.type != 'heading':
            return False
        if formatting_style == 'tight':
            return False
        if formatting_style == 'balanced':
            return item.level == 1
        return True  # roomy

    def format_item(item_id: str, list_indent: int = 0, is_under_misc: bool = False, sequence_num: Optional[int] = None) -> None:
        item = item_map[item_id]

        # Skip Misc section during normal iteration
        if item.id == misc_section_id and not is_under_misc:
            return

        # Add blank line before headings (except at start), based on style
        if should_add_blank_before(item) and lines and lines[-1] != '':
            lines.append('')

        lines.append(format_item_line(item, list_indent, sequence_num))

        # Add blank line after heading before comments or children, based on style
        if should_add_blank_after(item):
            lines.append('')

        # Add comments
        formatted_comments = format_comments(
            item.comments,
            item.type == 'list',
            list_indent
        )
        lines.extend(formatted_comments)

        # Add blank line after heading comments before children
        if item.type == 'heading' and item.comments and item.children:
            if should_add_blank_after(item):
                lines.append('')

        # Format children - renumber sequenced items
        child_sequence_num = 1
        for child_id in item.children:
            child = item_map[child_id]
            if child.type == 'list':
                next_indent = 0 if item.type == 'heading' else list_indent + 1
                # Pass sequence number for numbered items and increment
                child_seq = child_sequence_num if child.marker_type == 'numbered' else None
                if child.marker_type == 'numbered':
                    child_sequence_num += 1
                format_item(child_id, next_indent, is_under_misc, child_seq)
            else:
                format_item(child_id, 0, is_under_misc)

    # Format all root items except Misc
    for root_id in ast.root_ids:
        if root_id != misc_section_id:
            format_item(root_id, 0, False)

    # Add Misc section at the end (only for the misc file)
    if is_misc_file:
        # Add blank line before Misc heading based on style
        should_add_blank_before_misc = formatting_style != 'tight'
        if lines and lines[-1] != '' and should_add_blank_before_misc:
            lines.append('')
        lines.append(f'# {misc_heading}')

        # Add blank line after Misc heading based on style
        should_add_blank_after_misc = formatting_style != 'tight'

        # Add Misc items if they exist
        if misc_section_id:
            misc_item = item_map[misc_section_id]
            if misc_item.comments:
                if should_add_blank_after_misc:
                    lines.append('')
                lines.extend(misc_item.comments)
            if misc_item.children:
                if should_add_blank_after_misc:
                    lines.append('')
                misc_child_seq_num = 1
                for child_id in misc_item.children:
                    child = item_map[child_id]
                    child_seq = misc_child_seq_num if child.marker_type == 'numbered' else None
                    if child.marker_type == 'numbered':
                        misc_child_seq_num += 1
                    lines.append(format_item_line(child, 0, child_seq))
                    formatted_comments = format_comments(
                        child.comments,
                        child.type == 'list',
                        0
                    )
                    lines.extend(formatted_comments)

    return '\n'.join(lines) + '\n'
