# Quick-Reply Choice Buttons Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** When Jain offers options, render tappable buttons above the chat input. Tapping sends the label as a message. Buttons disappear on interaction.

**Architecture:** LLM includes `[CHOICES]...[/CHOICES]` in reply text per system prompt instructions. Backend regex-extracts choices into a new `choices` field on `ChatResponse`. Mobile renders them as pill buttons via a new `ChoiceButtons` component.

**Tech Stack:** FastAPI, Pydantic, pytest (backend); React Native, TypeScript, Zustand (mobile).

---

### Task 1: Backend — choices extraction helper with tests

**Files:**
- Create: `backend/app/services/choices.py`
- Test: `backend/tests/test_choices.py`

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_choices.py`:

```python
from app.services.choices import extract_choices


def test_extract_choices_basic():
    reply = "How would you like to proceed?\n[CHOICES]Fill out a form|Let AI help[/CHOICES]"
    clean, choices = extract_choices(reply)
    assert clean == "How would you like to proceed?"
    assert choices == ["Fill out a form", "Let AI help"]


def test_extract_choices_three_options():
    reply = "What next?\n[CHOICES]A|B|C[/CHOICES]"
    clean, choices = extract_choices(reply)
    assert clean == "What next?"
    assert choices == ["A", "B", "C"]


def test_extract_choices_strips_whitespace():
    reply = "Pick one:\n[CHOICES] Option A | Option B [/CHOICES]"
    clean, choices = extract_choices(reply)
    assert choices == ["Option A", "Option B"]


def test_extract_choices_none_when_absent():
    reply = "Just a normal reply with no choices."
    clean, choices = extract_choices(reply)
    assert clean == "Just a normal reply with no choices."
    assert choices is None


def test_extract_choices_malformed_no_closing_tag():
    reply = "Broken [CHOICES]A|B but no end tag"
    clean, choices = extract_choices(reply)
    assert clean == reply
    assert choices is None


def test_extract_choices_empty_pipes_ignored():
    reply = "Pick:\n[CHOICES]A||B|[/CHOICES]"
    clean, choices = extract_choices(reply)
    assert choices == ["A", "B"]


def test_extract_choices_single_option():
    reply = "Only one:\n[CHOICES]Do it[/CHOICES]"
    clean, choices = extract_choices(reply)
    assert choices == ["Do it"]


