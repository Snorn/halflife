"""Step 2's other half: turning a session into classifications, locally.

Delivery hands the harness a prompt and takes back an issue. Extraction hands
the harness a prompt and takes back verbs. Same seam, and here the seam is the
privacy boundary itself — see CLAUDE.md.
"""

from halflife.extraction.engine import (
    ExtractedSignal,
    ExtractionBrief,
    build_extraction_brief,
    record_signals,
)

__all__ = [
    "ExtractedSignal",
    "ExtractionBrief",
    "build_extraction_brief",
    "record_signals",
]
