"""
Browser category QuinceTool definitions.

These tools are NEVER executed directly by the navigate() handler's normal
leaf-execution path. They are handled by the RTSI state machine in
quince_mcp/rtsi/machine.py, which uses these definitions ONLY for their
descriptions, arguments, and feedback strings (to build children lists).

NEVER write to stdout from this module.
"""
from __future__ import annotations

from quince_mcp.schemas.tool import QuinceTool

_B = "root--browser"


# ---------------------------------------------------------------------------
# READ tools
# ---------------------------------------------------------------------------

list_tabs = QuinceTool(
    tool_id=f"{_B}--list-tabs",
    description=(
        "LIST THE BROWSER'S OPEN TABS. "
        "Use when you need to know which tabs are open or to find the tab_id of a page the user mentions. "
        "Do not use to read page contents."
    ),
    feedback="Here are the open tabs.",
)

refresh_page = QuinceTool(
    tool_id=f"{_B}--refresh-page",
    description=(
        "RE-READ THE CURRENT PAGE AND RETURN A FRESH LIST OF ITS CLICKABLE AND TYPEABLE ELEMENTS. "
        "Use when elements you need are missing, the page looks different from what you expect, "
        "or a ref stopped working. viewport = what is on screen; full = the whole page (longer). "
        "Do not use after every action; the page is re-read automatically."
    ),
    feedback="Here is the current page.",
    arguments={
        "scope": {
            "type": "string",
            "description": "viewport (default, on screen only) or full (entire page, longer).",
            "enum": ["viewport", "full"],
        }
    },
)

find_in_page = QuinceTool(
    tool_id=f"{_B}--find-in-page",
    description=(
        "SEARCH THE CURRENT PAGE FOR AN ELEMENT OR TEXT BY NAME, LABEL, OR WORDS. "
        "Use when the element you need is not in the current list, is below the visible area, "
        "or the page is long. Returns matching elements with refs. Do not use for web searches."
    ),
    feedback="Here are the matching elements.",
    arguments={
        "query": {
            "type": "string",
            "description": "A few words from the element's label or text, e.g. 'Compose' or 'Search'. Not a sentence.",
            "maxLength": 120,
        },
        "max_results": {
            "type": "integer",
            "description": "Maximum number of results to return (1–10, default 5).",
            "minimum": 1,
            "maximum": 10,
        },
    },
    required_arguments=["query"],
)

read_text = QuinceTool(
    tool_id=f"{_B}--read-text",
    description=(
        "READ THE READABLE TEXT OF THE CURRENT PAGE OR OF ONE ELEMENT. "
        "Use when the task needs the page's actual content (an article, a message, results, a table) "
        "rather than controls. Do not use just to find buttons or fields."
    ),
    feedback="Here is the page text.",
    arguments={
        "ref": {
            "type": "string",
            "description": "Optional. Read only this element's text. Omit to read the main content of the page.",
        },
        "max_chars": {
            "type": "integer",
            "description": "How much text to return. Use 4000 by default.",
            "minimum": 500,
            "maximum": 12000,
        },
    },
)


# ---------------------------------------------------------------------------
# ACT tools — Tabs
# ---------------------------------------------------------------------------

open_tab = QuinceTool(
    tool_id=f"{_B}--open-tab",
    description=(
        "OPEN A WEBSITE IN A NEW BROWSER TAB AND WAIT FOR IT TO LOAD. "
        "Use when the task needs a site that is not already open. "
        "The url must be a full web address starting with https:// (or a plain domain). "
        "Do not use to search the web by keywords, and do not use for chrome:// or file addresses."
    ),
    feedback="Opened the page.",
    arguments={
        "url": {
            "type": "string",
            "description": "THE WEB ADDRESS ONLY, e.g. https://mail.google.com. Not a search phrase. Not a description.",
            "maxLength": 2048,
        },
        "active": {
            "type": "boolean",
            "description": "true to bring the tab to the front (default true). False opens it in the background.",
        },
    },
    required_arguments=["url"],
)

use_current_tab = QuinceTool(
    tool_id=f"{_B}--use-current-tab",
    description=(
        "TAKE CONTROL OF THE TAB THE USER IS CURRENTLY LOOKING AT. "
        "Use only when the user says 'this page', 'this tab', 'the page I have open', or 'here'. "
        "Do not use to open a new site."
    ),
    feedback="Now controlling the current tab.",
)