def test_extract_choices_mid_text():
    reply = "Here are options [CHOICES]A|B[/CHOICES] and more text."
    clean, choices = extract_choices(reply)
    assert clean == "Here are options  and more text."
    assert choices == ["A", "B"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && pytest tests/test_choices.py -v`
Expected: FAIL with `ModuleNotFoundError: app.services.choices`.

- [ ] **Step 3: Implement the helper**

Create `backend/app/services/choices.py`:

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && pytest tests/test_choices.py -v`
Expected: 8 passed.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/choices.py backend/tests/test_choices.py
git commit -m "feat(chat): extract_choices helper for [CHOICES] parsing"
```

---

### Task 2: Backend — add `choices` to ChatResponse schema and wire into chat service

**Files:**
- Modify: `backend/app/schemas/chat.py`
- Modify: `backend/app/services/chat_service.py`
- Modify: `backend/app/routers/chat.py`
- Test: `backend/tests/test_chat_service.py`

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/test_chat_service.py`:

```python
async def test_chat_service_extracts_choices(registry, monkeypatch):
    from unittest.mock import AsyncMock

    from app.engine.base import LLMResponse
    from app.services.chat_service import ChatService

    fake_provider = AsyncMock()
    fake_provider.complete.return_value = LLMResponse(
        text="Pick one:\n[CHOICES]Option A|Option B[/CHOICES]",
        tool_calls=[],
    )

    service = ChatService(
        registry=registry,
        provider=fake_provider,
        tool_executor=AsyncMock(),
    )

    reply = await service.send([{"role": "user", "content": "help"}])
    assert reply.text == "Pick one:"
    assert reply.choices == ["Option A", "Option B"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_chat_service.py::test_chat_service_extracts_choices -v`
Expected: FAIL — `ChatReply` has no `choices` field.

- [ ] **Step 3: Add `choices` to `ChatReply` dataclass**

Edit `backend/app/services/chat_service.py`. Add the field to `ChatReply`:

```python
@dataclass
class ChatReply:
    text: str
    data: Any | None = None
    display_hint: str | None = None
    tool_events: list[dict] = field(default_factory=list)
    choices: list[str] | None = None
```

Add the import at the top:

```python
from .choices import extract_choices
```

- [ ] **Step 4: Call `extract_choices` before returning**

In the `send` method, find every `return ChatReply(text=response.text, ...)` line (there are two — one in the no-tool-calls early return at line ~98, and one in the max-rounds fallback at line ~170). For the main one (no tool calls):

Replace:

```python
            if not response.tool_calls:
                return ChatReply(
                    text=response.text,
                    data=last_data,
                    display_hint=last_display_hint,
                    tool_events=tool_events,
                )
```

with:

```python
            if not response.tool_calls:
                clean_text, choices = extract_choices(response.text)
                return ChatReply(
                    text=clean_text,
                    data=last_data,
                    display_hint=last_display_hint,
                    tool_events=tool_events,
                    choices=choices,
                )
```

Leave the max-rounds fallback as-is (no choices parsing needed for error case).

- [ ] **Step 5: Add `choices` to the response schema**

Edit `backend/app/schemas/chat.py`:

```python
class ChatResponse(BaseModel):
    reply: str
    data: Any | None = None
    display_hint: str | None = None
    tool_events: list[dict[str, Any]] = Field(default_factory=list)
    choices: list[str] | None = None
```

- [ ] **Step 6: Wire `choices` in the chat router**

Edit `backend/app/routers/chat.py`. Find where `ChatReply` is converted to `ChatResponse` and add `choices=reply.choices`. The exact line depends on the router shape — search for `ChatResponse(` in `backend/app/routers/chat.py`.

- [ ] **Step 7: Run tests**

Run: `cd backend && pytest tests/test_chat_service.py -v`
Expected: PASS (new test + all existing).

Run: `cd backend && pytest -x`
Expected: all pass.

- [ ] **Step 8: Commit**

```bash
git add backend/app/services/chat_service.py backend/app/schemas/chat.py backend/app/routers/chat.py backend/tests/test_chat_service.py
git commit -m "feat(chat): wire choices extraction into ChatService and ChatResponse"
```

---

### Task 3: Backend — add choices instruction to system prompt

**Files:**
- Modify: `backend/app/services/context_builder.py`
- Test: `backend/tests/test_context_builder.py`

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/test_context_builder.py`:

```python
def test_system_prompt_contains_choices_instruction(registry):
    from app.services.context_builder import build_system_prompt

    prompt = build_system_prompt(registry)
    assert "[CHOICES]" in prompt
    assert "pipe" in prompt.lower() or "|" in prompt
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_context_builder.py::test_system_prompt_contains_choices_instruction -v`
Expected: FAIL — prompt doesn't contain `[CHOICES]` yet.

- [ ] **Step 3: Add the instruction**

Edit `backend/app/services/context_builder.py`. Append to `JAIN_SYSTEM_PROMPT_BASE` (before the closing `"""`):

```python
JAIN_SYSTEM_PROMPT_BASE = """You are Jain, an AI assistant that helps users through a set of skills provided by plugins.

Your personality: friendly, concise, practical. You speak in short sentences unless the user asks for detail.

When a user request matches one of your available skills, use the appropriate tool to fulfill it. When asked to find real-world data (locations, listings, status), always use tools — never make up data.

When helping a user create or configure something, you can either:
1. Gather information conversationally by asking one question at a time, or
2. Present a form if the plugin provides one and the user prefers that.

Ask the user which they prefer if it's not obvious from context.

When you want to offer the user a choice between 2-4 options, include a choices block at the END of your reply in exactly this format:
[CHOICES]Option one|Option two|Option three[/CHOICES]

Rules for choices:
- Each option should be a short phrase (under 40 characters) the user would naturally type.
- Separate options with | (pipe).
- Place the [CHOICES] block AFTER your conversational text.
- Only include choices at genuine decision points — not for yes/no or when there is only one path.
- Do NOT include choices if the user already told you what they want.
"""
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && pytest tests/test_context_builder.py -v`
Expected: PASS.

- [ ] **Step 5: Run full suite**

Run: `cd backend && pytest -x`
Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add backend/app/services/context_builder.py backend/tests/test_context_builder.py
git commit -m "feat(chat): instruct LLM to use [CHOICES] for quick-reply options"
```

---

### Task 4: Mobile — add `activeChoices` to Zustand store

**Files:**
- Modify: `mobile/src/store/useAppStore.ts`
- Modify: `mobile/src/types.ts`

- [ ] **Step 1: Add `choices` to `ChatResponse` type**

Edit `mobile/src/types.ts`. Add to `ChatResponse`:

```typescript
export interface ChatResponse {
  reply: string;
  data: unknown | null;
  display_hint: string | null;
  tool_events: ToolEvent[];
  choices: string[] | null;
}
```

- [ ] **Step 2: Add `activeChoices` to the store**

Edit `mobile/src/store/useAppStore.ts`. Add to the `AppState` interface:

```typescript
  // Quick-reply choice buttons offered by the LLM
  activeChoices: string[] | null;
  setActiveChoices: (choices: string[] | null) => void;
  clearActiveChoices: () => void;
```

Add to the `create<AppState>` body:

```typescript
  activeChoices: null,
  setActiveChoices: (choices) => set({ activeChoices: choices }),
  clearActiveChoices: () => set({ activeChoices: null }),
```

- [ ] **Step 3: Commit**

```bash
git add mobile/src/types.ts mobile/src/store/useAppStore.ts
git commit -m "feat(mobile): add activeChoices to store and ChatResponse type"
```

---

### Task 5: Mobile — wire choices in useChat hook

**Files:**
- Modify: `mobile/src/hooks/useChat.ts`

- [ ] **Step 1: Set/clear choices in the send function**

Edit `mobile/src/hooks/useChat.ts`. At the top of the `send` function, BEFORE appending the user message, clear any active choices:

```typescript
    // Clear stale choice buttons before sending
    store.clearActiveChoices();
```

After receiving the response (after `setLastResponse(res)`), set choices if present:

```typescript
      // Quick-reply choices
      if (res.choices && res.choices.length > 0) {
        store.setActiveChoices(res.choices);
      }
```

Also add `clearActiveChoices` and `setActiveChoices` to the destructured store calls. Since `useChat` reads from `useAppStore.getState()` inside `send`, you access them as `store.clearActiveChoices()` and `store.setActiveChoices(res.choices)`.

- [ ] **Step 2: Commit**

```bash
git add mobile/src/hooks/useChat.ts
git commit -m "feat(mobile): set/clear activeChoices in useChat send flow"
```

---

### Task 6: Mobile — create ChoiceButtons component

**Files:**
- Create: `mobile/src/chat/ChoiceButtons.tsx`

- [ ] **Step 1: Create the component**

Create `mobile/src/chat/ChoiceButtons.tsx`:

```tsx
import React from "react";
import { ScrollView, StyleSheet, Text, TouchableOpacity, View } from "react-native";

interface ChoiceButtonsProps {
  choices: string[];
  onChoose: (label: string) => void;
}

export function ChoiceButtons({ choices, onChoose }: ChoiceButtonsProps) {
  return (
    <View style={styles.container}>
      <ScrollView
        horizontal
        showsHorizontalScrollIndicator={false}
        contentContainerStyle={styles.scroll}
      >
        {choices.map((label) => (
          <TouchableOpacity
            key={label}
            style={styles.pill}
            onPress={() => onChoose(label)}
          >
            <Text style={styles.pillText}>{label}</Text>
          </TouchableOpacity>
        ))}
      </ScrollView>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    borderTopWidth: 1,
    borderTopColor: "#e2e8f0",
    backgroundColor: "#fff",
    paddingVertical: 8,
  },
  scroll: {
    paddingHorizontal: 8,
    gap: 8,
  },
  pill: {
    borderWidth: 1.5,
    borderColor: "#2563eb",
    borderRadius: 20,
    paddingHorizontal: 16,
    paddingVertical: 8,
    backgroundColor: "#fff",
  },
  pillText: {
    color: "#2563eb",
    fontSize: 14,
    fontWeight: "500",
  },
});
```

- [ ] **Step 2: Commit**

```bash
git add mobile/src/chat/ChoiceButtons.tsx
git commit -m "feat(mobile): ChoiceButtons pill-style component"
```

---

### Task 7: Mobile — integrate ChoiceButtons into ChatScreen

**Files:**
- Modify: `mobile/src/screens/ChatScreen.tsx`

- [ ] **Step 1: Import and wire up**

Edit `mobile/src/screens/ChatScreen.tsx`.

Add imports:

```typescript
import { ChoiceButtons } from "../chat/ChoiceButtons";
```

Inside the component, subscribe to `activeChoices`:

```typescript
  const activeChoices = useAppStore((s) => s.activeChoices);
```

Add a handler for when a choice is tapped:

```typescript
  const onChoice = useCallback(
    (label: string) => {
      setInput("");
      send(label);
      listRef.current?.scrollToEnd({ animated: true });
    },
    [send],
  );
```

In the JSX, render `ChoiceButtons` between the `ToolIndicator` and the `inputRow` View:

```tsx
      <ToolIndicator visible={sending} />
      {activeChoices && activeChoices.length > 0 ? (
        <ChoiceButtons choices={activeChoices} onChoose={onChoice} />
      ) : null}
      <View style={styles.inputRow}>
```

- [ ] **Step 2: Verify no TypeScript errors**

Run on Mac: `cd mobile && npx tsc --noEmit`
Expected: no errors.

- [ ] **Step 3: Commit**

```bash
git add mobile/src/screens/ChatScreen.tsx
git commit -m "feat(mobile): render ChoiceButtons in ChatScreen above input"
```

---

### Task 8: End-to-end verification

**Files:** None — verification only.

- [ ] **Step 1: Run backend tests**

Run: `cd backend && pytest -v`
Expected: all pass (140 + new tests).

- [ ] **Step 2: Push and rebuild**

```bash
git push
```

On Mac: `cd ~/repos/jain && git pull && cd mobile && npx expo run:ios`

- [ ] **Step 3: Manual test in simulator**

Chat with Jain: "I want to create a yard sale"

Expected: Jain replies with text AND pill buttons ("Fill out a form" / "Let AI help me step by step" or similar). Tap a button — it sends as a message, buttons disappear, Jain responds accordingly.

- [ ] **Step 4: Verify graceful degradation**

Ask something that shouldn't trigger choices: "What's the weather?"

Expected: normal text reply, no buttons.

- [ ] **Step 5: No commit — verification only.**
