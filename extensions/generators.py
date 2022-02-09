import asyncio
import imghdr
import os
import re
import secrets
import textwrap  # textwrap.fill (text, width (characters?))
import warnings
from asyncio import create_subprocess_shell
from asyncio.subprocess import PIPE
from collections import Counter
from datetime import datetime
from functools import partial
from io import BytesIO
from random import choice, randint
from time import time

import discord
import qrcode
from bounded_pool_executor import BoundedProcessPoolExecutor
from discord.ext import commands, tasks
from lavalink.utils import format_time
from PIL import (Image, ImageColor, ImageDraw, ImageEnhance, ImageFilter,
                 ImageFont, ImageOps)
from utils import graphics, piltext, requests, textutils
from utils.glyph import TTFTool
from utils.threadpool import ExecutionThreadPool

color_rx = re.compile("([a-zA-Z0-9]{6})")
url_rx = re.compile("https?:\/\/(www\.)?.+\/\w+.[a-z]{2,6}", re.IGNORECASE)
processing_pool = ExecutionThreadPool(3)
executor_pool = BoundedProcessPoolExecutor(max_workers=10)
fucking_weebs = (
    'Unexpected item in bagging area',
    'PogChamp',
    'Bro you wanna buy some NFTs?',
    'I just shit my pants',
    'HAH! WEEB!',
    'Can\'t display that, nope',
    'hello? is this thing on?',
    'go sub to my onlyfans :3',
    'do you even understand the words?',
    'ram ranch is better',
    'based LOL'
    )

warnings.simplefilter('error', Image.DecompressionBombWarning)


def sizeof_fmt(num, suffix='B'):
    for unit in ['', 'Ki', 'Mi', 'Gi', 'Ti', 'Pi', 'Ei', 'Zi']:
        if abs(num) < 1024.0:
            return f'{num:3.1f} {unit}{suffix}'
        num /= 1024.0
    return f'{num:.1f} Yi{suffix}'


def to_bytes(im, fmt: str = 'png'):
    bio = BytesIO()
    im.save(bio, fmt)
    bio.seek(0)
    return bio


def close_all(frames):
    for frame in frames:
        frame.close()
        frame = None


