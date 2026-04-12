# Quick-Reply Choice Buttons

**Date:** 2026-04-11
**Status:** Design approved, ready for implementation plan

## Goal

When Jain offers the user options, render them as tappable buttons below the assistant message instead of making the user type. Tapping a button sends its label as the next user message. Buttons disappear once the user interacts (taps a choice or sends a manual message).

## Architecture

The LLM produces choices as formatted text in its reply. The backend parses them out into a structured field. The mobile app renders them as buttons. No new endpoints, no plugin schema changes, no tool invocations — just text parsing and UI rendering.

This is LLM-agnostic: the system prompt (which JAIN controls) instructs whatever model is running to format choices in a specific pattern. Any LLM that can follow formatting instructions produces parseable choices. If a model fails to format correctly, the raw text shows as a normal reply — graceful degradation.

## Format

The LLM includes a choices block at the end of its reply:

```
I can help! How would you like to proceed?
[CHOICES]Fill out a form|Let AI help me step by step[/CHOICES]
```

- Delimiter: `|` (pipe) between options
- Tags: `[CHOICES]...[/CHOICES]` — unlikely to appear in natural text
- Position: always at the end of the reply (the system prompt instructs this)
- Max choices: not enforced, but the prompt suggests 2-4 options

## Backend changes

### 1. System prompt addition (`context_builder.py`)

Add to the system prompt built by `ContextBuilder`:

```
When you want to offer the user a choice between 2-4 options, include a
choices block at the END of your reply in exactly this format:
[CHOICES]Option one|Option two[/CHOICES]

Rules:
- Each option is a short phrase (under 40 characters) the user would
  naturally type themselves.
- Separate options with | (pipe character).
- Place the [CHOICES] block AFTER your conversational reply text.
- Only include choices when there's a genuine decision point — don't
  offer choices for simple yes/no or when there's only one sensible path.
- Do NOT include choices if the user has already told you what they want.
```

### 2. Chat service parsing (`chat_service.py`)

After receiving the LLM's reply text, extract and strip the choices block:

```python
import re

_CHOICES_RE = re.compile(r"\[CHOICES\](.*?)\[/CHOICES\]", re.DOTALL)

def _extract_choices(reply: str) -> tuple[str, list[str] | None]:
    """Strip [CHOICES]...[/CHOICES] from reply, return (clean_reply, choices)."""
    match = _CHOICES_RE.search(reply)
    if not match:
        return reply, None
    raw = match.group(1).strip()
    choices = [c.strip() for c in raw.split("|") if c.strip()]
    clean_reply = reply[:match.start()].rstrip() + reply[match.end():]
    return clean_reply.strip(), choices if choices else None
```

Call this in `send()` before building the `ChatReply`, and populate the new `choices` field.

### 3. Schema change (`schemas/chat.py`)

Add to `ChatResponse`:

```python
choices: list[str] | None = None
```

The mobile app reads this field from the JSON response.

## Mobile changes

### 4. Zustand store (`useAppStore`)

Add:

```typescript
activeChoices: string[] | null;
setActiveChoices: (choices: string[] | null) => void;
clearActiveChoices: () => void;
```

### 5. useChat hook

After receiving a response with `choices`, call `setActiveChoices(res.choices)`. Before sending any message (user-typed or choice-tapped), call `clearActiveChoices()`.

### 6. ChoiceButtons component

A new component rendered in `ChatScreen` above the text input when `activeChoices` is non-null:

- Horizontal `ScrollView` with styled `TouchableOpacity` buttons
- Each button shows the choice label
- `onPress` calls `send(label)` — the existing chat send function
- Buttons disappear immediately on tap (because `send` clears `activeChoices`)

Visual style: pill-shaped buttons with JAIN's blue accent (`#2563eb`) as border, white background, blue text. Horizontal scroll if more than 2-3 options overflow the screen width.

### 7. ChatScreen integration

Render `<ChoiceButtons />` between the message list and the text input, conditionally on `activeChoices !== null`.

## Graceful degradation

- If the LLM doesn't include `[CHOICES]...[/CHOICES]`, `choices` is `null` and no buttons render. The reply displays normally.
- If the LLM formats choices incorrectly (e.g., missing closing tag), the regex doesn't match, and the raw text shows as-is. No crash.
- If the LLM includes choices with only one option, it renders as a single button. Harmless.

## What we're NOT building

- Rich choice payloads (action IDs, tool names, icons, colors) — choices are plain strings
- Multi-select
- Plugin-declared choices
- Persistent choice history (buttons are ephemeral)
- Choice-specific styling per option
- Keyboard shortcut / number-key selection

## Example flows

**Yard sale creation:**
```
User: "I want to create a yard sale"
Jain: "I can help! How would you like to proceed?
       [CHOICES]Fill out a form|Let AI help me step by step[/CHOICES]"

→ reply: "I can help! How would you like to proceed?"
  choices: ["Fill out a form", "Let AI help me step by step"]

→ Mobile renders two buttons. User taps "Fill out a form".
→ send("Fill out a form") → buttons disappear → Jain calls show_sale_form
```

**General decision point:**
```
User: "Tell me about yard sales"
Jain: "I can help with yard sales! What are you looking for?
       [CHOICES]Find sales near me|Create a new sale|Browse all listings[/CHOICES]"

→ Three buttons render. User taps "Find sales near me".
→ send("Find sales near me") → Jain calls find_yard_sales
```

## Success criteria

1. When Jain offers options, tappable buttons appear above the text input
2. Tapping a button sends the label as a chat message and the buttons disappear
3. Typing a manual message also clears the buttons
4. The feature works on both web (Chrome) and native iOS (simulator)
5. If the LLM doesn't produce choices, the UI is unchanged — no regressions
6. Backend tests verify the `[CHOICES]` parsing (extract, strip, edge cases)
