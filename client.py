import socket
import threading
import logging


user_name = ""

logging.basicConfig(level = logging.DEBUG, format="%(asctime)s - %(levelname)s - %(message)s")

tcp_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

tcp_server_addr = "127.0.0.1"
tcp_server_port = 9000
udp_server_addr = "127.0.0.1"
udp_server_port = 12345

print("enter ip")
user_ip = input() #testのために異なるローカルアドレス割り当てるための記述．実際にはIPを選択させる処理はいらない
print("enter udp port")
user_udp_port = input()

tcp_socket.bind((user_ip,0))


tcp_server_address = (tcp_server_addr, tcp_server_port)
udp_server_address = (udp_server_addr, udp_server_port)

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

    # 修正1:sendメソッド自体バイト列引数に持つから，辞書型ではなく，文字列エンコードしたものを送信
    #payload = {
    #    "user_name": user_name,
    #}

    payload = user_name.encode('utf-8')

    trcp_header = (
        len(room_name).to_bytes(1, 'big') +
        operation.to_bytes(1, 'big') +
        state.to_bytes(1, 'big') +
        # payLoadSize
        len(payload).to_bytes(29, 'big')
    )

    tcp_socket.send(trcp_header + room_name.encode('utf-8') + payload)

    # ステータスコードの受け取り
    responsed_status_code_header = tcp_socket.recv(32) 
    responsed_room_name_size = responsed_status_code_header[0]
    #responsed_state = responsed_status_code_header[2]
    responsed_payload_size = int.from_bytes(responsed_status_code_header[3:32],'big')

    responsed_status_code = tcp_socket.recv(responsed_room_name_size+responsed_payload_size)


    #responsed_room_name = responsed_status_code[0:respnsed_room_name_size]].decode('utf-8')
    responsed_payload = responsed_status_code[responsed_room_name_size:len(responsed_status_code)].decode('utf-8')

    logging.info("Status Code:%s",responsed_payload)

    responsed_token = tcp_socket.recv(1024)
    responsed_room_name_size = responsed_token[0]
    #responsed_state = responsed_token[2]
    #responsed_payload_size = int.from_bytes(responsed_token[3:32],'big')
    #responsed_room_name = responsed_token[32:32+responsed_room_name_size].decode('utf-8')
    responsed_payload = responsed_token[32+responsed_room_name_size:len(responsed_token)].decode('utf-8')

    logging.info("responsed_token:%s",responsed_payload)    
    return responsed_payload

# udp側の処理

def create_message_header(room_name,token):
        logging.debug("room_name:%s token:%s",room_name,token)
        return len(room_name).to_bytes(1,'big') + len(token.encode('utf-8')).to_bytes(1,'big')

def generate_message():
    print("Enter your message")
    message = input()
    return message

def generate_udp_data(room_name,token,is_ini_message): #is_ini_message == True なら初回udpサーバへの接続メッセージ生成
    #header:RoomNameSize(1)+TokenSize(1)
    #body: RoomName + Token + Message
    header = create_message_header(room_name,token)
    if is_ini_message:
        message = "New User:"+user_name+ " Joined"
    else:
        message = generate_message()
    body = room_name.encode('utf-8')+token.encode('utf-8')+message.encode('utf-8')

    return header + body


def create_udp_socket():
    sock = socket.socket(socket.AF_INET,socket.SOCK_DGRAM)

    sock.bind((user_ip,int(user_udp_port))) #bind するアドレスは仮

    return sock

def send_messages(room_name,token,udp_sock,thread1):
    try:
         while True:
            logging.debug("Thread動作確認2:%s",{thread1.is_alive()})

            message = generate_udp_data(room_name,token,False) #現状メッセージ打つたびに部屋名入力しないといけない（要修正）
            udp_sock.sendto(message,udp_server_address)
     
    finally:
         udp_socket.close()

def receive_messages(udp_sock):
    logging.debug("receive_messages is called")

    try:
        while True:
            message,_ = udp_sock.recvfrom(4094)
            room_name_size = message[0]
            token_size = message[1]
            logging.debug("receive message from udp server:%s",message)
            logging.info("receive message:%s",message[2+room_name_size+token_size:len(message)].decode('utf-8'))
    finally:
        udp_sock.close()

def main():
    udp_sock = create_udp_socket()
    thread1 = threading.Thread(target=receive_messages,args=(udp_sock,),daemon=True)
    thread1.start()

    token = createTcrpHeader() #createTCPHeader と その内部の送信処理は分けて書いた方がいいので，あとで分ける

    logging.debug("Thread動作確認:%s",{thread1.is_alive()})

    while True:
        logging.info("Enter your room name to join chat room")
            # ルーム名の記述
        room_name = input()
        if len(room_name) == 0:
            continue
        break

    initial_config_message = generate_udp_data(room_name,token,True) #コンフィグメッセージならTrue
    udp_sock.sendto(initial_config_message,udp_server_address)#udpチャットルームにjoinした瞬間にサーバへパケット送信して，udpサーバにこのクライアントのポート伝達


    send_messages(room_name,token,udp_sock,thread1)
    
if __name__ == "__main__":
    main()