class Generators(commands.Cog):
    __slots__ = ('bot',)

    def __init__(self, bot):
        self.bot = bot

    async def get_url(self, ctx, target: str, fmt: str = None, size: int = 512, fs_limit: int = -1):
        try:
            member = await commands.UserConverter().convert(ctx, target)
            url = str(member.avatar_url_as(size=size, format=fmt)).replace('webp', 'png')
        except commands.BadArgument:
            url = target.strip('<>')

        if url[:27] == 'https://cdn.discordapp.com/':
            headers = await requests.get(url).headers()

            if 'content-length' not in headers:
                return url

            if fs_limit > -1 and int(headers['content-length']) > fs_limit:
                if size == 128:
                    return url

                return await self.get_url(ctx, target, fmt=fmt, size=size // 2, fs_limit=fs_limit)

        return url

    def proc_gif(self, x, _bytes, multiplier):
        result = self.bot.loop.create_future()

        with Image.open(_bytes) as im:
            frames = [None] * im.n_frames
            frame_durations = []

            def magik_finish(index, buffer, future):
                buffer.close()

                with future.result() as processed:
                    frames[index] = Image.open(processed).convert('RGBA')

                processed_frames = sum(1 for f in frames if f is not None)
                x[0] = processed_frames
                x[1] = im.n_frames

                if processed_frames == im.n_frames:
                    gif_bytes = BytesIO()
                    frames[0].save(gif_bytes, save_all=True, append_images=frames[1:], format='gif', loop=0, duration=frame_durations, disposal=2, optimize=False, transparency=255)

                    gif_bytes.seek(0)
                    close_all(frames)

                    result.set_result(gif_bytes)

            for i in range(0, im.n_frames):
                im.seek(i)
                frame_durations.append(im.info.get('duration', 1))
                b = to_bytes(im)
                task = executor_pool.submit(graphics.process_magik, None, b, multiplier)
                task.add_done_callback(partial(magik_finish, i, b))

        return result

    @commands.command(aliases=['magic'])
    @commands.max_concurrency(1, commands.BucketType.guild)
    async def magik(self, ctx, target = None, multiplier: float = 0.5):
        """ Content-aware scaling. """
        filesize_limit = 1048576 * 10  # 10 MB

        url = await self.get_url(ctx, target or ctx.author.mention, fs_limit=filesize_limit)
        multi = min(max(multiplier, 0.5), 10)
        bypass = ctx.author.id in (180093157554388993,)

        if not url_rx.search(url):
            return await ctx.send('in what world does that look like a damn URL?')

        pixel_limit = 4_000_000
        headers = await requests.get_headers(url)

        if 'content-length' not in headers and not bypass:
            return await ctx.send('The server didn\'t respond with a `content-length` header. To prevent abuse, this image will not be processed.')

        con_len = int(headers['content-length'])
        if con_len > filesize_limit and not bypass:
            return await ctx.send(f'Max file size is {sizeof_fmt(filesize_limit)} (your file is {sizeof_fmt(con_len)} | {con_len})')

        image_data = await requests.get(url)
        img_header = image_data[:6]
        is_gif = img_header in (b'GIF89a', b'GIF87a')

        _bytes = BytesIO(image_data)
        img_format = imghdr.what(_bytes)
        _bytes.seek(0)

        if img_format not in ('gif', 'jpeg', 'bmp', 'png', 'webp') and not img_header[:3] == b'\xff\xd8\xff':  # jpg
            return await ctx.send('Unsupported file format.')

        if graphics.check_decompression_bomb(image_data):
            return await ctx.send('The provided image is a decompression bomb. Processing will not proceed.')

        with Image.open(_bytes) as img_test:
            w, h = img_test.size
            if w * h > pixel_limit and not bypass:
                return await ctx.send(f'Image resolution is too high! Cannot be more than {pixel_limit} pixels.')
            _bytes.seek(0)

        m = await ctx.send('Generating, this might take some time...') if is_gif else None

        stuff = [0, 0, 0]
        stuff.append(m)

        @tasks.loop(seconds=3.0)
        async def update_m():
            if stuff[0] > stuff[2]:
                # if stuff[3].channel.last_message_id != stuff[3].id:
                #     stuff[3] = await stuff[3].channel.send(f'{stuff[0]}/{stuff[1]} frames processed.')
                # else:
                await stuff[3].edit(content=f'{stuff[0]}/{stuff[1]} frames processed.')
                stuff[2] = stuff[0]

        update_m.start()

        fn = self.proc_gif if is_gif else graphics.process_magik
        try:
            res = await processing_pool.submit(fn, stuff, _bytes, multi)
        finally:
            update_m.stop()

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
            await ctx.send(content=ctx.author.mention, file=discord.File(res, filename='magik.png'))
            res.close()
            del res

    @commands.command(aliases=['print'])
    async def printer(self, ctx, target = None):
        """ image to ascii tbh """
        url = await self.get_url(ctx, target or ctx.author.mention, fmt='png')

        if not url_rx.search(url):
            return await ctx.send('in what world does that look like a damn URL?')

        resp = await requests.get(f'http://127.0.0.1:7080/printer?url={url}', always_return=True)
        
        if not resp:
            return await ctx.send('sorry api dead')

        content = resp.decode().replace('\r\n', '\n')

        if len(content) > 1990:
            return await ctx.send('too big 👀')

        lines = '\n'.join([l for l in content.splitlines() if not re.match(r'^\s*$', l)])
        await ctx.send(f'```\n{lines}```')

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
                final_text = piltext.wrap(font, text, 330)

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

    @commands.command(aliases=['rp', 'sp'])
    async def srp(self, ctx, flag: str = None):
        """
        Displays your Spotify rich presence as an image. 

        Pass '--qr' for a scannable QR code.
        """
        rp = next((spotify for spotify in ctx.author.activities if isinstance(spotify, discord.Spotify)), None)

        if not rp:
            return await ctx.send('You need to be listening to Spotify to use this.')

        if flag is not None:
            if flag == '--qr':
                qr_code = qrcode.make(f'spotify:track:{rp.track_id}') \
                    .convert('RGB') \
                    .resize((150, 150))

                bio = BytesIO()
                qr_code.save(bio, 'png')
                bio.seek(0)
                return await ctx.send(file=discord.File(bio, 'qr.png'))
            else:
                return await ctx.send('Valid flags are `--qr`.')

        ##### ASSETS #####
        spotify = Image.open('assets/generators/srp/spotify.png').resize((100, 30), resample=Image.LANCZOS).convert('RGBA')
        cover_bytes = BytesIO(await requests.get(rp.album_cover_url))
        big_cover = Image.open(cover_bytes).convert('RGBA')
        back_cover = big_cover.resize((500, 500), resample=Image.LANCZOS)

        back_cover = back_cover.filter(ImageFilter.GaussianBlur(radius=5))
        back_cover = ImageEnhance.Brightness(back_cover).enhance(0.5)

        cover = big_cover.resize((170, 170), resample=Image.LANCZOS)

        font = ImageFont.truetype('assets/generators/srp/circular-black.ttf', size=22)
        artist_font = font.font_variant(size=16)

        ##### COLOURS #####
        dom_col = self.get_dominant(back_cover)
        should_invert = ((dom_col[0] * 0.299) + (dom_col[1] * 0.587) + (dom_col[2] * 0.114)) <= 128  # 64
        text_col = (255, 255, 255) if should_invert else (0, 0, 0)

        #await ctx.send(((dom_col[0] * 0.299) + (dom_col[1] * 0.587) + (dom_col[2] * 0.114)))

        if should_invert:
            spotify = self.invert(spotify)

        base = Image.new('RGBA', (490, 190), dom_col)  # rp.colour.to_rgb()

        self.mask_rounded(cover, 0, 7)
        self.mask_rounded(base, 10, 10)

        # avg = int((dom_col[0] + dom_col[1] + dom_col[2]) / 3)
        # gradient = Image.new('L', (190, 1), color=avg)
        # alpha = 0
        # for x in range(180):
        #    gradient.putpixel((x, 0), alpha)
        #    alpha = min(255, alpha + 7)
        # gradient = gradient.resize(cover.size)
        # cover.putalpha(gradient)

        base.paste(back_cover, (0, -125), back_cover)
        base.paste(spotify, (375, 145), spotify)
        base.paste(cover, (10, 10), cover)

        font = piltext.font_auto_scale(font=font, text=rp.title, desired_width=285, size_min=19, size_max=24)
        artist_font = piltext.font_auto_scale(font=font, text=', '.join(rp.artists), desired_width=290, size_min=12, size_max=17)

        title = piltext.wrap(font, rp.title, 285)
        artist = piltext.wrap(artist_font, ', '.join(rp.artists), 290)

        title_height = sum(map(lambda line: font.getsize(line)[1], title.split('\n')))
        a_offset = 20 + title_height

        canv = ImageDraw.Draw(base)
        canv.text((195, 10), title, font=font, fill=text_col)
        #canv.text((195, 55), title, font=font, fill=text_col)
        canv.text((195, a_offset), artist, font=artist_font, fill=text_col)
        #canv.text((195, a_offset), artist, font=artist_font, fill=text_col)

        b = BytesIO()
        base.save(b, 'png')
        b.seek(0)

        await ctx.send(content=f'**<https://open.spotify.com/track/{rp.track_id}>**',
                       file=discord.File(b, 'spotify.png'))

    def mask_rounded(self, img, offset: int = 0, radius: int = 0):
        img_mask = Image.new('L', img.size, 0)
        mask = ImageDraw.Draw(img_mask)
        mask.rounded_rectangle((offset, offset, img_mask.width - offset, img_mask.height - offset), radius=radius, fill=255)
        img.putalpha(img_mask)

    def mask_ellipsis(self, img, offset: int = 0):
        img_mask = Image.new('L', img.size, 0)
        mask = ImageDraw.Draw(img_mask)
        mask.ellipse((offset, offset, img_mask.width - offset, img_mask.height - offset), fill=255)
        img.putalpha(img_mask)

    def get_dominant(self, image, average = False):
        colour_bands = [0, 0, 0]

        if average:
            colour_tuple = [None, None, None]

            for channel in range(3):
                # Get data for one channel at a time
                pixels = image.getdata(band=channel)
                values = []
                for pixel in pixels:
                    values.append(pixel)
                colour_tuple[channel] = int(sum(values) / len(values))
            return tuple(colour_tuple)
        else:
            for band in range(3):
                pixels = image.getdata(band=band)
                c = Counter(pixels)
                colour_bands[band] = c.most_common(1)[0][0]

            return tuple(colour_bands)

    def get_brightness(self, image) -> int:
        dom_col = self.get_dominant(image)
        return (dom_col[0] * 0.299) + (dom_col[1] * 0.587) + (dom_col[2] * 0.114)

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

    @commands.command(aliases=['scd'])
    async def snapchatdog(self, ctx, target):
        key_hee = 'no hoe'
        url = await self.get_url(ctx, target, 'png')
        img = await requests.post('https://api.pxlapi.dev/snapchat/dog',
                                  headers={'Authorization': 'Application ' + key_hee, 'Content-Type': 'application/json'},
                                  json={'images': [url]})
        if not img:
            return await ctx.send('No response, make sure the target\'s face is clear, and that their many chins aren\'t getting in the way.')
        b = BytesIO(img)
        b.seek(0)
        await ctx.send(file=discord.File(b, 'dog.png'))

    @commands.command()
    async def nice(self, ctx, *, text: str):
        """ anime tiddies  """
        if len(text) > 25:
            return await ctx.send('You need to specify text less than 25 characters long.')

        async with ctx.channel.typing():
            with BytesIO() as b:
                final_text = text.replace('\n', ' ').upper()

                base = Image.open("assets/nice.png").convert("RGBA")
                txtO = Image.new("RGBA", base.size, (255, 255, 255, 0))
                font = ImageFont.truetype("assets/wildwords.ttf", 32)
                scaled_font = piltext.font_auto_scale(font, final_text, 335, 22, 32)

                height_adjust = 2 if scaled_font.size <= 27 else 0

                canv = ImageDraw.Draw(txtO)
                canv.text((210, 136 + height_adjust), final_text, font=scaled_font, fill=(48, 48, 48))
                txtO = txtO.rotate(10.5, resample=Image.BICUBIC).filter(ImageFilter.BoxBlur(0.5))

                base.alpha_composite(txtO)

                base.save(b, "PNG")
                b.seek(0)
                await ctx.send(content=ctx.author.mention, file=discord.File(b, filename="mock.png"))

    @commands.command(aliases=['sus'])
    @commands.cooldown(1, 3, commands.BucketType.guild)
    async def us(self, ctx, target_or_image = None):
        url = await self.get_url(ctx, target_or_image or ctx.author.mention)

        if not url_rx.search(url):
            return await ctx.send('in what world does that look like a damn URL?')

        url = url.replace('"', '').replace('\'', '')
        img = await requests.get(url)
        fn = f'{abs(hash(img))}{str(time()).replace(".", "")}'

        with open(f'{fn}.png', 'wb') as f:
            f.write(img)
            f.close()

        proc = await create_subprocess_shell(f'ffmpeg -v error -loop 1 -r 1 -i {fn}.png -i sus.mp3 -shortest -t 17 {fn}.mp4', stdin=None, stderr=PIPE, stdout=None)
        _, err = await proc.communicate()

        try:
            await ctx.send(file=discord.File(f'{fn}.mp4'))
        except discord.HTTPException as e:
            if e.status == 413:
                await ctx.send('big big chungus big chungus big chungus')
            else:
                await ctx.send(e.text)

        if err:
            pages = textutils.paginate(err.decode(), 1950)
            for page in pages:
                await ctx.send(f"```bash\n{page}\n```")

        try:
            os.remove(f'{fn}.png')
        except (FileNotFoundError, PermissionError, OSError):
            pass

        try:
            os.remove(f'{fn}.mp4')
        except (FileNotFoundError, PermissionError, OSError):
            pass

    @commands.command()
    async def fe(self, ctx, target, distortion_strength: float = 0.5):
        """
        hi
        """
        from math import sqrt

        import numpy as np

        def get_fish_xn_yn(source_x, source_y, radius, distortion):
            """
            Get normalized x, y pixel coordinates from the original image and return normalized 
            x, y pixel coordinates in the destination fished image.
            :param distortion: Amount in which to move pixels from/to center.
            As distortion grows, pixels will be moved further from the center, and vice versa.
            """
            if 1 - distortion*(radius**2) == 0:
                return source_x, source_y

            return source_x / (1 - (distortion*(radius**2))), source_y / (1 - (distortion*(radius**2)))

        def fish(img, distortion_coefficient):
            # If input image is only BW or RGB convert it to RGBA
            # So that output 'frame' can be transparent.
            w, h = img.shape[0], img.shape[1]
            if len(img.shape) == 2:
                # Duplicate the one BW channel twice to create Black and White
                # RGB image (For each pixel, the 3 channels have the same value)
                bw_channel = np.copy(img)
                img = np.dstack((img, bw_channel))
                img = np.dstack((img, bw_channel))
            if len(img.shape) == 3 and img.shape[2] == 3:
                img = np.dstack((img, np.full((w, h), 255)))

            dstimg = np.zeros_like(img)
            w, h = float(w), float(h)

            # easier calcultion if we traverse x, y in dst image
            for x in range(len(dstimg)):
                for y in range(len(dstimg[x])):
                    # normalize x and y to be in interval of [-1, 1]
                    xnd, ynd = float((2*x - w)/w), float((2*y - h)/h)
                    # get xn and yn distance from normalized center
                    rd = sqrt(xnd**2 + ynd**2)
                    # new normalized pixel coordinates
                    xdu, ydu = get_fish_xn_yn(xnd, ynd, rd, distortion_coefficient)
                    # convert the normalized distorted xdn and ydn back to image pixels
                    xu, yu = int(((xdu + 1)*w)/2), int(((ydu + 1)*h)/2)
                    # if new pixel is in bounds copy from source pixel to destination pixel
                    if 0 <= xu and xu < img.shape[0] and 0 <= yu and yu < img.shape[1]:
                        dstimg[x][y] = img[xu][yu]

            return dstimg.astype(np.uint8)

        url = await self.get_url(ctx, target, 'png', size=2048)
        img_bytes = await requests.get(url)
        img = Image.open(BytesIO(img_bytes))
        nparr = np.asarray(img)

        res = fish(nparr, distortion_strength)
        imr = Image.fromarray(res, 'RGBA')
        b = BytesIO()
        imr.save(b, 'png')
        b.seek(0)
        await ctx.send(file=discord.File(b, 'fe.png'))

    @commands.command(aliases=['spotify'])
    async def swf(self, ctx):
        """ spotify rich presence but as a watch face """
        rp = next((spotify for spotify in ctx.author.activities if isinstance(spotify, discord.Spotify)), None)

        if not rp:
            return await ctx.send('You need to be listening to Spotify to use this.')

        cover_bytes = BytesIO(await requests.get(rp.album_cover_url))

        base = Image.new('RGBA', (1024, 1024), (0, 0, 0, 0))
        cover = Image.open(cover_bytes) \
            .convert('RGBA') \
            .resize((1024, 1024))
        cover = ImageEnhance.Brightness(cover) \
            .enhance(0.5) \
            .filter(ImageFilter.GaussianBlur(3))
        font = ImageFont.truetype('assets/generators/srp/circular-black.ttf', size=22)
        timer_font = ImageFont.truetype('assets/generators/srp/circular-black.ttf', size=54)
        artist_font = font.font_variant(size=16)

        should_invert = self.get_brightness(cover) <= 128
        fore_colour = (255, 255, 255) if should_invert else (0, 0, 0)

        self.mask_ellipsis(cover, 10)
        base.paste(cover, (0, 0), cover)

        duration = rp.duration.seconds
        elapsed = min((datetime.utcnow() - rp.start).seconds, duration)
        ts = f'{format_time(elapsed * 1000)[3:]}/{format_time(duration * 1000)[3:]}'
        progress = min((elapsed / duration) * 100, 100)
        self.arc_bar(base, (10, 10), (base.width - 10, base.height - 10), progress, 15, fore_colour)

        title_text = rp.title
        artist_text = ', '.join(rp.artists[:3])
        ttft = TTFTool('assets/generators/srp/circular-black.ttf')

        if ttft.chars_missing(title_text) or ttft.chars_missing(artist_text):
            font = ImageFont.truetype('assets/generators/srp/simsun.ttc', size=22)
            #title_text = choice(fucking_weebs)

        font = piltext.font_auto_scale(font=font, text=rp.title, desired_width=800, size_min=64, size_max=136)
        artist_font = piltext.font_auto_scale(font=font, text=artist_text, desired_width=700, size_min=56, size_max=116)

        # title = piltext.wrap(font, rp.title, 800)
        title = piltext.wrap(font, title_text, 800)
        artist = piltext.wrap(artist_font, artist_text, 700)

        title_height = sum(map(lambda line: font.getsize(line)[1], title.split('\n')))

        canv = ImageDraw.Draw(base)
        canv.text((512, 100), ts, font=timer_font, anchor='mt', fill=fore_colour)
        canv.text((512, 480), title, font=font, align='center', anchor='mm', fill=fore_colour)
        #canv.text((512, 512), '__________________', font=font, align='center', anchor='mm', fill=fore_colour)
        canv.text((512, 480 + (title_height // 2)), artist, font=artist_font, align='center', anchor='ma', fill=fore_colour)

        buf = BytesIO()
        base.resize((256, 256)) \
            .save(buf, 'png')
        buf.seek(0)
        await ctx.send(file=discord.File(buf, 'swf.png'))

    def arc_bar(self, img, xy, size, progress_pc, width, fill):
        draw = ImageDraw.Draw(img)
        draw.arc((xy, size), start=-90, end=-90 + (3.6 * progress_pc), width=width, fill=fill)

    @commands.command(aliases=['nft'])
    async def snft(self, ctx):
        """ spotify rich presence but as an nft """
        rp = next((spotify for spotify in ctx.author.activities if isinstance(spotify, discord.Spotify)), None)

        if not rp:
            return await ctx.send('You need to be listening to Spotify to use this.')

        cover_bytes = BytesIO(await requests.get(rp.album_cover_url))

        base = Image.new('RGBA', (1024, 966), (0, 0, 0, 0))
        bar_layer = base.copy()
        cover = Image.open(cover_bytes) \
            .convert('RGBA') \
            .resize((1024, 1024))
        cover = ImageEnhance.Brightness(cover) \
            .enhance(0.5) \
            .filter(ImageFilter.GaussianBlur(3))
        mask = Image.open('assets/generators/srp/nft.png').convert('L')
        bar_mask = Image.open('assets/generators/srp/nft_bar.png').convert('L')
        font = ImageFont.truetype('assets/generators/srp/circular-black.ttf', size=22)
        timer_font = ImageFont.truetype('assets/generators/srp/circular-black.ttf', size=54)
        artist_font = font.font_variant(size=16)

        should_invert = self.get_brightness(cover) <= 128
        fore_colour = (255, 255, 255) if should_invert else (0, 0, 0)

        base.paste(cover, (0, 0), cover)
        base.putalpha(mask)

        duration = rp.duration.seconds
        elapsed = min((datetime.utcnow() - rp.start).seconds, duration)
        ts = f'{format_time(elapsed * 1000)[3:]}/{format_time(duration * 1000)[3:]}'
        progress = min((elapsed / duration) * 100, 100)

        font = piltext.font_auto_scale(font=font, text=rp.title, desired_width=800, size_min=64, size_max=136)
        artist_font = piltext.font_auto_scale(font=font, text=', '.join(rp.artists), desired_width=700, size_min=56, size_max=116)

        title = piltext.wrap(font, rp.title, 800)
        artist = piltext.wrap(artist_font, ', '.join(rp.artists[:3]), 700)

        title_height = sum(map(lambda line: font.getsize(line)[1], title.split('\n')))

        bar_canv = ImageDraw.Draw(bar_layer)
        bar_canv.rectangle((0, 0, 1024, 9.6 * progress), fill='white')
        bar_layer.putalpha(bar_mask)
        base.paste(bar_layer, (0, 0), bar_layer)

        canv = ImageDraw.Draw(base)
        canv.text((512, 100), ts, font=timer_font, anchor='mt', fill=fore_colour)
        canv.text((512, 480), title, font=font, align='center', anchor='mm', fill=fore_colour)
        canv.text((512, 480 + (title_height // 2)), artist, font=artist_font, align='center', anchor='ma', fill=fore_colour)

        buf = BytesIO()
        base.resize((256, 256)) \
            .save(buf, 'png')
        buf.seek(0)
        await ctx.send(file=discord.File(buf, 'nft.png'))


def setup(bot):
    bot.add_cog(Generators(bot))
