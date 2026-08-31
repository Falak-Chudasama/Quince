from app.core.apis import apis

searxngAPI = apis.get("searxng")

def search(query: str):
    return {}