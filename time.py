#!/usr/bin/env python3
# elders_sgu_block_digits.py
# BeagleBone Black — SH1106 I2C — SGU-style block glyph clock (HH:MM)
# Requires: smbus2, pillow
# pip3 install smbus2 pillow

from smbus2 import SMBus
from PIL import Image, ImageDraw
import time, datetime

I2C_BUS = 1
I2C_ADDR = 0x3C
WIDTH = 132
VISIBLE_WIDTH = 128
HEIGHT = 64
PAGES = HEIGHT // 8
CMD_SET_PAGE = 0xB0

bus = SMBus(I2C_BUS)

def sh1106_init():
    cmds = [
        0xAE, 0xD5, 0x80, 0xA8, HEIGHT - 1, 0xD3, 0x00,
        0x40, 0xAD, 0x8B, 0xA1, 0xC8, 0xDA, 0x12,
        0x81, 0x7F, 0xD9, 0x22, 0xDB, 0x40, 0xA4, 0xA6, 0xAF
    ]
    for c in cmds:
        bus.write_byte_data(I2C_ADDR, 0x00, c)
        time.sleep(0.001)

def sh1106_clear():
    blank = [0x00] * WIDTH
    for page in range(PAGES):
        bus.write_byte_data(I2C_ADDR, 0x00, CMD_SET_PAGE | page)
        bus.write_byte_data(I2C_ADDR, 0x00, 0x00)
        bus.write_byte_data(I2C_ADDR, 0x00, 0x10)
        for i in range(0, WIDTH, 16):
            bus.write_i2c_block_data(I2C_ADDR, 0x40, blank[i:i+16])

def sh1106_display_image(img):
    px = img.convert('1').load()
    for page in range(PAGES):
        page_bytes = []
        for col in range(WIDTH):
            byte = 0
            vis_col = col - (WIDTH - VISIBLE_WIDTH) // 2
            for bit in range(8):
                y = page * 8 + bit
                if 0 <= vis_col < VISIBLE_WIDTH and 0 <= y < HEIGHT:
                    if px[vis_col, y] == 0:
                        byte |= (1 << bit)
            page_bytes.append(byte)
        bus.write_byte_data(I2C_ADDR, 0x00, CMD_SET_PAGE | page)
        bus.write_byte_data(I2C_ADDR, 0x00, 0x00)
        bus.write_byte_data(I2C_ADDR, 0x00, 0x10)
        for i in range(0, WIDTH, 16):
            bus.write_i2c_block_data(I2C_ADDR, 0x40, page_bytes[i:i+16])

# --- SGU block glyphs (clear blocks with spaces between) ---
# Each glyph: top "######", three inner rows (3 block positions per row), bottom "######", last "  ##  "
# Represent blocks as "##" and spaces as "  " for clarity in the arrays; renderer maps them to pixels.
GLYPHS = {
    '0': [
        "######",
        "                  ",  # 3 inner blocks rows flattened as chars - will map later
        "                  ",
        "                  ",
        "######",
        "  ##  "
    ],
    '1': [
        "######",
        "##                ",
        "                  ",
        "                  ",
        "######",
        "  ##  "
    ],
    '2': [
        "######",
        "####              ",
        "                  ",
        "                  ",
        "######",
        "  ##  "
    ],
    '3': [
        "######",
        "######            ",
        "                  ",
        "                  ",
        "######",
        "  ##  "
    ],
    '4': [
        "######",
        "######            ",
        "##                ",
        "                  ",
        "######",
        "  ##  "
    ],
    '5': [
        "######",
        "######            ",
        "####              ",
        "                  ",
        "######",
        "  ##  "
    ],
    '6': [
        "######",
        "######            ",
        "######            ",
        "                  ",
        "######",
        "  ##  "
    ],
    '7': [
        "######",
        "######            ",
        "######            ",
        "##                ",
        "######",
        "  ##  "
    ],
    '8': [
        "######",
        "######            ",
        "######            ",
        "####              ",
        "######",
        "  ##  "
    ],
    '9': [
        "######",
        "######            ",
        "######            ",
        "######            ",
        "######",
        "  ##  "
    ],
    ':': [
        "      ",
        "      ",
        "  ##  ",
        "      ",
        "  ##  ",
        "      "
    ],
    ' ': [
        "      ",
        "      ",
        "      ",
        "      ",
        "      ",
        "      "
    ]
}

