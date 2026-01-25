"""
Todoosy Sequence Utilities

Functions for working with sequenced (numbered) task lists.
"""

from dataclasses import dataclass, field
from typing import Optional
from copy import deepcopy

from .types import AST, ItemNode


@dataclass
class SequenceGap:
    position: int
    expected: int
    actual: int


@dataclass
class SequenceDuplicate:
    number: int
    ids: list[str]


@dataclass
class SequenceInfo:
    parent_id: str
    has_sequence: bool
    numbered_children: list[tuple[str, int]]  # (id, sequence_number)
    gaps: list[SequenceGap]
    duplicates: list[SequenceDuplicate]


def analyze_sequence(ast: AST, parent_id: str) -> SequenceInfo:
    """
    Analyze the sequence of numbered children under a parent item.
    Returns information about gaps and duplicates in the sequence.
    """
    item_map = {item.id: item for item in ast.items}

    parent = item_map.get(parent_id)
    if not parent:
        return SequenceInfo(
            parent_id=parent_id,
            has_sequence=False,
            numbered_children=[],
            gaps=[],
            duplicates=[],
        )

    # Collect numbered children
    numbered_children: list[tuple[str, int]] = []
    for child_id in parent.children:
        child = item_map.get(child_id)
        if child and child.marker_type == 'numbered' and child.sequence_number is not None:
            numbered_children.append((child_id, child.sequence_number))

    if not numbered_children:
        return SequenceInfo(
            parent_id=parent_id,
            has_sequence=False,
            numbered_children=[],
            gaps=[],
            duplicates=[],
        )

    # Find gaps - numbers should be consecutive starting from 1
    gaps: list[SequenceGap] = []
    for i, (child_id, seq_num) in enumerate(numbered_children):
        expected = i + 1
        if seq_num != expected:
            gaps.append(SequenceGap(position=i, expected=expected, actual=seq_num))

    # Find duplicates
    number_counts: dict[int, list[str]] = {}
    for child_id, seq_num in numbered_children:
        if seq_num not in number_counts:
            number_counts[seq_num] = []
        number_counts[seq_num].append(child_id)

    duplicates: list[SequenceDuplicate] = []
    for num, ids in number_counts.items():
        if len(ids) > 1:
            duplicates.append(SequenceDuplicate(number=num, ids=ids))

    return SequenceInfo(
        parent_id=parent_id,
        has_sequence=True,
        numbered_children=numbered_children,
        gaps=gaps,
        duplicates=duplicates,
    )


def renumber_children(ast: AST, parent_id: str) -> AST:
    """
    Renumber children of a parent to have consecutive sequence numbers starting from 1.
    Returns a new AST with the renumbered items.
    """
    new_ast = deepcopy(ast)
    item_map = {item.id: item for item in new_ast.items}

    parent = item_map.get(parent_id)
    if not parent:
        return new_ast

    # Renumber numbered children
    next_num = 1
    for child_id in parent.children:
        child = item_map.get(child_id)
        if child and child.marker_type == 'numbered':
            child.sequence_number = next_num
            next_num += 1

    return new_ast


def insert_sequenced_item(
    ast: AST,
    parent_id: str,
    position: int,
    new_item: ItemNode
) -> AST:
    """
    Insert a new item into a sequenced list at a specific position and renumber.
    Position is 0-indexed. Returns a new AST with the inserted and renumbered items.
    """
    new_ast = deepcopy(ast)
    item_map = {item.id: item for item in new_ast.items}

    parent = item_map.get(parent_id)
    if not parent:
        return new_ast

    # Generate new ID
    max_id = max(int(item.id) for item in new_ast.items)
    new_id = str(max_id + 1)

    # Create new item with new ID
    item = deepcopy(new_item)
    item.id = new_id
    item.sequence_number = position + 1

    # Insert into parent's children
    new_children = list(parent.children)
    new_children.insert(position, new_id)
    parent.children = new_children

    # Add to items
    new_ast.items.append(item)
    item_map[new_id] = item

    # Renumber all numbered children
    next_num = 1
    for child_id in parent.children:
        child = item_map.get(child_id)
        if child and child.marker_type == 'numbered':
            child.sequence_number = next_num
            next_num += 1

    return new_ast


def remove_sequenced_item(ast: AST, item_id: str) -> AST:
    """
    Remove an item from a sequenced list and renumber siblings.
    Returns a new AST with the item removed and siblings renumbered.
    """
    new_ast = deepcopy(ast)
    new_ast.items = [item for item in new_ast.items if item.id != item_id]
    item_map = {item.id: item for item in new_ast.items}

    # Find and update parent
    for item in new_ast.items:
        if item_id in item.children:
            item.children = [c for c in item.children if c != item_id]

            # Renumber numbered children
            next_num = 1
            for child_id in item.children:
                child = item_map.get(child_id)
                if child and child.marker_type == 'numbered':
                    child.sequence_number = next_num
                    next_num += 1
            break

    # Update root_ids if necessary
    new_ast.root_ids = [id for id in new_ast.root_ids if id != item_id]

    return new_ast


def convert_to_sequence(ast: AST, parent_id: str) -> AST:
    """
    Convert bullet children of a parent to numbered items.
    Returns a new AST with bullet items converted to numbered.
    """
    new_ast = deepcopy(ast)
    item_map = {item.id: item for item in new_ast.items}

    parent = item_map.get(parent_id)
    if not parent:
        return new_ast

    # Convert bullet children to numbered
    next_num = 1
    for child_id in parent.children:
        child = item_map.get(child_id)
        if child and child.type == 'list':
            child.marker_type = 'numbered'
            child.sequence_number = next_num
            next_num += 1

    return new_ast


def convert_to_bullets(ast: AST, parent_id: str) -> AST:
    """
    Convert numbered children of a parent to bullet items.
    Returns a new AST with numbered items converted to bullets.
    """
    new_ast = deepcopy(ast)
    item_map = {item.id: item for item in new_ast.items}

    parent = item_map.get(parent_id)
    if not parent:
        return new_ast

    # Convert numbered children to bullets
    for child_id in parent.children:
        child = item_map.get(child_id)
        if child and child.marker_type == 'numbered':
            child.marker_type = 'bullet'
            child.sequence_number = None

    return new_ast
