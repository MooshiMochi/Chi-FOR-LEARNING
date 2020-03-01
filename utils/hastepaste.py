from urllib.parse import quote

import aiohttp

_headers = {
    'User-Agent': 'Parallax (https://github.com/Devoxin/Parallax)',
    'Content-Type': 'application/x-www-form-urlencoded'
}


async def create(content: str):
    async with aiohttp.request('POST', 'https://hastepaste.com/api/create',
                               data=f'raw=false&text={quote(content)}', headers=_headers) as res:
        return await res.text() if res.status >= 200 and res.status < 400 else None
