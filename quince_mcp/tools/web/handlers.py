from __future__ import annotations

import html
import ipaddress
import json
import re
import socket
import urllib.parse
import urllib.request
from typing import Any


def _validate_public_url(url: str) -> str | None:
    """
    Reject non-HTTP(S) schemes and loopback / private / link-local IP targets
    to prevent SSRF against localhost services or cloud metadata endpoints.
    Returns an error string if blocked, or None if allowed.
    """
    try:
        parsed = urllib.parse.urlparse(url)
    except Exception:
        return "Malformed URL"

    if parsed.scheme not in ("http", "https"):
        return f"Blocked URL scheme: {parsed.scheme}"

    host = (parsed.hostname or "").strip().lower()
    if not host:
        return "URL missing hostname"

    if host in ("localhost", "localhost.localdomain") or host.endswith(".local"):
        return f"Blocked loopback/local host: {host}"

    # Direct IP literal check
    try:
        ip = ipaddress.ip_address(host)
        if ip.is_loopback or ip.is_private or ip.is_link_local or ip.is_multicast or ip.is_reserved or ip.is_unspecified:
            return f"Blocked non-public IP target: {host}"
    except ValueError:
        # Hostname: resolve DNS best-effort to block local/metadata aliases
        try:
            for info in socket.getaddrinfo(host, None):
                resolved_ip = ipaddress.ip_address(info[4][0].split("%")[0])
                if (
                    resolved_ip.is_loopback
                    or resolved_ip.is_private
                    or resolved_ip.is_link_local
                    or resolved_ip.is_reserved
                    or resolved_ip.is_unspecified
                ):
                    return f"Blocked hostname resolving to non-public IP: {host} -> {resolved_ip}"
        except Exception:
            pass

    return None


DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)


def _clean_html_text(raw_html: str) -> str:
    """Strip HTML tags and scripts, leaving clean human-readable text."""
    # Remove script, style, head, svg, noscript
    cleaned = re.sub(r"<(script|style|head|svg|noscript)[^>]*>.*?</\1>", " ", raw_html, flags=re.DOTALL | re.IGNORECASE)
    # Convert line breaks and paragraph ends
    cleaned = re.sub(r"</?(p|div|br|h[1-6]|li|tr)[^>]*>", "\n", cleaned, flags=re.IGNORECASE)
    # Strip all remaining tags
    cleaned = re.sub(r"<[^>]+>", " ", cleaned)
    # Decode HTML entities
    cleaned = html.unescape(cleaned)
    # Normalize multiple whitespace/newlines
    lines = [line.strip() for line in cleaned.splitlines()]
    non_empty = [line for line in lines if line]
    return "\n".join(non_empty)


