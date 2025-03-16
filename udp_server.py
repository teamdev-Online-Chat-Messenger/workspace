import socket
import threading
import time

SERVER_HOST = '0.0.0.0'
SERVER_PORT = 12345
BUFFERSIZE = 4096
TIMEOUT = 60
CHECK_INTERVAL = 5

rooms = {}  # {room_name: {addr: (token, last_active), ...}}

'''一定期間メッセージのないクライアントを削除'''
def remove_inactive_clients():
  while True:
    current_time = time.time()
    for room, clients in list(rooms.items()):
      inactive = [addr for addr, (_, last_active) in clients.items() if current_time - last_active > TIMEOUT]
      for addr in inactive:
        print(f"クライアントがタイムアウトしました: {addr}（ルーム: {room}）")
        del rooms[room][addr]
      if not rooms[room]:
        print(f"ルーム{room}を閉じました")
        del rooms[room]
    time.sleep(CHECK_INTERVAL)

'''同一ルームのクライアントにメッセージを転送'''
def broadcast_message(sock, room, sender_addr, message):
  for addr in rooms.get(room, {}):
    if addr != sender_addr:
      try:
        sock.sendto(message, addr)
      except Exception as e:
        print(f"送信エラー({addr})： {e}")

#rooms(roomとtoken)：TCPと共有の必要
#方法：DB、共有ファイル(json)
def main():
  sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
  sock.bind((SERVER_HOST,SERVER_PORT))

  print(f"サーバーを起動しました, {SERVER_HOST}, {SERVER_PORT}")

  # 非アクティブなクライアント削除用スレッド
  thread = threading.Thread(target = remove_inactive_clients, daemon=True)
  thread.start()

  while True:
    try:
      data, addr = sock.recvfrom(BUFFERSIZE)
    except socket.timeout:
      continue
    if len(data) < 2:
      continue

    try:
      #プロトコル：最初の一バイトがユーザー名のバイトサイズ
      room_name_size = data[0]
      token_size = data[1]

      idx = 2
      room = data[idx:idx+room_name_size].decode('utf-8')
      idx += room_name_size
      token = data[idx:idx+token_size].decode('utf-8')
      idx += token_size
      message = data[idx:]

      #クライアントの認証ちぇっく
      if room not in rooms or addr not in rooms[room] or rooms[room][addr][0] != token:
        print(f"不正なクライアント {addr}")
        continue

      rooms[room][addr] = (token, time.time())
      print(f"{room}, {addr}: {message.decode('utf-8')}")

      broadcast_message(sock,room,addr,message)

    except Exception as e:
      print(f"エラー: {e}")
      continue


if __name__ == '__main__':
  main()
