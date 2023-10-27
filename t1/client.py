import socket
import uuid

PORT = 5050
SERVER = "127.0.1.1"
ADDRESS = (SERVER, PORT)
DISCONNECT_IDENTIFIER = 0
START_MESSAGE = 'Start!'
BUFFER_SIZE = 1024

client = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

def close_client():
  client.close()

def send_to_server(data):
  client.sendto(data, ADDRESS)

def receive_from_server():
  return client.recvfrom(BUFFER_SIZE)

def get_package_count(data):
  return int.from_bytes(data[:4], "big")

def get_package_data(data):
  return data[-1020:]

def build_package(data):
  return {"package_count": get_package_count(data), "data": get_package_data(data)}

def sort_packages(packages):
  return sorted(packages, key = lambda x: x['package_count'])

def write_to_file(packages):
  file_identifier = str(uuid.uuid4())

  with open(file_identifier, 'wb') as media:
    for package in packages:
      media.write(package['data'])

packages = []

send_to_server(START_MESSAGE.encode())

while True:
  data, address = receive_from_server()

  package = build_package(data)

  if package['package_count'] == DISCONNECT_IDENTIFIER: break

  packages.append(package)

packages = sort_packages(packages)

write_to_file(packages)

close_client()