def _web_search(query: str, max_results: int = 5) -> dict[str, Any]:
    """Search the web using DuckDuckGo and return structured results."""
    query = (query or "").strip()
    if not query:
        return {"error": "Query cannot be empty"}

    max_results = max(1, min(max_results, 10))
    results = []
    abstract = None

    # Step 1: Check DuckDuckGo Instant Answer API first for direct facts
    try:
        ia_url = (
            f"https://api.duckduckgo.com/?q={urllib.parse.quote(query)}"
            "&format=json&no_html=1&skip_disambig=1"
        )
        req = urllib.request.Request(ia_url, headers={"User-Agent": DEFAULT_USER_AGENT})
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8", errors="ignore"))
            if data.get("AbstractText"):
                abstract = {
                    "heading": data.get("Heading", ""),
                    "text": data.get("AbstractText", ""),
                    "source": data.get("AbstractSource", ""),
                    "url": data.get("AbstractURL", ""),
                }
            for topic in data.get("RelatedTopics", [])[:max_results]:
                if isinstance(topic, dict) and topic.get("Text") and topic.get("FirstURL"):
                    results.append({
                        "title": topic.get("Text", "").split(" - ")[0],
                        "snippet": topic.get("Text", ""),
                        "url": topic.get("FirstURL", ""),
                    })
    except Exception:
        pass

    # Step 2: Query DuckDuckGo HTML if we need more organic search results
    if len(results) < max_results:
        try:
            html_url = f"https://html.duckduckgo.com/html/?q={urllib.parse.quote(query)}"
            req = urllib.request.Request(html_url, headers={"User-Agent": DEFAULT_USER_AGENT})
            with urllib.request.urlopen(req, timeout=7) as resp:
                html_doc = resp.read().decode("utf-8", errors="ignore")

                # Match result elements
                blocks = re.findall(
                    r'<a[^>]*class="result__url"[^>]*href="([^"]+)"[^>]*>(.*?)</a>.*?'
                    r'<a[^>]*class="result__snippet"[^>]*>(.*?)</a>',
                    html_doc,
                    flags=re.DOTALL | re.IGNORECASE,
                )

                for raw_url, raw_title, raw_snippet in blocks:
                    if len(results) >= max_results:
                        break
                    # Clean DuckDuckGo redirect url if needed
                    parsed_url = raw_url.strip()
                    if "/l/?uddg=" in parsed_url:
                        match = re.search(r"uddg=([^&]+)", parsed_url)
                        if match:
                            parsed_url = urllib.parse.unquote(match.group(1))

                    snippet = _clean_html_text(raw_snippet)
                    title = _clean_html_text(raw_title)
                    if parsed_url and (snippet or title):
                        results.append({
                            "title": title or parsed_url,
                            "snippet": snippet,
                            "url": parsed_url,
                        })
        except Exception as exc:
            if not results and not abstract:
                return {
                    "query": query,
                    "error": f"Search request failed: {exc}",
                    "results": [],
                }

    return {
        "query": query,
        "abstract": abstract,
        "result_count": len(results),
        "results": results[:max_results],
    }


def _fetch_webpage(url: str, max_chars: int = 4000) -> dict[str, Any]:
    """Fetch content of a webpage and extract clean readable text."""
    url = (url or "").strip()
    if not url:
        return {"error": "URL cannot be empty"}

    if "://" not in url:
        url = "https://" + url

    blocked_reason = _validate_public_url(url)
    if blocked_reason:
        return {"url": url, "error": blocked_reason, "blocked": True}

    max_chars = max(500, min(max_chars, 20000))

    try:
        req = urllib.request.Request(url, headers={"User-Agent": DEFAULT_USER_AGENT})
        with urllib.request.urlopen(req, timeout=10) as resp:
            content_type = resp.headers.get_content_type()
            raw_bytes = resp.read(max_chars * 10)  # read enough bytes to parse text
            charset = resp.headers.get_content_charset() or "utf-8"
            raw_text = raw_bytes.decode(charset, errors="ignore")

            # Extract title if present
            title_match = re.search(r"<title[^>]*>(.*?)</title>", raw_text, flags=re.IGNORECASE | re.DOTALL)
            title = _clean_html_text(title_match.group(1)) if title_match else ""

            if "html" in content_type:
                clean_text = _clean_html_text(raw_text)
            else:
                clean_text = raw_text.strip()

            truncated = len(clean_text) > max_chars
            final_text = clean_text[:max_chars] if truncated else clean_text

            return {
                "url": url,
                "title": title,
                "content_type": content_type,
                "content": final_text,
                "length_chars": len(final_text),
                "truncated": truncated,
            }
    except Exception as exc:
        return {
            "url": url,
            "error": f"Failed to fetch webpage: {exc}",
        }


