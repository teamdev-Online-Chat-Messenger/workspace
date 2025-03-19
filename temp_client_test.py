import socket
import threading

server_ip = "127.0.0.1"
server_port = 9000
NUM_CLIENTS = 10  #クライアントの数

def client_task(client_id):
    client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    client_socket.connect((server_ip, server_port))

    # ルーム作成リクエストを送信
    room_name = f"room{client_id}".encode('utf-8')
    user_name = f"user{client_id}".encode('utf-8')

    if client_id == 2:
        room_name = "room1".encode("utf-8")
        message = (
            len(room_name).to_bytes(1, 'big')  # room_name のサイズ
            + b"\x02"  # operation
            + b"\x00"  # state
            + len(user_name).to_bytes(29, 'big')  # operation_payload_size
            + room_name
            + user_name
        )

 
    else:
        message = (
            len(room_name).to_bytes(1, 'big')  # room_name のサイズ
            + b"\x01"  # operation
            + b"\x00"  # state
            + len(user_name).to_bytes(29, 'big')  # operation_payload_size
            + room_name
            + user_name
        )

    client_socket.send(message)

    # レスポンスを受信
    response = client_socket.recv(1024)
    print("--------------------------",client_socket,"------------------\n")
    print(f"Client {client_id} - Server Response:", response)
    print("response decode:",response.decode('utf-8'))
    print("\n")

    response = client_socket.recv(1024)
    print("--------------------------",client_socket,"------------------\n")
    print(f"Client {client_id} - Server Second Response:", response)
    print("\n Second response decode:",response.decode('utf-8'))
    print("\n")
    

    client_socket.close()

# 複数のクライアントを並行実行
threads = []
for i in range(NUM_CLIENTS):
    thread = threading.Thread(target=client_task, args=(i,))
    thread.start()
    threads.append(thread)

# 全スレッドの終了を待つ
for thread in threads:
    thread.join()