switch_tab = QuinceTool(
    tool_id=f"{_B}--switch-tab",
    description=(
        "BRING AN EXISTING TAB TO THE FRONT AND WORK IN IT. "
        "Use when the needed page is already open; take tab_id from list-tabs. Never invent a tab_id."
    ),
    feedback="Switched to that tab.",
    arguments={
        "tab_id": {
            "type": "integer",
            "description": "Exact tab_id from list-tabs. Never invent one.",
        }
    },
    required_arguments=["tab_id"],
)

close_tab = QuinceTool(
    tool_id=f"{_B}--close-tab",
    description=(
        "CLOSE ONE BROWSER TAB THAT QUINCE CONTROLS. "
        "Use only when the user asks to close a tab or the task is finished and the tab is no longer needed. "
        "Do not use to leave a page."
    ),
    feedback="Tab closed.",
    arguments={
        "tab_id": {
            "type": "integer",
            "description": "Exact tab_id to close. Take it from list-tabs. Never invent one.",
        }
    },
    required_arguments=["tab_id"],
)

navigate = QuinceTool(
    tool_id=f"{_B}--navigate",
    description=(
        "MOVE THE CURRENT TAB TO A NEW ADDRESS OR THROUGH ITS HISTORY. "
        "goto = load a different url in this tab; back/forward = browser history; reload = refresh the page. "
        "Use goto only with a full web address."
    ),
    feedback="Navigation done.",
    arguments={
        "action": {
            "type": "string",
            "description": "goto, back, forward, or reload.",
            "enum": ["goto", "back", "forward", "reload"],
        },
        "url": {
            "type": "string",
            "description": "Required only when action is goto. The web address only.",
        },
    },
    required_arguments=["action"],
)


# ---------------------------------------------------------------------------
# ACT tools — Actions
# ---------------------------------------------------------------------------

click = QuinceTool(
    tool_id=f"{_B}--click",
    description=(
        "CLICK ONE ELEMENT ON THE CURRENT PAGE. "
        "Use for buttons, links, tabs, menu items, checkboxes, and anything clickable, "
        "by its ref from the latest page list. Use set-checked for checkboxes when the goal "
        "is a specific on/off state. Do not use to type text. "
        "Do not invent refs; use only refs shown in the latest page list."
    ),
    feedback="Clicked. Here is what changed on the page.",
    arguments={
        "ref": {
            "type": "string",
            "description": "Exact ref such as e12 from the latest page list. Never invent one.",
        },
        "click_type": {
            "type": "string",
            "description": "single by default. double or right only when the user asks for it.",
            "enum": ["single", "double", "right"],
        },
    },
    required_arguments=["ref"],
)

type_text = QuinceTool(
    tool_id=f"{_B}--type-text",
    description=(
        "TYPE TEXT INTO ONE TEXT FIELD. "
        "Use for text boxes, search boxes, text areas, and editable regions, by ref. "
        "Set press_enter true only when the user wants the text submitted right now (like running a search). "
        "Never use for passwords, card numbers, or codes; ask the user instead. "
        "Do not use to click buttons."
    ),
    feedback="Typed. Here is what changed.",
    arguments={
        "ref": {
            "type": "string",
            "description": "Exact ref of the text field from the latest page list.",
        },
        "text": {
            "type": "string",
            "description": "ONLY the exact text to type. No quotation marks, no explanation.",
            "maxLength": 2000,
        },
        "clear_first": {
            "type": "boolean",
            "description": "true to replace what is already in the field (default true for search boxes and short fields); false to add to the end.",
        },
        "press_enter": {
            "type": "boolean",
            "description": "true only if the text must be submitted immediately after typing.",
        },
    },
    required_arguments=["ref", "text"],
)

press_key = QuinceTool(
    tool_id=f"{_B}--press-key",
    description=(
        "PRESS ONE KEYBOARD KEY IN THE PAGE. "
        "Use for Enter, Tab, Escape, arrow keys, and similar single keys when clicking is not the "
        "right tool (for example Escape to close a popup, arrows to move in a list). "
        "Do not use to type words; use type-text."
    ),
    feedback="Key pressed.",
    arguments={
        "key": {
            "type": "string",
            "description": "One key from the allowed list.",
            "enum": [
                "Enter", "Tab", "Shift+Tab", "Escape", "Backspace", "Delete",
                "Space", "ArrowUp", "ArrowDown", "ArrowLeft", "ArrowRight",
                "PageUp", "PageDown", "Home", "End",
            ],
        },
        "ref": {
            "type": "string",
            "description": "Optional. Focus this element first.",
        },
    },
    required_arguments=["key"],
)

