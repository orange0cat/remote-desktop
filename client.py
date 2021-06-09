from PIL import ImageGrab
from pynput.mouse import Controller, Button
from configparser import RawConfigParser
import numpy as np
import socket
import sys
import cv2
import time
import struct
import json
import hashlib
import win32api
import win32con
import threading
# pyinstaller 打包时需添加 --hidden-import=pynput.keyboard._win32 --hidden-import=pynput.mouse._win32

resolution = (win32api.GetSystemMetrics(win32con.SM_CXSCREEN), win32api.GetSystemMetrics(win32con.SM_CYSCREEN))
resize = (1400, 800)

class MyConfigParser(RawConfigParser):
    def __init__(self, defaults=None):
        RawConfigParser.__init__(self, defaults=defaults)

    def optionxform(self, option_str):
        return option_str


def socket_client(host, port):
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.connect((host, port))
        print(s.recv(1024).decode())
    except socket.error as e:
        print(e)
        sys.exit(1)

    resize_ratio = (resolution[0]/resize[0], resolution[1]/resize[1])

    base_info = {
        'resize_ratio': resize_ratio
    }
    s.send(json.dumps(base_info).encode())
    while True:
        response = s.recv(1024)
        if response.decode() == "client info confirm":
            break

    receive_thread = threading.Thread(target=receive_mouse_msg, args=(s, ))
    receive_thread.start()
    encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), 95]
    while True:
        flag, msg = make_screen_img(encode_param)
        if not flag:
            break
        flag = send_msg(s, msg)
        if not flag:
            break
        time.sleep(0.01)
    s.close()

def make_screen_img(encode_param):
    try:
        screen = ImageGrab.grab()
        bgr_img = cv2.cvtColor(np.array(screen), cv2.COLOR_RGB2BGR)  # 颜色空间转换, cv2.COLOR_RGB2BGR 将RGB格式转换成BGR格式
        img = cv2.resize(bgr_img, resize)  # 缩放图片
        return True, cv2.imencode(".jpg", img, encode_param)[1].tostring()  # 把当前图片img按照jpg格式编码
    except Exception as e:
        print(e)
        return False, None


def get_msg_info(msg):
    return len(msg), hashlib.md5(msg).hexdigest()


def make_msg_header(msg_length, msg_md5):
    header = {
        'msg_length': msg_length,
        'msg_md5': msg_md5
    }
    return json.dumps(header).encode()

def send_msg(conn, msg):
    msg_length, msg_md5 = get_msg_info(msg)
    msg_header = make_msg_header(msg_length, msg_md5)
    msg_header_length = struct.pack('i', len(msg_header))
    try:
        header_len_res = conn.send(msg_header_length)
        header_res = conn.send(msg_header)
        msg_res = conn.sendall(msg)
        return True
    except socket.error as e:
        print(e)
        return False


def receive_mouse_msg(conn, ):
    mouse = Controller()
    while True:
        try:
            msg_length = struct.unpack('i', conn.recv(4))[0]
            mouse_msg = json.loads(conn.recv(msg_length).decode())
            mouse_position = mouse_msg.get('mouse_position')
            event = mouse_msg.get('event')
            flags = mouse_msg.get('flags')
            mouse_event(mouse, mouse_position[0], mouse_position[1], event, flags)
            print(mouse_position[0], mouse_position[1], event, flags)

        except Exception as e:
            print(e)
            break
    conn.close()

def mouse_event(mouse, x, y, event, flags):
    flag_event = get_flag_event(flags)
    mouse.position = (x, y)
    # 鼠标左键
    if event == cv2.EVENT_LBUTTONDOWN:
        mouse.press(Button.left)
    elif event == cv2.EVENT_LBUTTONUP:
        mouse.release(Button.left)
    elif event == cv2.EVENT_LBUTTONDBLCLK:
        mouse.click(Button.left, 2)
    # 鼠标中键
    elif event == cv2.EVENT_MBUTTONDOWN:
        mouse.press(Button.middle)
    elif event == cv2.EVENT_MBUTTONUP:
        mouse.release(Button.middle)
    elif event == cv2.EVENT_MBUTTONDBLCLK:
        mouse.click(Button.middle, 2)
    # 鼠标右键
    elif event == cv2.EVENT_RBUTTONDOWN:
        mouse.press(Button.right)
    elif event == cv2.EVENT_RBUTTONUP:
        mouse.release(Button.right)
    elif event == cv2.EVENT_RBUTTONDBLCLK:
        mouse.click(Button.right, 2)


def get_flag_event(value):
    flags = [
        cv2.EVENT_FLAG_LBUTTON, # 1
        cv2.EVENT_FLAG_RBUTTON, # 2
        cv2.EVENT_FLAG_MBUTTON, # 4
        cv2.EVENT_FLAG_CTRLKEY, # 8
        cv2.EVENT_FLAG_SHIFTKEY, # 16
        cv2.EVENT_FLAG_ALTKEY, # 32
    ]
    flag_events = []
    for flag in sorted(flags, reverse=True):
        if value >= flag:
            flag_events.append(flag)
            value -= flag
    return flag_events


if __name__ == '__main__':
    config = MyConfigParser()
    config.read('config.ini', encoding='utf-8')
    server_host = config.get('Server', 'host')
    server_port = config.getint('Server', 'port')
    socket_client(server_host, server_port)