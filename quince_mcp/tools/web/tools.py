from __future__ import annotations

from quince_mcp.schemas.tool import QuinceTool
from .handlers import (
    _web_search,
    _fetch_webpage,
    _get_weather,
    _http_request,
)

base_tool_id = "root--web"

web_search = QuinceTool(
    tool_id=f"{base_tool_id}--search",
    description=(
        "SEARCH THE LIVE INTERNET USING DUCKDUCKGO. "
        "Use when the user asks for current real-time news, facts, documentation, "
        "search queries, finding websites, or questions that require up-to-date internet results. "
        "Returns titles, snippets, and source URLs."
    ),
    handler=_web_search,
    arguments={
        "query": {
            "type": "string",
            "description": "The search query string."
        },
        "max_results": {
            "type": "integer",
            "description": "Maximum number of search results to return (default 5, max 10)."
        }
    },
    required_arguments=["query"]
)

fetch_webpage = QuinceTool(
    tool_id=f"{base_tool_id}--fetch-webpage",
    description=(
        "FETCH AND EXTRACT CLEAN READABLE TEXT CONTENT FROM A WEBPAGE URL. "
        "Use when the user provides a link/URL and asks to read, summarize, or extract text from it. "
        "Strips HTML, scripts, and styling to provide clean article text."
    ),
    handler=_fetch_webpage,
    arguments={
        "url": {
            "type": "string",
            "description": "The web URL to fetch (e.g. 'https://en.wikipedia.org/wiki/Python')."
        },
        "max_chars": {
            "type": "integer",
            "description": "Maximum text characters to return (default 4000)."
        }
    },
    required_arguments=["url"]
)

get_weather = QuinceTool(
    tool_id=f"{base_tool_id}--get-weather",
    description=(
        "GET REAL-TIME WEATHER FORECAST AND CURRENT CONDITIONS FOR ANY CITY OR LOCATION. "
        "Use when the user asks about the weather, temperature, rain, wind, or 3-day forecast "
        "for their current location or any specified city/country."
    ),
    handler=_get_weather,
    arguments={
        "location": {
            "type": "string",
            "description": "City or location name (e.g. 'New York', 'London', 'Tokyo', 'Mumbai'). Leave empty for current location."
        }
    },
    required_arguments=[]
)

http_request = QuinceTool(
    tool_id=f"{base_tool_id}--http-request",
    description=(
        "SEND AN HTTP/REST REQUEST TO AN API OR WEB ENDPOINT. "
        "Use to interact with external web APIs, call webhooks, or retrieve JSON data from REST services."
    ),
    handler=_http_request,
    arguments={
        "url": {
            "type": "string",
            "description": "Destination API URL."
        },
        "method": {
            "type": "string",
            "description": "HTTP method: GET, POST, PUT, DELETE, PATCH (default 'GET').",
            "enum": ["GET", "POST", "PUT", "DELETE", "PATCH"]
        },
        "body": {
            "type": "string",
            "description": "Optional request payload string or serialized JSON."
        }
    },
    required_arguments=["url"]
)

web = QuinceTool(
    tool_id=base_tool_id,
    description=(
        "LIVE WEB SEARCH, WEBPAGE READING, WEATHER, AND API ACCESS. "
        "Search the internet with DuckDuckGo, extract readable text from any URL, "
        "check live weather forecasts for any city, or make HTTP/REST requests."
    ),
    kind="category",
    children=[
        web_search,
        fetch_webpage,
        get_weather,
        http_request,
    ]
)

web_tool_tree = {
    f"{base_tool_id}": web,
    f"{base_tool_id}--search": web_search,
    f"{base_tool_id}--fetch-webpage": fetch_webpage,
    f"{base_tool_id}--get-weather": get_weather,
    f"{base_tool_id}--http-request": http_request,
}
