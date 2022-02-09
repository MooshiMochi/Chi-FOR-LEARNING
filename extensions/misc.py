import re
import urllib.parse as url
from asyncio import create_subprocess_shell
from asyncio.subprocess import PIPE
from base64 import b64encode
from datetime import datetime
from io import BytesIO
from random import choice, randint, sample, seed
from time import time

import discord
import pytesseract
import qrcode
from aiogoogletrans import Translator
from bs4 import BeautifulSoup
from discord.ext import commands
from PIL import Image
from pytz import UnknownTimeZoneError, timezone
from pyzbar import pyzbar
from utils import (cache, duckduckgo, requests, textutils, transcoder, twitch,
                   ziputil)

translator = Translator()
time_fmt = "%Y-%m-%dT%H:%M:%SZ"
tw_api = "https://api.twitch.tv/helix"
headers = {"Authorization": "Bearer hee hee", "Client-ID": "hee hee"}
alphanumeric = [chr(i) for i in range(97, 123)] + [chr(i) for i in range(65, 90)] + [chr(i) for i in range(48, 57)]
alphabet = [chr(i) for i in range(97, 123)]
sukk_my_kokk = 'hee hee'
file_formats = {
    'best': ('-f b', 'mp4', False, []),
    'mp4': ('-f 18', 'mp4', False, []),
    'webm': ('-f 251', 'webm', False, []),
    'webmvideo': ('-f bestvideo[ext=webm]+bestaudio[ext=webm]', 'webm', False, []),
    'mp3fucked': ('-f 251/bestaudio[ext=webm]/bestaudio/b', 'mp3', True, ['-b:a 8k']),
    'mp3mq': ('-f 251/bestaudio[ext=webm]/bestaudio/b', 'mp3', True, ['-b:a 128k']),
    'mp3hq': ('-f 251/bestaudio[ext=webm]/bestaudio/b', 'mp3', True, ['-b:a 192k']),
    'custom': ('-f b', '{}', True, [])
}


def escape_brackets(text: str):
    return text.replace('[', '(').replace(']', ')') if text else ''


def trim_end(text: str, limit: int):
    if len(text) > limit:
        return text[:limit] + '...'

    return text


