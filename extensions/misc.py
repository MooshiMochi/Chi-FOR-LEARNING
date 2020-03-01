import urllib.parse as url
from base64 import b64encode
from datetime import datetime
from io import BytesIO
from random import choice, randint, sample, seed
from time import time

import discord
from bs4 import BeautifulSoup
from discord.ext import commands
from PIL import Image
from pytz import UnknownTimeZoneError, timezone

import pytesseract
from aiogoogletrans import Translator
from utils import cache, duckduckgo, pagination, parsers, requests

translator = Translator()
time_fmt = "%Y-%m-%dT%H:%M:%SZ"
tw_api = "https://api.twitch.tv/helix"
headers = {"Client-ID": "no"}
alphanumeric = [chr(i) for i in range(97, 123)] + [chr(i) for i in range(65, 90)] + [chr(i) for i in range(48, 57)]
alphabet = [chr(i) for i in range(97, 123)]


def escape_brackets(text: str):
    if not text:
        return ''

    return text.replace('[', '(').replace(']', ')')


def trim_end(text: str, limit: int):
    if len(text) > limit:
        return text[:limit] + '...'

    return text


class Misc(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    async def idek(self, ctx, *, text):
        words = text.split(' ')

        out = ''
        for word in words:
            val = 0
            for character in list(word):
                character = character.lower()

                if character not in alphabet:
                    continue

                if val == 0:
                    val = 1

                val *= (alphabet.index(character) + 1)

            if val != 0:
                out += f'{str(val)} '

        await ctx.send(out)

    @commands.command(aliases=['upreme'])
    async def supreme(self, ctx, *, trash: str):
        """ Supreme-style memes """
        embed = discord.Embed(colour=0xDE3F83, title='Su:b:reme')
        embed.set_image(url=f'https://api.alexflipnote.xyz/supreme?text={url.quote(trash)}')
        embed.set_footer(text='api.alexflipnote.xyz')
        await ctx.send(embed=embed)

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

    @commands.command()
    @commands.cooldown(rate=1, per=2.0, type=commands.BucketType.user)
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
        user_info = await requests.get(f'{tw_api}/users?login={streamer}', json=True, headers=headers)

        if not user_info['data']:
            return await ctx.send('Invalid streamer name.')

        user = user_info['data'][0]
        user_id = user['id']
        stream = await requests.get(f'{tw_api}/streams?user_id={user_id}', json=True, headers=headers)

        if not stream['data']:
            return await ctx.send(f'**{streamer}** isn\'t live.')

        stream = stream['data'][0]
        game_id = stream['game_id']
        start_time = stream['started_at']
        title = stream['title']
        viewers = 'viewer' if stream['viewer_count'] == 1 else 'viewers'

        game_info = await requests.get(f'{tw_api}/games?id={game_id}', json=True, headers=headers)
        game = game_info['data'][0]['name'] if game_info['data'] else 'Unknown'

        now = datetime.utcnow()
        then = datetime.strptime(start_time, time_fmt)
        time = parsers.time_string(now - then)

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

        results = await requests.get(f"{tw_api}/streams?game={url.quote(game)}", json=True, headers=headers)

        if not results or not results['data']:
            return await ctx.send("No streams found matching that game")

        results = results['data']

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

    @commands.command(hidden=True)
    async def slam(self, ctx):
        """ Shows now playing from Slam! Hardstyle radio station """
        res = await requests.get('https://live.slam.nl/slam-hardstyle/metadata/hardstyle_livewall', json=True)

        if not res:
            return await ctx.send('Unable to get now playing.')

        await ctx.send(f'{res["nowArtist"]} - {res["nowTitle"]}')

    @commands.command(aliases=['t'])
    async def translate(self, ctx, to: str, *, query: str):
        """ Translate text to another language! """
        try:
            result = await translator.translate(query, dest=to)
            await ctx.send(f'`[{result.src.upper()} -> {to.upper()}]` {result.text}')
        except Exception as e:
            await ctx.send('Unable to translate: ' + str(e))

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
        if len(text.replace(', ', ',').split(',')) < 2:
            return await ctx.send('You need to split your text with a comma.')

        async with ctx.typing():
            data = await requests.get(f'https://dankmemer.services/api/crab?text={text}', headers={'Authorization': 'no'})

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
        import re
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

    @commands.command()
    async def ocr(self, ctx, image_url: str):
        """ Identifies text within an image via OCR. """
        im_data = await requests.get(image_url)

        if not im_data:
            return await ctx.send('Invalid image.')

        img = Image.open(BytesIO(im_data))
        result = pytesseract.image_to_string(img)

        pages = pagination.paginate(result)

        for page in pages:
            await ctx.send(f'```\n{page}```')


def setup(bot):
    bot.add_cog(Misc(bot))
