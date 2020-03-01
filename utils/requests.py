import aiohttp
import asyncio

session = aiohttp.ClientSession()


async def get(url, json=False, always_return=False, *args, **kwargs):
    try:
        async with session.get(url, *args, **kwargs) as r:
            if r.status != 200 and not always_return:
                return None

            if json:
                return await r.json(content_type=None)

            return await r.read()

    except (aiohttp.ClientOSError, aiohttp.ClientConnectorError, asyncio.TimeoutError):
        return None


async def get_headers(url, *args, **kwargs):
    try:
        async with session.get(url, *args, **kwargs) as r:
            if r.status != 200:
                return {}

            return r.headers

    except (aiohttp.ClientOSError, aiohttp.ClientConnectorError, asyncio.TimeoutError):
        return None