scroll = QuinceTool(
    tool_id=f"{_B}--scroll",
    description=(
        "SCROLL THE CURRENT PAGE OR A SCROLLABLE AREA. "
        "down/up = about one screen; top/bottom = jump; to_element = bring the element at ref into view. "
        "Use when needed elements are off screen."
    ),
    feedback="Scrolled.",
    arguments={
        "direction": {
            "type": "string",
            "description": "down, up, top, bottom, or to_element.",
            "enum": ["down", "up", "top", "bottom", "to_element"],
        },
        "ref": {
            "type": "string",
            "description": "Needed only for to_element, or to scroll inside a specific scrollable area.",
        },
    },
    required_arguments=["direction"],
)

select_option = QuinceTool(
    tool_id=f"{_B}--select-option",
    description=(
        "CHOOSE AN OPTION IN A STANDARD DROPDOWN (select) FIELD. "
        "Use when the field is a dropdown whose options are listed. "
        "For custom dropdowns that are not standard, click the field and then click the option instead."
    ),
    feedback="Option selected.",
    arguments={
        "ref": {
            "type": "string",
            "description": "Exact ref of the dropdown.",
        },
        "option": {
            "type": "string",
            "description": "The visible option label to choose. Not the ref.",
            "maxLength": 200,
        },
    },
    required_arguments=["ref", "option"],
)

set_checked = QuinceTool(
    tool_id=f"{_B}--set-checked",
    description=(
        "SET A CHECKBOX, RADIO BUTTON, OR SWITCH TO A SPECIFIC ON/OFF STATE. "
        "Use when the user wants something checked/unchecked/enabled/disabled. "
        "Does nothing if it is already in that state."
    ),
    feedback="Checkbox state set.",
    arguments={
        "ref": {
            "type": "string",
            "description": "Exact ref of the checkbox, radio, or switch.",
        },
        "checked": {
            "type": "boolean",
            "description": "true to turn on / check; false to turn off / uncheck.",
        },
    },
    required_arguments=["ref", "checked"],
)

hover = QuinceTool(
    tool_id=f"{_B}--hover",
    description=(
        "MOVE THE POINTER OVER ONE ELEMENT WITHOUT CLICKING. "
        "Use only to reveal hover menus or tooltips. Do not use to click."
    ),
    feedback="Hovered.",
    arguments={
        "ref": {
            "type": "string",
            "description": "Exact ref of the element.",
        }
    },
    required_arguments=["ref"],
)

fill_form = QuinceTool(
    tool_id=f"{_B}--fill-form",
    description=(
        "FILL SEVERAL FORM FIELDS IN ONE STEP (UP TO 8). "
        "Use when the page shows a form and the user supplied several values. "
        "refs and values are parallel lists: values[i] goes into refs[i]. "
        "Handles text fields, dropdowns, and checkboxes. Never submits the form, never fills passwords. "
        "Do not use for a single field; use type-text."
    ),
    feedback="Form filled.",
    arguments={
        "refs": {
            "type": "array",
            "description": "List of exact refs, in the order to fill.",
            "items": {"type": "string"},
            "maxItems": 8,
        },
        "values": {
            "type": "array",
            "description": "List of the values, same length and order as refs. For checkboxes use true or false.",
            "items": {"type": "string"},
            "maxItems": 8,
        },
    },
    required_arguments=["refs", "values"],
)

wait = QuinceTool(
    tool_id=f"{_B}--wait",
    description=(
        "WAIT A FEW SECONDS FOR THE PAGE TO FINISH LOADING OR UPDATING. "
        "Use when the page clearly says it is loading or results have not appeared yet. "
        "Do not use as a default step."
    ),
    feedback="Waited.",
    arguments={
        "seconds": {
            "type": "integer",
            "description": "Whole seconds, 1 to 10.",
            "minimum": 1,
            "maximum": 10,
        }
    },
    required_arguments=["seconds"],
)


# ---------------------------------------------------------------------------
# CONTROL tools
# ---------------------------------------------------------------------------

record_comparison = QuinceTool(
    tool_id=f"{_B}--record-comparison",
    description=(
        "WRITE ONE SHORT COMPARISON OF THE PAGE BEFORE AND AFTER YOUR LAST ACTION. "
        "State what actually changed (or that nothing changed), in plain words, under 280 characters. "
        "Base it only on the change report you were given. "
        "Do not guess and do not describe what you hoped would happen."
    ),
    feedback="Comparison recorded.",
    arguments={
        "comparison": {
            "type": "string",
            "description": "What changed after the action, based only on the change report. If nothing changed, say 'Nothing changed.'",
            "maxLength": 280,
        }
    },
    required_arguments=["comparison"],
)

continue_tool = QuinceTool(
    tool_id=f"{_B}--continue",
    description=(
        "KEEP WORKING ON THE TASK. "
        "Choose this when the last action worked as expected but the user's task is NOT finished yet, "
        "or when an action failed in a way you can try to fix with a different approach."
    ),
    feedback="Continuing.",
)

