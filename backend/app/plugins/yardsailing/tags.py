"""Curated tag vocabulary for yard sales.

Stored and compared lowercased. The display names preserve capitalization
for the UI. Users may add custom tags beyond this list — the model accepts
any string ≤ 64 chars, but the tag chips in the form default to these.
"""

CURATED_TAGS: list[str] = [
    "Furniture",
    "Toys",
    "Tools",
    "Baby Items",
    "Clothing",
    "Books",
    "Electronics",
    "Kitchen",
    "Sports",
    "Garden",
    "Holiday",
    "Art",
    "Free",
]


def normalize(tag: str) -> str:
    """Store as lowercase, trimmed, whitespace-collapsed."""
    return " ".join(tag.strip().lower().split())
