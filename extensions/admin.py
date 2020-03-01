import asyncio
import json
import re
import textwrap
from asyncio.subprocess import PIPE, STDOUT
from secrets import token_urlsafe
from time import time

import discord
from discord.ext import commands
from utils import hastepaste, pagination

module_rx = re.compile('extensions\/(\w+)\.py')  # noqa: W605


class Admin(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.env = {}

    def sanitize(self, s):
        return s.replace('`', '′')

    @commands.command()
    @commands.is_owner()
    async def reload(self, ctx, *modules: str):
        """ Reload extensions """
        if not modules:
            return await ctx.send('whatchawantmetoreload.gif')

        out = ''
        for module in set(modules):  # dedupe
            try:
                self.bot.unload_extension(f'extensions.{module}')
                self.bot.load_extension(f'extensions.{module}')
            except Exception as exception:
                out += f'{module:15}ERR: {str(exception)}\n'
                import traceback
                traceback.print_exc()
            else:
                out += f'{module:15}OK\n'

        await ctx.send(f'```\nModule         Status\n----------------------\n{out.strip()}```')

    @commands.command()
    @commands.is_owner()
    async def cleanup(self, ctx, amount: int):
        """ Cleans up messages sent by the bot """
        if amount <= 0 or amount > 100:
            return await ctx.send('Invalid amount.')

        await ctx.channel.purge(limit=amount, check=lambda m: m.author.id == self.bot.user.id, bulk=False)

    @commands.command()
    @commands.is_owner()
    async def bash(self, ctx, *, command: str):
        """ Execute bash commands """

        proc = await asyncio.create_subprocess_shell(command, stdin=None, stderr=PIPE, stdout=PIPE)
        out = (await proc.stdout.read()).decode('utf-8')
        err = (await proc.stderr.read()).decode('utf-8')

        if not out and not err:
            return await ctx.message.add_reaction('👌')

        if out:
            pages = pagination.paginate(out, 1950)
            for page in pages:
                await ctx.send(f"```bash\n{page}\n```")

        if err:
            pages = pagination.paginate(err, 1950)
            for page in pages:
                await ctx.send(f"```bash\n{page}\n```")

    @commands.command()
    @commands.is_owner()
    async def eval(self, ctx, *, code: str):
        """ Evaluate Python code """
        if code == 'exit()':
            self.env.clear()
            return await ctx.send('Environment cleared')

        player = self.bot.lavalink.player_manager.players.get(ctx.guild.id) if ctx.guild else None

        self.env.update({
            'self': self,
            'bot': self.bot,
            'ctx': ctx,
            'message': ctx.message,
            'channel': ctx.message.channel,
            'guild': ctx.message.guild,
            'author': ctx.message.author,
            'player': player,
        })

        if code.startswith('```py'):
            code = code[5:]

        code = code.strip('`').strip()

        _code = '''
async def func():
    try:
{}
    finally:
        self.env.update(locals())
'''.format(textwrap.indent(code, ' ' * 6))

        _eval_start = time() * 1000

        try:
            exec(_code, self.env)
            output = await self.env['func']()

            if output is None:
                output = ''
            elif not isinstance(output, str):
                output = f'\n{repr(output) if output else str(output)}\n'
            else:
                output = f'\n{output}\n'
        except Exception as e:
            output = f'\n{type(e).__name__}: {e}\n'

        _eval_end = time() * 1000

        code = code.split('\n')
        s = ''
        for i, line in enumerate(code):
            s += '>>> ' if i == 0 else '... '
            s += line + '\n'

        _eval_time = _eval_end - _eval_start
        message = f'{s}{output}# {_eval_time:.3f}ms'

        try:
            await ctx.send(f'```py\n{self.sanitize(message)}```')
        except discord.HTTPException:
            paste = await hastepaste.create(message)
            await ctx.send(f'Eval result: <{paste}>')

    @commands.command()
    @commands.is_owner()
    async def setgame(self, ctx, *, game: str):
        """ Changes the current game """
        await self.bot.change_presence(activity=discord.Game(name=game))
        await ctx.send('Game set :thumbsup:')

    @commands.command()
    @commands.is_owner()
    async def auth(self, ctx, user: discord.User, sharex: bool):
        """ Allows a user to access cdn.serux.pro, and optionally, the ShareX endpoint. """
        keys = self.read_json('/home/devoxin/cdn.serux.pro/id-auth.json')
        keys.append(str(user.id))
        keys = list(set(keys))
        self.write_json('/home/devoxin/cdn.serux.pro/id-auth.json', keys)

        if sharex:
            token = f'{user.name.lower()}-{token_urlsafe(15)}'
            api_keys = self.read_json('/home/devoxin/server/keys.json')
            api_keys.append(token)
            api_keys = list(set(api_keys))
            self.write_json('/home/devoxin/server/keys.json', api_keys)
            await ctx.author.send(f'**{user.name}\'s token**: {token}')

        await ctx.send('Done.')

    def read_json(self, filepath: str):
        with open(filepath) as f:
            return json.load(f)

    def write_json(self, filepath, obj):
        with open(filepath, 'w') as f:
            json.dump(obj, f)


def setup(bot):
    bot.add_cog(Admin(bot))
