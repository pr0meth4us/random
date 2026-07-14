from PIL import Image

img = Image.open("scratch/poster_gen/poster.png").convert("RGB")
width, height = img.size

# Find the bounding box of pixels that are very close to white (e.g. R>240, G>240, B>240)
min_x = width
min_y = height
max_x = 0
max_y = 0

for y in range(height):
    for x in range(width):
        r, g, b = img.getpixel((x, y))
        if r > 240 and g > 240 and b > 240:
            if x < min_x: min_x = x
            if x > max_x: max_x = x
            if y < min_y: min_y = y
            if y > max_y: max_y = y

print(f"White card approx bounds: ({min_x}, {min_y}) to ({max_x}, {max_y})")
print(f"Width: {max_x - min_x}, Height: {max_y - min_y}")
