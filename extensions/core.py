import os
import threading
from datetime import datetime

import discord
import psutil
from discord.ext import commands

from utils import parsers


class Core(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.init_extensions()

    def init_extensions(self):
        for ext in os.listdir('extensions'):
            if not ext.endswith('.py') or ext.startswith('core'):
                continue

            try:
                self.bot.load_extension(f'extensions.{ext[:-3]}')
            except Exception as e:
                print(f'{ext:15}ERR: {str(e)}')
            else:
                print(f'{ext:15}OK')

    @commands.command()
    async def invite(self, ctx):
        """ Provides an invite link for the bot """
        await ctx.send(f'Add the bot: <{self.bot.invite_url}>\nJoin the support server: <https://discord.gg/xvtH2Yn>')

    @commands.command()
    async def stats(self, ctx):
        """ Displays bot statistics """
        ram_usage = psutil.Process().memory_full_info().rss / 1024**2
        threads = threading.activeCount()
        players = sum([1 for _ in self.bot.lavalink.player_manager.players.values() if _.is_playing])

        embed = discord.Embed(colour=0xDE3F83, title='Statistics!', description='Developer: **Devoxin#0101**')
        embed.add_field(name='Uptime', value=parsers.time_string(datetime.utcnow() - ctx.bot.boot), inline=True)
        embed.add_field(name='RAM Usage', value=f'{ram_usage:.2f}MB', inline=True)
        embed.add_field(name='Threads', value=threads, inline=True)
        embed.add_field(name='Servers', value=str(len(ctx.bot.guilds)), inline=True)
        embed.add_field(name='Players', value=str(players), inline=True)
        await ctx.send(embed=embed)

    @commands.command(aliases=['reboot'])
    @commands.is_owner()
    async def restart(self, ctx):
        """ Restarts the bot """
        await ctx.send('Please wait...')
        await ctx.bot.logout()


def setup(bot):
    bot.add_cog(Core(bot))
