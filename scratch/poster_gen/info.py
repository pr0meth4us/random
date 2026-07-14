from PIL import Image

def get_info(path):
    with Image.open(path) as img:
        print(f"{path}: {img.size}, mode={img.mode}")

get_info("scratch/poster_gen/poster.png")
get_info("scratch/poster_gen/logo.png")
get_info("scratch/poster_gen/qr.png")
