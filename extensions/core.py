import os
import threading
from datetime import datetime

import discord
import psutil
from discord.ext import commands
from utils import textutils
from utils.textutils import AnsiFormat


class Core(commands.Cog):
    __slots__ = ('bot',)

    def __init__(self, bot):
        self.bot = bot
        self.bot.remove_command('help')
        self.init_extensions()

    def init_extensions(self):
        for ext in os.listdir('extensions'):
            if not ext.endswith('.py') or ext.startswith('core'):
                continue

            try:
                self.bot.load_extension(f'extensions.{ext[:-3]}')
            except Exception as e:
                print(f'\x1b[2K{ext:20}ERR: {str(e)}')
            except commands.ExtensionAlreadyLoaded:
                pass
            else:
                print(f'\x1b[2K{ext:20}OK', end='\r')
        
        print(f'\x1b[2KLoaded {len(self.bot.extensions)} extensions into memory.')

    @commands.command(name='help')
    async def _help(self, ctx, specific: str = None):
        """ The help command, obviously.

        To view a list of commands in a cog, specify "s.help COG_NAME"
        To view specific information for a command, specify "s.help COMMAND_NAME"

        Example (Cog commands, case sensitive):
        s.help Music

        Example (Command syntax, case sensitive):
        s.help play        
        """
        embed = discord.Embed(colour=0xefefef, title='Chi Help Menu')

        if specific:
            exact = self.bot.get_command(specific) or self.bot.get_cog(specific)

            if exact:
                return await ctx.send_help(specific)

            closest = (99999, None)
            for command in self.bot.commands:
                distance = textutils.levenshtein_distance(specific, command.name)
                if distance < closest[0]:
                    closest = (distance, command)

            if closest[0] < 10 and closest[1] is not None:
                embed.description = f'No command found with the name `{specific}`.\nDid you mean `{closest[1].name}`?'
                embed.set_footer(text=f'Estimated with a distance of {closest[0]}')
                return await ctx.send(embed=embed)
            return await ctx.send(distance)

        cog_list = ctx.bot.cogs.copy()

        if ctx.author.id != 180093157554388993:
            cog_list.pop('Admin')
            cog_list.pop('Debugging')

        embed.description = '\n'.join(sorted(map(lambda cog: f'`{cog.qualified_name}` — *{len(cog.get_commands())} commands*', cog_list.values())))
        embed.add_field(name='\u200b', value='This is a list of available cogs within Chi.\nUse `s.help COG_NAME` to view a list of commands.\nThe cog name is case sensitive.')
        await ctx.send(embed=embed)

    @commands.command()
    async def invite(self, ctx):
        """ Provides an invite link for the bot """
        await ctx.send(f'Add the bot: <{self.bot.invite_url}>\nJoin the support server: <https://discord.gg/xvtH2Yn>')

    @commands.command()
    async def stats(self, ctx):
        """ Displays bot statistics """
        ram_usage = psutil.Process().memory_full_info().rss / 1024**2
        threads = threading.activeCount()
        players = sum(1 for _ in self.bot.lavalink.player_manager.players.values() if _.is_playing)

        adaptive = lambda val, lim: AnsiFormat.red if val > lim else AnsiFormat.green

        await ctx.send(f"""```ansi
{AnsiFormat.white("Developer:")} {AnsiFormat.blue("devoxin#0001")}

   {AnsiFormat.white("Uptime:")} {AnsiFormat.blue(textutils.time_string(datetime.utcnow() - ctx.bot.boot))}
{AnsiFormat.white("RAM Usage:")} {adaptive(ram_usage, 900)(f'{ram_usage:.2f} MB')}
  {AnsiFormat.white("Threads:")} {adaptive(threads, 15)(threads)}
  {AnsiFormat.white("Servers:")} {AnsiFormat.blue(len(ctx.bot.guilds))}
  {AnsiFormat.white("Players:")} {AnsiFormat.blue(players)}```
        """)

    @commands.command(aliases=['reboot'])
    @commands.is_owner()
    async def restart(self, ctx):
        """ Restarts the bot """
        await ctx.send('Please wait...')
        await ctx.bot.logout()


def setup(bot):
    bot.add_cog(Core(bot))
