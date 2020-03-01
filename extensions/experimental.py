import asyncio
import discord
from discord.ext import commands
from utils.equalizer import Equalizer

REACTIONS = ('◀', '⬅', '⏫', '🔼', '🔽', '⏬', '➡', '▶', '⏺')


class Experimental(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

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
            await self.apply_gain(player, selected, gain)
            await self.interact(ctx, player, eq, m, selected)
        elif reaction == '🔽':
            gain = max(eq.get_gain(selected) - 0.1, -0.25)
            eq.set_gain(selected, gain)
            await self.apply_gain(player, selected, gain)
            await self.interact(ctx, player, eq, m, selected)
        elif reaction == '⏫':
            gain = 1.0
            eq.set_gain(selected, gain)
            await self.apply_gain(player, selected, gain)
            await self.interact(ctx, player, eq, m, selected)
        elif reaction == '⏬':
            gain = -0.25
            eq.set_gain(selected, gain)
            await self.apply_gain(player, selected, gain)
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
            await player.set_gains(*[(x, y) for x, y in enumerate(gains)])
        elif isinstance(gains, dict):
            await player.set_gain(gains['band'], gains['gain'])

    async def get_reaction(self, ctx, m_id):
        reactions = ['◀', '⬅', '⏫', '🔼', '🔽', '⏬', '➡', '▶', '⏺']

        def check(r, u):
            return r.message.id == m_id and \
                    u.id == ctx.author.id and \
                    r.emoji in reactions

        done, pending = await asyncio.wait([
            self.bot.wait_for('reaction_add', check=check),
            self.bot.wait_for('reaction_remove', check=check)
        ], timeout=20, return_when=asyncio.FIRST_COMPLETED)

        #reaction, user = await self.bot.wait_for('reaction_add', check=check, timeout=20)

        for future in pending:
            future.cancel()

        if done:
            result = done.pop().result()
            return result[0].emoji


def setup(bot):
    bot.add_cog(Experimental(bot))
