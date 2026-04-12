import re

_CHOICES_RE = re.compile(r"\[CHOICES\](.*?)\[/CHOICES\]", re.DOTALL)


def extract_choices(reply: str) -> tuple[str, list[str] | None]:
    """Extract [CHOICES]...[/CHOICES] from an LLM reply.

    Returns (clean_reply, choices). If no choices block is found, returns
    the original reply and None.
    """
    match = _CHOICES_RE.search(reply)
    if not match:
        return reply, None
    raw = match.group(1).strip()
    choices = [c.strip() for c in raw.split("|") if c.strip()]
    clean = (reply[: match.start()].rstrip() + reply[match.end() :]).strip()
    return clean, choices if choices else None
