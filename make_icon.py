from PIL import Image, ImageDraw
from pathlib import Path

image = Image.new('RGBA', (256, 256), (0, 0, 0, 0))
draw = ImageDraw.Draw(image)
draw.rounded_rectangle((8, 8, 248, 248), 60, fill='#ae96ef')
ink = '#211930'
draw.rounded_rectangle((56, 106, 200, 141), 7, outline=ink, width=11)
draw.rounded_rectangle((66, 137, 190, 208), 5, outline=ink, width=11)
draw.line((128, 107, 128, 208), fill=ink, width=11)
draw.ellipse((79, 56, 128, 105), outline=ink, width=10)
draw.ellipse((128, 56, 177, 105), outline=ink, width=10)
image.save(Path(__file__).parent / 'icons/droppilot.ico', sizes=[(32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
