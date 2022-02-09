from time import time

from rethinkdb import RethinkDB
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

def check_blocked(user_id: int):
    return r.table('blocked') \
        .get(str(user_id)) \
        .coerce_to('bool') \
        .default(False) \
        .run(connection)

def set_blocked(user_id: int, block: bool):
    if block:
        r.table('blocked') \
            .insert({'id': str(user_id)}, conflict='replace') \
            .run(connection)
    else:
        r.table('blocked') \
            .get(str(user_id)) \
            .delete() \
            .run(connection)