class Misc(commands.Cog):
    __slots__ = ('bot',)

    def __init__(self, bot):
        self.bot = bot

    # @commands.command()
    # async def idek(self, ctx, *, text):
    #     words = text.split(' ')

    #     out = ''
    #     for word in words:
    #         val = 0
    #         for character in list(word):
    #             character = character.lower()

    #             if character not in alphabet:
    #                 continue

    #             if val == 0:
    #                 val = 1

    #             val *= (alphabet.index(character) + 1)

    #         if val != 0:
    #             out += f'{str(val)} '

    #     await ctx.send(out)

    @commands.command()
    async def avatar(self, ctx, nerd: discord.Member = None):
        url = str((nerd or ctx.author).avatar_url_as(static_format='png'))
        await ctx.send(url)

    @commands.command()
    async def trump(self, ctx):
        quote = await requests.get('https://api.whatdoestrumpthink.com/api/v1/quotes/random', json=True)
        await ctx.send(quote['message'])

    @commands.command()
    async def avatarthief(self, ctx):
        """ Gets the avatar of a random member in the server """
        member = choice(ctx.guild.members)
        embed = discord.Embed(colour=0xDE3F83, title=f'{member.name}\'s avatar')
        embed.set_image(url=member.avatar_url)
        await ctx.send(embed=embed)

    @commands.command()
    async def dog(self, ctx):
        """ Images of dogs! """
        res = None
        retries = 5

        while retries and (not res or res.lower().endswith('.mp4')):
            res = (await requests.get('https://random.dog/woof')).decode()
            retries -= 1

        embed = discord.Embed(colour=0xDE3F83)
        embed.set_image(url=f'https://random.dog/{res}')
        embed.set_footer(text='Powered by random.dog')
        await ctx.send(embed=embed)

    @commands.command()
    async def cat(self, ctx):
        """ Images of cats! """
        res = await requests.get('http://aws.random.cat/meow', json=True)

        if not res:
            return await ctx.send('Unable to contact API')

        embed = discord.Embed(colour=0xDE3F83)
        embed.set_image(url=res['file'])
        embed.set_footer(text='Powered by random.cat')
        await ctx.send(embed=embed)

    @commands.command(aliases=['ducc'])
    async def duck(self, ctx):
        """ Images of ducks! """
        res = await requests.get('https://random-d.uk/api/v1/quack', json=True)

        if not res:
            return await ctx.send('Unable to contact API')

        embed = discord.Embed(colour=0xDE3F83, title='QUACK! 🦆')
        embed.set_image(url=res['url'])
        embed.set_footer(text=res['message'])
        await ctx.send(embed=embed)

    @commands.command()
    async def gay(self, ctx):
        """ How gay!? """
        seed(ctx.author.id)
        await ctx.send(f'{ctx.author}, you\'re {randint(0, 100)}% gay!')

    # @commands.command()
    # @commands.cooldown(rate=1, per=2.0, type=commands.BucketType.user)
    async def fml(self, ctx):
        """ Posts a random story from fmylife """
        async with ctx.typing():
            r = await requests.get('http://www.fmylife.com/random')
            page = BeautifulSoup(r, 'html.parser')
            posts = page.find_all('p', class_='block hidden-xs')
            post = choice(posts).get_text().strip()
            await ctx.send(post)

    @commands.command()
    @commands.cooldown(rate=1, per=5.0, type=commands.BucketType.user)
    async def search(self, ctx, *, query: str):
        """ Searches DuckDuckGo for something (BETA) """
        async with ctx.typing():
            results = await duckduckgo.search(query, safe=duckduckgo.SafeSearch.STRICT)

            if not results:
                return await ctx.send('Nothing found ¯\\_(ツ)_/¯')

            em = discord.Embed(colour=0xDE3F83, description='')

            for result in results[:5]:
                em.description += f'[**{escape_brackets(result.title)}**]({result.url})\n{trim_end(result.description, 100)}\n\n'

            await ctx.send(embed=em)

    @commands.command()
    @commands.cooldown(rate=1, per=5.0, type=commands.BucketType.user)
    async def image(self, ctx, *, query: str):
        """ Returns the top image related to the query from DuckDuckGo """
        async with ctx.typing():
            results = await duckduckgo.images(query, safe=duckduckgo.SafeSearch.STRICT)

            if not results:
                return await ctx.send('Nothing found ¯\\_(ツ)_/¯')

            em = discord.Embed(colour=0xDE3F83)
            em.set_image(url=results[0])
            await ctx.send(embed=em)

    @commands.command()
    @commands.cooldown(rate=1, per=5.0, type=commands.BucketType.user)
    async def images(self, ctx, *, query: str):
        """ Returns a random image related to the query from DuckDuckGo """
        async with ctx.typing():
            results = await duckduckgo.images(query, safe=duckduckgo.SafeSearch.STRICT)

            if not results:
                return await ctx.send('Nothing found ¯\\_(ツ)_/¯')

            em = discord.Embed(colour=0xDE3F83)
            em.set_image(url=choice(results))
            await ctx.send(embed=em)

    @commands.command()
    @commands.cooldown(rate=1, per=5.0, type=commands.BucketType.user)
    async def weather(self, ctx, *, location: str):
        """ Displays the weather forecast for the given location """
        async with ctx.typing():
            result = await duckduckgo.weather(location)

            if not result:
                return await ctx.send('Nothing found.')

            area = result['flags']['ddg-location']
            current = result['currently']

            fahrenheit = current['temperature']
            celsius = round((fahrenheit - 32) * 0.5556)

            fl_fahrenheit = current['apparentTemperature']
            fl_celsius = round((fl_fahrenheit - 32) * 0.5556)

            wind_speed_mph = current['windSpeed']
            wind_speed_kmh = wind_speed_mph * 1.609

            minutely_summary = f'**Summary**: {result["minutely"]["summary"]}' if 'minutely' in result else ''
            icon = f'https://duckduckgo.com/assets/weather/png/80px/{current["icon"]}-alt.png'

            em = discord.Embed(colour=0xDE3F83,
                               title=area,
                               description=minutely_summary)
            #    description=f'**Forecast**: {current["summary"]}\n'
            #                f'**Temperature**: {fahrenheit}°F | {celsius}°C\n'
            #                f'**Feels Like**: {fl_fahrenheit}°F | {fl_celsius}°C\n'
            #                f'**Humidity**: {(current["humidity"] * 100):.0f}%\n\n'
            #                f'{minutely_summary}')
            em.add_field(name='Forecast', value=current['summary'], inline=True)
            em.add_field(name='Temperature', value=f'{fahrenheit}°F | {celsius}°C\nFeels like: {fl_fahrenheit}°F | {fl_celsius}°C', inline=True)
            em.add_field(name='Humidity', value=f'{(current["humidity"] * 100):.0f}%', inline=True)
            em.add_field(name='Wind Speed', value=f'{wind_speed_mph} mph | {wind_speed_kmh:.2f} kmh')
            em.set_footer(
                text=f'Timezone: {result["timezone"].replace("_", " ")}')
            em.set_thumbnail(url=icon)
            await ctx.send(embed=em)

    @commands.command()
    async def time(self, ctx, tz: str):
        """ Displays the time for the given timezone. """
        try:
            tz = timezone(tz)
        except UnknownTimeZoneError:
            await ctx.send('Invalid timezone')
        else:
            d = datetime.now(tz=tz)
            await ctx.send(d.strftime('%H:%M %d %B %Y'))

    @commands.command()
    async def tokenize(self, ctx, target: commands.MemberConverter() = None):
        """ Generates a random (fake) token """
        target_id = target.id if target else ctx.author.id
        token = b64encode(str(target_id).encode('utf-8')
                          ).decode('utf-8').strip('=') + '.'
        t = int(time() - 1293840000)
        b = t.to_bytes((t.bit_length() + 7) // 8, 'big') or b'\0'
        token += b64encode(b).decode('utf-8').strip('=') + '.'

        for i in range(27):
            token += choice(alphanumeric)

        await ctx.send(f'```\n{token}\n```')

    @commands.command()
    async def live(self, ctx, streamer: commands.clean_content):
        """ Check if a Twitch streamer is live! """
        if not (user := await twitch.get_user_info(streamer)):
            return await ctx.send('Invalid streamer name.')

        if not (stream := await twitch.get_stream_info(user['id'])):
            return await ctx.send(f'**{streamer}** isn\'t live.')

        game_id = stream['game_id']
        start_time = stream['started_at']
        title = stream['title']
        viewers = 'viewer' if stream['viewer_count'] == 1 else 'viewers'

        game_info = await twitch.get_game_info(game_id)
        game = game_info['name'] if game_info else 'Unknown'

        now = datetime.utcnow()
        then = datetime.strptime(start_time, time_fmt)
        time = textutils.time_string(now - then)

        embed = discord.Embed(colour=0xDE3F83,
                              title=f"{streamer}",
                              description=f'**[{title}](https://twitch.tv/{streamer})**\n\n'
                                          f'\👤 {stream["viewer_count"]} {viewers}\n'
                                          f'\🎮 {game}\n'
                                          f'\⏱ Streaming for {time}')
        embed.set_thumbnail(url=user['profile_image_url'])
        await ctx.send(embed=embed)

    @commands.command()
    async def streaming(self, ctx, game: str, language: str = None):
        """ Find streamers that are streaming the specified game! """
        if not (game_id := await twitch.get_game_by_name(game)):
            return await ctx.send('No games found with that name.')

        if not (results := await twitch.get_streams_by_game(game_id)):
            return await ctx.send("No streams found matching that game")

        if language:
            results = list(filter(lambda s: language.lower() in s.get('language', 'en').lower(), results))

            if not results:
                return await ctx.send("No streams found in that language")

        streams = sample(results, 5) if len(results) > 5 else results
        output = ""

        for s in streams:
            lang = s['language']
            streamer = s['user_name']
            viewers = s['viewer_count']
            streamurl = f'https://twitch.tv/{streamer}'

            output += f"[`[{lang.upper()}] 👤{viewers}` **{streamer}**]({streamurl})\n"

        embed = discord.Embed(colour=0xDE3F83,
                              title=f"Displaying {len(streams)}/{len(results)} results for {game}",
                              description=output)
        await ctx.send(embed=embed)

    # @commands.command(hidden=True)
    # async def slam(self, ctx):
    #     """ Shows now playing from Slam! Hardstyle radio station """
    #     res = await requests.get('https://live.slam.nl/slam-hardstyle/metadata/hardstyle_livewall', json=True)

    #     if not res:
    #         return await ctx.send('Unable to get now playing.')

    #     await ctx.send(f'{res["nowArtist"]} - {res["nowTitle"]}')

    @commands.command(aliases=['t'])
    async def translate(self, ctx, to: str, *, query: str):
        """ Translate text to another language! """
        return await ctx.send('google changed stuff and command went poopy, command now disabled :(((((((((((((((((((((')
        # try:
        #     result = await translator.translate(query, dest=to)
        #     await ctx.send(f'`[{result.src.upper()} -> {to.upper()}]` {result.text}')
        # except Exception as e:
        #     await ctx.send('Unable to translate: ' + str(e))

    @commands.command()
    async def rate(self, ctx, amount: float, from_: str, to: str):
        """ Convert from one currency to another """
        from_ = from_.upper()
        to = to.upper()

        res = await cache.get_rates(from_)

        if isinstance(res, str):
            return await ctx.send(f'An error occurred during the request:\n`{res}`')

        if to not in res:
            return await ctx.send(f'An error occurred during the request:\n`Base \'{to}\' is not supported.`')

        rate = float(res[to])
        total = rate * amount

        await ctx.send(f'**{amount:.2f} {from_} -> {total:.2f} {to}**')

    @commands.command()
    @commands.cooldown(rate=1, per=30, type=commands.BucketType.default)
    async def crab(self, ctx, *, text: str):
        """ Crab rave memes """
        splitterino = text.replace(', ', ',').split(',')
        if len(splitterino) < 2 or len(splitterino) > 2:
            return await ctx.send('You need to split your text with a comma. (And no more than 1 comma)')

        async with ctx.typing():
            data = await requests.get(f'https://dankmemer.services/api/crab?text={text}', headers={'Authorization': sukk_my_kokk})

            if not data:
                return await ctx.send('lol rip api')

            wrapped = BytesIO(data)
            await ctx.send(file=discord.File(wrapped, filename='crab.mp4'))

    @commands.command()
    async def display(self, ctx, url: str):
        """ Outputs a text file from a URL to the channel """
        try:
            d = await requests.get(url)
            await ctx.send(f'```\n{d.decode()}```')
        except Exception as e:
            await ctx.send(f'```\n{e}```')

    @commands.command(hidden=True)
    async def gensxcu(self, ctx):
        """ Generates a base ShareX Custom Uploader for accessing serux.pro """
        template = """
{
  "Name": "Serux.pro",
  "DestinationType": "ImageUploader",
  "RequestURL": "https://serux.pro/upload",
  "FileFormName": "file",
  "Headers": {
    "Authorization": "YOUR AUTH KEY"
  },
  "URL": "https://serux.pro/$json:path$"
}
"""
        encoded = template.encode()
        bytes_ = BytesIO(encoded)
        await ctx.send(file=discord.File(bytes_, filename="seruxpro.sxcu"))

    @commands.command()
    async def owoify(self, ctx, *, s: str):
        faces = ["(・`ω´・)", "OwO", "owo", "oωo", "òωó", "°ω°", "UwU", ">w<", "^w^"]
        face = choice(faces)
        patterns = [
            (r"(?:r|l)", "w"),
            (r"(?:R|L)", "W"),
            (r"n([aeiou])", r"ny\1"),
            (r"N([aeiou])", r"Ny\1"),
            (r"N([AEIOU])", r"NY\1"),
            (r"ove", "uv"),
            (r"!+", face),
        ]

        for pattern, replacement in patterns:
            s = re.sub(pattern, replacement, s)

        await ctx.send(s)

    @commands.command(hidden=True)
    async def augustify(self, ctx, *, s: str):
        s = re.sub(r'(u+|o+|U+|O+)', r'\1w\1', s)
        await ctx.send(s)

    @commands.command(aliases=['smts'])
    @commands.is_owner()
    async def sendmethisshit(self, ctx, track_id: str, fmt: str = 'best', *encoder_args: str):
        """ why are you snooping fam

        best/mp4/webm/webmvideo/mp3fucked/mp3mq/mp3hq/custom
        """
        fmt_first, *extra = fmt.split(':') if track_id not in file_formats else [track_id]
        if fmt_first == 'custom' and not extra:
            return await ctx.send('You must specify a container format when using the custom option, e.g. `custom:webm`')

        if track_id in file_formats:
            player = self.bot.lavalink.player_manager.get(ctx.guild.id)

            if not player or not player.current:
                return await ctx.send('Not playing.')

            video_id, file_name = f'ytsearch:{player.current.title} {player.current.author}', player.current.title
        else:
            video_id, *filename = track_id.split(',')
            file_name = filename[0] if filename else video_id

        fmt_flag, fmt_ext, fmt_reenc, fmt_encargs = file_formats.get(fmt_first, (None, None, None, None))
        fmt_ext = fmt_ext.format(extra[0]) if extra else fmt_ext

        if not fmt_flag:
            return await ctx.send('best/mp4/webm/webmvideo/mp3fucked/mp3mq/mp3hq/custom')

        m = await ctx.send('<a:processing:620018387380207662> Processing...')
        proc = await create_subprocess_shell(f'yt-dlp --quiet "{video_id.strip("<>")}" {fmt_flag} -o -', stdin=None, stderr=PIPE, stdout=PIPE)
        out, err = await proc.communicate()

        if not out and not err:
            return await m.edit(content='Processing error!')

        if out:
            if fmt_reenc or encoder_args:
                if fmt_ext == 'mp4':
                    return await m.edit(content='__Transcode error!__\nDue to the nature of the MP4 container, mp4 transcoding is unsupported!')
                await m.edit(content='<a:processing:620018387380207662> Transcoding...')
                print('re-encoding')
                b = BytesIO(await transcoder.transcode(out, fmt_ext, fmt_encargs + list(encoder_args)))
            else:
                b = BytesIO(out)
            try:
                await ctx.send(file=discord.File(b, f'{file_name}.{fmt_ext}'))
            except discord.HTTPException as e:
                if e.status == 413:
                    await ctx.send('big big chungus big chungus big chungus')
                else:
                    await ctx.send(e.text)
            else:
                await m.delete()

        if err and not 'YoutubeSearchIE' in err.decode():
            pages = textutils.paginate(err.decode(), 1950)
            for page in pages:
                await ctx.send(f"```bash\n{page}\n```")

    @commands.command()
    async def ocr(self, ctx, image_url: str):
        """ Identifies text within an image via OCR. """
        im_data = await requests.get(image_url)

        if not im_data:
            return await ctx.send('Invalid image.')

        img = Image.open(BytesIO(im_data))
        result = pytesseract.image_to_string(img, config=r'--psm 6')

        pages = textutils.paginate(result)

        for page in pages:
            await ctx.send(f'```\n{page}```')

    @commands.command(aliases=['je', 'jumboify', 'splitemoji', 'split'])
    async def jumbomoji(self, ctx, image_url: str, filename_prefix: str, h_parts: int = 3, v_parts: int = 2):
        """
        Converts an image into several smaller images consisting of <#parts>.

        h_parts: int - How many columns of images to produce (horizontal).
        v_parts: int - How many rows of images to produce (vertical).
        """
        im_data = await requests.get(image_url)

        if not im_data:
            return await ctx.send('Invalid image.')

        img = Image.open(BytesIO(im_data))
        w, h = img.size

        segment_w = w // h_parts
        segment_h = h // v_parts

        image_sections = []

        for row in range(v_parts):
            for column in range(h_parts):
                segment_x, segment_y = (segment_w * column, segment_h * row)
                section = BytesIO()

                img.crop((segment_x, segment_y, segment_x + segment_w, segment_y + segment_h)).save(section, format='png')
                image_sections.append((f'{filename_prefix}{len(image_sections) + 1}.png', section))

        zip_file = ziputil.make_zip(image_sections)
        zip_file.seek(0)
        await ctx.send(file=discord.File(zip_file, 'emojis.zip'))

    @commands.command()
    async def qrmake(self, ctx, text: str):
        """ Make your very own QR code! """
        qr_code = qrcode.make(text) \
            .convert('RGB') \
            .resize((150, 150))

        bio = BytesIO()
        qr_code.save(bio, 'png')
        bio.seek(0)
        return await ctx.send(file=discord.File(bio, 'qr.png'))

    @commands.command()
    async def qrread(self, ctx, image_url: str):
        """ Read a QR code. """
        im_data = await requests.get(image_url)

        if not im_data:
            return await ctx.send('Invalid image.')

        img = BytesIO(im_data)
        qr = pyzbar.decode(Image.open(img))

        if not qr:
            return await ctx.send('QR decode failed.')

        await ctx.send(f"__`QR read by {str(ctx.author)} at {datetime.now().strftime('%H:%M:%S %d/%m/%y')}`__\n{qr[0].data.decode('ascii')}")

    @commands.command()
    async def rainbow(self, ctx, *, text: str):
        s = '```ansi\n'

        for chr in list(text):
            s += getattr(textutils.AnsiFormat, choice(textutils.AnsiFormat._COLOURS))(chr)

        s += '```'

        await ctx.send(s)

    @commands.command(hidden=True, aliases=['recolor', 'rc'], description='we do a little trolling')
    @commands.cooldown(1, 3, commands.BucketType.guild)
    @commands.has_role(825135268994220055)
    async def recolour(self, ctx):
        r = next((r for r in ctx.guild.roles if r.name == 'rainbow'), None)

        if not r:
            return await ctx.send('devoxin delete role????')

        col = randint(0x000000, 0xffffff)
        await ctx.send(f'New role colour: {col}')
        await r.edit(colour=col)


def setup(bot):
    bot.add_cog(Misc(bot))
