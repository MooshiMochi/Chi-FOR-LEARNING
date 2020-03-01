from io import BytesIO
from discord.ext import commands

from PIL import Image, ImageEnhance, ImageColor
from utils import requests

import discord
import re

url_rx = re.compile("https?:\/\/(www\.)?.+\/\w+.[a-z]{2,6}", re.IGNORECASE)


class Imaging(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def member_or_url(self, ctx, target):
        try:
            member = await commands.MemberConverter().convert(ctx, target)
            url = str(member.avatar_url_as(format='png'))
        except commands.BadArgument:
            url = target

        return url

    async def get_image(self, url):
        return Image.open(BytesIO(await requests.get(url)))

    @commands.command()
    async def brightness(self, ctx, target, brightness: float):
        """ Change the brightness of an image.
        Target can be anything that resolves into a user, or a URL"""
        url = await self.member_or_url(ctx, target)

        if not url_rx.search(url):
            return await ctx.send('in what world does that look like a damn URL?')

        img = await self.get_image(url)
        enhanced = ImageEnhance.Brightness(img).enhance(brightness)

        out = BytesIO()
        enhanced.save(out, 'PNG')
        out.seek(0)

        await ctx.send(file=discord.File(out, filename='image.png'))

    @commands.command()
    async def color(self, ctx, target, color: float):
        """ Change the color balance of an image.
        Target can be anything that resolves into a user, or a URL"""
        url = await self.member_or_url(ctx, target)

        if not url_rx.search(url):
            return await ctx.send('in what world does that look like a damn URL?')

        img = await self.get_image(url)
        enhanced = ImageEnhance.Color(img).enhance(color)

        out = BytesIO()
        enhanced.save(out, 'PNG')
        out.seek(0)

        await ctx.send(file=discord.File(out, filename='image.png'))

    @commands.command()
    async def transparency(self, ctx, target, r: int=255, g: int=255, b: int=255, offset: int=0):
        """ Makes the pixels matching the specified color transparent. Color defaults to white.

        Target: Either a user (uses their avatar), or a URL to an image.
        Color : The color to make transparent. RGB format (3 numbers, space separated).

        You may specify a 4th number for the "color" parameter, this number will be used
        to loosely match pixels close to the provided RGB color.
        """
        url = await self.member_or_url(ctx, target)

        if not url_rx.search(url):
            return await ctx.send('in what world does that look like a damn URL?')

        if '.gif' in url.lower():
            return await ctx.send('GIFs are not supported.')

        async with ctx.typing():
            img = (await self.get_image(url)).convert('RGBA')
            pixels = img.getdata()

            r_lower, r_upper = (r - offset, r + offset)
            g_lower, g_upper = (g - offset, g + offset)
            b_lower, b_upper = (b - offset, b + offset)

            new_pixels = []

            for pixel in pixels:
                if (pixel[0] >= r_lower and pixel[0] <= r_upper) and \
                        (pixel[1] >= g_lower and pixel[1] <= g_upper) and \
                        (pixel[2] >= b_lower and pixel[2] <= b_upper):
                    new_pixels.append((255, 255, 255, 0))
                else:
                    new_pixels.append(pixel)

            img.putdata(new_pixels)

            out = BytesIO()
            img.save(out, 'PNG')
            out.seek(0)

            await ctx.send(file=discord.File(out, filename='image.png'))

    @commands.command()
    async def stripcolors(self, ctx, target, *hex_codes: str):
        """ Removes the given colours from the given image """
        url = await self.member_or_url(ctx, target)

        if not url_rx.search(url):
            return await ctx.send('in what world does that look like a damn URL?')

        if '.gif' in url.lower():
            return await ctx.send('GIFs are not supported.')

        rgb_codes = []
        for code in hex_codes:
            try:
                rgb_codes.append(ImageColor.getrgb(code))
            except ValueError:
                return await ctx.send(f'`{code}` is not a valid hex code.')

        def check_pixel(pxl):
            r, g, b, *extra = pxl
            return any((r, g, b) == code for code in rgb_codes)

            # for code in rgb_codes:
            #     rc, rg, rb, *rextra = code

            #     if rc == r and rg == g and rb == b:
            #         return True

            # return False

        async with ctx.typing():
            img = (await self.get_image(url)).convert('RGBA')

            new_pixels = []

            for pixel in img.getdata():
                if check_pixel(pixel):
                    new_pixels.append((255, 255, 255, 0))
                else:
                    new_pixels.append(pixel)

            img.putdata(new_pixels)

            out = BytesIO()
            img.save(out, 'PNG')
            out.seek(0)

            await ctx.send(file=discord.File(out, filename='image.png'))


def setup(bot):
    bot.add_cog(Imaging(bot))
