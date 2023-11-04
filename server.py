from datetime import datetime
import socket
import threading
import cv2
import struct
import time
import argparse
import base64
import imutils
import queue
import os

SERVER = socket.gethostbyname(socket.gethostname())
PORT = 3030
ADDRESS = (SERVER, PORT)
MAX_PAYLOAD_SIZE = 65000
HEADER_FORMAT = "!IIHH"
HEADER_SIZE = struct.calcsize(HEADER_FORMAT)
MAX_PACKAGE_SIZE = HEADER_SIZE + MAX_PAYLOAD_SIZE
START_MESSAGE = '!start'
SUBSCRIBED_MESSAGE = '!subscribed'
VIDEO_WIDTH = 400

server = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
server.bind(ADDRESS)

video_fps = 0
delay = 0
clients_address = []
frame_queue = queue.Queue(maxsize=10)

media_path = ""


def get_timestamp():
    timestamp = datetime.now()
    return timestamp.strftime("%d-%m-%Y %H:%M:%S")


def add_log(message: str):
    print(f"[{get_timestamp()}]: {message}")


def build_packet(frame_number: int, sequence_number: int, video_fps: int, payload: bytes) -> bytes:
    # Build the package header
    header = struct.pack(HEADER_FORMAT, frame_number,
                         sequence_number, video_fps, len(payload))
    # Prepend the header to the payload
    packet = header + payload
    return packet


def send_packet(packet, address):
    time.sleep(delay / 1000)
    server.sendto(packet, address)


def client_already_subscribed(address):
    for client_address in clients_address:
        if client_address == address:
            return True

    return False


def listen_to_subscriptions():
    add_log(f"Server is listening for subscriptions on {SERVER}:{PORT}")

    while True:
        data, address = server.recvfrom(MAX_PACKAGE_SIZE)
        decoded_data = data.decode('utf-8')

        if decoded_data != START_MESSAGE:
            add_log(f"{decoded_data} unknown start message!")
            continue

        if client_already_subscribed(address):
            add_log(f"{address} already subscribed.")
            continue

        clients_address.append(address)

        add_log(
            f"New client {address} subscribed. {len(clients_address)} active clients.")


def send_packet_to_clients(frame_number, sequence_number, payload):
    packet = build_packet(
        frame_number, sequence_number, video_fps, payload)
    for client_address in clients_address:
        send_packet(packet, client_address)


def read_video():
    global video_fps
    video_capture = cv2.VideoCapture(media_path)
    video_fps = int(video_capture.get(cv2.CAP_PROP_FPS))
    while (video_capture.isOpened()):
        try:
            _, frame = video_capture.read()
            frame = imutils.resize(frame, width=VIDEO_WIDTH)
            frame_queue.put(frame)
        except:
            os._exit(1)
    add_log('Player closed')
    video_capture.release()


def handle_client():
    global video_fps

    frame_number = 0

    while True:
        frame = frame_queue.get()
        retval, raw_frame = cv2.imencode(
            ".jpeg", frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
        frame_data = base64.b64encode(raw_frame)

        chunks = [frame_data[i:i + MAX_PAYLOAD_SIZE]
                  for i in range(0, len(frame_data), MAX_PAYLOAD_SIZE)]

        sequence_number = 0

        send_packet_to_clients(frame_number, sequence_number,
                               len(chunks).to_bytes(4, 'big'))

        sequence_number += 1

        for chunk in chunks:
            add_log(
                f"[PACKAGE INFO]: frame: {frame_number} - sequence: {sequence_number} - size: {len(chunk)}")
            send_packet_to_clients(frame_number, sequence_number, chunk)

            sequence_number += 1

        frame_number += 1


def send_media_to_clients():
    while True:
        if len(clients_address) > 0:
            handle_client()


def check_file_existence(file_path):
    if not os.path.exists(file_path):
        print(f"File {file_path} not found.")
        os._exit(1)


def handle_args():
    global delay, media_path

    parser = argparse.ArgumentParser(
        prog='Server',
        description='Server that sends media to clients'
    )

    parser.add_argument('-d', '--delay', type=float,
                        help='Defines a time interval, in milliseconds, for sending packets')

    parser.add_argument('-m', '--media-path', type=str,
                        help='Defines the path to the media. Must be a video file (.mp4)')

    args = parser.parse_args()

    if args.media_path == None:
        print("The path to the media must be provided. Use -h option to get help")
        os._exit(1)

    media_path = args.media_path

    if args.delay != None:
        delay = args.delay


def main():

    handle_args()

    check_file_existence(media_path)

    video_thread = threading.Thread(target=read_video)
    video_thread.start()

    thread = threading.Thread(target=send_media_to_clients)
    thread.start()

    listen_to_subscriptions()


try:
    main()
finally:
    pass
    # server.close()
