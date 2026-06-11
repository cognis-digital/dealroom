"""dealroom — M&A / VC due-diligence assistant. Part of the Cognis Neural Suite."""

from dealroom.core import (
    TOOL_NAME,
    TOOL_VERSION,
    DEAL_TYPES,
    SEVERITY_ORDER,
    ChecklistItem,
    DataroomError,
    FileEntry,
    Risk,
    ScanResult,
    build_checklist,
    checklist_to_dict,
    scan_dataroom,
    to_html,
)

__version__ = TOOL_VERSION

__all__ = [
    "TOOL_NAME",
    "TOOL_VERSION",
    "__version__",
    "DEAL_TYPES",
    "SEVERITY_ORDER",
    "ChecklistItem",
    "DataroomError",
    "FileEntry",
    "Risk",
    "ScanResult",
    "build_checklist",
    "checklist_to_dict",
    "scan_dataroom",
    "to_html",
]
