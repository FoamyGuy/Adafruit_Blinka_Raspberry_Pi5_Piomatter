#!/usr/bin/python3
"""
Display a (possibly scaled) X session to a matrix

The display runs until the graphical program exits.

The display doesn't get a keyboard or mouse, so you have to use a program that
will get its input in some other way, such as from a gamepad.

For help with commandline arguments, run `python virtualdisplay.py --help`

This needs additional software to be installed (besides a graphical program to run). At a minimum you have to
install a virtual display server program (xvfb) and the pyvirtualdisplay importable Python module:

    $ sudo apt install -y xvfb
    $ pip install pyvirtualdisplay

Here's an example for running an emulator using a rom stored in "/tmp/snesrom.smc" on a virtual 128x128 panel made from 4 64x64 panels:

    $ python virtualdisplay.py --pinout AdafruitMatrixHatBGR  --scale 2 --backend xvfb  --width 128 --height 128  --serpentine --num-address-lines 5 --num-planes 4  -- mednafen -snes.xscalefs 1 -snes.yscalefs 1 -snes.xres 128 -video.fs 1 -video.driver softfb  /tmp/snesrom.smc
"""
# To run a nice emulator:

import shlex
import string
import traceback
from subprocess import Popen, run, check_output

import adafruit_blinka_raspberry_pi5_piomatter as piomatter
import click
import numpy as np
from PIL import ImageEnhance

import piomatter_click
from pyvirtualdisplay.smartdisplay import SmartDisplay
import sys

import tty
import termios

import selectors
import os

# def is_data():
#     data_list, _, _ = select.select([sys.stdin], [], [], 0.1)
#     return bool(data_list)
#
#
# def read_keyboard_data():
#     data_list, _, _ = select.select([sys.stdin], [], [], 0)
#     if bool(data_list):
#         return data_list[0].read()
#     return None
keyboard_debug = True
keys_down = set()
normal_characters = string.ascii_letters + string.digits
# key_map = {
#     " ": "space",
#     "/": "slash",
#     "\\": "backslash",
#     "'": "apostrophe",
#     b"\x7f".decode(): "BackSpace",
#     ".": "period",
#     ",": "comma",
#     "\t": "Tab",
#     "\r": "Return",
#     "!": "exclam",
#     "?": "question",
#     "@": "at",
#     "<": "less",
#     ">": "greater",
#     "=": "equal",
#     ";": "semicolon",
#     ":": "colon",
#     "+": "plus",
#     "-": "minus",
#     "*": "asterisk",
#     "(": "parenleft",
#     ")": "parenright",
#     "&": "ampersand",
#     "%": "percent",
#     "$": "dollar",
#     "#": "numbersign",
#     "": "",
#     "": "",
#     "": "",
# }
key_map = {
    b' ': "space",
    b'/': "slash",
    b'\\': "backslash",
    b"'": "apostrophe",
    b'\x7f': "BackSpace",
    b'.': "period",
    b',': "comma",
    b'\t': "Tab",
    b'\r': "Return",
    b'!': "exclam",
    b'?': "question",
    b'@': "at",
    b'<': "less",
    b'>': "greater",
    b'=': "equal",
    b';': "semicolon",
    b':': "colon",
    b'+': "plus",
    b'-': "minus",
    b'*': "asterisk",
    b'(': "parenleft",
    b')': "parenright",
    b'&': "ampersand",
    b'%': "percent",
    b'$': "dollar",
    b'#': "numbersign",
    b'\x1b[A': "Up",
    b'\x1b[B': "Down",
    b'\x1b[C': "Right",
    b'\x1b[D': "Left",
    b'\x1b': "Escape",
    b'^': "caret",
    b'[': "bracketleft",
    b']': "bracketright",
    b'{': "braceleft",
    b'}': "braceright",
    b'_': "underscore",
    #b'': "",
}

ctrl_modified_range = (1, 26)




