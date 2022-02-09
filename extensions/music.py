import inspect
import math
import re
from urllib.parse import quote

import discord
import lavalink
from discord.ext import commands
from lavalink.events import QueueEndEvent, TrackExceptionEvent, TrackStartEvent
from sources.spotify import SpotifyAudioTrack, SpotifySource
from utils import requests, textutils

url_rx = re.compile(r'https?:\/\/(?:www\.)?.+')


def sizeof_fmt(num, suffix='B'):
    for unit in ['', 'Ki', 'Mi', 'Gi', 'Ti', 'Pi', 'Ei', 'Zi']:
        if abs(num) < 1024.0:
            return f'{num:3.1f}{unit}{suffix}'
        num /= 1024.0
    return f'{num:.1f}Yi{suffix}'


class Music(commands.Cog):
    __slots__ = ('bot',)

    def __init__(self, bot):
        self.bot = bot

        if not hasattr(bot, 'lavalink'):
            bot.lavalink = lavalink.Client(bot.user.id)
            bot.lavalink.add_node('127.0.0.1', 42069, 'no', 'eu', name='no')
            bot.add_listener(bot.lavalink.voice_update_handler, 'on_socket_response')
            bot.lavalink.queue_dc = True

        bot.lavalink._event_hooks.clear()
        bot.lavalink.add_event_hooks(self)
        self.reload_sources()

    def reload_sources(self):
        self.bot.lavalink.sources.clear()
        self.bot.lavalink.register_source(SpotifySource('absolutely not', 'no way'))

    def is_playing(func):
        async def wrapper(*args, **kwargs):
            this, ctx, *_ = args
            player = this.bot.lavalink.player_manager.get(ctx.guild.id)

            if not player or not player.current:
                return await ctx.send('Not playing.')

            setattr(ctx, 'player', player)
            return await func(*args, **kwargs)

        setattr(wrapper, '__name__', func.__name__)
        setattr(wrapper, '__signature__', inspect.signature(func))
        return wrapper

    @commands.Cog.listener()
    async def on_socket_response(self, data):
        if not data or 't' not in data:
            return

        if data['t'] == 'VOICE_STATE_UPDATE' and int(data['d']['user_id']) == self.bot.user.id:
            g_id = int(data['d']['guild_id'])
            player = self.bot.lavalink.player_manager.get(g_id)

            if not data['d']['channel_id'] and player:
                await self.bot.lavalink.player_manager.destroy(g_id)

    async def cog_before_invoke(self, ctx):
        guild_check = ctx.guild is not None

        if guild_check:
            await self.ensure_voice(ctx)

        return guild_check

    async def cog_command_error(self, ctx, error):
        if isinstance(error, commands.CommandInvokeError):
            await ctx.send(error.original or str(error))

    @lavalink.listener(TrackStartEvent)
    async def on_track_start(self, event: TrackStartEvent):
        ch = event.player.fetch('channel')

        if isinstance(event.track, SpotifyAudioTrack):
            recomm = event.player.fetch('auto', [])

            if event.track.identifier not in recomm:
                recomm.append(event.track.identifier)

                if len(recomm) > 5:
                    recomm.pop(0)

            event.player.store('auto', recomm)

        if ch:
            await ch.send(embed=self.build_embed('Track Started', f'{event.track.title} - {event.track.author}'))

    @lavalink.listener(TrackExceptionEvent)
    async def on_track_exception(self, event: TrackExceptionEvent):
        event.player.repeat = False
        ch = event.player.fetch('channel')

        if ch:
            await ch.send(embed=self.build_embed('shiver me timbers', event.exception))

    @lavalink.listener(QueueEndEvent)
    async def on_queue_end(self, event: QueueEndEvent):
        if not self.bot.lavalink.queue_dc:
            return

        source = next((source for source in self.bot.lavalink.sources if isinstance(source, SpotifySource)), None)
        recomm = event.player.fetch('auto', [])

        if source and recomm:
            rec_track = await source.load_recommended(recomm)

            if rec_track:
                return await event.player.play(rec_track)

        guild_id = event.player.guild_id
        await self.connect_to(guild_id, None)

    def build_embed(self, title: str, description: str):
        return discord.Embed(colour=0x83B0B5, title=title, description=description)

    async def connect_to(self, guild_id: int, channel_id: str):
        """ Connects to the given voicechannel ID. A channel_id of `None` means disconnect. """
        guild = self.bot.get_guild(guild_id)
        await guild.change_voice_state(channel=guild.get_channel(channel_id))

    @commands.command(aliases=['p'])
    async def play(self, ctx, *, query: str):
        """ Searches and plays a song from a given query. """
        player = self.bot.lavalink.player_manager.players.get(ctx.guild.id)

        raw_query = query
        query = query.strip('<>')

        if not url_rx.match(query) and not query.startswith('spotify:'):
            query = f'spsearch:{query}'

        results = await self.bot.lavalink.get_tracks(query, check_local=True)

        if not results or not results.tracks:
            return await ctx.send(f'`{raw_query}` yielded no results.')

        if results.load_type == 'PLAYLIST_LOADED':
            tracks = results.tracks

            for track in tracks:
                player.add(requester=ctx.author.id, track=track)

            embed = self.build_embed('Playlist Enqueued!', f'{results.playlist_info.name} - {len(tracks)} tracks')
        else:
            track = results.tracks[0]
            embed = self.build_embed('Track Enqueued', f'[{track.title} - {track.author}]({track.uri})')
            player.add(requester=ctx.author.id, track=track)

        if not player.is_playing:
            player.store('channel', ctx.channel)
            await player.play()
        else:
            await ctx.send(embed=embed)

    @commands.command()
    @is_playing
    async def seek(self, ctx, *, seconds: int):
        """ Seeks to a given position in a track. (RELATIVE SEEKING) """
        track_time = max(0, ctx.player.position + (seconds * 1000))
        await ctx.player.seek(track_time)
        await ctx.send(f'Moved track to **{lavalink.utils.format_time(track_time)}**')

    @commands.command(aliases=['forceskip'])
    @is_playing
    async def skip(self, ctx):
        """ Skips the current track. """
        await ctx.player.skip()
        await ctx.send('⏭ | Skipped.')

    @commands.command()
    @is_playing
    async def stop(self, ctx):
        """ Stops the player and clears its queue. """
        ctx.player.fetch('auto', []).clear()
        ctx.player.queue.clear()
        await ctx.player.stop()
        await ctx.send('⏹ | Stopped.')

    @commands.command(aliases=['np', 'n', 'playing'])
    @is_playing
    async def now(self, ctx):
        """ Shows some stats about the currently playing song. """
        player = ctx.player
        position = lavalink.utils.format_time(player.position)
        duration = '🔴 LIVE' if player.current.stream else lavalink.utils.format_time(player.current.duration)
        fmt = f'{player.current.title} - {player.current.author}' \
            if isinstance(player.current, SpotifyAudioTrack) else player.current.title
        song = f'**[{fmt}]({player.current.uri})**\n({position}/{duration})'
        embed = discord.Embed(color=0x93B1B4, title='Now Playing', description=song)
        await ctx.send(embed=embed)

    @commands.command(aliases=['q'])
    async def queue(self, ctx, page: int = 1):
        """ Shows the player's queue. """
        player = self.bot.lavalink.player_manager.players.get(ctx.guild.id)

        if not player.queue:
            return await ctx.send('Nothing queued.')

        items_per_page = 10
        pages = math.ceil(len(player.queue) / items_per_page)

        start = (page - 1) * items_per_page
        end = start + items_per_page

        queue_list = ''
        queue_dur = 0
        for index, track in enumerate(player.queue[start:end], start=start):
            queue_list += f'`{index + 1}.` [**{track.title} - {track.author}**]({track.uri})\n'
            queue_dur += track.duration

        embed = discord.Embed(colour=0x93B1B4,
                              description=f'**{len(player.queue)} tracks**\n\n{queue_list}')
        embed.set_footer(text=f'Viewing page {page}/{pages} | Duration: {lavalink.utils.format_time(queue_dur)}')
        await ctx.send(embed=embed)

    @commands.command(aliases=['resume'])
    @is_playing
    async def pause(self, ctx):
        """ Pauses/Resumes the current track. """
        if ctx.player.paused:
            await ctx.player.set_pause(False)
            await ctx.send('⏯ | Resumed')
        else:
            await ctx.player.set_pause(True)
            await ctx.send('⏯ | Paused')

    @commands.command(aliases=['vol'])
    @is_playing
    async def volume(self, ctx, volume: int = None):
        """ Changes the player's volume (0-1000). """
        if not volume:
            return await ctx.send(f'🔈 | {ctx.player.volume}%')

        await ctx.player.set_volume(volume)  # Lavalink will automatically cap values between, or equal to 0-1000.
        await ctx.send(f'🔈 | Set to {ctx.player.volume}%')

    @commands.command()
    @is_playing
    async def shuffle(self, ctx):
        """ Shuffles the player's queue. """
        ctx.player.shuffle = not ctx.player.shuffle
        await ctx.send('🔀 | Shuffle ' + ('enabled' if ctx.player.shuffle else 'disabled'))

    @commands.command(aliases=['loop'])
    @is_playing
    async def repeat(self, ctx):
        """ Repeats the current song until the command is invoked again. """
        ctx.player.repeat = not ctx.player.repeat
        await ctx.send('🔁 | Repeat ' + ('enabled' if ctx.player.repeat else 'disabled'))

    @commands.command()
    async def remove(self, ctx, index: int):
        """ Removes an item from the player's queue with the given index. """
        player = self.bot.lavalink.player_manager.players.get(ctx.guild.id)

        if not player.queue:
            return await ctx.send('Nothing queued.')

        if index > len(player.queue) or index < 1:
            return await ctx.send(f'Index has to be **between** 1 and {len(player.queue)}')

        removed = player.queue.pop(index - 1)  # Account for 0-index.

        await ctx.send(f'Removed **{removed.title}** from the queue.')

    @commands.command()
    async def find(self, ctx, *, query):
        """ Lists the first 10 search results from a given query. """
        player = self.bot.lavalink.player_manager.players.get(ctx.guild.id)

        if not query.startswith(('ytsearch:', 'scsearch:', 'spotify:')):
            query = f'spsearch:{query}'

        results = await self.bot.lavalink.get_tracks(query, check_local=True)

        if not results or not results.tracks:
            return await ctx.send('Nothing found.')

        tracks = results.tracks[:10]  # First 10 results

        o = ''
        for index, track in enumerate(tracks, start=1):
            o += f'`{index}.` [{track.title} - {track.author}]({track.uri})\n'

        embed = discord.Embed(color=0x93B1B4, description=o)
        await ctx.send(embed=embed)

    @commands.command()
    @is_playing
    async def lyrics(self, ctx):
        """ Displays the lyrics for the current track. """
        player = ctx.player
        author = player.current.author.replace('- Topic', '')
        query = player.current.title + ' ' + author

        # if not (req := await requests.get(f'https://lyrics.tsu.sh/v1/raw?q={quote(query)}')):
        if not (req := await requests.get(f'https://evan.lol/lyrics/search/top?q={quote(query)}', json=True)):
            return await ctx.send('No lyrics found.')

        # for page in textutils.paginate(req.decode(), 1950):
        #     await ctx.send(f'```\n{page}```')

        embed = discord.Embed(colour=0x00fefe, title=f'Lyrics | {player.current.title} / {author}')
        for index, field in enumerate(textutils.paginate(req['lyrics'], 450), start=1):
            embed.add_field(name=f'[{index}]', value=field)

        await ctx.send(embed=embed)

    @commands.command(aliases=['dc'])
    async def disconnect(self, ctx):
        """ Disconnects the player from the voice channel and clears its queue. """
        player = self.bot.lavalink.player_manager.players.get(ctx.guild.id)

        if not player.is_connected:
            return await ctx.send('Not connected.')

        if not ctx.author.voice or (player.is_connected and ctx.author.voice.channel.id != int(player.channel_id)):
            return await ctx.send('You\'re not in my voicechannel!')

        player.queue.clear()
        await player.stop()
        await self.connect_to(ctx.guild.id, None)
        await ctx.send('*⃣ | Disconnected.')

    @commands.command(aliases=['ll'])
    async def lavalink(self, ctx):
        embed = discord.Embed(colour=0x00fefe, title='Lavalink Node Stats')

        for node in self.bot.lavalink.node_manager.nodes:
            stats = node.stats
            ud, uh, um, us = lavalink.utils.parse_time(stats.uptime)
            embed.add_field(
                name=node.name,
                value=f'Uptime: {ud:.0f}d {uh:.0f}h{um:.0f}m{us:.0f}s\n'
                      f'Players: {stats.players} ({stats.playing_players} playing)\n'
                      f'Memory: {sizeof_fmt(stats.memory_used)}/{sizeof_fmt(stats.memory_reservable)}\n'
                      'CPU:\n'
                      f'\u200b\tCores: {stats.cpu_cores}\n'
                      f'\u200b\tSystem Load: {stats.system_load * 100:.2f}%\n'
                      f'\u200b\tLavalink Load: {stats.lavalink_load * 100:.2f}%\n'
                      'Frames:\n'
                      f'\u200b\tSent: {stats.frames_sent}\n'
                      f'\u200b\tNulled: {stats.frames_nulled}\n'
                      f'\u200b\tDeficit: {stats.frames_deficit}\n'
                      f'Node Penalty: {stats.penalty.total:.2f}',
                inline=True
            )

        await ctx.send(embed=embed)

    async def ensure_voice(self, ctx):
        """ This check ensures that the bot and command author are in the same voicechannel. """
        player = self.bot.lavalink.player_manager.create(ctx.guild.id, endpoint=str(ctx.guild.region))
        # Create returns a player if one exists, otherwise creates.

        bypass = ctx.command.name in ('find', 'lavalink')
        should_connect = ctx.command.name in ('play')  # Add commands that require joining voice to work.

        if bypass:
            return True

        if not ctx.author.voice or not ctx.author.voice.channel:
            raise commands.CommandInvokeError('Join a voicechannel first.')

        if not player.is_connected:
            if not should_connect:
                raise commands.CommandInvokeError('Not connected.')

            permissions = ctx.author.voice.channel.permissions_for(ctx.me)

            if not permissions.connect or not permissions.speak:  # Check user limit too?
                raise commands.CommandInvokeError('I need the `CONNECT` and `SPEAK` permissions.')

            player.store('channel', ctx.channel.id)
            await self.connect_to(ctx.guild.id, ctx.author.voice.channel.id)
        else:
            if int(player.channel_id) != ctx.author.voice.channel.id:
                raise commands.CommandInvokeError('You need to be in my voicechannel.')


def setup(bot):
    bot.add_cog(Music(bot))
