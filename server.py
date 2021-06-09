from PIL import ImageGrab
import socket
import threading
import time
import struct
import sys
import cv2
import json
import hashlib
import numpy as np
import win32api
import win32con

host = '0.0.0.0'
port = 8001

def socket_service():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind((host, port))
        s.listen(10)
    except socket.error as e:
        print(e)
        sys.exit(1)
    print('Waiting connection...')

    while True:
        conn, addr = s.accept()
        t = threading.Thread(target=deal_data, args=(conn, addr))
        t.start()


def deal_data(conn, addr):
    print('Accept new connection from {0}'.format(addr))
    conn.send('Hi, Welcome to the server!'.encode())

    while True:
        try:
            resize_ratio = json.loads(get_msg(conn, 1024).decode())
            if resize_ratio.get('resize_ratio'):
                conn.send("client info confirm".encode())
                break
        except Exception as e:
            print(e)

    param = {
        'resize_ratio': resize_ratio.get('resize_ratio'),
        'conn': conn,
        'pos': (0, 0)
    }
    window_name = addr[0]
    cv2.namedWindow(window_name)
    cv2.setMouseCallback(window_name, OnMouseMove, param=param)

    while True:
        encode_header_len = get_msg(conn, 4)
        if not encode_header_len:
            break
        msg_header_length = struct.unpack('i', encode_header_len)[0]
        encode_header = get_msg(conn, msg_header_length)
        if not encode_header:
            break
        msg_header = json.loads(encode_header.decode())
        img_data = recv_msg(conn, msg_header)
        if not img_data:
            break
        if hashlib.md5(img_data).hexdigest() != msg_header['msg_md5']:
            break
        msg_decode = np.frombuffer(img_data, np.uint8)
        img_decode = cv2.imdecode(msg_decode, cv2.IMREAD_COLOR)

        if cv2.getWindowProperty(window_name, cv2.WND_PROP_VISIBLE) <= 0:
            break
        cv2.imshow(window_name, img_decode)
        key = cv2.waitKey(20)
        print(key) if key != -1 else None

    cv2.destroyAllWindows()
    conn.close()

def get_msg(conn, length):
    try:
        return conn.recv(length)
    except socket.error as e:
        print(e)


def recv_msg(conn, msg_header):
    recv_size = 0
    img_data = b''
    while recv_size < msg_header['msg_length']:
        if msg_header['msg_length'] - recv_size > 10240:
            recv_data = get_msg(conn, 10240)
        else:
            recv_data = get_msg(conn, msg_header['msg_length']-recv_size)
        recv_size += len(recv_data)
        img_data += recv_data
    return img_data


def OnMouseMove(event, x, y, flags, param):
    win32api.SetCursor(win32api.LoadCursor(0, win32con.IDC_ARROW ))

    conn = param['conn']
    screen_x = round(x * param['resize_ratio'][0])
    screen_y = round(y * param['resize_ratio'][1])

    if (screen_x, screen_y) == param['pos'] and event == 0 and flags == 0:
        pass
    else:
        param['pos'] = (screen_x, screen_y)
        msg = {'mouse_position': (screen_x, screen_y), 'event': event, 'flags': flags}
        try:
            conn.send(struct.pack('i', len(json.dumps(msg))))
            conn.send(json.dumps(msg).encode())
            # print('event: {},  x: {},  y: {}  flags: {}'.format(event, x, y, flags))
        except socket.error as e:
            print(e)


if __name__ == '__main__':
    socket_service()