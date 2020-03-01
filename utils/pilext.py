from io import BytesIO

def to_bytes(im, fmt: str = 'png'):
    bio = BytesIO()
    im.save(bio, fmt)
    bio.seek(0)
    return bio

def close(*im):
    for image in im:
        image.close()
