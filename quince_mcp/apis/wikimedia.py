import html
import json
import re
from urllib.parse import urlencode, quote
from urllib.request import Request, urlopen


USER_AGENT = "Quince/1.0 (local personal assistant)"


class WikimediaClient:
    def __init__(self, timeout: float = 10.0):
        self.timeout = timeout

    def _request(self, url: str, params: dict[str, object]) -> dict:
        query = urlencode({key: value for key, value in params.items() if value is not None})
        request = Request(
            f"{url}?{query}",
            headers={
                "User-Agent": USER_AGENT,
                "Accept": "application/json"
            }
        )

        with urlopen(request, timeout=self.timeout) as response:
            return json.loads(response.read().decode("utf-8"))

    def _action(self, project: str, params: dict[str, object]) -> dict:
        return self._request(f"https://{project}/w/api.php", params)

    def wikipedia_search(self, query: str, limit: int = 5):
        data = self._action(
            "en.wikipedia.org",
            {
                "action": "query",
                "list": "search",
                "srsearch": query,
                "srlimit": limit,
                "srprop": "snippet|size|wordcount|timestamp",
                "format": "json",
                "formatversion": 2,
                "utf8": 1,
            }
        )

        results = []

        for item in data.get("query", {}).get("search", []):
            results.append({
                "title": item.get("title"),
                "snippet": item.get("snippet"),
                "size": item.get("size"),
                "wordcount": item.get("wordcount"),
                "timestamp": item.get("timestamp"),
                "url": f"https://en.wikipedia.org/wiki/{quote(item.get('title', '').replace(' ', '_'), safe='')}",
            })

        return {
            "query": query,
            "results": results,
            "count": len(results)
        }

    def wikipedia_summary(self, title: str):
        data = self._request(
            f"https://en.wikipedia.org/api/rest_v1/page/summary/{quote(title.replace(' ', '_'), safe='')}",
            {}
        )

        return {
            "title": data.get("title"),
            "description": data.get("description"),
            "extract": data.get("extract"),
            "thumbnail": data.get("thumbnail", {}).get("source"),
            "url": data.get("content_urls", {}).get("desktop", {}).get("page"),
            "page_type": data.get("type"),
        }

    def wikipedia_page(self, title: str, max_chars: int = 12000):
        data = self._action(
            "en.wikipedia.org",
            {
                "action": "query",
                "prop": "extracts|info",
                "inprop": "url",
                "explaintext": 1,
                "exsectionformat": "plain",
                "titles": title,
                "format": "json",
                "formatversion": 2,
                "utf8": 1,
            }
        )

        pages = data.get("query", {}).get("pages", [])

        if not pages:
            raise LookupError(f"Wikipedia page '{title}' was not found")

        page = pages[0]
        extract = page.get("extract") or ""
        truncated = len(extract) > max_chars

        return {
            "title": page.get("title"),
            "extract": extract[:max_chars],
            "truncated": truncated,
            "max_chars": max_chars,
            "url": page.get("fullurl"),
        }

    def wikipedia_sections(self, title: str):
        data = self._action(
            "en.wikipedia.org",
            {
                "action": "parse",
                "page": title,
                "prop": "sections",
                "format": "json",
                "formatversion": 2,
                "utf8": 1,
            }
        )

        parse = data.get("parse")

        if not parse:
            raise LookupError(f"Wikipedia page '{title}' was not found")

        return parse.get("title"), parse.get("sections", [])

    def wikipedia_section(self, title: str, section: str, max_chars: int = 8000):
        page_title, sections = self.wikipedia_sections(title)
        normalized = " ".join(section.casefold().split())
        selected = None

        if normalized.isdigit():
            index = int(normalized)
            for item in sections:
                if str(item.get("index")) == str(index):
                    selected = item
                    break
        else:
            for item in sections:
                item_title = " ".join(str(item.get("line", "")).casefold().split())
                if item_title == normalized:
                    selected = item
                    break

        if selected is None:
            available = [item.get("line") for item in sections if item.get("line")]
            raise LookupError(
                f"Wikipedia section '{section}' was not found in '{page_title}'. Available sections: {available}"
            )

        data = self._action(
            "en.wikipedia.org",
            {
                "action": "parse",
                "page": page_title,
                "section": selected.get("index"),
                "prop": "text|wikitext",
                "format": "json",
                "formatversion": 2,
                "utf8": 1,
            }
        )

        parse = data.get("parse")
        if not parse:
            raise LookupError(f"Wikipedia section '{section}' was not found in '{page_title}'")

        text = parse.get("text") or {}
        raw_html = text.get("*") if isinstance(text, dict) else str(text)
        plain_text = html.unescape(re.sub(r"<[^>]+>", " ", raw_html))
        plain_text = re.sub(r"[ \t]+", " ", plain_text)
        plain_text = re.sub(r"\n{3,}", "\n\n", plain_text).strip()

        return {
            "title": page_title,
            "section": selected.get("line"),
            "extract": plain_text[:max_chars],
            "truncated": len(plain_text) > max_chars,
            "max_chars": max_chars,
            "url": f"https://en.wikipedia.org/wiki/{quote(page_title.replace(' ', '_'), safe='')}",
        }

    def wikipedia_random(self):
        data = self._action(
            "en.wikipedia.org",
            {
                "action": "query",
                "generator": "random",
                "grnnamespace": 0,
                "grnlimit": 1,
                "prop": "extracts|info",
                "inprop": "url",
                "exintro": 1,
                "explaintext": 1,
                "format": "json",
                "formatversion": 2,
                "utf8": 1,
            }
        )

        pages = data.get("query", {}).get("pages", [])

        if not pages:
            raise LookupError("Wikipedia did not return a random article")

        page = pages[0]

        return {
            "title": page.get("title"),
            "extract": page.get("extract"),
            "url": page.get("fullurl"),
        }

    def wikipedia_geosearch(self, location: str, radius_m: int = 10000, limit: int = 10):
        search = self.wikipedia_search(location, limit=1)

        if not search["results"]:
            raise LookupError(f"Could not resolve '{location}' to a Wikipedia location")

        title = search["results"][0]["title"]

        coordinates = self._action(
            "en.wikipedia.org",
            {
                "action": "query",
                "prop": "coordinates",
                "titles": title,
                "format": "json",
                "formatversion": 2,
            }
        )

        pages = coordinates.get("query", {}).get("pages", [])
        page_coordinates = pages[0].get("coordinates", []) if pages else []

        if not page_coordinates:
            raise LookupError(f"Could not resolve coordinates for Wikipedia location '{location}'")

        lat = page_coordinates[0].get("lat")
        lon = page_coordinates[0].get("lon")

        data = self._action(
            "en.wikipedia.org",
            {
                "action": "query",
                "list": "geosearch",
                "gscoord": f"{lat}|{lon}",
                "gsradius": radius_m,
                "gslimit": limit,
                "gsnamespace": 0,
                "format": "json",
                "formatversion": 2,
            }
        )

        results = []
        for item in data.get("query", {}).get("geosearch", []):
            results.append({
                "title": item.get("title"),
                "page_id": item.get("pageid"),
                "lat": item.get("lat"),
                "lon": item.get("lon"),
                "distance_m": item.get("dist"),
            })

        return {
            "location": location,
            "resolved_title": title,
            "center": {"latitude": lat, "longitude": lon},
            "radius_m": radius_m,
            "results": results,
            "count": len(results)
        }

    def wikipedia_pageviews(self, title: str, start_date: str | None = None, end_date: str | None = None):
        from datetime import timedelta, date

        today = date.today()
        end = today - timedelta(days=1)
        start = end - timedelta(days=6)

        start_value = start_date or start.strftime("%Y%m%d")
        end_value = end_date or end.strftime("%Y%m%d")

        article = quote(title.replace(' ', '_'), safe='')
        url = (
            "https://wikimedia.org/api/rest_v1/metrics/pageviews/per-article/"
            f"en.wikipedia.org/all-access/user/{article}/daily/{start_value}/{end_value}"
        )

        data = self._request(url, {})
        items = data.get("items", [])

        return {
            "title": title,
            "project": "en.wikipedia.org",
            "start_date": start_value,
            "end_date": end_value,
            "views": items,
            "total_views": sum(int(item.get("views", 0)) for item in items)
        }

    def wiktionary_search(self, query: str, limit: int = 5):
        return self._search_project("en.wiktionary.org", query, limit)

    def wiktionary_entry(self, term: str, max_chars: int = 8000):
        data = self._action(
            "en.wiktionary.org",
            {
                "action": "query",
                "prop": "extracts|info",
                "inprop": "url",
                "titles": term,
                "explaintext": 1,
                "format": "json",
                "formatversion": 2,
                "utf8": 1,
            }
        )

        pages = data.get("query", {}).get("pages", [])
        if not pages:
            raise LookupError(f"Wiktionary entry '{term}' was not found")

        page = pages[0]
        extract = page.get("extract") or ""

        if not extract:
            raise LookupError(f"Wiktionary entry '{term}' has no readable definition content")

        return {
            "term": term,
            "title": page.get("title"),
            "content": extract[:max_chars],
            "truncated": len(extract) > max_chars,
            "max_chars": max_chars,
            "url": page.get("fullurl"),
        }

    def wikiquote_search(self, query: str, limit: int = 5):
        return self._search_project("en.wikiquote.org", query, limit)

    def wikidata_search(self, query: str, limit: int = 5):
        data = self._action(
            "www.wikidata.org",
            {
                "action": "wbsearchentities",
                "search": query,
                "language": "en",
                "uselang": "en",
                "limit": limit,
                "type": "item",
                "format": "json",
                "formatversion": 2,
            }
        )

        results = []
        for item in data.get("search", []):
            results.append({
                "id": item.get("id"),
                "label": item.get("label"),
                "description": item.get("description"),
                "concept_uri": item.get("concepturi"),
            })

        return {
            "query": query,
            "results": results,
            "count": len(results)
        }

    def wikidata_entity(self, entity_id: str):
        data = self._action(
            "www.wikidata.org",
            {
                "action": "wbgetentities",
                "ids": entity_id,
                "languages": "en",
                "props": "labels|descriptions|aliases|claims|sitelinks",
                "format": "json",
                "formatversion": 2,
            }
        )

        entities = data.get("entities", {})
        entity = entities.get(entity_id)

        if not entity or "missing" in entity:
            raise LookupError(f"Wikidata entity '{entity_id}' was not found")

        return {
            "id": entity.get("id"),
            "labels": entity.get("labels", {}),
            "descriptions": entity.get("descriptions", {}),
            "aliases": entity.get("aliases", {}),
            "claims": entity.get("claims", {}),
            "sitelinks": entity.get("sitelinks", {}),
            "url": f"https://www.wikidata.org/wiki/{entity_id}"
        }

    def commons_search(self, query: str, limit: int = 5):
        data = self._action(
            "commons.wikimedia.org",
            {
                "action": "query",
                "list": "search",
                "srsearch": query,
                "srnamespace": 6,
                "srlimit": limit,
                "format": "json",
                "formatversion": 2,
                "utf8": 1,
            }
        )

        pages = data.get("query", {}).get("search", [])
        titles = [item.get("title") for item in pages if item.get("title")]

        image_info = {}

        if titles:
            info = self._action(
                "commons.wikimedia.org",
                {
                    "action": "query",
                    "titles": "|".join(titles),
                    "prop": "imageinfo",
                    "iiprop": "url|mime|size",
                    "format": "json",
                    "formatversion": 2,
                }
            )

            for page in info.get("query", {}).get("pages", []):
                values = page.get("imageinfo", [])
                if values:
                    image_info[page.get("title")] = values[0]

        results = []
        for item in pages:
            title = item.get("title")
            info = image_info.get(title, {})
            results.append({
                "title": title,
                "snippet": item.get("snippet"),
                "mime": info.get("mime"),
                "size": info.get("size"),
                "url": info.get("url"),
                "page_url": f"https://commons.wikimedia.org/wiki/{quote(str(title or '').replace(' ', '_'), safe='')}",
            })

        return {
            "query": query,
            "results": results,
            "count": len(results)
        }

    def _search_project(self, project: str, query: str, limit: int):
        data = self._action(
            project,
            {
                "action": "query",
                "list": "search",
                "srsearch": query,
                "srlimit": limit,
                "srprop": "snippet|size|wordcount|timestamp",
                "format": "json",
                "formatversion": 2,
                "utf8": 1,
            }
        )

        results = []
        for item in data.get("query", {}).get("search", []):
            title = item.get("title")
            results.append({
                "title": title,
                "snippet": item.get("snippet"),
                "size": item.get("size"),
                "wordcount": item.get("wordcount"),
                "timestamp": item.get("timestamp"),
                "url": f"https://{project}/wiki/{quote(str(title or '').replace(' ', '_'), safe='')}",
            })

        return {
            "query": query,
            "results": results,
            "count": len(results)
        }


wikimedia_client = WikimediaClient(timeout=10.0)
