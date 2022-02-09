import re
from concurrent.futures import ThreadPoolExecutor
from io import BytesIO

import discord
import requests
from discord.ext import commands

from PIL import Image, ImageDraw, ImageEnhance, ImageFont, ImageSequence

executor_pool = ThreadPoolExecutor(max_workers=10)
MAX_IMAGE_SIZE = 5 * 1000 * 1000
MAX_FILE_LIMIT = 15
MAX_LOOP_ITER = 10

PROC_M = {}  # user m id -> bot response id


class GifMaker:
    __slots__ = ('_seek', '_frames', '_durations')

    def __init__(self):
        self._seek = 0
        self._frames = []
        self._durations = []

    @classmethod
    def from_image(cls, image):
        gm = cls()
        for frame in ImageSequence.Iterator(image):
            b = BytesIO()
            frame.save(b, 'png')
            b.seek(0)
            gm.add_frame(Image.open(b), frame.info.get('duration', 1))

        return gm

    @property
    def frames(self):
        for i in range(len(self._frames) - self._seek):
            yield self._frames[i + self._seek], self._durations[i + self._seek]

    def copy(self):
        maker = GifMaker()

        for frame, duration in self.frames:
            maker.add_frame(frame.copy(), duration)

        return maker

    def add_frame(self, frame, duration):
        self._frames.append(frame)
        self._durations.append(duration)

    def export(self):
        gif_bytes = BytesIO()
        self._frames[0].save(gif_bytes, save_all=True, append_images=self._frames[1:], format='gif',
                             loop=0, duration=self._durations, disposal=2, optimize=True)
        gif_bytes.seek(0)
        return gif_bytes

    def export_selected_frame(self):
        frame_bytes = BytesIO()
        self._frames[self._seek].save(frame_bytes, 'png')
        frame_bytes.seek(0)
        return frame_bytes


class Text:
    __slots__ = ('size', 'font', 'colour')

    def __init__(self, size, font):
        self.size = size
        self.font = font or 'assets/generators/facts/verdana.ttf'
        self.colour = (0, 0, 0)

    def print_(self, target, s, x, y):
        font = ImageFont.truetype(self.font, self.size)
        canv = ImageDraw.Draw(target)
        canv.text((x, y), s, font=font, fill=self.colour)
        #return 
        #out = Image.alpha_composite(base, txtO)


