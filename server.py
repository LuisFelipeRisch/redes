from datetime import datetime
import socket
import threading
import cv2
import struct
import time
import argparse
import uuid

SERVER = socket.gethostbyname(socket.gethostname())
PORT = 3030
ADDRESS = (SERVER, PORT)
MEDIA_PATH = "video.mp4"
MAX_PAYLOAD_SIZE = 1480
HEADER_FORMAT = "!IIHH"
HEADER_SIZE = struct.calcsize(HEADER_FORMAT)
MAX_PACKAGE_SIZE = HEADER_SIZE + MAX_PAYLOAD_SIZE
START_MESSAGE = '!start'
SUBSCRIBED_MESSAGE = '!subscribed'

server = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
server.bind(ADDRESS)

video_fps = 0
delay = 0.5
clients_address = []

def get_timestamp():
    timestamp = datetime.now()
    return timestamp.strftime("%d-%m-%Y %H:%M:%S")


def add_log(message: str):
    print(f"[{get_timestamp()}]: {message}")


def build_packet(frame_number: int, sequence_number: int, payload: bytes) -> bytes:
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

def encode_message(message):
    return message.encode('utf-8')

def listen_to_subscribes():
    add_log("Thread started. Listening to subscribes.")

    while True:
        data, address = server.recvfrom(MAX_PACKAGE_SIZE)
        decoded_data = data.decode('utf-8')

        if decoded_data != START_MESSAGE:
            add_log(f"{decoded_data} unknown start message!")
            continue

        if client_already_subscribed(address):
            add_log(f"{address} already connected!")
            continue

        clients_address.append(address)

        add_log(f"New client({address}) connected. Now, we have {len(clients_address)} active clients.")

        encoded_subscribed_message = encode_message(SUBSCRIBED_MESSAGE)

        packet = build_packet(0, 0, encoded_subscribed_message)

        send_packet(packet, address)


def start_thread_to_listen_subscribes():
    add_log("Starting thread to listen subscribes...")

    thread = threading.Thread(target=listen_to_subscribes)
    thread.start()

def empty_clients():
    return len(clients_address) == 0

def send_packet_to_clients(frame_number, sequence_number, payload):
    for client_address in clients_address:
        packet = build_packet(frame_number, sequence_number, payload)

        send_packet(packet, client_address)

def handle_client():
    global video_fps

    video_capture = cv2.VideoCapture(MEDIA_PATH)
    video_fps = int(video_capture.get(cv2.CAP_PROP_FPS))
    ret, frame = video_capture.read()
    frame_number = 0

    while ret:
        retval, compressed_frame = cv2.imencode(".jpg", frame)
        frame_data = compressed_frame.tobytes()

        chunks = [frame_data[i:i + MAX_PAYLOAD_SIZE]
                  for i in range(0, len(frame_data), MAX_PAYLOAD_SIZE)]


        sequence_number = 0

        send_packet_to_clients(frame_number, sequence_number, len(chunks).to_bytes(4, 'big'))

        sequence_number += 1

        for chunk in chunks:
            # add_log(f"Sending package to {address}")
            add_log(
                f"[PACKAGE INFO]: frame: {frame_number} - sequence: {sequence_number} - size: {len(chunk)}")
            send_packet_to_clients(frame_number, sequence_number, chunk)

            sequence_number += 1

        ret, frame = video_capture.read()
        frame_number += 1

def send_media_to_clients():
    while True:
        if empty_clients(): continue

        handle_client()

def main():
    add_log(f"Server is listening on {SERVER}:{PORT}")

    thread = threading.Thread(target=send_media_to_clients)
    thread.start()

    listen_to_subscribes()

parser = argparse.ArgumentParser(
    prog='Server',
    description='Server that sends media to clients'
)

parser.add_argument('-d', '--delay', type=float, help='Defines a time interval, in milliseconds, for sending packets')

args = parser.parse_args()

if args.delay != None:
    delay = args.delay

try:
    main()
finally:
    pass
    # server.close()