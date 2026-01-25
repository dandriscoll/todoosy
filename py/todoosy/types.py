"""
Todoosy Types
"""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class ItemMetadata:
    due: Optional[str] = None
    due_soft: Optional[bool] = None
    priority: Optional[int] = None
    estimate_minutes: Optional[int] = None
    progress: Optional[str] = None
    hashtags: list[str] = field(default_factory=list)           # Direct hashtags (without # prefix, lowercase)
    effective_hashtags: list[str] = field(default_factory=list) # All hashtags including inherited from ancestors


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
    marker_type: Optional[str] = None  # 'bullet' | 'numbered' - only for list items
    sequence_number: Optional[int] = None  # Original number for numbered items


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
    formatting_style: str = "roomy"  # Valid: roomy, balanced, tight


# SettingValue can be: str, list[str], or dict[str, str]
SettingValue = str | list[str] | dict[str, str]


@dataclass
class Settings:
    """Extended settings interface that supports both known and custom settings."""

    # Known settings with typed values
    timezone: Optional[str] = None
    priorities: dict[str, str] = field(default_factory=dict)
    misc: str = "todoosy.md/Misc"
    calendar_format: str = "yyyy-mm-dd"
    formatting_style: str = "roomy"

    # Extended settings for custom user-defined settings
    extended: dict[str, SettingValue] = field(default_factory=dict)


@dataclass
class ParsedToken:
    type: str  # 'due' | 'priority' | 'estimate' | 'progress' | 'hashtag'
    value: str | int
    raw: str
    start: int
    end: int
    soft: Optional[bool] = None  # Only for 'due' tokens - indicates a soft/flexible date


@dataclass
class ParenGroup:
    start: int
    end: int
    content: str
    tokens: list[ParsedToken] = field(default_factory=list)
    has_recognized_tokens: bool = False
