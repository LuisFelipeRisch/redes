import socket
import json

PORT = 5050
SERVER = "127.0.1.1"
ADDRESS = (SERVER, PORT)
DISCONNECT_MESSAGE = '!DISCONNECT'
START_MESSAGE = 'Start!'

client = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

client.sendto(START_MESSAGE.encode(), ADDRESS)

message, address = client.recvfrom(1024)
message = message.decode()

while message != DISCONNECT_MESSAGE:
  received_dict = json.loads(message)

  print("Received data:", received_dict)
  print("key1:", received_dict['key1'])

  message, address = client.recvfrom(1024)
  message = message.decode()

client.close()