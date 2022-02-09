from asyncio import create_subprocess_shell
from asyncio.subprocess import PIPE


class TranscodeError(Exception):
    def __init__(self, message: str):
        super().__init__(message)


async def transcode(input_bytes: bytes, output_format: str, extra_args: list = []):
    arg_format = '' if not extra_args else ' '.join(extra_args) + ' '
    print(f'ffmpeg -v error -i - {arg_format}-f {output_format} pipe:1')
    proc = await create_subprocess_shell(f'ffmpeg -v error -i - {arg_format}-f {output_format} pipe:1', stdin=PIPE, stderr=PIPE, stdout=PIPE)
    out, err = await proc.communicate(input_bytes)

    if not out:
        if err:
            raise TranscodeError(err.decode())

        raise TranscodeError('Transcoded yielded no output and no error')

    return out
