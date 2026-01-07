"""
Todoosy Types
"""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class ItemMetadata:
    due: Optional[str] = None
    priority: Optional[int] = None
    estimate_minutes: Optional[int] = None
    progress: Optional[str] = None


@dataclass
class ItemNode:
    id: str
    type: str  # 'heading' | 'list'
    raw_line: str
    title_text: str
    metadata: ItemMetadata
    comments: list[str] = field(default_factory=list)
    children: list[str] = field(default_factory=list)
    item_span: tuple[int, int] = (0, 0)
    subtree_span: tuple[int, int] = (0, 0)
    line: int = 1
    column: int = 1
    level: Optional[int] = None  # Only for headings


@dataclass
class AST:
    items: list[ItemNode] = field(default_factory=list)
    root_ids: list[str] = field(default_factory=list)


@dataclass
class Warning:
    code: str
    message: str
    line: Optional[int] = None
    column: Optional[int] = None
    span: Optional[tuple[int, int]] = None


@dataclass
class UpcomingItem:
    id: str
    due: str
    priority: Optional[int]
    path: str
    item_span: tuple[int, int]
    priority_label: Optional[str] = None


@dataclass
class MiscItem:
    id: str
    title_text: str
    item_span: tuple[int, int]


@dataclass
class Scheme:
    timezone: Optional[str] = None
    priorities: dict[str, str] = field(default_factory=dict)
    misc: str = "todoosy.md/Misc"  # format: "filename/headingname"
    calendar_format: str = "yyyy-mm-dd"  # Valid: yyyy-mm-dd, yyyy/mm/dd, mm/dd/yyyy, dd/mm/yyyy


@dataclass
class ParsedToken:
    type: str  # 'due' | 'priority' | 'estimate'
    value: str | int
    raw: str
    start: int
    end: int


@dataclass
class ParenGroup:
    start: int
    end: int
    content: str
    tokens: list[ParsedToken] = field(default_factory=list)
    has_recognized_tokens: bool = False
