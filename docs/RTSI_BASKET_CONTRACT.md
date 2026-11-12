# RTSI (Real-Time Screen Interaction) — Basket Integration Contract

This contract defines the exact interface and requirements that **Basket** (the parent agent / orchestrator) must follow to drive browser operations through Quince's RTSI capability.

---

## 1. Entering the RTSI Mode
To initiate browser control, Basket calls:
```json
navigate("root--browser", {})
```
* **If extension is not connected**:
  ```json
  {
    "success": false,
    "error": "extension_not_connected",
    "terminate": true,
    "message": "The browser extension is not connected, so I can't control the browser."
  }
  ```
* **If connected**: Returns `was_category_call: true`, `terminate: false`, `extra.rtsi` metadata, and `extra.mode_prompt`.
  * Basket must **inject `mode_prompt`** into the system prompt for all subsequent tool hops while `rtsi` metadata is present.
  * When `rtsi` is absent (or upon session termination), Basket removes `mode_prompt`.

---

## 2. Per-Hop LLM Settings
While RTSI is active:
* **Tool Calling**: Grammar-constrained tool selection, `tool_choice: "required"`, temperature: 0.
* **Reasoning/Thinking**: Disabled for fast hop latency (~45 tok/s).
* **Max Tokens**: Small (e.g., 256 tokens; comparisons are $\le 280$ chars).
* **Argument Schemas**: Provided dynamically in each response's `children[*].arguments`.
  * `refs` and `values` are string arrays.
  * `clear_first`, `press_enter`, `checked`, `active` are booleans.

---

## 3. Call Cap & Timeouts
* **Call Cap**: Replace the default global hop limit with `extra.rtsi.max_hops` while in RTSI.
* **MCP Call Timeout**: Must be at least **30 seconds** for all `root--browser*` tools.

---

## 4. Observation Context Management
* **`replaces: "observation"`**: When received, Basket must **delete** any previous observation text from the agent context window and store only `result.observation`.
* Keep only the latest `state_change_text` and `comparison_history`. Never accumulate raw snapshots across hops.

---

## 5. `await_user` Flow (Confirmation & Questions)
When a response contains `extra.await_user`:
```json
{
  "await_user": {
    "kind": "confirmation" | "question",
    "question": "Should I send this? The button says \"Send\" on mail.google.com.",
    "timeout_s": 60
  }
}
```
1. Basket stops the automated loop.
2. Speaks `await_user.question` directly using the TTS deterministic speech engine.
3. Captures user voice utterance (STT transcript).
4. Routes transcript directly (bypassing normal router) to:
   ```json
   navigate("root--browser--provide-answer", {"answer": "<transcript>"})
   ```
5. If user does not answer within `timeout_s`, Basket calls:
   ```json
   navigate("root--browser--provide-answer", {"answer": ""})
   ```

---

## 6. User Interruptions
If the user presses push-to-talk or interrupts mid-task:
1. Basket halts the loop immediately.
2. Calls `navigate("terminate")` to release control, reset indicators, and end the session.

---

## 7. Termination Semantics
When the LLM calls `root--browser--successful-termination` or `root--browser--unsuccessful-termination`:
* The MCP server closes the session and returns the **root menu** with `result.rtsi_outcome`:
  ```json
  {
    "status": "success" | "failed",
    "summary": "Task completed successfully",
    "steps": 4,
    "final_url": "https://example.com/checkout/success",
    "final_title": "Order Confirmed"
  }
  ```
* `terminate: false`: Allows Basket to chain next actions (e.g., save note to productivity, or terminate).
* Final speech should be synthesized from `rtsi_outcome.summary`.

---

## 8. Error Codes Reference

| Error Code | Meaning | Recommended Basket Action |
|---|---|---|
| `extension_not_connected` | Extension WebSocket disconnected | Apologize and prompt user to connect extension |
| `session_expired` | Idle / duration limit reached | End loop and inform user |
| `session_ended` | Session ended unexpectedly | Re-enter via `root--browser` if needed |
| `stale_ref` | Element changed or refreshed | Fresh observation provided; LLM retries |
| `sensitive_field` | Attempted write into password/credit card | Warn LLM to not touch sensitive fields |
| `not_allowed_in_state` | Out-of-state tool call | Pick tool from valid `children` list |
