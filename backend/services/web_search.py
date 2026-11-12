"""Optional, bounded Brave search. Search snippets are untrusted evidence."""
import json
import logging
from urllib.parse import urlencode, urlparse
from urllib.request import Request, urlopen
import config

log = logging.getLogger("panman.web")


def search(question: str) -> str:
    if not config.WEB_SEARCH_ENABLED or not config.WEB_SEARCH_API_KEY:
        return ""
    if config.WEB_SEARCH_PROVIDER != "brave":
        raise ValueError("Unsupported web search provider")
    url = "https://api.search.brave.com/res/v1/web/search?" + urlencode({"q": question[:300], "count": config.WEB_SEARCH_RESULTS})
    request = Request(url, headers={"Accept": "application/json", "X-Subscription-Token": config.WEB_SEARCH_API_KEY})
    with urlopen(request, timeout=config.WEB_SEARCH_TIMEOUT_SECONDS) as response:
        payload = json.load(response)
    results = []
    for item in payload.get("web", {}).get("results", [])[:config.WEB_SEARCH_RESULTS]:
        link = item.get("url", "")
        parsed = urlparse(link)
        if parsed.scheme != "https" or not parsed.hostname:
            continue
        title = str(item.get("title", ""))[:180]
        snippet = str(item.get("description", ""))[:600]
        results.append(f"{title} ({parsed.hostname}, {link}): {snippet}")
    return "\n".join(results)
