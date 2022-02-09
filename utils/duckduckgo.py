import json
import re
from urllib.parse import quote

import aiohttp
from bs4 import BeautifulSoup

_http = aiohttp.ClientSession()
_user_agent = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/98.0.4758.81 Safari/537.36'
_vqd_re = re.compile('vqd=([0-9-]+)\&')
_weather_re = re.compile('{.+}')


class SafeSearch:
    STRICT = (1, 'a')
    MODERATE = (-1, 'c')
    OFF = (-2, 'c')


class SearchResult:
    __slots__ = ('title', 'description', 'url')

    def __init__(self, title, description, url):
        self.title = title
        self.description = description
        self.url = url


async def get_vqd(query: str, safe=SafeSearch.OFF, timeout=30, proxy=None, locale='wt-wt'):
    async with _http.get(f'https://duckduckgo.com/?q={query}&ex=-2', timeout=timeout, proxy=proxy, headers={'User-Agent': _user_agent}) as search_page:
        body = await search_page.read()
        vqd = _vqd_re.search(body.decode())

        return vqd.group(1) if vqd else None


async def search(query: str, locale='uk-en', safe=SafeSearch.OFF, timeout=30, proxy=None):
    if not query:
        raise ValueError('query must be defined')

    async with _http.get(f'https://duckduckgo.com/html/?q={quote(query)}&kl={locale}&ex={safe[0]}',
                         timeout=timeout,
                         proxy=proxy,
                         headers={'User-Agent': _user_agent}) as page:

        p = await page.read()

        parse = BeautifulSoup(p, 'html.parser')
        ads = parse.findAll('div', attrs={'class': 'result--ad'}) or []

        for ad in ads:
            ad.decompose()

        results = parse.find_all('div', attrs={'class': 'result__body'})
        not_found = parse.find_all('div', attrs={'class': 'no-results'})

        res = []

        if not_found:
            return res

        for result in results:
            anchor = result.find('a')
            title = anchor.get_text()
            url = anchor.get('href')
            description = result.find(class_='result__snippet')
            description = 'No description available' if not description else description.get_text()
            sr = SearchResult(title, description, url)
            res.append(sr)

        return res


async def images(query: str, page=1, locale='wt-wt', safe=SafeSearch.OFF, timeout=30, proxy=None):
    if not query:
        raise ValueError('query must be defined')

    vqd = await get_vqd(quote(query))

    if not vqd:
        return []

    async with _http.get(f'https://duckduckgo.com/i.js?q={quote(query)}&l={locale}&o=json&f=,,,&p={page}&vqd={vqd}',
                         timeout=timeout,
                         proxy=proxy,
                         headers={'User-Agent': _user_agent}) as page:

        json = await page.json(content_type=None)

        if not json:
            return []

        res = [r['image'] for r in json['results']]
        return res


async def weather(query: str, timeout=30, proxy=None):
    if not query:
        raise ValueError('query must be defined')

    async with _http.get(f'https://duckduckgo.com/js/spice/forecast/{query}',
                         timeout=timeout,
                         proxy=proxy,
                         headers={'User-Agent': _user_agent}) as page:

        page_json = _weather_re.search((await page.read()).decode())

        if not page_json:
            return None

        return json.loads(page_json.group())


def _shutdown():
    _http.close()
