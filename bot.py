import json
import traceback
from datetime import datetime

import discord
from discord.ext import commands
from discord.ext.commands import errors

from utils import cache

with open("config.json") as f:
    config = json.load(f)


class Bot(commands.AutoShardedBot):
    def __init__(self, **options):
        super().__init__(**options)
        self.boot = datetime.utcnow()
        self._init = False
        print('[Chi] Connecting to Discord...', end='\r')

    async def on_ready(self):
        if not self._init:
            self._init = True
            print('\x1b[2K[Chi] Connected.')
        await self.change_presence(activity=discord.Game(name="s.help"))
        self.invite_url = discord.utils.oauth_url(self.user.id)
        self.load_extension('extensions.core')

    async def on_command_error(self, ctx, exception):
        if isinstance(exception, errors.MissingRequiredArgument):
            command = ctx.invoked_subcommand or ctx.command
            await ctx.send_help(command)

        elif isinstance(exception, errors.CommandInvokeError):
            exception = exception.original
            _traceback = traceback.format_tb(exception.__traceback__)
            _traceback = ''.join(_traceback)

            error = ('`{0}` in command `{1}`: ```py\nTraceback (most recent call last):\n{2}{0}: {3}\n```')\
                .format(type(exception).__name__, ctx.command.qualified_name, _traceback, exception)

            await ctx.send(error)

        elif isinstance(exception, errors.CommandOnCooldown):
            await ctx.send('You can use this command in {0:.0f} seconds.'.format(exception.retry_after))

        elif not isinstance(exception, errors.CommandNotFound):
            await ctx.send(exception)

    async def on_message(self, message):
        if message.author.bot:
            return

        if cache.check_blocked(message.author.id):
            return

        await self.process_commands(message)


bot = Bot(command_prefix=config.get('BOT_PREFIX'), max_messages=None, intents=discord.Intents.all())
bot.run(config.get('BOT_TOKEN'))
