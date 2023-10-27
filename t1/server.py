import socket
import threading

PORT = 5050
SERVER = socket.gethostbyname(socket.gethostname())
ADDRESS = (SERVER, PORT)
DISCONNECT_IDENTIFIER = 0
BUFFER_SIZE = 1024
MEDIA_PATH = 'moves/move1.mp4'

server = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

server.bind(ADDRESS)

def handle_client(encoded_data, address):
  print(f"[NEW CONNECTION] {address} wants to receive the full video")

  data = encoded_data.decode()

  print(f"[{address}] {data}")

  with open(MEDIA_PATH, 'rb') as media:
    package_count = 1

    while True:
      media_data = media.read(BUFFER_SIZE - 4)

      if media_data:
        data = package_count.to_bytes(4, 'big')
        data += media_data

        server.sendto(data, address)

        package_count += 1
      else:
        break

  print(f"[SERVER] Finished to send Media to {address}")

  data = DISCONNECT_IDENTIFIER.to_bytes(4, 'big')

  server.sendto(data, address)

def start_server():
  print(f"[SERVER] server is running in address: {SERVER} on port: {PORT}")

  while True:
    encoded_data, address = server.recvfrom(BUFFER_SIZE)

    thread = threading.Thread(target=handle_client, args=(encoded_data, address))
    thread.start()

    print(f"[ACTIVE CONNECTIONS] {threading.active_count() - 1}")

print("[SERVER] is starting...")

start_server()

print("[SERVER] is closing...")

server.close()