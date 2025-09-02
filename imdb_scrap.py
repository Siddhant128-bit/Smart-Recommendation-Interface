import requests
from bs4 import BeautifulSoup
import json
from urllib.parse import urljoin

BASE_URL = "https://www.imdb.com"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/126.0.0.0 Safari/537.36"
    )
}


def _pick_itemlist_ldjson(soup):
    """Find the largest ItemList JSON-LD block (ignore breadcrumbs, etc.)."""
    candidates = []
    for tag in soup.find_all("script", type="application/ld+json"):
        raw = (tag.string or "").strip()
        if not raw:
            continue
        try:
            data = json.loads(raw)
        except Exception:
            continue

        objs = data if isinstance(data, list) else [data]
        for obj in objs:
            if isinstance(obj, dict) and obj.get("@type") == "ItemList":
                candidates.append(obj)

    if not candidates:
        return None
    return max(candidates, key=lambda o: len(o.get("itemListElement", [])))


def _parse_itemlist(obj):
    """Extract movies sorted by ListItem.position."""
    movies = []
    for li in obj.get("itemListElement", []):
        itm = li.get("item", {}) or {}
        title = itm.get("name")
        link = urljoin(BASE_URL, (itm.get("url") or "").split("?")[0])
        rating = (itm.get("aggregateRating") or {}).get("ratingValue")
        pos = li.get("position")
        movies.append((pos, title, link, rating))

    # Sort by position, ignore None
    movies.sort(key=lambda x: (x[0] is None, x[0]))
    return [(t, u, r) for _, t, u, r in movies]


def get_top_250_movies():
    url = f"{BASE_URL}/chart/top/"
    resp = requests.get(url, headers=HEADERS, timeout=15)
    soup = BeautifulSoup(resp.text, "html.parser")

    itemlist = _pick_itemlist_ldjson(soup)
    if not itemlist:
        return []

    return _parse_itemlist(itemlist)


def get_trending_movies():
    url = f"{BASE_URL}/chart/moviemeter/"
    resp = requests.get(url, headers=HEADERS, timeout=15)
    soup = BeautifulSoup(resp.text, "html.parser")

    itemlist = _pick_itemlist_ldjson(soup)
    if not itemlist:
        return []

    return _parse_itemlist(itemlist)


if __name__ == "__main__":
    print("### Trending Movies ###")
    trending_movies = get_trending_movies()
    for rank, (title, link, rating) in enumerate(trending_movies, start=1):
        print(f"{rank}. {title} → {link}, Rating {rating}")

    print("\n" + "#" * 40 + "\n")

    print("### Top 250 Movies ###")
    top_250_movies = get_top_250_movies()
    for rank, (title, link, rating) in enumerate(top_250_movies, start=1):
        print(f"{rank}. {title} → {link}, Rating {rating}")