# Instead of storing long space strings, build inner rows dynamically using blocks-per-row logic.
GLYPH_BLOCKS_PER_ROW = 3
GLYPH_ROWS_INNER = 3  # number of inner rows
def build_glyph_from_digit(d):
    # d: int 0..9
    # total inner blocks = 9, fill left-to-right, top-to-bottom
    n = int(d)
    rows = []
    rows.append("######")
    blocks_left = n
    for r in range(GLYPH_ROWS_INNER):
        row = []
        for b in range(GLYPH_BLOCKS_PER_ROW):
            if blocks_left > 0:
                row.append("##")
                blocks_left -= 1
            else:
                row.append("  ")
        rows.append("".join(row))
    rows.append("######")
    rows.append("  ##  ")
    return rows

# Build final glyph table
PROP_GLYPHS = {str(d): build_glyph_from_digit(d) for d in range(10)}
# colon glyph: two centered dots
def make_colon():
    rows = []
    rows.append("      ")
    rows.append("      ")
    rows.append("  ##  ")
    rows.append("      ")
    rows.append("  ##  ")
    rows.append("      ")
    return rows
PROP_GLYPHS[':'] = make_colon()
PROP_GLYPHS[' '] = ["      "]*6

# Determine glyph width and height
GLYPH_H = len(next(iter(PROP_GLYPHS.values())))
GLYPH_W = len(PROP_GLYPHS['0'][1])  # inner row length

def draw_glyph(draw, glyph, x, y, scale):
    for ry, row in enumerate(glyph):
        for cx in range(0, len(row), 2):
            cell = row[cx:cx+2]
            if cell == "##":
                x0 = x + (cx//2) * scale
                y0 = y + ry * scale
                draw.rectangle([x0, y0, x0 + scale - 1, y0 + scale - 1], fill=0)

def render_time_image(tstr, colon_on=True):
    # compute scale so 5 glyphs fit horizontally
    glyph_pixel_w = (GLYPH_W//2) *  (VISIBLE_WIDTH // (5 * (GLYPH_W//2 + 1)))  # rough estimate fallback
    # simpler: pick SCALE such that total <= VISIBLE_WIDTH
    for S in range(8,1,-1):
        total_w = (GLYPH_W//2) * S * 5 + (5-1) * S
        if total_w <= VISIBLE_WIDTH:
            SCALE = S
            break
    else:
        SCALE = 2
    SPACING = SCALE
    glyph_pixel_w = (GLYPH_W//2) * SCALE
    glyph_pixel_h = GLYPH_H * SCALE
    total_w = glyph_pixel_w * 5 + SPACING * 4
    x_start = (VISIBLE_WIDTH - total_w)//2
    y = (HEIGHT - glyph_pixel_h)//2
    img = Image.new('1', (VISIBLE_WIDTH, HEIGHT), 1)
    draw = ImageDraw.Draw(img)
    x = x_start
    for ch in tstr:
        if ch == ':' and not colon_on:
            g = PROP_GLYPHS[' ']
        else:
            g = PROP_GLYPHS.get(ch, PROP_GLYPHS[' '])
        draw_glyph(draw, g, x, y, SCALE)
        x += glyph_pixel_w + SPACING
    return img

def main():
    sh1106_init()
    sh1106_clear()
    last = None
    blink = True
    try:
        while True:
            now = datetime.datetime.now()
            tstr = now.strftime("%H:%M")
            colon_on = (now.second % 2 == 0)
            if tstr != last or colon_on != blink:
                img = render_time_image(tstr, colon_on=colon_on)
                sh1106_display_image(img)
                last = tstr
                blink = colon_on
            time.sleep(0.12)
    except KeyboardInterrupt:
        sh1106_clear()
        bus.close()

if __name__ == "__main__":
    main()
