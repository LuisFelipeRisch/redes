from datetime import datetime
from typing import List, Dict, TypedDict
import socket
import struct
import cv2
import numpy


class PacketDict(TypedDict):
    id: int
    data: bytes


PacketData = Dict[str, PacketDict]


class FrameDict(TypedDict):
    id: int
    total: int
    received: int
    data: PacketData


# FramesDict =

SERVER = socket.gethostbyname(socket.gethostname())
PORT = 3030
ADDRESS = (SERVER, PORT)
HEADER_FORMAT = "!IIH"
CONFIG_FORMAT = "!II"
MAX_PAYLOAD_SIZE = 60000
HEADER_SIZE = struct.calcsize(HEADER_FORMAT)
MAX_PACKAGE_SIZE = HEADER_SIZE + MAX_PAYLOAD_SIZE
START_MESSAGE = '!start'

client = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
client.connect(ADDRESS)

# frames_buffer: = []
frames: Dict[str, FrameDict] = {}

frame_height = 0
frame_width = 0


def get_timestamp():
    timestamp = datetime.now()
    return timestamp.strftime("%d-%m-%Y %H:%M:%S")


def add_log(message: str):
    print(f"[{get_timestamp()}]: {message}")


def start_communication():
    add_log("Requesting media to server.")
    client.sendto(START_MESSAGE.encode('utf-8'), ADDRESS)


def read_video_config(data: bytes):
    global frame_height, frame_width

    width, height = struct.unpack(CONFIG_FORMAT, data)

    frame_height = height
    frame_width = width


def play_frame(frame_data: bytes):
    frame = numpy.frombuffer(frame_data, dtype=numpy.uint8)
    add_log(f"HEIGHT: {frame_height} - WIDTH: {frame_width}")
    frame = frame.reshape((frame_height, frame_width, 3))
    cv2.imshow('Video', frame)
    cv2.waitKey(25)


def mount_full_frame(total: int, data: PacketData):
    bytes = b""

    for i in range(total):
        data_bytes = data[f"{i + 1}"]['data']
        add_log(f'INDEX: {i+1} - LENGTH: {len(data_bytes)}')
        bytes += data_bytes

    add_log(f"BYTES LENGTH: {len(bytes)}")
    play_frame(bytes)


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
            total = int.from_bytes(frame_data, 'big')
            frame['total'] = total
        else:
            frame['received'] += 1
            frame['data'][data_key] = {
                'id': sequence_number, 'data': frame_data}

            if ('received' in frame) and ('total' in frame):
                add_log(
                    f"TOTAL: {frame['total']} - RECEIVED: {frame['received']}")
                if frame['received'] == frame['total']:
                    add_log(f"FULL FRAME {frame_number}")
                    mount_full_frame(frame['total'], frame['data'])


def listen_from_server():
    add_log("Listening to server...")

    while True:
        data, address = client.recvfrom(MAX_PACKAGE_SIZE)
        # add_log(f"Received a package from {address}")

        header = data[:HEADER_SIZE]
        frame_number, sequence_number, payload_size = struct.unpack(
            HEADER_FORMAT, header)
        frame_data = data[HEADER_SIZE:]

        if frame_number != 0:
            append_package(frame_number, sequence_number, frame_data)
        else:
            read_video_config(frame_data)

        add_log(
            f"[PACKAGE INFO]: frame: {frame_number} - sequence: {sequence_number} - size: {payload_size}")


start_communication()
listen_from_server()
