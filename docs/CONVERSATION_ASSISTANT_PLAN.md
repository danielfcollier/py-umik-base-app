# Conversation Assistant — Implementation Plan

## Overview

A new standalone app (`audio-tools --assist`) that continuously transcribes a
live conversation in 30-second chunks, and on a keypress sends the accumulated
transcript to an LLM to suggest a response in the conversation's language.
Context is maintained across keypresses for multi-turn assistance.

---

## Decisions

| Decision | Choice | Rationale |
|---|---|---|
| App type | New standalone app | Clean separation; reuses existing audio infrastructure |
| Transcription | `faster-whisper` `large-v3` | Best accuracy for pt-br and en-us; 1-2 min latency is acceptable |
| Chunk size | 30 seconds | Balances transcript freshness with Whisper call overhead |
| Speaker labelling | Skipped | Keypress trigger makes diarization non-essential |
| Context window | 5 min rolling (10 × 30s chunks) | Enough for a meaningful conversation segment |
| LLM provider | LiteLLM (pluggable) | Single interface for Claude, Gemini, GPT and others |
| Trigger | Keypress (spacebar) | User decides when they need help; removes question-detection complexity |
| Language | Selected at startup via `--language` | Passed to Whisper and used in LLM system prompt |
| UI | Textual TUI (two panels) | Already used in the project (`real_time_meter_tui.py`) |

---

## New Dependencies

```toml
# pyproject.toml additions
"faster-whisper>=1.0.0"
"litellm>=1.40.0"
```

`textual` is assumed to already be present. No new audio deps — microphone
capture reuses the existing `AudioBaseApp` + `AudioPipeline`.

---

## File Structure

```
src/umik_base_app/
├── apps/
│   └── conversation_assistant.py   # main app + TUI + entry point
├── llm/
│   ├── __init__.py
│   ├── client.py                   # thin LiteLLM wrapper
│   └── conversation.py             # conversation history + message builder
└── sinks/
    └── transcription_sink.py       # 30s buffer → faster-whisper → transcript store
```

---

## CLI Integration

Add to `cli.py` `_DISPATCH` and `_HELP`:

```python
"assist": ("umik_base_app.apps.conversation_assistant", "main", "audio-tools-assist"),
```

```python
"assist": "Live conversation transcription and LLM response assistant",
```

---

## CLI Arguments (`conversation_assistant.py`)

| Flag | Default | Description |
|---|---|---|
| `--language` | required | `pt-br` or `en-us` — sets Whisper language and LLM response language |
| `--llm-model` | `claude-sonnet-4-6` | LiteLLM model string (e.g. `gemini/gemini-2.0-flash`, `gpt-4o`) |
| `--max-context-minutes` | `5` | Rolling transcript window in minutes (default: 5 min = 10 chunks) |
| `--device-id` | system default | Microphone device ID (reuses existing `AppArgs`) |
| `--whisper-model` | `large-v3` | faster-whisper model size (`tiny`, `small`, `medium`, `large-v3`) |
| `--whisper-device` | `cpu` | `cpu` or `cuda` |

---

## Architecture

```
Startup
  Parse --language, --llm-model, --max-context-minutes
  Load faster-whisper model (done once, blocks until ready)
  Launch TUI

Audio loop (continuous, background thread)
  AudioBaseApp captures mic audio
  TranscriptionSink buffers 30s of samples
  On buffer full:
    → faster-whisper.transcribe(chunk, language=lang)
    → append text to TranscriptStore (rolling, max 10 chunks)
    → update TUI transcript panel

On spacebar
  If TranscriptStore is empty: show "No transcript yet."
  Else:
    → ConversationHistory.build_messages(transcript, language)
    → litellm.completion(model, messages)
    → display response in TUI suggestion panel
    → append (transcript_snapshot, response) to ConversationHistory

On next spacebar
  Same, but ConversationHistory includes prior exchanges (multi-turn)
```

---

## Module Detail

### `sinks/transcription_sink.py`

