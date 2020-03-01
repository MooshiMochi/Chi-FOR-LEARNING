import asyncio
import discord
import importlib
import inspect
import sys
from discord.ext import commands
from time import time
from watchdog.events import FileSystemEventHandler, FileModifiedEvent
from watchdog.observers import Observer
from utils import hastepaste


class Debugging(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.watchdog = False
        self.observer = None

    def toggle_watchdog(self, ctx):
        self.watchdog = not self.watchdog

        if self.watchdog:
            handler = Handler(self.bot, ctx)
            self.observer = Observer()
            self.observer.schedule(handler, '.', recursive=True)
            self.observer.start()
        else:
            self.observer.stop()
            self.observer.join()
            self.observer = None

    def cog_unload(self):
        if self.observer:
            self.observer.stop()
            self.observer.join()
            self.observer = None

    @commands.command()
    @commands.is_owner()
    async def watchdog(self, ctx):
        self.toggle_watchdog(ctx)

        if self.watchdog:
            await ctx.send('Watchdog enabled.')
        else:
            await ctx.send('Watchdog disabled.')

    @commands.command()
    @commands.is_owner()
    async def source(self, ctx, *, command: str):
        """ Shows the source code of a command. """
        cmd = self.bot.get_command(command)

        if not cmd:
            return await ctx.send('No command with that name exists.')

        source = inspect.getsource(cmd.callback)

        if len(source) > 1990:
            paste = await hastepaste.create(source)
            await ctx.send(f'Source too big, uploaded to HastePaste: <{paste}>')
        else:
            await ctx.send(f'```\n{source}```')


class Handler(FileSystemEventHandler):
    def __init__(self, bot, ctx):
        self.bot = bot
        self.ctx = ctx

        self.cd = {}

    def check_cd(self, event):
        x = f'{type(event).__name__}:{event.src_path}'

        if x not in self.cd:
            self.cd[x] = time()
            return True
        else:
            cd_set = self.cd[x]
            if 1 > (time() - cd_set):
                return False
            else:
                self.cd[x] = time()
                return True

    def on_moved(self, event):
        pass

    def on_created(self, event):
        pass

    def on_deleted(self, event):
        pass

    def on_modified(self, event):
        if self.check_cd(event):
            self.bot.loop.create_task(self.on_modified_async(event))

    async def on_modified_async(self, event):
        if isinstance(event, FileModifiedEvent):
            if 'pycache' in event.src_path:
                return

            full_path = event.src_path.split('/')
            path = '/'.join(full_path[1:])
            ext = path.split('.')[-1] if '.' in path else None

            if not ext or not ext == 'py':
                return

            reloadable = '.'.join(full_path[1:]).strip('.py')

            m = await self.ctx.send(f'`[Watchdog]` <a:processing:620018387380207662> :: Auto-reloading `{reloadable}`')

            try:
                if 'extensions' in reloadable:
                    self.bot.reload_extension(reloadable)
                elif 'utils' in reloadable and reloadable in sys.modules:
                    importlib.reload(sys.modules[reloadable])
                else:
                    return await m.edit(content=f'`[Watchdog]` Unknown extension {event.src_path}')
            except Exception as ex:
                await m.edit(content=f'`[Watchdog]` Reloading `{reloadable}` failed: {ex}')
            else:
                await m.edit(content=f'`[Watchdog]` `{reloadable}` reloaded.')


def setup(bot):
    bot.add_cog(Debugging(bot))
