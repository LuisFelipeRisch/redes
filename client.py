from datetime import datetime
from typing import List, Dict, TypedDict
import socket
import struct
import cv2
import numpy
import threading


class PacketDict(TypedDict):
    id: int
    data: bytes


PacketData = Dict[str, PacketDict]


class FrameDict(TypedDict):
    id: int
    total: int
    received: int
    data: PacketData


SERVER = socket.gethostbyname(socket.gethostname())
PORT = 3030
ADDRESS = (SERVER, PORT)
HEADER_FORMAT = "!IIHH"
CONFIG_FORMAT = "!II"
MAX_PAYLOAD_SIZE = 1480
HEADER_SIZE = struct.calcsize(HEADER_FORMAT)
MAX_PACKAGE_SIZE = HEADER_SIZE + MAX_PAYLOAD_SIZE
START_MESSAGE = '!start'
BUFFER_SIZE = 3600

client = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
client.connect(ADDRESS)

buffer_count = 0
buffer_init = {'index': 0, 'frame': 0}
buffer_end = {'index': -1, 'frame': 0}
buffer = [None] * BUFFER_SIZE
frames: Dict[str, FrameDict] = {}

video_fps = 0


def get_timestamp():
    timestamp = datetime.now()
    return timestamp.strftime("%d-%m-%Y %H:%M:%S")


def add_log(message: str):
    print(f"[{get_timestamp()}]: {message}")


def start_communication():
    add_log("Requesting media to server.")
    client.sendto(START_MESSAGE.encode('utf-8'), ADDRESS)


def play_buffer():
    global buffer_count
    while True:
        add_log(f"BUFFER COUNT: {buffer_count}")
        if (buffer_count > 0):
            frame_data = buffer[buffer_init['index']]
            if (frame_data != None):
                play_frame(frame_data)
                buffer[buffer_init['index']] = None
                buffer_count -= 1
            buffer_init['index'] = (buffer_init['index'] + 1) % BUFFER_SIZE


def play_frame(frame_data: bytes):
    frame = numpy.frombuffer(frame_data, dtype=numpy.uint8)
    frame = frame.reshape(frame.shape[0], 1)
    frame = cv2.imdecode(frame, cv2.IMREAD_COLOR)
    cv2.imshow('Video', frame)
    cv2.waitKey(25)


def mount_full_frame(frame_number: int, total: int, data: PacketData):
    global buffer_count
    bytes = b""

    for i in range(total):
        data_bytes = data[f"{i + 1}"]['data']
        bytes += data_bytes

    offset = frame_number - buffer_end['frame']

    if buffer_end['index'] == -1:
        buffer_index = 0
    else:
        buffer_index = buffer_end['index'] + offset
        if (buffer_end['index'] == 0 and offset < 0) or (buffer_end['index'] == BUFFER_SIZE - 1 and offset > 0):
            buffer_index = abs(BUFFER_SIZE - buffer_index)

    print(f"BUFFER INDEX: {buffer_index}")
    print(f"BUFFER END INDEX: {buffer_end['index']}")
    print(f"OFFSET: {offset}")

    if offset > 0 or buffer_end['index'] == -1:
        buffer_end['index'] = buffer_index
        buffer_end['frame'] = frame_number

    buffer[buffer_index] = bytes
    buffer_count += 1


def append_package(frame_number: int, sequence_number: int, frame_data: bytes):
    frame_key = f"{frame_number}"
    data_key = f"{sequence_number}"

    if frame_key not in frames:
        if sequence_number == 0:
            total = int.from_bytes(frame_data, 'big')

            frames[frame_key] = {'id': frame_number, 'total': total,
                                 'received': 0, 'data': {}}
        else:
            frames[frame_key] = {'id': frame_number,
                                 'received': 1, 'data': {data_key: {'id': sequence_number, 'data': frame_data}}}
    else:
        frame = frames[frame_key]

        if sequence_number == 0:
            total = int.from_bytes(frame_data, 'mount_full_framebig')
            frame['total'] = total
        else:
            frame['received'] += 1
            frame['data'][data_key] = {
                'id': sequence_number, 'data': frame_data}

            if ('received' in frame) and ('total' in frame):
                if frame['received'] == frame['total']:
                    add_log(f"FULL FRAME {frame_number}")
                    mount_full_frame(
                        frame_number, frame['total'], frame['data'])


def start_player():
    thread = threading.Thread(target=play_buffer)
    thread.start()


def listen_from_server():
    global video_fps

    add_log("Listening to server...")

    while True:
        data, address = client.recvfrom(MAX_PACKAGE_SIZE)
        add_log(f"Received a package from {address}")

        header = data[:HEADER_SIZE]
        frame_number, sequence_number, video_fps, payload_size = struct.unpack(
            HEADER_FORMAT, header)
        frame_data = data[HEADER_SIZE:]

        append_package(frame_number, sequence_number, frame_data)

        add_log(
            f"[PACKAGE INFO]: frame: {frame_number} - sequence: {sequence_number} - size: {payload_size}")


start_communication()
start_player()
listen_from_server()