@click.command
@click.option("--scale", type=float, help="The scale factor, larger numbers mean more virtual pixels", default=1)
@click.option("--backend", help="The pyvirtualdisplay backend to use", default="xvfb")
@click.option("--extra-args", help="Extra arguments to pass to the backend server", default="")
@click.option("--rfbport", help="The port number for the --backend xvnc", default=None, type=int)
@click.option("--use-xauth/--no-use-xauth", help="If a Xauthority file should be created", default=False)
@piomatter_click.standard_options
@click.argument("command", nargs=-1)
def main(scale, backend, use_xauth, extra_args, rfbport, width, height, serpentine, rotation, pinout, n_planes,
         n_addr_lines, command):
    def handle_key_event(evt_data):
        #print(f"inside handle key event {evt_data}")
        if evt_data in key_map.keys():
            keys_down.add(key_map[evt_data])
            run(["xdotool", "keydown", key_map[evt_data]], env=disp.env())
        elif evt_data.decode() in normal_characters:
            #print(f"sending '{evt_data.decode()}'")
            run(["xdotool", "keydown", f"{evt_data.decode()}"], env=disp.env())
            # print(f"result: {result}")
            keys_down.add(evt_data.decode())
            # if "No such key name" not in result.stderr:
            #     keys_down.add(kbd_data)

        elif ctrl_modified_range[0] <= int.from_bytes(evt_data) <= ctrl_modified_range[1]:
            keys_down.add("Control_L")
            run(["xdotool", "keydown", "Control_L"], env=disp.env())

            modified_key = chr(int.from_bytes(evt_data) + 96)
            print(f"ctrl modified {modified_key}")
            keys_down.add(modified_key)
            run(["xdotool", "keydown", modified_key], env=disp.env())

        elif len(evt_data) > 1:
            print("recvd multiple")
            for char_val in evt_data:
                print(f"{char_val}   {chr(char_val)}")
                char_bytes = char_val.to_bytes(1)
                handle_key_event(char_bytes)
        else:
            print(f"unknown input data: {evt_data}")

    old_settings = termios.tcgetattr(sys.stdin)
    selector = selectors.DefaultSelector()
    selector.register(fileobj=sys.stdin, events=selectors.EVENT_READ)

    tty.setraw(sys.stdin.fileno())
    kwargs = {}
    if backend == "xvnc":
        kwargs['rfbport'] = rfbport
    if extra_args:
        kwargs['extra_args'] = shlex.split(extra_args)
    print("xauth", use_xauth)
    geometry = piomatter.Geometry(width=width, height=height, n_planes=n_planes, n_addr_lines=n_addr_lines,
                                  rotation=rotation)
    framebuffer = np.zeros(shape=(geometry.height, geometry.width, 3), dtype=np.uint8)
    matrix = piomatter.PioMatter(colorspace=piomatter.Colorspace.RGB888Packed, pinout=pinout, framebuffer=framebuffer,
                                 geometry=geometry)

    try:
        with SmartDisplay(backend=backend, use_xauth=use_xauth, size=(round(width * scale), round(height * scale)),
                          manage_global_env=False, **kwargs) as disp, Popen(command, env=disp.env()) as proc:
            while proc.poll() is None:
                img = disp.grab(autocrop=False)

                # print(disp.env())
                if img is None:
                    continue
                img = img.resize((width, height))
                enhancer = ImageEnhance.Brightness(img)
                img = enhancer.enhance(0.85)
                framebuffer[:, :] = np.array(img)
                matrix.show()

                # inc_kbd_data = read_keyboard_data()
                # if inc_kbd_data is not None:
                #     print(inc_kbd_data)
                #     if c == '\x11':
                #          raise KeyboardInterrupt
                # if is_data():
                #     # https://gitlab.com/nokun/gestures/-/wikis/xdotool-list-of-key-codes
                #     c = sys.stdin.read(1).encode()
                #     if keyboard_debug:
                #         if c == b'\x11':
                #             raise KeyboardInterrupt
                #         print(c)
                #
                #         if c == b'\x1b':  # x1b is ESC
                #             print(f"is more data? {is_data()}")
                #             #next_read = sys.stdin.read(1).encode()
                #             #print(f"next: {next_read}")
                event_count = 0
                for key, __ in selector.select(timeout=0):
                    event_count += 1
                    # character = key.fileobj.read(1)
                    kbd_data = os.read(key.fileobj.fileno(), 3)
                    if keyboard_debug:
                        print(kbd_data)

                    handle_key_event(kbd_data)

                # no kbd events, so keyup all keys
                if event_count == 0:
                    for key in keys_down:
                        run(["xdotool", "keyup", key], env=disp.env())

    finally:
        termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_settings)


if __name__ == '__main__':
    main()
