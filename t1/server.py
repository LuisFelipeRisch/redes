import socket
import threading
import json

PORT = 5050
SERVER = socket.gethostbyname(socket.gethostname())
ADDRESS = (SERVER, PORT)
DISCONNECT_MESSAGE = '!DISCONNECT'

server = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

server.bind(ADDRESS)

def handle_client(message, address):
  print(f"[NEW CONNECTION] {address} wants to receive the full video")

  message = message.decode()

  print(f"[{address}] {message}")

  data = {"key1": "value1", "key2": "value2", "key3": 42}
  json_data = json.dumps(data)

  server.sendto(json_data.encode(), address)

  server.sendto(DISCONNECT_MESSAGE.encode(), address)

def start_server():
  print(f"[SERVER] server is running in address: {SERVER} on port: {PORT}")

  while True:
    message, address = server.recvfrom(1024)

    thread = threading.Thread(target=handle_client, args=(message, address))
    thread.start()

    print(f"[ACTIVE CONNECTIONS] {threading.active_count() - 1}")

  pass

print("[SERVER] is starting...")

start_server()

print("[SERVER] is closing...")

server.close()