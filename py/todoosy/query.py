"""
Todoosy Query Engine
"""

from dataclasses import dataclass, field
from typing import Optional

from .parser import parse
from .types import AST, ItemNode, UpcomingItem, MiscItem, Scheme


@dataclass
class UpcomingResult:
    items: list[UpcomingItem] = field(default_factory=list)


@dataclass
class MiscResult:
    items: list[MiscItem] = field(default_factory=list)


def build_path(item_id: str, ast: AST) -> str:
    """Build the path to an item."""
    item_map = {item.id: item for item in ast.items}
    parent_map: dict[str, str] = {}

    for item in ast.items:
        for child_id in item.children:
            parent_map[child_id] = item.id

    parts: list[str] = []
    current_id: Optional[str] = item_id

    while current_id is not None:
        item = item_map.get(current_id)
        if item:
            parts.insert(0, item.title_text)
        current_id = parent_map.get(current_id)

    return ' > '.join(parts)


def query_upcoming(text: str, scheme: Optional[Scheme] = None) -> UpcomingResult:
    """Get all items with due dates, sorted by date and priority."""
    result = parse(text)
    ast = result.ast
    items: list[UpcomingItem] = []

    for item in ast.items:
        if item.metadata.due:
            upcoming_item = UpcomingItem(
                id=item.id,
                due=item.metadata.due,
                priority=item.metadata.priority,
                path=build_path(item.id, ast),
                item_span=item.item_span,
            )

            # Add priority label if scheme is provided
            if scheme and item.metadata.priority is not None:
                label = scheme.priorities.get(str(item.metadata.priority))
                if label:
                    upcoming_item.priority_label = label

            items.append(upcoming_item)

    # Sort by:
    # 1. Due date ascending
    # 2. Priority ascending (lower is higher priority, None treated as infinity)
    # 3. Document order
    def sort_key(item: UpcomingItem) -> tuple:
        priority = item.priority if item.priority is not None else float('inf')
        return (item.due, priority, item.item_span[0])

    items.sort(key=sort_key)

    return UpcomingResult(items=items)


def query_misc(text: str) -> MiscResult:
    """Get all items under the Misc section."""
    result = parse(text)
    ast = result.ast
    items: list[MiscItem] = []

    # Find the Misc section
    misc_section_id = None
    for item in ast.items:
        if item.type == 'heading' and item.title_text == 'Misc' and item.level == 1:
            misc_section_id = item.id
            break

    if misc_section_id is None:
        return MiscResult(items=items)

    # Get all direct children of the Misc section
    item_map = {item.id: item for item in ast.items}
    misc_section = item_map.get(misc_section_id)

    if not misc_section:
        return MiscResult(items=items)

    for child_id in misc_section.children:
        child = item_map.get(child_id)
        if child:
            items.append(MiscItem(
                id=child.id,
                title_text=child.title_text,
                item_span=child.item_span,
            ))

    return MiscResult(items=items)
