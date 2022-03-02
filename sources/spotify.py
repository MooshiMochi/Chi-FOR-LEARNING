import re
from base64 import b64encode
from lavalink.models import DeferredAudioTrack, LoadResult, LoadType, PlaylistInfo, Source
from utils import requests

ARTIST_URI_REGEX = re.compile(r'^(?:https?://(?:open\.)?spotify\.com|spotify)([/:])artist\1([a-zA-Z0-9]+)')
TRACK_URI_REGEX = re.compile(r'^(?:https?://(?:open\.)?spotify\.com|spotify)([/:])track\1([a-zA-Z0-9]+)')
PLAYLIST_URI_REGEX = re.compile(r'^(?:https?://(?:open\.)?spotify\.com(?:/user/[a-zA-Z0-9_]+)?|spotify)([/:])playlist\1([a-zA-Z0-9]+)')


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

    @classmethod
    def from_items(cls, items):
        return list(map(cls.from_dict, items))

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
        return LoadResult(LoadType.SEARCH, SpotifyAudioTrack.from_items(res['tracks']['items']))

    async def _load_artist(self, artist_id: str):
        artist = await self._req_endpoint(f'artists/{artist_id}')
        top_tracks = await self._req_endpoint(f'artists/{artist_id}/top-tracks', query={'market': 'GB'})
        return LoadResult(LoadType.PLAYLIST, SpotifyAudioTrack.from_items(top_tracks['tracks']), PlaylistInfo(f'{artist["name"]}\'s Top Tracks'))

    async def _load_track(self, track_id: str):
        res = await self._req_endpoint(f'tracks/{track_id}')
        return LoadResult(LoadType.TRACK, [SpotifyAudioTrack.from_dict(res)])

    async def _load_playlist(self, playlist_id: str, offset: int = 0):
        playlist = await self._req_endpoint(f'playlists/{playlist_id}')
        tracks = await self._req_endpoint(f'playlists/{playlist_id}/tracks?offset={offset}')
        return LoadResult(LoadType.PLAYLIST,
                          SpotifyAudioTrack.from_items(map(lambda item: item['track'], tracks['items'])),
                          PlaylistInfo(playlist['name']))

    async def load_recommended(self, track_ids):
        res = await self._req_endpoint('recommendations', query={'seed_tracks': ','.join(track_ids), 'market': 'GB', 'limit': 1})
        return list(map(SpotifyAudioTrack.from_dict, res['tracks']))[0]

    async def load_item(self, client, query):
        if query.startswith('spsearch:'):
            return await self._load_search(query[9:])

        if (matcher := TRACK_URI_REGEX.match(query)):
            return await self._load_track(track_id=matcher.group(2))

        if (matcher := PLAYLIST_URI_REGEX.match(query)):
            return await self._load_playlist(playlist_id=matcher.group(2))

        if (matcher := ARTIST_URI_REGEX.match(query)):
            return await self._load_artist(artist_id=matcher.group(2))

        return None