```python
class TranscriptionSink(AudioSink):
    """
    Buffers 30s of audio, calls faster-whisper, appends to TranscriptStore.
    Runs transcription in a ThreadPoolExecutor to avoid blocking audio capture.
    """
    def __init__(self, sample_rate, whisper_model, language, store, on_update):
        ...
    def handle(self, ctx): ...         # accumulate samples
    def _transcribe(self, audio): ...  # called in thread pool
```

`TranscriptStore` is a simple `collections.deque(maxlen=10)` of
`{"chunk_index": int, "text": str, "timestamp": datetime}` dicts.

---

### `llm/conversation.py`

Manages the full LLM message list across keypresses.

```python
class ConversationHistory:
    def build_messages(self, transcript_chunks, language) -> list[dict]:
        """
        Returns the full messages list for the LiteLLM call.

        system: role + language instruction
        assistant turns: prior suggestions
        user turns: transcript snapshots + instruction

        If called without a keypress (future: context-only update):
          user content ends with "No response needed yet, continue listening."
        On keypress:
          user content ends with "Suggest a response for the user."
        """
```

Message structure:

```
[
  {role: system,    content: "You are assisting the user in a live conversation.
                              Respond in [language]. Be concise."},
  {role: user,      content: "<transcript chunk 1-3>\nNo response needed yet,
                              continue listening."},          # context-only (if applicable)
  {role: assistant, content: "(acknowledged)"},
  {role: user,      content: "<transcript chunk 4-7>\nSuggest a response."},
  {role: assistant, content: "<previous suggestion>"},        # prior keypress
  {role: user,      content: "<transcript chunk 8-10>\nSuggest a response."},
]
```

Context-only turns (when the rolling window advances without a keypress) keep
the LLM informed of the conversation flow without asking for a response. The
assistant acknowledges with a minimal reply to keep the turn structure valid.

---

### `llm/client.py`

```python
import litellm

def complete(model: str, messages: list[dict]) -> str:
    response = litellm.completion(model=model, messages=messages)
    return response.choices[0].message.content
```

API keys are read from environment variables by LiteLLM automatically:
`ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `GEMINI_API_KEY`, etc.

---

### `apps/conversation_assistant.py` — TUI layout

Two-panel Textual layout:

```
┌─────────────────────────────────────────────────────┐
│  audio-tools assist  [language]  [model]  [SPACE=suggest] │
├─────────────────────────────┬───────────────────────┤
│  Transcript                 │  Suggestion           │
│                             │                       │
│  [00:00] lorem ipsum...     │  ┌───────────────┐   │
│  [00:30] dolor sit amet...  │  │ <LLM response>│   │
│  [01:00] ...                │  └───────────────┘   │
│                             │                       │
│  (scrollable, auto-scroll)  │  (latest only)        │
└─────────────────────────────┴───────────────────────┘
  q: quit   space: get suggestion   c: copy suggestion
```

Key bindings:

| Key | Action |
|---|---|
| `space` | Trigger LLM suggestion |
| `c` | Copy latest suggestion to clipboard |
| `q` / `ctrl+c` | Quit |

---

## Implementation Order

1. **`TranscriptStore`** — deque wrapper, no deps, testable in isolation
2. **`TranscriptionSink`** — plug into existing `AudioPipeline`, verify Whisper output
3. **`llm/client.py`** + **`llm/conversation.py`** — build and test message structure with a mock transcript
4. **TUI skeleton** — two-panel layout, hardcoded dummy data
5. **Wire together** — connect sink → store → keypress → LLM → TUI
6. **CLI integration** — add to `cli.py`, add `--assist` to `audio-tools`
7. **End-to-end test** — run with a real microphone, both languages

---

## Open Questions

- Should the transcript panel show raw text or `[HH:MM] text` with timestamps?
- Should `--language` accept `auto` to let Whisper detect language per chunk?
- Clipboard copy (`c`) — use `pyperclip` or Textual built-in?
