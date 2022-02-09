import json
import urllib.parse as url

from utils import requests

API_BASE_URL = "https://api.twitch.tv/helix"
CLIENT_ID = 'hehe no'
CLIENT_SECRET = 'no :)'
OAUTH_TOKEN = ''


class TwitchError(Exception):
    def __init__(self, message: str):
        super().__init__(message)


def request_headers():
    return {
        'Authorization': f'Bearer {OAUTH_TOKEN}',
        'Client-ID': CLIENT_ID
    }


async def refresh_access_token():
    global OAUTH_TOKEN

    req = await requests.post(f'https://id.twitch.tv/oauth2/token?client_id={CLIENT_ID}&client_secret={CLIENT_SECRET}&grant_type=client_credentials')

    if not req:
        raise TwitchError('Unable to refresh access token!')

    body = json.loads(req.decode())
    OAUTH_TOKEN = body['access_token']
    #expires_in


async def validate_request(req):
    if not req:
        return False

    if 'status' in req and req['status'] != 200:
        if req['status'] == 401:
            await refresh_access_token()
            raise TwitchError('Access token lifespan lapsed; regeneration requested. Try again later.')

        raise TwitchError(f'Request yielded invalid response with status {req["status"]}')


async def get_game_by_name(name: str):
    req = await requests.get(f'{API_BASE_URL}/games?name={url.quote(name)}', json=True, headers=request_headers(), always_return=True)
    if await validate_request(req) is False:
        return None

    if not req.get('data'):
        return None

    return req['data'][0]['id']


async def get_streams_by_game(game_id: str):
    req = await requests.get(f'{API_BASE_URL}/streams?game_id={game_id}', json=True, headers=request_headers(), always_return=True)
    if await validate_request(req) is False:
        return None

    return req['data']


async def get_user_info(username: str):
    req = await requests.get(f'{API_BASE_URL}/users?login={username}', json=True, headers=request_headers(), always_return=True)
    if await validate_request(req) is False:
        return None

    return req['data'][0] if 'data' in req else None


async def get_stream_info(user_id: str):
    req = await requests.get(f'{API_BASE_URL}/streams?user_id={user_id}', json=True, headers=request_headers(), always_return=True)
    if await validate_request(req) is False:
        return None

    return req['data'][0] if 'data' in req else None


async def get_game_info(game_id: str):
    req = await requests.get(f'{API_BASE_URL}/games?id={game_id}', json=True, headers=request_headers(), always_return=True)
    if await validate_request(req) is False:
        return None

    return req['data'][0] if 'data' in req else None
