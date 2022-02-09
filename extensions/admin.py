import asyncio
import json
import re
import textwrap
import traceback
from asyncio.subprocess import PIPE
from io import BytesIO
from secrets import token_urlsafe
from time import time

import discord
from discord.ext import commands
from utils import cache, textutils
from utils.textutils import AnsiFormat


class Admin(commands.Cog):
    __slots__ = ('bot', 'env')

    def __init__(self, bot):
        self.bot = bot
        self.env = {}

    def sanitize(self, s):
        return s.replace('`', '′')

    @commands.command()
    @commands.is_owner()
    async def block(self, ctx, user_id: int, blocked: bool):
        """ Block a user from the bot. """
        cache.set_blocked(user_id, blocked)
        await ctx.send("User blocked." if blocked else "User unblocked.")

    @commands.command()
    @commands.is_owner()
    async def reload(self, ctx, *modules: str):
        """ Reload extensions """
        if not modules:
            return await ctx.send('whatchawantmetoreload.gif')

        loaded_modules = [ext.__name__ for ext in self.bot.extensions.values()]

        out = ''
        for module in set(modules):  # dedupe
            extension = f'extensions.{module}'
            out += f'{AnsiFormat.white(module)}\n'

            if extension in loaded_modules:
                steps = [('module_unload', self.bot.unload_extension), ('module_load', self.bot.load_extension)]
            elif extension not in loaded_modules:
                steps = [('module_load', self.bot.load_extension)]

            for name, step in steps:
                try:
                    step(extension)
                except commands.errors.ExtensionNotFound:
                    out += f'  {AnsiFormat.red(name)}: {AnsiFormat.white("Extension not found")}\n'
                except commands.errors.ExtensionError as ext_err:
                    original = ext_err.original
                    out += f'  {AnsiFormat.red(name)}: {AnsiFormat.white(original.__class__.__name__ + ": " + str(original))}\n'
                except Exception as exception:
                    out += f'  {AnsiFormat.red(name)}: {AnsiFormat.white(str(exception))}\n'
                    traceback.print_exc()
                else:
                    out += f'  {AnsiFormat.green(name)}: {AnsiFormat.white("OK")}\n'

        await ctx.send(f'''```ansi
{AnsiFormat.blue("====== Module Management Status ======")}
{out.strip()}```
        ''')

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
            pages = textutils.paginate(out, 1950)
            for page in pages:
                await ctx.send(f"```bash\n{page}\n```")

        if err:
            pages = textutils.paginate(err, 1950)
            for page in pages:
                await ctx.send(f"```bash\n{page}\n```")

    @commands.command()
    @commands.is_owner()
    async def eval(self, ctx, *, code: str = None):
        """ Evaluate Python code """
        if not code:
            if not ctx.message.attachments:
                return await ctx.send('Nothing to evaluate.')

            atch = ctx.message.attachments[0]
            if not atch.filename.endswith('.txt'):
                return await ctx.send('File to evaluate must be a text document.')

            buf = BytesIO()
            await atch.save(buf, seek_begin=True, use_cached=False)
            code = buf.read().decode()
            
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
            paste = await textutils.dump(message)
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