class ImgEngine(commands.Cog):
    __slots__ = ('bot',)

    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_message_edit(self, old, new):
        if old.content.startswith('s.process') and new.content.startswith('s.process'):
            await self.bot.process_commands(new)

    async def send_help(self, ctx):
        await ctx.send('''```
You may edit your message to change the resulting image without spamming the channel.

:: Declare a variable:
    def <var_name>: <func>

    :: <func>:
        load(url)               :: Loads an image from the given URL
        load_gif(url)           :: Loads a GIF from the given URL
        copy(var)               :: Copies an image from an existing var
        new_gif()               :: Creates a GIF Image instance used for creating gifs. Use `.add_frame(var,duration)` to add frames
        canvas(width,height)    :: Creates a blank (transparent) canvas with the specified width and height
        text(size(, font))      :: Creates a new text element that can be applied to images. Size is an int, font is a string.

:: General Operations:
    loop(times, statement)      :: Runs the provided statement the given amount of times.
                                   Statement should be written normally like any other line.
                                   You may use `;` to execute multiple statements that would otherwise be written across multiple lines.
    render(fmt || png)          :: Renders the image with the given format, or png by default.
    preview(index)              :: Renders a single frame from a GIF image.```''')

        await ctx.send('''```
:: Text operations:
    size(pt)                    :: The new font size.
    print(img, text, x, y)      :: Writes the text onto the specified image at the given co-ordinates.

:: Image operations:
    colour(r, g, b)             :: Sets the colour of the image or text, depending what the function is called on.
    rotate(degrees(, expand))   :: Rotates the image by the specified amount of degrees. Expand can be `0` or `1`
    opacity(alpha)              :: Sets the opacity of the image
    mode(palette)               :: Sets the image's palette mode (RGB, RGBA etc. Refer to PIL Image docs)
    apply(img, x, y)            :: Pastes the specified image at the given co-ordinates
    extend(w, h, fill)          :: Extends the image by the given width and height, with the given fill color
    scale(width, height)        :: Scales the image to the given width and height
    hflip()                     :: Horizontally flips the image
    vflip()                     :: Vertically flips the image
    filter(r, g, b, s)          :: Filters out the specified colour. `s` is scope, (0-255), where colors in the range
                                   of scope are filtered out (i.e. 10,10,10,20 means -10,-10,-10 to 30,30,30 are filtered)
    match_scale(img)            :: Resizes the image to match another's dimensions```''')
        await ctx.send('''```
    add_frame(img, duration)    :: Adds an image to a `GifMaker` with the given duration.
    rev_frames()                :: Reverses frames of a GIF image. This operation converts the specified image into a 
                                   `GifMaker` instance.
    map_frames(statement)       :: Iterates over every frame in the target `GifMaker` instance, applying the statement to each frame.
                                   Each frame is accessible within the statement via the `frame` variable.
    add_all(target_gif)         :: Adds the frames of the target GIF to the source GIF.
    seek_to(index)              :: Seeks the given GIF instance to the provided index. Useful for manipulating GIFs after a given frame.```''')

    @commands.command()
    async def process(self, ctx, *, code: str):
        """ Arbitrary code evaluation based on image processing.

        Specify '?' to see basic usage and operations.
        Special thanks to Zenrac#0001 for testing.
        """
        if code == '?':
            return await self.send_help(ctx)

        if ctx.message.id in PROC_M:
            try:
                old_message = await ctx.channel.fetch_message(PROC_M[ctx.message.id])
            except (discord.HTTPException, discord.NotFound):
                pass
            else:
                await old_message.delete()

        setattr(ctx, 'LIMIT_BYPASS', ctx.author.id in (180093157554388993,))

        if code.startswith('```py'):
            code = code[5:]

        code = code.strip('`').strip()

        async with ctx.typing():
            result = await self.bot.loop.run_in_executor(executor_pool, self._process, ctx, code)

            if not result:
                return

            m = None

            if isinstance(result, str):
                m = await ctx.send(result)

            if isinstance(result, discord.File):
                m = await ctx.send(file=result)

            if m is not None:
                PROC_M[ctx.message.id] = m.id

    def _process(self, ctx, code: str):
        env = {}

        for line in code.split('\n'):
            if not line:
                continue

            words = self.get_words(line)
            for i, word in enumerate(words):
                res = self._evaluate(ctx, env, line, words, word, i)

                if res == 0:
                    return
                elif res == 1:
                    break
                elif res == 2:
                    continue
                elif res is not None:
                    return res

    def _evaluate(self, ctx, env, line, words, word, i):
        if word == 'def':  # Assignment
            var_ = self.safe_get(words, i + 1)

            if not var_:
                return self.get_stack(ctx, line, 'Invalid var_name!')

            var_name_ = re.match('^([a-zA-Z]+):$', var_)

            if not var_name_:
                return self.get_stack(ctx, line, 'var_name must consist of A-Z and end with :!')

            var_name = var_name_.group(1)

            func = self.safe_get(words, i + 2)

            if not func:
                return self.get_stack(ctx, line, 'Assignment must be followed by a function call!')

            match = re.match('^([a-zA-Z_]+)\((.+)?\)$', func)  # noqa: W605

            if not match:
                return self.get_stack(ctx, line, f'Function {func} must be called with parenthesis and a parameter!')

            func, param = (match.group(1), match.group(2))

            if func == 'load':
                if len(env) > MAX_FILE_LIMIT - 1 and not ctx.LIMIT_BYPASS:
                    return self.get_stack(ctx, line, f'Unable to copy image; you have hit the `{MAX_FILE_LIMIT}` active images cap!')

                env[var_name] = self.get_image(param.strip('<>'), ctx.LIMIT_BYPASS)
                return 1  # TODO: Check if words follow assignment?
            elif func == 'load_gif':
                if len(env) > MAX_FILE_LIMIT - 1 and not ctx.LIMIT_BYPASS:
                    return self.get_stack(ctx, line, f'Unable to copy image; you have hit the `{MAX_FILE_LIMIT}` active images cap!')

                img = self.get_image(param.strip('<>'), ctx.LIMIT_BYPASS)
                env[var_name] = GifMaker.from_image(img)
                return 1
            elif func == 'copy':
                if len(env) > MAX_FILE_LIMIT - 1 and not ctx.LIMIT_BYPASS:
                    return self.get_stack(ctx, line, f'Unable to copy image; you have hit the `{MAX_FILE_LIMIT}` active images cap!')

                if param not in env:
                    return self.get_stack(ctx, line, f'{param} referenced before assignment!')

                env[var_name] = env[param].copy()
                return 1
            elif func == 'new_gif':
                env[var_name] = GifMaker()  # Consider params?
                return 1
            elif func == 'canvas':
                params = self.get_params(param)

                if len(param) < 2:
                    return self.get_stack(ctx, line, 'canvas operation requires 2 params: width, height')

                w, h = (int(params[0]), int(params[1]))

                if w < 1 or h < 1:
                    return self.get_stack(ctx, line, 'width/height parameters must be 1 or bigger!')

                if w > 4000 or h > 4000:
                    return self.get_stack(ctx, line, 'width/height parameters may not exceed 4000!')

                env[var_name] = Image.new('RGBA', (w, h), (255, 255, 255, 0))
                return 1
            elif func == 'text':
                params = self.get_params(param)

                if len(param) < 1:
                    return self.get_stack(ctx, line, 'text operation requires at least 1 parameter: size')

                try:
                    size = int(params[0])
                except ValueError:
                    return self.get_stack(ctx, line, 'size must be an integer')

                font = params[1] if len(params) >= 2 else None

                env[var_name] = Text(size, font)
                return 1
            else:
                return self.get_stack(ctx, line, f'Unknown function {func}')
        else:
            match = re.match('^([a-zA-Z]+)\.([a-zA-Z_]+)\((.+)?\)$', word)   # noqa: W605

            if not match:
                match = re.match('^loop\((\d+), ?(.+)?\)$', line)

                if not match:
                    return self.get_stack(ctx, line, f'Unknown operation/variable {word}')

                times, statement = (int(match.group(1)), match.group(2))
                statements = statement.split(';')

                if times > MAX_LOOP_ITER:
                    return self.get_stack(ctx, line, f'loop cannot exceed {MAX_LOOP_ITER} iterations')

                for _ in range(times):
                    for stmt in statements:
                        if not stmt:
                            continue

                        swords = self.get_words(stmt)
                        for si, sword in enumerate(swords):
                            res = self._evaluate(ctx, env, stmt, swords, sword, si)

                            if res == 0:
                                return 0

                            if res == 1:
                                break

                            if res == 2:
                                continue

                return 2

            var, op, param = (match.group(1), match.group(2), match.group(3))

            if var not in env:
                return self.get_stack(ctx, line, f'{var} referenced before assignment!')

            if op == 'rotate':
                params = self.get_params(param)

                if len(params) == 2:
                    deg, ex = float(params[0]), params[1] == '1'
                else:
                    deg, ex = float(params[0]), False

                env[var] = env[var].rotate(deg, resample=Image.BILINEAR, expand=ex)
            elif op == 'opacity':
                env[var].putalpha(int(param))
            elif op == 'mode':
                env[var] = env[var].convert(param)
            elif op == 'apply':
                params = self.get_params(param)

                if len(params) < 3:
                    return self.get_stack(ctx, line, 'apply operation requires 3 params: img, x, y')

                dest, x, y = params

                if dest not in env:
                    return self.get_stack(ctx, line, f'{dest} referenced before assignment!')

                env[var].paste(env[dest], (int(x), int(y)), mask=env[dest])
            elif op == 'scale':
                params = self.get_params(param)

                if len(params) < 2:
                    return self.get_stack(ctx, line, 'scale operation requires 2 params: width, height')

                width, height = params

                if int(width) > 4096 or int(height) > 4096:
                    return self.get_stack(ctx, line, 'width/height parameters may not exceed 4096!')

                env[var] = env[var].resize((int(width), int(height)), resample=Image.BICUBIC)
            elif op == 'extend':
                params = self.get_params(param)

                if len(params) < 3:
                    return self.get_stack(ctx, line, 'extend operation requires 3 params: width, height, fill')

                width, height, fill = params

                if int(width) > 2048 or int(height) > 2048:
                    return self.get_stack(ctx, line, 'width/height parameters may not exceed 2048!')

                img = env[var]
                base = Image.new(img.mode, (img.width + int(width), img.height + int(height)), fill)

                if img.mode == 'RGBA':
                    base.paste(img, (0, 0), img)
                else:
                    base.paste(img, (0, 0))

                env[var] = base
            elif op == 'hflip':
                env[var] = env[var].transpose(Image.FLIP_LEFT_RIGHT)
            elif op == 'vflip':
                env[var] = env[var].transpose(Image.FLIP_TOP_BOTTOM)
            elif op == 'brightness':
                env[var] = ImageEnhance.Brightness(env[var]).enhance(float(param))
            elif op == 'match_scale':
                dest = param

                if dest not in env:
                    return self.get_stack(ctx, line, f'{dest} referenced before assignment!')

                env[var] = env[var].resize(env[dest].size)
            elif op == 'seek_to':
                if not isinstance(env[var], GifMaker):
                    return self.get_stack(ctx, line, 'The referenced var is not of type `Gif`!')

                frame_num = int(param)
                frame_count = len(env[var]._frames)
                if frame_num < 0:
                    return self.get_stack(ctx, line, 'Cannot seek before 0!')

                if frame_count < frame_num:
                    return self.get_stack(ctx, line, f'Seek index exceeds frame count! ({frame_num} > {frame_count})')

                env[var]._seek = frame_num
            elif op == 'filter':
                params = self.get_params(param)

                if len(params) < 3:
                    return self.get_stack(ctx, line, 'filter operation requires 3-4 params: r,g,b(,s)')

                if len(params) == 3:
                    r, g, b, s = (int(c) for c in params), 0
                else:
                    r, g, b, s = (int(c) for c in params)

                env[var].convert('RGBA')
                pixels = env[var].getdata()

                r_lower, r_upper = (r - s, r + s)
                g_lower, g_upper = (g - s, g + s)
                b_lower, b_upper = (b - s, b + s)

                new_pixels = []

                for pixel in pixels:
                    if (pixel[0] >= r_lower and pixel[0] <= r_upper) and \
                            (pixel[1] >= g_lower and pixel[1] <= g_upper) and \
                            (pixel[2] >= b_lower and pixel[2] <= b_upper):
                        new_pixels.append((255, 255, 255, 0))
                    else:
                        new_pixels.append(pixel)

                env[var].putdata(new_pixels)
            elif op == 'add_frame':
                if not isinstance(env[var], GifMaker):
                    return self.get_stack(ctx, line, 'The referenced var is not of type `Gif`!')

                params = self.get_params(param)

                if len(params) < 2:
                    return self.get_stack(ctx, line, 'add_frame operation requires 2 params: img, duration')

                img, duration = params
                env[var].add_frame(env[img], float(duration))
            elif op == 'rev_frames':
                gif = env[var]
                gif._frames = gif._frames[::-1]
                gif._durations = gif._durations[::-1] 
            elif op == 'map_frames':
                if not isinstance(env[var], GifMaker):
                    return self.get_stack(ctx, line, 'The referenced var is not of type `Gif`!')

                statements = param.split(';')

                for frame, duration in env[var].frames:
                    env['frame'] = frame
                    for stmt in statements:
                        if not stmt:
                            continue

                        swords = self.get_words(stmt)
                        for si, sword in enumerate(swords):
                            res = self._evaluate(ctx, env, stmt, swords, sword, si)

                            if res == 0:
                                return 0

                            if res == 1:
                                break

                            if res == 2:
                                continue

                del env['frame']
            elif op == 'add_all':
                if not isinstance(env[var], GifMaker):
                    return self.get_stack(ctx, line, 'The referenced var is not of type `Gif`!')

                if param not in env:
                    return self.get_stack(ctx, line, f'{param} referenced before assignment!')

                target_gif = env[param]

                if not isinstance(target_gif, GifMaker):
                    return self.get_stack(ctx, line, 'The referenced var is not of type `Gif`!')

                for frame, duration in target_gif.frames:
                    env[var].add_frame(frame, duration)
            elif op == 'colour':
                if not isinstance(env[var], Text) and not isinstance(env[var], Image.Image):
                    return self.get_stack(ctx, line, 'The referenced var is not of type `Text` or `Image`!')

                params = self.get_params(param)

                if len(params) < 3 or len(params) > 3:
                    return self.get_stack(ctx, line, f'Expected 3 parameters, got {len(params)}')

                def try_int(i):
                    try:
                        return int(i)
                    except ValueError:
                        return None

                r, g, b = list(map(try_int, params))
                invalid = next((i for i, c in enumerate((r, g, b)) if c is None), None)

                if invalid is not None:
                    channel = ('r', 'g', 'b')[invalid]
                    return self.get_stack(ctx, line, f'{channel} must be an integer')

                if isinstance(env[var], Text):
                    env[var].colour = (r, g, b)
                elif isinstance(env[var], Image.Image):
                    for x in range(env[var].width):
                        for y in range(env[var].height):
                            env[var].putpixel((x, y), (r, g, b))
            elif op == 'size':
                if not isinstance(env[var], Text):
                    return self.get_stack(ctx, line, f'The referenced var is not of type `Text`!')

                try:
                    pt = int(param)
                except ValueError:
                    return self.get_stack(ctx, line, f'pt must be an integer')

                env[var].size = pt
            elif op == 'print':
                if not isinstance(env[var], Text):
                    return self.get_stack(ctx, line, f'The referenced var is not of type `Text`!')

                params = self.get_params(param)

                if len(params) < 4:
                    return self.get_stack(ctx, line, f'Expected 4 parameters, got {len(params)}')

                target_img, t, x, y = params

                if target_img not in env:
                    return self.get_stack(ctx, line, f'{i} referenced before assignment!')

                if not isinstance(env[target_img], Image.Image):
                    return self.get_stack(ctx, line, f'The referenced var is not of type `Image`!')

                try:
                    x = int(x)
                except ValueError:
                    return self.get_stack(ctx, line, f'x must be an integer')

                try:
                    y = int(y)
                except ValueError:
                    return self.get_stack(ctx, line, f'y must be an integer')

                #env[param] =
                env[var].print_(env[target_img], t, x, y)
            elif op == 'render':
                img = env[var]
                if isinstance(img, GifMaker):
                    rendered, fmt = img.export(), 'gif'
                else:
                    fmt = (param or 'png').lower()

                    if fmt not in ('png', 'jpeg', 'bmp', 'webp'):
                        return self.get_stack(ctx, line, f'Format must be one of `png`, `jpeg`, `bmp`, `webp`!')

                    rendered = BytesIO()
                    img.save(rendered, fmt)
                    rendered.seek(0)

                return discord.File(rendered, filename=f'render.{fmt}')
            elif op == 'preview':
                if not isinstance(env[var], GifMaker):
                    return self.get_stack(ctx, line, 'The referenced var is not of type `Gif`!')

                seek = int(param)
                env[var]._seek = seek
                frame = env[var].export_selected_frame()
                return discord.File(frame, filename=f'preview.png')
            else:
                return self.get_stack(ctx, line, f'Unknown func {op}')

    def get_image(self, url, bypass):
        res = requests.get(url, stream=True)
        content_size = int(res.headers.get('content-length', 0))

        if content_size > MAX_IMAGE_SIZE and not bypass:
            raise OverflowError(f'Image exceeds max size ({content_size} > {MAX_IMAGE_SIZE})')

        return Image.open(BytesIO(res.content))

    def get_params(self, param):
        return [p.strip() for p in param.split(',')]
        # return param.replace(' ', '').split(',')

    def get_words(self, line):
        words = []
        depth = 0
        start = 0

        for index, char in enumerate(list(line)):
            if char == '(':
                depth += 1
            elif char == ')':
                depth -= 1
            elif char == ' ' and depth == 0:
                if start != index:
                    words.append(line[start:index])
                start = index + 1

        words.append(line[start:])
        return words

    def safe_get(self, arr, i):
        if i > len(arr) - 1:
            return None

        return arr[i]

    def get_stack(self, ctx, line, error):
        return f'```\n{line}\n\nError: {error}```'


def setup(bot):
    bot.add_cog(ImgEngine(bot))
