import asyncio
import imghdr
import re
import secrets
import textwrap  # textwrap.fill (text, width (characters?))
from collections import Counter
from datetime import datetime
from functools import partial
from io import BytesIO
from random import choice, randint
from time import time

import discord
from discord.ext import commands

from bounded_pool_executor import BoundedProcessPoolExecutor
from PIL import Image, ImageColor, ImageDraw, ImageFont, ImageOps
from utils import graphics, parsers, pilext, requests, textutils
from utils.threadpool import ExecutionThreadPool
from utils.timer import Timer

color_rx = re.compile("([a-zA-Z0-9]{6})")
url_rx = re.compile("https?:\/\/(www\.)?.+\/\w+.[a-z]{2,6}", re.IGNORECASE)
processing_pool = ExecutionThreadPool(3)
executor_pool = BoundedProcessPoolExecutor(max_workers=10)


class Generators(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def get_url(self, ctx, target: str, fmt: str = None, size: int = 512):
        try:
            member = await commands.UserConverter().convert(ctx, target)
            url = str(member.avatar_url_as(size=size, format=fmt)).replace('webp', 'png')
        except commands.BadArgument:
            url = target.strip('<>')

        return url

    def proc_gif(self, _bytes, multiplier):
        result = self.bot.loop.create_future()
        im = Image.open(_bytes)

        frames = [None for _ in range(im.n_frames)]
        frame_durations = []

        def on_progress_update(ind, fut):
            frames[ind] = Image.open(fut.result()).convert('RGBA')
            done = sum(1 for f in frames if f is not None)

            if done == im.n_frames:
                gif_bytes = BytesIO()
                frames[0].save(gif_bytes, save_all=True, append_images=frames[1:], format='gif', loop=0, duration=frame_durations, disposal=2, optimize=False, transparency=255) # optimize=False, transparency=255
                gif_bytes.seek(0)

                pilext.close(im, *frames)
                result.set_result(gif_bytes)

        for i in range(0, im.n_frames):
            im.seek(i)
            frame_durations.append(im.info.get('duration', 1))
            b = pilext.to_bytes(im)
            task = executor_pool.submit(graphics.process_magik, b, multiplier)
            task.add_done_callback(partial(on_progress_update, i))

        return result

    @commands.command(aliases=['magic'])
    @commands.cooldown(1, 5, commands.BucketType.guild)
    async def magik(self, ctx, target = None, multiplier: float = 0.5):
        """ Content-aware scaling. """
        url = await self.get_url(ctx, target or ctx.author.mention)
        multi = max(min(parsers.as_number(multiplier, 0.5), 10), 0.5)

        if not url_rx.search(url):
            return await ctx.send('in what world does that look like a damn URL?')

        filesize_limit = 8 * 1000000
        headers = await requests.get_headers(url)

        if 'content-length' not in headers or int(headers['content-length']) > filesize_limit:
            return await ctx.send('The server didn\'t respond with a `content-length` header. To prevent abuse, this image will not be processed.')

        _bytes = BytesIO(await requests.get(url))
        img_format = imghdr.what(_bytes)

        if img_format not in ('gif', 'jpeg', 'bmp', 'png', 'webp'):
            return await ctx.send('Unsupported file format.')

        is_gif = _bytes.read(6) in (b'GIF89a', b'GIF87a')
        _bytes.seek(0)
        m = await ctx.send('Generating, this might take some time...') if is_gif else None

        fn = self.proc_gif if is_gif else graphics.process_magik
        res = await processing_pool.submit(fn, _bytes, multi)

        if isinstance(res, asyncio.Future):
            await res
            _bytes = res.result()
            _fname = secrets.token_urlsafe(8)

            with open(f'/home/devoxin/server/i/magik_{_fname}.gif', 'wb') as _file:
                _file.write(_bytes.read())

            _bytes.close()
            del _bytes

            await ctx.send(f'https://serux.pro/magik_{_fname}.gif')
        else:
            await ctx.send(file=discord.File(res, filename='magik.png'))

    @commands.command(name='invert')
    @commands.cooldown(1, 3, commands.BucketType.user)
    async def invert_(self, ctx, target):
        """ Ever wanted to see the stuff of nightmares? """
        url = await self.get_url(ctx, target, 'png')

        async with ctx.typing():
            with BytesIO() as bio:
                img = Image.open(BytesIO(await requests.get(url)))
                img = self.invert(img)
                img.save(bio, 'PNG')
                bio.seek(0)
                await ctx.send(file=discord.File(bio, filename='invert.png'))

    @commands.command()
    @commands.cooldown(1, 3, commands.BucketType.user)
    async def kills(self, ctx, target):
        """ an image so beautiful it will kill you if you look at it """
        url = await self.get_url(ctx, target, 'png', 1024)

        async with ctx.typing():
            with BytesIO() as bio:
                base = Image.open("assets/generators/kills/template.png").convert("RGBA")
                img = Image.open(BytesIO(await requests.get(url))).resize((1362, 1604))

                base.paste(img, (1161, 237))
                base.save(bio, 'PNG')
                bio.seek(0)
                await ctx.send(file=discord.File(bio, filename='invert.png'))


    @commands.command()
    async def preview(self, ctx, hexcode: str):
        """ Preview a colour (requires hex-code)
        Example: preview 0x0000FF or preview random """
        if hexcode.startswith('0x') or hexcode.startswith('#'):
            hexcode = hexcode.replace('0x', '').strip('#')

        is_random = hexcode == 'random'

        if not is_random:
            match = color_rx.match(hexcode)

        if not is_random and not match:
            return await ctx.send('Invalid hex-code specified.')

        rawcode = ("%06x" % randint(0x000000, 0xFFFFFF)) if is_random else match.group()

        try:
            rgb = ImageColor.getrgb(f'#{rawcode}')
        except ValueError:
            return await ctx.send("invalid hexxy boye")

        embed = discord.Embed(colour=int(rawcode, 16),
                              title="Colour Info",
                              description=f"**Hex:** #{rawcode}\n**RGB:** {rgb}")
        embed.set_thumbnail(url='https://serux.pro/colour?rgb={},{},{}'.format(*rgb))
        await ctx.send(embed=embed)

    @commands.command()
    @commands.cooldown(rate=1, per=2.0, type=commands.BucketType.user)
    async def facts(self, ctx, *, text: commands.clean_content(fix_channel_mentions = True)):
        """ Can't argue with facts! """
        if len(text) > 120:
            return await ctx.send("You need to specify text less than 120 characters long.")

        async with ctx.channel.typing():
            with BytesIO() as b:
                final_text = textwrap.fill(text, 22)

                base = Image.open("assets/generators/facts/template.jpg").convert("RGBA")
                txtO = Image.new("RGBA", base.size, (255, 255, 255, 0))
                font = ImageFont.truetype("assets/generators/facts/verdana.ttf", 20)

                canv = ImageDraw.Draw(txtO)
                canv.text((65, 400), final_text, font=font, fill="Black")

                txtO = txtO.rotate(-15, resample=Image.BICUBIC)

                out = Image.alpha_composite(base, txtO)

                out.save(b, "PNG")
                b.seek(0)
                await ctx.send(file=discord.File(b, filename="facts.png"))

    @commands.command()
    @commands.cooldown(rate=1, per=2.0, type=commands.BucketType.user)
    async def sign(self, ctx, *, text: commands.clean_content(fix_channel_mentions = True)):
        """ making creative command descriptions is hard tbh """
        if len(text) > 120:
            return await ctx.send(f'Sorry! Text needs to be less than 120 characters long. **({len(text)}/120)**')

        async with ctx.channel.typing():
            with BytesIO() as b:
                font = ImageFont.truetype("assets/generators/sign/verdana.ttf", 30)
                final_text = textutils.wrap(font, text, 330)

                lines = final_text.split('\n')
                l_adjust = 200 if len(lines) < 4 else 228

                base = Image.open("assets/generators/sign/template.png").convert("RGBA")
                txtO = Image.new("RGBA", base.size, (255, 255, 255, 0))

                canv = ImageDraw.Draw(txtO)
                canv.text((l_adjust, 200), final_text, font=font, fill="Black")

                txtO = txtO.rotate(12.5, resample=Image.BICUBIC)

                out = Image.alpha_composite(base, txtO)

                out.save(b, "PNG")
                b.seek(0)
                await ctx.send(file=discord.File(b, filename="sign.png"))

    @commands.command()
    @commands.cooldown(rate=1, per=2.0, type=commands.BucketType.user)
    async def calling(self, ctx, *, text: commands.clean_content(fix_channel_mentions = True)):
        """ Hello, police? I'd like to report some thots """
        if len(text) > 95:
            return await ctx.send("You need to specify text less than 95 characters long.")

        async with ctx.channel.typing():
            with BytesIO() as b:
                final_text = textwrap.fill(text, 33)

                base = Image.open("assets/generators/calling/template.jpg").convert("RGBA")
                txtO = Image.new("RGBA", base.size, (255, 255, 255, 0))
                font = ImageFont.truetype("assets/generators/calling/verdana.ttf", 35)

                canv = ImageDraw.Draw(txtO)
                canv.text((5, 5), final_text, font=font, fill="Black")

                out = Image.alpha_composite(base, txtO)

                out.save(b, "PNG")
                b.seek(0)
                await ctx.send(file=discord.File(b, filename="calling.png"))

    @commands.command()
    @commands.cooldown(rate=1, per=2.0, type=commands.BucketType.user)
    async def ohno(self, ctx, *, text: commands.clean_content(fix_channel_mentions = True)):
        """ For when that one guy says something incredibly stupid """
        if len(text) > 35:
            return await ctx.send("You need to specify text less than 35 characters long.")

        async with ctx.channel.typing():
            with BytesIO() as b:
                final_text = textwrap.fill(text, 20)

                base = Image.open("assets/generators/ohno/template.jpg").convert("RGBA")
                txtO = Image.new("RGBA", base.size, (255, 255, 255, 0))
                font = ImageFont.truetype("assets/generators/ohno/verdana.ttf", 25)

                canv = ImageDraw.Draw(txtO)
                canv.text((310, 30), final_text, font=font, fill="Black")

                out = Image.alpha_composite(base, txtO)

                out.save(b, "PNG")
                b.seek(0)
                await ctx.send(file=discord.File(b, filename="ohno.png"))

    @commands.command()
    @commands.cooldown(rate=1, per=2.0, type=commands.BucketType.user)
    async def skulls(self, ctx, *, text: commands.clean_content(fix_channel_mentions = True)):
        """ Lesser-intelligent being """
        if len(text) > 30:
            return await ctx.send("You need to specify text less than 30 characters long.")

        async with ctx.channel.typing():
            with BytesIO() as b:
                final_text = textwrap.fill(text, 13)

                base = Image.open("assets/generators/skulls/template.jpg").convert("RGBA")
                txtO = Image.new("RGBA", base.size, (255, 255, 255, 0))
                font = ImageFont.truetype("assets/generators/skulls/verdana.ttf", 24)

                canv = ImageDraw.Draw(txtO)
                canv.text((310, 410), final_text, font=font, fill="Black")

                out = Image.alpha_composite(base, txtO)

                out.save(b, "PNG")
                b.seek(0)
                await ctx.send(content=ctx.author.mention, file=discord.File(b, filename="skulls.png"))

    @commands.command()
    @commands.cooldown(rate=1, per=2.0, type=commands.BucketType.user)
    async def decide(self, ctx, *, text: commands.clean_content(fix_channel_mentions = True)):
        """ Decisions, decisions, decisions... """
        decisions = list(filter(None, text.strip().split('|')))

        if len(decisions) < 2:
            return await ctx.send('You need to give two decisions split by `|`')

        if len(decisions[0]) > 30 or len(decisions[1]) > 30:
            return await ctx.send('Decisions cannot be longer than 20 characters.')

        async with ctx.channel.typing():
            with BytesIO() as b:
                decisions[0] = textwrap.fill(decisions[0], 11).strip()
                decisions[1] = textwrap.fill(decisions[1], 10).strip()

                base = Image.open("assets/generators/decide/template.png").convert("RGBA")
                dec1 = ImageFont.truetype("assets/generators/decide/verdana.ttf", 20)
                dec2 = ImageFont.truetype("assets/generators/decide/verdana.ttf", 18)
                txt1 = Image.new("RGBA", base.size, (255, 255, 255, 0))
                txt2 = Image.new("RGBA", base.size, (255, 255, 255, 0))

                canv1 = ImageDraw.Draw(txt1)
                canv2 = ImageDraw.Draw(txt2)
                canv1.text((115, 65), decisions[0], font=dec1, fill="Black")
                canv2.text((300, 75), decisions[1], font=dec2, fill="Black")

                txt1 = txt1.rotate(13, resample=Image.BICUBIC)
                txt2 = txt2.rotate(12, resample=Image.BICUBIC)
                comp1 = Image.alpha_composite(base, txt1)
                out = Image.alpha_composite(comp1, txt2)

                out.save(b, "PNG")
                b.seek(0)
                await ctx.send(content=ctx.author.mention, file=discord.File(b, filename="decide.png"))

    @commands.command()
    @commands.cooldown(rate=1, per=2.0, type=commands.BucketType.user)
    async def history(self, ctx, *, text: commands.clean_content(fix_channel_mentions = True)):
        """ Sample text  """
        if len(text) > 15:
            return await ctx.send('You need to specify text less than 15 characters long.')

        async with ctx.channel.typing():
            with BytesIO() as b:
                final_text = text.replace('\n', ' ').upper()
                left_adjust = 150

                if len(final_text) > 5:
                    left_adjust = left_adjust - (15 * (len(final_text) - 5))

                base = Image.open("assets/generators/history/template.png").convert("RGBA")
                txtO = Image.new("RGBA", base.size, (255, 255, 255, 0))
                font = ImageFont.truetype("assets/generators/history/impact.ttf", 50)

                canv = ImageDraw.Draw(txtO)
                canv.text((left_adjust, 302), final_text, font=font, fill="White")

                out = Image.alpha_composite(base, txtO)

                out.save(b, "PNG")
                b.seek(0)
                await ctx.send(content=ctx.author.mention, file=discord.File(b, filename="mock.png"))

    @commands.command()
    async def radial(self, ctx, target, blur: int=10):
        if blur > 1000:
            return await ctx.send('<:huhh:514932599421009921> too much blur')

        url = await self.get_url(ctx, target, 'png')

        async with ctx.typing():
            img_bytes = await requests.get(url)
            rendered = await self.bot.loop.run_in_executor(executor_pool, graphics.process_radial, img_bytes, blur)

            b = BytesIO(rendered)
            b.seek(0)
            await ctx.send(file=discord.File(b, filename='radial.png'))

    @commands.command()
    async def srp(self, ctx):
        """ Displays your Spotify rich presence as an image. """
        if not ctx.author.activity or not isinstance(ctx.author.activity, discord.Spotify):
            return await ctx.send('You need to be listening to Spotify to use this.')

        rp = ctx.author.activity

        spotify_bytes = BytesIO(await requests.get('http://logos-download.com/wp-content/uploads/2016/08/Spotify_logo_black.png'))
        cover_bytes = BytesIO(await requests.get(rp.album_cover_url))

        spotify = Image.open(spotify_bytes).resize((100, 30), resample=Image.LANCZOS).convert('RGBA')
        cover = Image.open(cover_bytes).resize((190, 190), resample=Image.LANCZOS).convert('RGBA')

        dom_col = self.get_dominant(cover)
        should_invert = ((dom_col[0] * 0.299) + (dom_col[1] * 0.587) + (dom_col[2] * 0.114)) <= 64
        text_col = (255, 255, 255) if should_invert else (0, 0, 0)

        if should_invert:
            spotify = self.invert(spotify)

        font = ImageFont.truetype('assets/generators/srp/circular-black.ttf', 23)
        artist_font = font.font_variant(size=18)

        base = Image.new('RGBA', (500, 200), rp.colour.to_rgb())
        overlay = Image.new('RGBA', (490, 190), dom_col)

        #avg = int((dom_col[0] + dom_col[1] + dom_col[2]) / 3)
        #gradient = Image.new('L', (255, 1), color=avg)
        #alpha = 0
        #for x in range(255):
        #    gradient.putpixel((x, 0), alpha)
        #    alpha = min(255, alpha + 7)
        #gradient = gradient.resize(cover.size)
        #cover.putalpha(gradient)

        base.paste(overlay, (5, 5), overlay)
        base.paste(spotify, (10, 10), spotify)
        base.paste(cover, (305, 5), cover)

        title = textutils.wrap(font, rp.title, 290)
        artist = textutils.wrap(artist_font, ', '.join(rp.artists), 290)

        title_height = sum(map(lambda line: font.getsize(line)[1], title.split('\n')))
        a_offset = 55 + title_height

        canv = ImageDraw.Draw(base)
        canv.text((10, 45), title, font=font, fill=text_col)
        canv.text((10, a_offset), artist, font=artist_font, fill=text_col)

        b = BytesIO()
        base.save(b, 'png')
        b.seek(0)

        await ctx.send(content=f'**<https://open.spotify.com/track/{rp.track_id}>**',
                       file=discord.File(b, 'spotify.png'))

    def to_ms(self, dt):
        epoch = datetime.utcfromtimestamp(0)
        return (dt - epoch).total_seconds() * 1000.0

    def invert(self, img):
        if img.mode == 'RGBA':
            r, g, b, a = img.split()
            rgb_image = Image.merge('RGB', (r, g, b))
            inverted = ImageOps.invert(rgb_image)
            r, g, b = inverted.split()
            img = Image.merge('RGBA', (r, g, b, a))
        else:
            img = ImageOps.invert(img)

        return img

    def get_dominant(self, image):
        colour_bands = [0, 0, 0]

        for band in range(3):
            pixels = image.getdata(band=band)
            c = Counter(pixels)
            colour_bands[band] = c.most_common(1)[0][0]

        return tuple(colour_bands)

        # colour_tuple = [None, None, None]
        # for channel in range(3):
        #     # Get data for one channel at a time
        #     pixels = image.getdata(band=channel)
        #     values = []
        #     for pixel in pixels:
        #         values.append(pixel)
        #     colour_tuple[channel] = int(sum(values) / len(values))
        # return tuple(colour_tuple)


def setup(bot):
    bot.add_cog(Generators(bot))
