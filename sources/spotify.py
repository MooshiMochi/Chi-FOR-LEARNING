import re
from base64 import b64encode
from lavalink.models import DeferredAudioTrack, LoadResult, LoadType, PlaylistInfo, Source
from utils import requests

TRACK_URI_REGEX = re.compile(r'^(?:https?://(?:open\.)?spotify\.com|spotify)([/:])track\1([a-zA-Z0-9]+)')


class LoadError(Exception):
    pass


class SpotifyAudioTrack(DeferredAudioTrack):
    @classmethod
    def from_dict(cls, metadata):
        return cls({
            'identifier': metadata['id'],
            'title': metadata['name'],
            'author': metadata['artists'][0]['name'],
            'length': metadata['duration_ms'],
            'uri': f'https://open.spotify.com/track/{metadata["id"]}',
            'isSeekable': True,
            'isStream': False
        }, requester=0)

    async def load(self, client):
        result = await client.get_tracks(f'ytmsearch:{self.title} {self.author}')

        if result.load_type != LoadType.SEARCH or not result.tracks:
            raise LoadError(result.load_type.value)

        b64 = result.tracks[0].track
        self.track = b64
        return b64


class SpotifySource(Source):
    def __init__(self, clId, clSec):
        super().__init__('spotify')
        self._creds = b64encode(f'{clId}:{clSec}'.encode()).decode()
        self._token = None

    async def _refresh_oauth(self):
        res = await requests.post('https://accounts.spotify.com/api/token',
                                  headers={'Authorization': f'Basic {self._creds}', 'Content-Type': 'application/x-www-form-urlencoded'},
                                  data={'grant_type': 'client_credentials'},
                                  json=True)

        if not res:
            raise LoadError('token refresh shidded pants')

        self._token = res['access_token']

    async def _req_endpoint(self, url, query=None, is_retry: bool = False):
        if not self._token:
            await self._refresh_oauth()

        base_req = requests.get(f'https://api.spotify.com/v1/{url}',
                                params=query,
                                headers={'Authorization': f'Bearer {self._token}'})
        res = await base_req.json()

        if not res:
            status = await base_req.status()

            if status == 401 and not is_retry:
                self._token = None
                return await self._req_endpoint(url, query, is_retry=True)

            raise LoadError('Spotify API did not return a valid response!')

        return res

    async def _load_search(self, query: str):
        res = await self._req_endpoint('search', query={'q': query, 'type': 'track', 'limit': 10})
        return list(map(SpotifyAudioTrack.from_dict, res['tracks']['items']))

    async def _load_track(self, track_id: str):
        res = await self._req_endpoint(f'tracks/{track_id}')
        return SpotifyAudioTrack.from_dict(res)

    async def load_recommended(self, track_ids):
        res = await self._req_endpoint('recommendations', query={'seed_tracks': ','.join(track_ids), 'limit': 1})
        return list(map(SpotifyAudioTrack.from_dict, res['tracks']))[0]

    async def load_item(self, client, query):
        if query.startswith('spsearch:'):
            spotify_tracks = await self._load_search(query[9:])

            if not spotify_tracks:
                return LoadResult(LoadType.SEARCH, spotify_tracks)

        if (matcher := TRACK_URI_REGEX.match(query)):
            track_id = matcher.group(2)
            spotify_track = await self._load_track(track_id)

            if spotify_track:
                return LoadResult(LoadType.TRACK, [spotify_track])

        return None
