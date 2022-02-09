import asyncio

import discord
from discord.ext import commands
from lavalink.filters import Equalizer as llEq
from utils import gsmarena
from utils.equalizer import Equalizer

REACTIONS = ('◀', '⬅', '⏫', '🔼', '🔽', '⏬', '➡', '▶', '⏺')


class Experimental(commands.Cog):
    __slots__ = ('bot',)

    def __init__(self, bot):
        self.bot = bot

    @commands.command(aliases=['ps'])
    async def phonespecs(self, ctx, *, phone_model: str):
        """ Searches GSMArena for a phone and displays specifications. """
        return await ctx.send('I got the bot banned from the website whilst testing stuff :skull:')
        models = await gsmarena.search_phones(phone_model)

        if not models or models[0].name == 'Try this':
            return await ctx.send('No matching models found')

        if len(models) > 1:
            menu = '\n'.join([f'`{index}`. [{model.name}]({model.url})' for index, model in enumerate(models, start=1)])
            return await ctx.send(embed=discord.Embed(colour=0xfefefe, title='Select Your Model', description=menu))

        specs = await models[0].fetch_specs()
        await ctx.send(str(specs))

    @commands.command()
    async def eq(self, ctx):
        player = self.bot.lavalink.player_manager.players.get(ctx.guild.id)
        eq = player.fetch('eq', Equalizer())

        veq = await ctx.send(f'```\n{eq.visualise()}```')
        for reaction in REACTIONS:
            await veq.add_reaction(reaction)

        await self.interact(ctx, player, eq, veq, 0)

    async def interact(self, ctx, player, eq, m, selected):
        player.store('eq', eq)
        selector = f'{" " * 8}{"     " * selected}^^^'
        await m.edit(content=f'```\n{eq.visualise()}\n{selector}```')

        reaction = await self.get_reaction(ctx, m.id)
        print(reaction)

        if not reaction or reaction not in REACTIONS:
            try:
                await m.clear_reactions()
            except discord.Forbidden:
                pass
        elif reaction == '⬅':
            await self.interact(ctx, player, eq, m, max(selected - 1, 0))
        elif reaction == '➡':
            await self.interact(ctx, player, eq, m, min(selected + 1, 14))
        elif reaction == '🔼':
            gain = min(eq.get_gain(selected) + 0.1, 1.0)
            eq.set_gain(selected, gain)
            await self.apply_gains(player, eq.bands)
            await self.interact(ctx, player, eq, m, selected)
        elif reaction == '🔽':
            gain = max(eq.get_gain(selected) - 0.1, -0.25)
            eq.set_gain(selected, gain)
            await self.apply_gains(player, eq.bands)
            await self.interact(ctx, player, eq, m, selected)
        elif reaction == '⏫':
            gain = 1.0
            eq.set_gain(selected, gain)
            await self.apply_gains(player, eq.bands)
            await self.interact(ctx, player, eq, m, selected)
        elif reaction == '⏬':
            gain = -0.25
            eq.set_gain(selected, gain)
            await self.apply_gains(player, eq.bands)
            await self.interact(ctx, player, eq, m, selected)
        elif reaction == '◀':
            await self.interact(ctx, player, eq, m, 0)
        elif reaction == '▶':
            await self.interact(ctx, player, eq, m, 14)
        elif reaction == '⏺':
            for band in range(eq._band_count):
                eq.set_gain(band, 0.0)

            await self.apply_gains(player, eq.bands)
            await self.interact(ctx, player, eq, m, selected)

    async def apply_gain(self, player, band, gain):
        await self.apply_gains(player, {'band': band, 'gain': gain})

    async def apply_gains(self, player, gains):
        if isinstance(gains, list):
            e = llEq()
            e.update(bands=[(x, y) for x, y in enumerate(gains)])
            await player.set_filter(e)
        elif isinstance(gains, dict):
            await player.set_gain(gains['band'], gains['gain'])

        await player._apply_filters()

    async def get_reaction(self, ctx, m_id):
        reactions = ['◀', '⬅', '⏫', '🔼', '🔽', '⏬', '➡', '▶', '⏺']

        def check(payload):
            return payload.message_id == m_id and \
                    payload.user_id == ctx.author.id and \
                    payload.emoji.name in reactions

        done, pending = await asyncio.wait([
            self.bot.wait_for('raw_reaction_add', check=check),
            self.bot.wait_for('raw_reaction_remove', check=check)
        ], timeout=20, return_when=asyncio.FIRST_COMPLETED)

        #reaction, user = await self.bot.wait_for('reaction_add', check=check, timeout=20)

        for future in pending:
            future.cancel()

        if done:
            result = done.pop().result()
            return result.emoji.name


def setup(bot):
    bot.add_cog(Experimental(bot))
