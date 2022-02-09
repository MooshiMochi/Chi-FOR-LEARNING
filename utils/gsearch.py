import aiohttp
from bs4 import BeautifulSoup

_http = aiohttp.ClientSession()
_user_agent = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/64.0.3282.186 Safari/537.36'
_google_search = 'https://google.co.uk/search?q='


class SearchResult:
    __slots__ = ('title', 'description', 'url')

    def __init__(self, title, description, url):
        self.title = title
        self.description = description
        self.url = url


async def search(query: str, safe='off', timeout=30, proxy=None):
    if not query:
        raise ValueError('query must not be none or empty')

    async with _http.get(_google_search + query + 'safe=' + safe,
                         timeout=timeout,
                         proxy=proxy,
                         headers={'User-Agent': _user_agent}) as page:

        p = await page.read()

        parse = BeautifulSoup(p, 'html.parser')
        results = parse.findAll('div', attrs={'class': 'rc'})

        res = []

        for result in results:
            anchor = result.find('a')
            title = anchor.get_text()
            url = anchor.get('href')
            description = result.find(class_='st').get_text()
            sr = SearchResult(title, description, url)
            res.append(sr)

        return res


async def _shutdown():
    await _http.close()
