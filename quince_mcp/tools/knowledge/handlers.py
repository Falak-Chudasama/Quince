from quince_mcp.apis.wikimedia import wikimedia_client


def _search_wikipedia(query: str, limit: int = 5):
    return wikimedia_client.wikipedia_search(query, limit)


def _get_wikipedia_summary(title: str):
    return wikimedia_client.wikipedia_summary(title)


def _get_wikipedia_page(title: str, max_chars: int = 12000):
    return wikimedia_client.wikipedia_page(title, max_chars)