successful_termination = QuinceTool(
    tool_id=f"{_B}--successful-termination",
    description=(
        "THE TASK IS FULLY DONE. "
        "Choose this only when the page state clearly shows the user's whole request is complete "
        "(not just one step). If anything unusual happened or you are unsure, do not choose this."
    ),
    feedback="Browser task completed successfully.",
    arguments={
        "result_summary": {
            "type": "string",
            "description": "One or two plain sentences saying what was accomplished, for the user to hear.",
            "maxLength": 300,
        }
    },
    required_arguments=["result_summary"],
)

unsuccessful_termination = QuinceTool(
    tool_id=f"{_B}--unsuccessful-termination",
    description=(
        "STOP BECAUSE THE TASK CANNOT BE COMPLETED. "
        "Choose this when you are blocked (login wall, captcha, missing page, repeated failures, "
        "nothing works) or something unexpected or unsafe happened. Playing safe is correct when in doubt."
    ),
    feedback="Browser task stopped.",
    arguments={
        "reason": {
            "type": "string",
            "description": "One or two plain sentences saying what blocked you, for the user to hear.",
            "maxLength": 300,
        }
    },
    required_arguments=["reason"],
)

cross_question = QuinceTool(
    tool_id=f"{_B}--cross-question",
    description=(
        "PAUSE AND ASK THE USER ONE QUESTION. "
        "Choose this when you need information only the user has (a choice, a missing detail, "
        "a password or code, a confirmation) before you can go on. "
        "The task is not ended; it resumes after the user answers. Do not use to chat."
    ),
    feedback="Waiting for the user's answer.",
    arguments={
        "question": {
            "type": "string",
            "description": "One short, clear question to speak to the user.",
            "maxLength": 200,
        }
    },
    required_arguments=["question"],
)

# Hidden tool — called by Basket only, never shown to the LLM.
provide_answer = QuinceTool(
    tool_id=f"{_B}--provide-answer",
    description="INTERNAL: route the user's spoken answer back to the RTSI machine. Hidden from the LLM.",
    feedback="Answer received.",
    arguments={
        "answer": {
            "type": "string",
            "description": "The user's spoken utterance (STT transcript).",
        }
    },
    required_arguments=["answer"],
    hidden=True,
)


# ---------------------------------------------------------------------------
# Category
# ---------------------------------------------------------------------------

browser = QuinceTool(
    tool_id=_B,
    kind="category",
    description=(
        "OPERATE WEBSITES IN THE USER'S OWN CHROME BROWSER (RTSI MODE). "
        "Use for any task that needs a live website: opening a site, reading the current page, "
        "clicking, typing, scrolling, filling forms, switching tabs, or completing a multi-step web task. "
        "Do not use for facts Wikipedia can answer, for notes/timers/memory, or for local computer controls."
    ),
    children=[
        list_tabs, open_tab, use_current_tab, switch_tab, close_tab, navigate,
        refresh_page, find_in_page, read_text,
        click, type_text, press_key, scroll, select_option, set_checked, hover,
        fill_form, wait,
        record_comparison, continue_tool, successful_termination, unsuccessful_termination,
        cross_question, provide_answer,
    ],
)


# ---------------------------------------------------------------------------
# Tool tree (all ids for TOOL_TREE registry)
# ---------------------------------------------------------------------------

browser_tool_tree: dict[str, QuinceTool] = {
    _B: browser,
    f"{_B}--list-tabs": list_tabs,
    f"{_B}--open-tab": open_tab,
    f"{_B}--use-current-tab": use_current_tab,
    f"{_B}--switch-tab": switch_tab,
    f"{_B}--close-tab": close_tab,
    f"{_B}--navigate": navigate,
    f"{_B}--refresh-page": refresh_page,
    f"{_B}--find-in-page": find_in_page,
    f"{_B}--read-text": read_text,
    f"{_B}--click": click,
    f"{_B}--type-text": type_text,
    f"{_B}--press-key": press_key,
    f"{_B}--scroll": scroll,
    f"{_B}--select-option": select_option,
    f"{_B}--set-checked": set_checked,
    f"{_B}--hover": hover,
    f"{_B}--fill-form": fill_form,
    f"{_B}--wait": wait,
    f"{_B}--record-comparison": record_comparison,
    f"{_B}--continue": continue_tool,
    f"{_B}--successful-termination": successful_termination,
    f"{_B}--unsuccessful-termination": unsuccessful_termination,
    f"{_B}--cross-question": cross_question,
    f"{_B}--provide-answer": provide_answer,
}
