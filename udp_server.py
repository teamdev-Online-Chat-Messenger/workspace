import socket
import threading
import time
import pickle
from cryptography.hazmat.primitives import serialization

SERVER_HOST = '0.0.0.0'
SERVER_PORT = 12345
BUFFERSIZE = 4096
TIMEOUT = 60
CHECK_INTERVAL = 5
PICKLE_FILE = 'rooms.pkl' #ここは合わせる


rooms = {}  # {room_name: {'host_addr': addr, 'clients': {addr: (token, last_active)}}}

'''
暗号化について
クライアントからのメッセージ：
公開鍵を クライアント → TCPサーバー → UDPサーバー
'''
'''暗号化に伴いroomの形状変更(クライアントが作る公開鍵を保持する)
rooms[room_name] = {
    'host_addr': addr,
    'clients': {
        addr: {
            'token': token,
            'last_active': time.time(),
            'public_key': client_public_key_pem.decode('utf-8')  # クライアントの公開鍵をPEM形式で保存
        }
    }
}
'''

'''
UDPサーバー→クライアント のメッセージ：
サーバーからのメッセージ：公開鍵をUDP TCP クライアント
'''
#実際にはTCPが秘密鍵、公開鍵を作り公開鍵はクライアントに送る
'''
with open('server_private_key.pem', 'rb') as f:   #TCPで作った秘密鍵を取得する(.pemファイル名はTCPに合わせる)
    server_private_key = serialization.load_pem_private_key(
        f.read(),
        password=None
    )
'''

'''pickleからroomsをロードする関数'''
def load_rooms():
  try:
    with open(PICKLE_FILE, 'rb') as f:
      rooms = pickle.load(f)
      return rooms
  except FileNotFoundError:
    return {}


'''一定期間メッセージのないクライアントを削除、ホストが抜けたときにroomを削除'''
def remove_inactive_clients():
  while True:
    rooms = load_rooms()
    current_time = time.time()
    delete = False
    for room, info in list(rooms.items()):
      inactive = [addr for addr, (_, last_active) in info['clients'].items() if current_time - last_active > TIMEOUT]
      for addr in inactive:
        if addr == info['host_addr']:
          print(f"ホスト{addr}が退出しました。　ルーム{room}を閉じます。")
          del rooms[room]
          delete = True
          break
        else:
          print(f"クライアントがタイムアウトしました: {addr}（ルーム: {room}）")
          del rooms[room]['clients'][addr]
      if room in rooms and not rooms[room]['clients']:
        print(f"クライアントがいなくなったので、ルーム{room}を閉じました")
        del rooms[room]
        delete = True
    if delete:
      with open(PICKLE_FILE, 'wb') as f:
        pickle.dump(rooms, f)
    time.sleep(CHECK_INTERVAL)

'''同一ルームのクライアントにメッセージを転送'''
def broadcast_message(sock, room, sender_addr, message):
  rooms = load_rooms()  # pickleから最新のデータを読み込む
  if room not in rooms:
    return
  for addr in rooms.get(room, {}).get('clients', {}):
    if addr != sender_addr:
      try:
        sock.sendto(message, addr)
      except Exception as e:
        print(f"送信エラー({addr})： {e}")


def main():
  sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
  sock.bind((SERVER_HOST,SERVER_PORT))

  print(f"サーバーを起動しました, {SERVER_HOST}, {SERVER_PORT}")

  # 非アクティブなクライアント削除用スレッド
  thread = threading.Thread(target = remove_inactive_clients, daemon=True)
  thread.start()

  while True:
    if 'last_pickle_load' not in locals() or time.time() - last_pickle_load > 1:
            rooms = load_rooms()
            last_pickle_load = time.time()
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
      if room not in rooms or addr not in rooms[room]['clients'] or rooms[room]['clients'][addr][0] != token:

        time.sleep(0.1)  # 100ミリ秒だけ待つ（重要）
        rooms = load_rooms()  # 再読み込み（重要）
        if room not in rooms or addr not in rooms[room]['clients'] or rooms[room]['clients'][addr][0] != token:
          print(f"不正なクライアント {addr}")
          continue

      rooms[room]['clients'][addr] = (token, time.time())
      print(f"{room}, {addr}: {message.decode('utf-8')}")

      broadcast_message(sock,room,addr,message)

    except Exception as e:
      print(f"エラー: {e}")
      continue


if __name__ == '__main__':
  main()
