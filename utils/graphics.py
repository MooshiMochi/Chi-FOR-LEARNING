import subprocess
from io import BytesIO
from os import listdir

from PIL import Image as PILImage
from wand.color import Color
from wand.image import Image


def process_magik(unused, img_bytes, multiplier):
    bio = BytesIO()

    with Image(file=img_bytes) as img:
        o_width = img.width
        o_height = img.height
        img.liquid_rescale(width=int(img.width * 0.5),
                           height=int(img.height * 0.5),
                           delta_x=multiplier,
                           rigidity=0)
        img.liquid_rescale(width=int(img.width * 1.5),  
                           height=int(img.height * 1.5),
                           delta_x=2,
                           rigidity=0)
        img.resize(width=o_width, height=o_height)
        img.save(file=bio)
        img.destroy()

    bio.seek(0)
    return bio

# def process_magik(img_bytes, multiplier):
#     base_args = [
#         'convert', '-',
#         '-liquid-rescale', f'50%x50%+{multiplier}-0',
#         '-liquid-rescale', '150%x150%+2-0',
#         '-resize', '150%x150%',
#         'png:-'
#     ]
#     proc = subprocess.Popen(base_args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, stdin=subprocess.PIPE)
#     stdout, stderr = proc.communicate(img_bytes.read())
#     bio = BytesIO(stdout)
#     bio.seek(0)
#     return bio

def process_radial(img_bytes, blur):
    base_args = ['convert', '-', '-rotational-blur', str(blur), 'png:-']
    proc = subprocess.Popen(base_args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, stdin=subprocess.PIPE)
    stdout, stderr = proc.communicate(img_bytes)
    return stdout

def check_decompression_bomb(buffer):
    try:
        i = PILImage.open(BytesIO(buffer))
    except (PILImage.DecompressionBombWarning, PILImage.DecompressionBombError):
        return True
    else:
        i.close()
        return False
