import requests
from bs4 import BeautifulSoup
import json
import imdb

def get_top_250_movies():
    url = "https://www.imdb.com/chart/top/"
    headers = {"User-Agent": "Mozilla/5.0"}
    resp = requests.get(url, headers=headers)
    soup = BeautifulSoup(resp.content, "html.parser")
    json_ld = soup.find("script", type="application/ld+json").string
    data = json.loads(json_ld)
    movies = [(item['item']['name'], item['item']['url']) for item in data['itemListElement']]

    return movies

def get_trending_movies():

    # URL of IMDb Most Popular Movies
    url = "https://www.imdb.com/chart/moviemeter/"
    headers = {"User-Agent": "Mozilla/5.0"}

    # Fetch page
    response = requests.get(url, headers=headers)
    soup = BeautifulSoup(response.content, "html.parser")

    # Find the JSON-LD script
    json_ld = soup.find("script", type="application/ld+json").string

    # Load JSON
    data = json.loads(json_ld)

    # Extract movie names + links in order
    movies = [(item['item']['name'], item['item']['url']) for item in data['itemListElement']]
    return movies

if __name__=='__main__':
    """
    trending_movies=get_trending_movies()
    for rank, (title, link) in enumerate(trending_movies, start=1):
        print(f"{rank}. {title} → {link}")
    """

    print('#'*25)
    top_250_movies=get_top_250_movies()
    for rank,(title,link) in enumerate(top_250_movies):
        print(f"{rank}. {title} -> {link}")