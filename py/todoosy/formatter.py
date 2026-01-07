"""
Todoosy Formatter
"""

from .parser import parse
from .types import ItemNode, ItemMetadata


def format_metadata(metadata: ItemMetadata) -> str:
    """Format metadata as a canonical string."""
    parts: list[str] = []

    if metadata.due:
        parts.append(f"due {metadata.due}")

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

    return f"({' '.join(parts)})" if parts else ''


def format_item_line(item: ItemNode, indent: int = 0) -> str:
    """Format a single item line."""
    indent_str = '  ' * indent
    meta_str = format_metadata(item.metadata)
    title_with_meta = f"{item.title_text} {meta_str}" if meta_str else item.title_text

    if item.type == 'heading':
        hashes = '#' * (item.level or 1)
        return f"{hashes} {title_with_meta}"

    return f"{indent_str}- {title_with_meta}"


def format_comments(comments: list[str], is_list_item: bool, indent: int) -> list[str]:
    """Format comments with proper indentation."""
    if not comments:
        return []

    if is_list_item:
        indent_str = '  ' * (indent + 1)
        return [f"{indent_str}{c}" for c in comments]

    return list(comments)


def format(text: str) -> str:
    """Format a todoosy document."""
    result = parse(text)
    ast = result.ast
    lines: list[str] = []
    item_map = {item.id: item for item in ast.items}

    # Track Misc section
    misc_section_id = None
    for item in ast.items:
        if item.type == 'heading' and item.title_text == 'Misc' and item.level == 1:
            misc_section_id = item.id
            break

    def format_item(item_id: str, list_indent: int = 0, is_under_misc: bool = False) -> None:
        item = item_map[item_id]

        # Skip Misc section during normal iteration
        if item.id == misc_section_id and not is_under_misc:
            return

        # Add blank line before headings (except at start)
        if item.type == 'heading' and lines and lines[-1] != '':
            lines.append('')

        lines.append(format_item_line(item, list_indent))

        # Add blank line after heading before comments or children
        if item.type == 'heading':
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
            lines.append('')

        # Format children
        for child_id in item.children:
            child = item_map[child_id]
            if child.type == 'list':
                next_indent = 0 if item.type == 'heading' else list_indent + 1
                format_item(child_id, next_indent, is_under_misc)
            else:
                format_item(child_id, 0, is_under_misc)

    # Format all root items except Misc
    for root_id in ast.root_ids:
        if root_id != misc_section_id:
            format_item(root_id, 0, False)

    # Add Misc section at the end
    if lines and lines[-1] != '':
        lines.append('')
    lines.append('# Misc')

    # Add Misc items if they exist
    if misc_section_id:
        misc_item = item_map[misc_section_id]
        if misc_item.comments:
            lines.append('')
            lines.extend(misc_item.comments)
        if misc_item.children:
            lines.append('')
            for child_id in misc_item.children:
                child = item_map[child_id]
                lines.append(format_item_line(child, 0))
                formatted_comments = format_comments(
                    child.comments,
                    child.type == 'list',
                    0
                )
                lines.extend(formatted_comments)

    return '\n'.join(lines) + '\n'