def _get_weather(location: str = "") -> dict[str, Any]:
    """Get live weather and forecast for any city or current location via wttr.in."""
    loc = (location or "").strip()
    encoded = urllib.parse.quote(loc) if loc else ""
    endpoint = f"https://wttr.in/{encoded}?format=j1"

    try:
        req = urllib.request.Request(endpoint, headers={"User-Agent": "curl/7.68.0"})
        with urllib.request.urlopen(req, timeout=7) as resp:
            data = json.loads(resp.read().decode("utf-8", errors="ignore"))

            current = data.get("current_condition", [{}])[0]
            nearest = data.get("nearest_area", [{}])[0]
            area_name = nearest.get("areaName", [{}])[0].get("value", "")
            region = nearest.get("region", [{}])[0].get("value", "")
            country = nearest.get("country", [{}])[0].get("value", "")
            location_str = f"{area_name}, {region}, {country}".strip(", ")

            weather_desc = current.get("weatherDesc", [{}])[0].get("value", "Unknown")

            # Daily forecast summary
            daily_forecast = []
            for day in data.get("weather", [])[:3]:
                daily_forecast.append({
                    "date": day.get("date"),
                    "max_temp_c": day.get("maxtempC"),
                    "min_temp_c": day.get("mintempC"),
                    "avg_temp_c": day.get("avgtempC"),
                    "condition": day.get("hourly", [{}])[4].get("weatherDesc", [{}])[0].get("value", "") if len(day.get("hourly", [])) > 4 else "",
                })

            return {
                "location": location_str or loc or "Current Location",
                "condition": weather_desc,
                "temperature_c": current.get("temp_C"),
                "temperature_f": current.get("temp_F"),
                "feels_like_c": current.get("FeelsLikeC"),
                "feels_like_f": current.get("FeelsLikeF"),
                "humidity_percent": current.get("humidity"),
                "wind_speed_kmph": current.get("windspeedKmph"),
                "wind_direction": current.get("winddir16Point"),
                "uv_index": current.get("uvIndex"),
                "visibility_km": current.get("visibility"),
                "forecast_3_days": daily_forecast,
            }
    except Exception as exc:
        # Fallback to plain text format
        try:
            txt_endpoint = f"https://wttr.in/{encoded}?format=3"
            req2 = urllib.request.Request(txt_endpoint, headers={"User-Agent": "curl/7.68.0"})
            with urllib.request.urlopen(req2, timeout=5) as resp2:
                plain_weather = resp2.read().decode("utf-8", errors="ignore").strip()
                return {
                    "location": loc or "Current Location",
                    "weather_summary": plain_weather,
                }
        except Exception:
            return {
                "location": loc,
                "error": f"Failed to retrieve weather: {exc}",
            }


def _http_request(
    url: str,
    method: str = "GET",
    headers: dict[str, str] | None = None,
    body: str | None = None,
    timeout_seconds: int = 10,
) -> dict[str, Any]:
    """Execute an HTTP/REST request to an external API or URL."""
    url = (url or "").strip()
    if not url:
        return {"error": "URL cannot be empty"}

    if "://" not in url:
        url = "https://" + url

    blocked_reason = _validate_public_url(url)
    if blocked_reason:
        return {"url": url, "error": blocked_reason, "blocked": True}

    method = method.upper().strip()
    timeout_seconds = max(1, min(timeout_seconds, 30))
    req_headers = {"User-Agent": DEFAULT_USER_AGENT}
    if headers:
        req_headers.update(headers)

    data_bytes = body.encode("utf-8") if body else None

    try:
        req = urllib.request.Request(
            url=url,
            data=data_bytes,
            headers=req_headers,
            method=method,
        )
        with urllib.request.urlopen(req, timeout=timeout_seconds) as resp:
            content_type = resp.headers.get_content_type()
            raw_response = resp.read(50000).decode("utf-8", errors="ignore")

            # Parse as JSON if content-type is json
            json_data = None
            if "json" in content_type:
                try:
                    json_data = json.loads(raw_response)
                except Exception:
                    pass

            return {
                "url": url,
                "method": method,
                "status_code": resp.status,
                "content_type": content_type,
                "response_json": json_data,
                "response_text": raw_response if json_data is None else None,
            }
    except urllib.error.HTTPError as exc:
        err_body = ""
        try:
            err_body = exc.read().decode("utf-8", errors="ignore")
        except Exception:
            pass
        return {
            "url": url,
            "method": method,
            "status_code": exc.code,
            "error": f"HTTP Error {exc.code}: {exc.reason}",
            "response_body": err_body[:2000],
        }
    except Exception as exc:
        return {
            "url": url,
            "method": method,
            "error": str(exc),
        }
