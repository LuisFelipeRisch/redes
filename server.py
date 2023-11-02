from datetime import datetime
import socket
import threading
import cv2
import struct
import time
import argparse

SERVER = socket.gethostbyname(socket.gethostname())
PORT = 3030
ADDRESS = (SERVER, PORT)
MEDIA_PATH = "video.mp4"
MAX_PAYLOAD_SIZE = 1480
HEADER_FORMAT = "!IIHH"
HEADER_SIZE = struct.calcsize(HEADER_FORMAT)
MAX_PACKAGE_SIZE = HEADER_SIZE + MAX_PAYLOAD_SIZE
START_MESSAGE = '!start'

server = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
server.bind(ADDRESS)

video_fps = 0
delay = 0.5


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


def handle_client(data: bytes, address):
    global video_fps

    decoded_data = data.decode("utf-8")
    add_log(
        f"New connection from {address} with message: {decoded_data}.")
    if decoded_data != START_MESSAGE:
        add_log(f"Unknown message from {address}")
        return

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
        initial_packet = build_packet(
            frame_number, sequence_number, len(chunks).to_bytes(4, 'big'))
        send_packet(initial_packet, address)

        sequence_number += 1

        for chunk in chunks:
            packet = build_packet(frame_number, sequence_number, chunk)

            add_log(f"Sending package to {address}")
            add_log(
                f"[PACKAGE INFO]: frame: {frame_number} - sequence: {sequence_number} - size: {len(chunk)}")
            send_packet(packet, address)

            sequence_number += 1

        ret, frame = video_capture.read()
        frame_number += 1


def start_server():
    add_log(f"Server is listening on {SERVER}:{PORT}")
    while True:
        data, address = server.recvfrom(MAX_PACKAGE_SIZE)
        thread = threading.Thread(
            target=handle_client, args=(data, address)
        )
        thread.start()
        add_log(f"{threading.active_count() - 1} active communication.")


def main():
    add_log("Starting server...")
    start_server()
    add_log("Closing server...")
    server.close()
    add_log("Server closed")


parser = argparse.ArgumentParser(
    prog='Server',
    description='Server that sends media to clients'
)

parser.add_argument('-d', '--delay', type=float, help='Defines a time interval, in milliseconds, for sending packets')

args = parser.parse_args()

if args.delay != None:
    delay = args.delay

main()
