from math import floor


# TODO: Chop long single-words
# from PIL import ImageFont

def wrap(font, text, max_line_width) -> str:
    """
    Wraps the text onto newlines accordingly, based on the given boundaries.

    Parameters
    ----------
    font: PIL.ImageFont
        The font to be used for measurement.
    text: str
        The text to wrap.
    max_line_width: int
        The maximum width of a line.

    Returns
    -------
    str
        The text, split where needed to ensure no overflow.
    """
    words = text.split()

    lines = []
    line = []

    for word in words:
        newline = ' '.join(line + [word])

        w, h = font.getsize(newline)

        if w > max_line_width:
            lines.append(' '.join(line))
            line = [word]
        else:
            line.append(word)

    if line:
        lines.append(' '.join(line))

    return ('\n'.join(lines)).strip()


def auto_text_size(text, font, desired_width, size_min, size_max, font_scalar=1):
    for size in range(size_max, size_min, -font_scalar):
        new_font = font.font_variant(size=size)
        font_width, _ = new_font.getsize(text)
        if font_width >= desired_width:
            wrapped = wrap(new_font, text, desired_width)
            w = max(new_font.getsize(line)[0] for line in wrapped.splitlines())
            if abs(desired_width - w) <= 10:
                return new_font, wrapped

    fallback = font.font_variant(size=fallback_size)
    return fallback, wrap(fallback, text, desired_width)


def font_auto_scale(font, text, desired_width, size_min, size_max, font_scalar=1):
    for size in range(size_max, size_min - 1, -font_scalar):
        new_font = font.font_variant(size=size)
        font_width, _ = new_font.getsize(text)
        if font_width <= desired_width:
            return new_font
            # w = max(new_font.getsize(line)[0] for line in wrapped.splitlines())
            # if abs(desired_width - w) <= 10:
            #     return new_font, wrapped

    fallback = font.font_variant(size=size_min)
    return fallback  #, wrap(fallback, text, desired_width)

# def auto_text_size(text, font, size, container_width, min_size=30, max_size=50):
#     ifont = ImageFont.truetype(font=font, size=size)
#     w, _ = ifont.getsize(text)
#
#     while w >= container_width and ifont.size > 0:
#         if not (min_size < ifont.size) < max_size:
#             break
#
#         ifont = ifont.font_variant(size=ifont.size - 1)
#         w, _ = ifont.getsize(text)
#
#     return ifont, wrap(ifont, text, container_width)
