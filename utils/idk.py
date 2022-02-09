def fit_font_to_width(font: ImageFont.truetype, text: str, max_width: int) -> ImageFont.truetype:
    while font.getsize(text)[0] > max_width and font.size > 0:
        font = ImageFont.truetype(font.path, font.size - 1)
    return font


def fit_text_font_to_circle(base_font: ImageFont.FreeTypeFont, text, xy, anchor, cir_radius, cir_center) -> ImageFont.truetype:
    font = base_font
    fx, fy = xy
    cx, cy = cir_center

    bbox = font.getbbox(text, anchor=anchor)

    while not all([
        (cx - (bbox[0] + fx)) ** 2 + (cy - (bbox[1] + fy)) ** 2 < cir_radius ** 2,
        (cx - (bbox[0] + fx)) ** 2 + (cy - (bbox[3] + fy)) ** 2 < cir_radius ** 2,
        (cx - (bbox[2] + fx)) ** 2 + (cy - (bbox[1] + fy)) ** 2 < cir_radius ** 2,
        (cx - (bbox[2] + fx)) ** 2 + (cy - (bbox[3] + fy)) ** 2 < cir_radius ** 2,
    ]) and font.size > 1:
        font = ImageFont.truetype(font.path, font.size - 1)
        bbox = font.getbbox(text, anchor=anchor)

    return font


def wrap_text_in_circle(draw: ImageDraw.ImageDraw, xy, cir_radius, cir_center, text, fill=None, font=None, min_font_size=10, anchor=None, spacing=4, direction=None, features=None, language=None, stroke_width=0, stroke_fill=None, embedded_color=False):
    base_font = font
    lines = text.split(" ")
    text_draw_offset = 0
    x, y = xy

    while len(lines) > 0:
        text = ""
        contained = True
        while contained:
            if text != "":
                if direction == "btt":
                    text = " " + text
                else:
                    text += " "
            if direction == "btt":
                text = lines.pop(-1) + text
            else:
                text += lines.pop(0)

            font = fit_text_font_to_circle(base_font, text, (x, y + text_draw_offset), anchor, cir_radius,
                                           cir_center)

            if len(lines) == 0:
                contained = False
            if font.size < min_font_size and text.count(" ") > 0:
                if direction == "btt":
                    last_word = text.split(" ")[0]
                    text = " ".join(text.split(" ")[1:])
                    lines.append(last_word)
                else:
                    last_word = text.split(" ")[-1]
                    text = " ".join(text.split(" ")[:-1])
                    lines.insert(0, last_word)
                contained = False

        font = fit_text_font_to_circle(base_font, text, (x, y + text_draw_offset), anchor, cir_radius,
                                       cir_center)
        tdirection = None if direction == "btt" else direction
        draw.text((x, y + text_draw_offset), text, fill, font, anchor, spacing, None, tdirection, features, language,
                  stroke_width, stroke_fill, embedded_color)
        if direction == "btt":
            text_draw_offset -= font.size + spacing
        else:
            text_draw_offset += font.size + spacing
