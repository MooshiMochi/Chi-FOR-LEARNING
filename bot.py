import json
import traceback
from datetime import datetime

import discord
from discord.ext import commands
from discord.ext.commands import errors


with open("config.json") as f:
    config = json.load(f)


class Bot(commands.AutoShardedBot):
    def __init__(self, **options):
        super().__init__(**options)
        self.boot = datetime.utcnow()

    async def on_ready(self):
        print(f'Logged in as {self.user.name}')
        await self.change_presence(activity=discord.Game(name=f"s.help | smonk weeds"))
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

        await self.process_commands(message)


bot = Bot(command_prefix=config.get('BOT_PREFIX'))
bot.run(config.get('BOT_TOKEN'))
