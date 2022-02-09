from fontTools.ttLib import TTFont


class TTFTool:
    def __init__(self, font_path):
        self._font = TTFont(font_path)

    def char_exists(self, unicode_char) -> bool:
        for cmap in self._font['cmap'].tables:
            if cmap.isUnicode() and ord(unicode_char) in cmap.cmap:
                return True

        return False

    def chars_missing(self, unicode_chars) -> bool:
        for char in list(unicode_chars):
            if not self.char_exists(char):
                return True

        return False
