import asyncio
from rethinkdb import RethinkDB
from time import time
from utils import requests

r = RethinkDB()
connection = r.connect(db='serux')


async def get_rates(base: str):
    res = r.table('rates').get(base).run(connection)

    if not res or res['expires'] > time():
        res = await requests.get(f'https://api.exchangeratesapi.io/latest?base={base}', json=True, always_return=True)

        if 'error' in res:
            return res['error']

        r.table('rates').insert({
            'id': base,
            'expires': time() + 300,  # Update in 5 minutes
            **res['rates']
        }).run(connection)

        return res['rates']
    else:
        return res
