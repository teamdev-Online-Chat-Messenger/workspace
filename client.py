import socket

tcp_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

server_address = "127.0.0.1"
server_port = 9000

tcp_server_address = (server_address, tcp_server_port)
udp_server_address = (server_address, udp_server_port)

tcp_socket.connect(tcp_server_address)

class Client:
    pass

def getUserName():
    while True:
        print("Enter your name")
        user_name = input()
        if len(user_name) == 0:
            continue
        user_name_size = len(user_name.encode('utf-8'))
        break
    return user_name, user_name_size

# オペレーション
def getOperation():
    print("Would you like to create a new room or join an existing one? (Type 'create' or 'join')")
    while True:
        # ルームを作るか、参加するかを質問
        user_choice = input()
        # 小文字にする
        user_choice = user_choice.lower()
        # ルームを作成
        if user_choice == "create":
            print("Creating a new chat room...")
            # ルームの作成の操作コード
            return 1
        # ルームに参加
        elif user_choice == "join":
            print("Joining an existing chat room...")
            # ルームへの参加の操作コード
            return 2
        # エラー
        else:
            print("Invalid input. Please type 'create' or 'join'.")

# ルーム名の取得
def getRoomInfo():
    while True:
        print("Enter your room name")
        # ルーム名の記述
        room_name = input()
        if len(room_name) == 0:
            continue
        room_name_size = len(room_name.encode('utf-8'))
    return room_name, room_name_size

# tcrpヘッダーの作成
def createTcrpHeader():
    room_name, room_name_size = getRoomInfo()
    operation = getOperation()
    state = 0
    user_name, user_name_size = getUserName()

    payload = {
        "user_name": user_name,

    }

    trcp_header = (
        len(room_name).to_bytes(1, 'big') +
        operation.to_bytes(1, 'big') +
        state.to_bytes(1, 'big') +
        # payLoadSize
        len(payload).to_bytes(29, 'big')
    )

    tcp_socket.send(trcp_header + room_name.encode('utf-8') + payload)

    # ステータスコードの受け取り
    while True:
        # responsed data
        responsed_data = tcp_socket.recv(32)
        responsed_room_name_size = responsed_data[0]
        responsed_state = responsed_header[2]
        
        
        if responsed_state == 1:
            pass

        elif responsed_state == 2:
            # トークンの取得
            token = 
            tcp_socket.close()
            break

    return token


# udp側の処理

# def receive_messages():
#     try:
#         while True:


# def send_messages():
#     try:
#         udp_header = (
#             room_name_size.to_bytes(1, 'big') +
#             token_size.to_bytes(1, 'big')
#         )
#         print("Send message")
#         while True:
#             message = input()
#             send_payload = {
#                 "user": username,
#                 "message": message,
#             }
#             body = (
#                 room_name.encode('utf-8') + 
#                 token_size
#             )
#     finally:
#         udp_socket.close()
        
