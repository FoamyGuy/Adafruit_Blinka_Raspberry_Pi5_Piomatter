import requests
from PIL import ImageFont, ImageDraw, Image
import adafruit_raspberry_pi5_piomatter
import numpy as np
import time


total_width = 128
total_height = 64

bottom_half_shift_compensation = 1

# Load the font
font = ImageFont.truetype("LindenHill-webfont.ttf", 26)  # Replace "arial.ttf" with your desired font file
#font = ImageFont.truetype("LindenHill-webfont.ttf", 46)  # Replace "arial.ttf" with your desired font file
# font = ImageFont.truetype("pointfree.ttf", 26)  # Replace "arial.ttf" with your desired font file
# font = ImageFont.truetype("LindenHill-Italic-webfont.ttf", 30)  # Replace "arial.ttf" with your desired font file

# Text to measure
#text = "Hello, World!"


quote_resp = requests.get("https://www.adafruit.com/api/quotes.php").json()

text = f'{quote_resp[0]["text"]} - {quote_resp[0]["author"]}'
#text = "Nothing is work unless you'd rather be doing something else - George Halas"
#text = "lllll " * 12
#print(text)

#print(font.getbbox(text))
x, y, text_width, text_height = font.getbbox(text)

full_txt_img = Image.new("RGB", (int(text_width) + 6, int(text_height) + 6), (0, 0, 0))
draw = ImageDraw.Draw(full_txt_img)
draw.text((3, 0), text, font=font, fill=(0, 128, 128))
full_txt_img.save("quote.png")

single_frame_img = Image.new("RGB", (total_width, total_height), (0, 0, 0))

geometry = adafruit_raspberry_pi5_piomatter.Geometry(width=total_width, height=total_height, n_addr_lines=4, rotation=adafruit_raspberry_pi5_piomatter.Orientation.R180)
framebuffer = np.asarray(single_frame_img) + 0  # Make a mutable copy

matrix = adafruit_raspberry_pi5_piomatter.AdafruitMatrixBonnetRGB888Packed(framebuffer, geometry)

print("Ctrl-C to exit")
while True:
    for x_pixel in range(-total_width-1,full_txt_img.width):
        #print(x_pixel)
        #print((x_pixel, 0, x_pixel + 64, 64))
        #single_frame_img = full_txt_img.crop((x_pixel, 0, 64, 64))
        #cur_frame = full_txt_img.crop((x_pixel, 0, x_pixel + 64, 64))

        if bottom_half_shift_compensation == 0:
            # full paste
            single_frame_img.paste(full_txt_img.crop((x_pixel, 0, x_pixel + total_width, total_height)), (0, 0))

        else:
            # top half
            #single_frame_img.paste(full_txt_img.crop((x_pixel, 0, x_pixel + total_width, total_height//2)), (0, 0))
            single_frame_img.paste(full_txt_img.crop((x_pixel, 0, x_pixel + total_width, 16)), (0, 0))
            # bottom half shift right 1 px
            single_frame_img.paste(full_txt_img.crop((x_pixel, 16, x_pixel + total_width, total_height)), (bottom_half_shift_compensation, 16))


        framebuffer[:] = np.asarray(single_frame_img)
        #time.sleep(0.1)
        #time.sleep(0.05)
        matrix.show()
        #time.sleep(0.05)
        #time.sleep(0.033)
        #time.sleep(0.1)
