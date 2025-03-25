import sys
import os
import socket
import threading
import time
import pickle
import logging
import traceback

logging.basicConfig(level = logging.DEBUG, format="%(asctime)s - %(levelname)s - %(message)s")

SERVER_HOST = '0.0.0.0'
SERVER_PORT = 12345
BUFFERSIZE = 4096
TIMEOUT = 40
CHECK_INTERVAL = 5
PICKLE_FILE = 'rooms.pkl' #ここは合わせる

#この形式addr=(ip,port) --> addr=ip　に変更（TCP,UDPソケットで利用するポートが異なるから）
rooms = {}  #{room_name: {'host_addr': addr, 'clients': {addr: (token, last_active)}},room_name2: {...}}
ip_udp_port = {}


'''pickleからroomsをロードする関数'''
def load_rooms():
  try:
    with open(PICKLE_FILE, 'rb') as f:
      rooms = pickle.load(f)
      return rooms
  except FileNotFoundError:
    return {}


'''一定期間メッセージのないクライアントを削除、ホストが抜けたときにroomを削除'''
def remove_inactive_clients(sock):
  while True:
    rooms = load_rooms()
    logging.debug("remove_inactive:: rooms:%s",rooms)
    current_time = time.time()
    for room, info in list(rooms.items()):
      delete = False
      inactive = [addr for addr, (_, last_active) in info['clients'].items() if current_time - last_active > TIMEOUT]
      logging.debug("remove_ina::inactive:%s",inactive)
      for addr in inactive:
        if addr == info['host_addr']:
          print(f"ホスト{addr}が退出しました。　ルーム{room}を閉じます。")

          data = bytearray()
          data.extend(len(room.encode('utf-8')).to_bytes(1, 'big'))
          data.extend((0).to_bytes(1, 'big'))
          idx = len(data)
          data.extend(room.encode('utf-8'))
          message = f"ホスト{addr}が退出しました。　ルーム{room}を閉じます。".encode('utf-8')
          data.extend(message)
          broadcast_message(sock,rooms,room,addr,data)

          del rooms[room]
          delete = True

        else:
          print(f"クライアントがタイムアウトしました: {addr}（ルーム: {room}）")
          delete = True
          data = bytearray()
          data.extend(len(room.encode('utf-8')).to_bytes(1, 'big'))
          data.extend((0).to_bytes(1, 'big'))
          idx = len(data)
          data.extend(room.encode('utf-8'))
          message = f"メッセージを長時間送信していなかったため，退出しました。".encode('utf-8')
          data.extend(message)
          try:
            del rooms[room]['clients'][addr]
            sock.sendto(data, (str(addr),int(ip_udp_port[addr])))
          except Exception as e:
            logging.debug("Error: %s",e)

      if room in rooms and not rooms[room]['clients']:
        print(f"クライアントがいなくなったので、ルーム{room}を閉じました")
        del rooms[room]
        delete = True

      if delete:

        logging.debug("after remove_inactive:: rooms:%s",rooms)

        with open(PICKLE_FILE, 'wb') as f:
          logging.debug("after deleted rooms:%s",rooms)
          pickle.dump(rooms, f)
    time.sleep(CHECK_INTERVAL)

'''同一ルームのクライアントにメッセージを転送'''
def broadcast_message(sock, rooms, room, sender_addr, message):
  logging.debug("room:%s",room)
  logging.debug("broadcast_message is called:rooms:%s",rooms)
  for addr in rooms.get(room, {}).get('clients', {}):
    logging.debug("broad_cast:log: addr %s",addr)
    logging.debug("sender_addr:%s",sender_addr)
    if addr != sender_addr[0]: #この判定をポート除いて，IPだけで判定する
      try:
        logging.debug("data:%s is sent to Address:%s %s",message,addr,ip_udp_port[addr])
        sock.sendto(message, (str(addr),int(ip_udp_port[addr])))
      except Exception as e:
        e_type,e_object,e_traceback = sys.exc_info()
        print(f"エラー: {e}")
        print(f"行::{e_traceback.tb_lineno}")


def main():
  sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
  sock.bind((SERVER_HOST,SERVER_PORT))

  print(f"サーバーを起動しました, {SERVER_HOST}, {SERVER_PORT}")

  # 非アクティブなクライアント削除用スレッド
  thread = threading.Thread(target = remove_inactive_clients, args = (sock,) ,daemon=True)
  thread.start()

  while True:
    if 'last_pickle_load' not in locals() or time.time() - last_pickle_load > 1:
            rooms = load_rooms()
            logging.debug("rooms->%s",rooms)
            last_pickle_load = time.time()
    try:
      data, addr = sock.recvfrom(BUFFERSIZE)

      ip_udp_port[addr[0]] = addr[1]  #各UDPクライアントのPort番号を記録

      if len(data) < 2:
        continue


      #プロトコル：最初の一バイトがユーザー名のバイトサイズ
      room_name_size = data[0]
      token_size = data[1]

      idx = 2
      room = data[idx:idx+room_name_size].decode('utf-8')
      idx += room_name_size
      token = data[idx:idx+token_size].decode('utf-8')
      idx += token_size
      message = data[idx:]

      #クライアントの認証チェック
      flag = True

      if (room not in rooms) or (rooms[room]['clients'][addr[0]][0] != token):
          logging.info("認証失敗")
          logging.debug("correct token: %s",rooms[room]['clients'][addr[0]][0])
          logging.debug("user token:%s",token)
          data = bytearray()
          data.extend(len(room.encode('utf-8')).to_bytes(1, 'big'))
          data.extend((0).to_bytes(1, 'big'))
          idx = len(data)
          data.extend(room.encode('utf-8'))
          message = f"認証に失敗しました".encode('utf-8')
          data.extend(message)

          continue #TCP,UDPサーバのpickleの書き込み読み込みタイミングの差異で，ユーザが登録される前に読み込んでエラーとなる可能性があるので，再度読み込んでみる

      for room_addr in rooms[room]['clients'].keys():
          logging.debug("test debug:%s",room_addr)
          if room_addr == addr[0]:
            flag = False 
      if flag:
        print(f"不正なクライアント {addr}")
        continue


      rooms[room]['clients'][addr[0]] = (token, time.time())

      with open(PICKLE_FILE, 'wb') as f:
          logging.debug("update user last active time:%s",rooms)
          pickle.dump(rooms, f)      
      
      print(f"{room}, {addr}: {message.decode('utf-8')}")

      broadcast_message(sock,rooms,room,addr,data)

    except socket.timeout:
      continue



    except Exception as e:
      e_type,e_object,e_traceback = sys.exc_info()
      logging.info(f"エラー発生: {type(e).__name__}: {e}")
      traceback.print_exc()  # 詳細なエラーログを出力
      continue

if __name__ == '__main__':
  try:
    main()
  finally:
    os.remove("rooms.pkl")
