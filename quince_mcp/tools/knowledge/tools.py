from quince_mcp.schemas.tool import QuinceTool

from .handlers import (
    _get_wikipedia_page,
    _get_wikipedia_summary,
    _search_wikipedia,
)


base_tool_id = "root--knowledge"


search_wikipedia = QuinceTool(
    tool_id=f"{base_tool_id}--wikipedia--search",
    description=(
        "SEARCH ENGLISH WIKIPEDIA FOR AN ARTICLE. "
        "Use when the user asks about a topic and the intended Wikipedia "
        "article is unknown or ambiguous. "
        "Do not use when the exact article is already known."
    ),
    handler=_search_wikipedia,
    arguments={
        "query": {
            "type": "string",
            "description": (
                "A concise Wikipedia search query derived from the user's request."
            ),
        },
        "limit": {
            "type": "integer",
            "description": (
                "Maximum number of search results. Use 5 by default."
            ),
            "minimum": 1,
            "maximum": 20,
        },
    },
    required_arguments=["query"],
)


get_wikipedia_summary = QuinceTool(
    tool_id=f"{base_tool_id}--wikipedia--summary",
    description=(
        "GET THE LEAD SUMMARY OF ONE ENGLISH WIKIPEDIA ARTICLE. "
        "Use for normal factual questions, short explanations, "
        "or concise overviews when the intended article is known. "
        "Prefer this over page for ordinary questions."
    ),
    handler=_get_wikipedia_summary,
    arguments={
        "title": {
            "type": "string",
            "description": (
                "The intended English Wikipedia article title. "
                "Use an exact title when known from context or search results."
            ),
        }
    },
    required_arguments=["title"],
)


get_wikipedia_page = QuinceTool(
    tool_id=f"{base_tool_id}--wikipedia--page",
    description=(
        "GET DETAILED CONTENT FROM ONE ENGLISH WIKIPEDIA ARTICLE. "
        "Use when the user asks for detailed information, substantial context, "
        "or more information than the article summary provides. "
        "Do not use for ordinary factual questions when summary is sufficient."
    ),
    handler=_get_wikipedia_page,
    arguments={
        "title": {
            "type": "string",
            "description": (
                "The intended English Wikipedia article title."
            ),
        },
        "max_chars": {
            "type": "integer",
            "description": (
                "Maximum amount of article text to return. Use 12000 by default."
            ),
            "minimum": 1000,
            "maximum": 30000,
        },
    },
    required_arguments=["title"],
)


wikipedia = QuinceTool(
    tool_id=f"{base_tool_id}--wikipedia",
    description=(
        "ENGLISH WIKIPEDIA TOOLS. "
        "Use search when the intended article is unknown, "
        "summary for normal factual lookups, "
        "and page when detailed article content is required."
    ),
    kind="category",
    children=[
        search_wikipedia,
        get_wikipedia_summary,
        get_wikipedia_page,
    ],
)


knowledge = QuinceTool(
    tool_id=base_tool_id,
    description=(
        "EXTERNAL KNOWLEDGE RETRIEVAL THROUGH WIKIPEDIA. "
        "Use this category for Wikipedia-based factual information. "
        "Do not use for personal memory, notes, timers, local computer control, "
        "or general internet browsing."
    ),
    kind="category",
    children=[
        wikipedia,
    ],
)


knowledge_tool_tree = {
    f"{base_tool_id}": knowledge,

    f"{base_tool_id}--wikipedia": wikipedia,
    f"{base_tool_id}--wikipedia--search": search_wikipedia,
    f"{base_tool_id}--wikipedia--summary": get_wikipedia_summary,
    f"{base_tool_id}--wikipedia--page": get_wikipedia_page,
}