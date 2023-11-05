from datetime import datetime
from typing import List, Dict, TypedDict
import socket
import struct
import cv2
import numpy as np
import threading
import time
import base64
import argparse
import os
import traceback
import signal


class PacketDict(TypedDict):
    id: int
    data: bytes


PacketData = Dict[str, PacketDict]


class FrameDict(TypedDict):
    id: int
    total: int
    received: int
    data: PacketData


HEADER_FORMAT = "!IIHHI"
MAX_PAYLOAD_SIZE = 5000
HEADER_SIZE = struct.calcsize(HEADER_FORMAT)
MAX_PACKAGE_SIZE = HEADER_SIZE + MAX_PAYLOAD_SIZE
BUFFER_SIZE = 3600
CONFIRMATION_TIMEOUT = 5
SUBSCRIBE_MESSAGE = '!subscribe'
UNSUBSCRIBE_MESSAGE = '!unsubscribe'

buffer_count = 0
buffer_init = {'index': 0, 'frame': 0}
buffer_end = {'index': -1, 'frame': 0}
buffer = [None] * BUFFER_SIZE
frames: Dict[str, FrameDict] = {}

video_fps = 0
total_frames = 0
video_finished = False

server_ip = ""
server_port = ""
client = None

expected_sequence = 0

unordered_count = 0
unreceived_count = 0


def get_timestamp():
    timestamp = datetime.now()
    return timestamp.strftime("%d-%m-%Y %H:%M:%S")


def add_log(message: str):
    print(f"[{get_timestamp()}]: {message}")


def unsubscribe():
    add_log("Subscribing to server...")
    client.sendto(UNSUBSCRIBE_MESSAGE.encode(
        'utf-8'), (server_ip, server_port))


def subscribe():
    add_log("Subscribing to server...")
    client.sendto(SUBSCRIBE_MESSAGE.encode('utf-8'), (server_ip, server_port))


def play_buffer():
    global buffer_count
    cv2.namedWindow('Video', cv2.WINDOW_NORMAL)
    while not video_finished or buffer_count > 0:
        if (buffer_count > 0):
            frame_data = buffer[buffer_init['index']]
            if (frame_data != None):
                time.sleep(1/video_fps)
                play_frame(frame_data)
                buffer[buffer_init['index']] = None
                buffer_count -= 1
            buffer_init['index'] = (buffer_init['index'] + 1) % BUFFER_SIZE


def play_frame(frame_data: bytes):
    decoded_data = base64.b64decode(frame_data, ' /')
    npdata = np.fromstring(decoded_data, dtype=np.uint8)
    frame = cv2.imdecode(npdata, 1)
    cv2.imshow('Video', frame)
    key = cv2.waitKey(1) & 0xFF
    if key == ord('q'):
        unsubscribe()
        client.close()
        os._exit(1)


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

    if offset > 0 or buffer_end['index'] == -1:
        buffer_end['index'] = buffer_index
        buffer_end['frame'] = frame_number

    buffer[buffer_index] = bytes
    buffer_count += 1


def append_package(frame_number: int, sequence_number: int, frame_data: bytes):
    global video_finished, unordered_count, expected_sequence

    frame_key = f"{frame_number}"
    data_key = f"{sequence_number}"

    if (sequence_number != expected_sequence and sequence_number > (expected_sequence - 1)):
        unordered_count += 1

    expected_sequence = sequence_number + 1

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
                if frame['received'] == frame['total']:
                    expected_sequence = 0
                    mount_full_frame(
                        frame_number, frame['total'], frame['data'])
                    if frame_number == (total_frames - 1):
                        add_log(
                            "All frames received. The client stopped listening from the server.")
                        video_finished = True


def start_player():
    thread = threading.Thread(target=play_buffer)
    thread.start()


def unpack_packet(packet):
    global video_fps, total_frames
    header = packet[:HEADER_SIZE]
    frame_number, sequence_number, fps, payload_size, frames_count = struct.unpack(
        HEADER_FORMAT, header)
    frame_data = packet[HEADER_SIZE:]

    video_fps = fps
    total_frames = frames_count

    return frame_number, sequence_number, fps, payload_size, frame_data


def listen_from_server():
    global video_fps

    add_log("Listening to server...")

    while not video_finished:
        packet, address = client.recvfrom(MAX_PACKAGE_SIZE)
        add_log(f"Received a package from {address}")

        frame_number, sequence_number, video_fps, payload_size, frame_data = unpack_packet(
            packet)

        add_log(
            f"[PACKAGE INFO]: frame: {frame_number} - sequence: {sequence_number} - size: {payload_size}")

        append_package(frame_number, sequence_number, frame_data)


def handle_args():
    global server_ip, server_port

    parser = argparse.ArgumentParser(
        prog='Client',
        description='Client that receives media from server'
    )

    parser.add_argument('-ip', '--server-ip', type=str,
                        help='Defines the server ip.')

    parser.add_argument('-p', '--server-port', type=int,
                        help='Defines the server port.')

    args = parser.parse_args()

    if args.server_ip == None or args.server_port == None:
        print(
            "Server ip and port must be passed as arguments. Please, use -h option to get help.")
        os._exit(1)

    server_ip = args.server_ip
    server_port = args.server_port


def close_socket():
    global client
    if client != None:
        client.close()
        client = None


# Unsubscribe the server if a ctrl + C is received
def signal_handler(sig, frame):
    global client
    if client != None:
        unsubscribe()
    close_socket()
    os._exit(0)


def count_lost_packets():
    lost_count = 0
    for frame_key, frame in frames.items():
        if 'total' not in frame:
            add_log(
                f"It is impossible to precisely determine the number of packets lost by the client in frame {frame_key} due to incomplete data transmission. However, it is evident that the client lost, at the very least, one packet, specifically the initial packet of the frame.")
            lost_count += 1
        else:
            lost_count += (frame['total'] - frame['received'])

    return lost_count


def show_report():
    lost_count = count_lost_packets()
    add_log(
        f"There were {lost_count} packets lost and {unordered_count} packets received out of order.")


def main():
    global client
    try:
        signal.signal(signal.SIGINT, signal_handler)

        handle_args()

        client = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        subscribe()

        start_player()
        listen_from_server()

        show_report()
    finally:
        close_socket()


main()
