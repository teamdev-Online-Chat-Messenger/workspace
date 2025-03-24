import socket
import threading
import logging
import time
import sys
import errno
import os

user_name = ""
room_name_token = {} #userが指定した部屋名と，それに対応したtokenを記録

logging.basicConfig(level = logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

tcp_server_addr = "127.0.0.1"
tcp_server_port = 9000
udp_server_addr = "127.0.0.1"
udp_server_port = 12345


user_ip = input("Enter IP Address (127.0.0.2~) --> ") #testのために異なるローカルアドレス割り当てるための記述．実際にはIPを選択させる処理はいらない
user_udp_port = input("Enter Port for UDP --> ")



tcp_server_address = (tcp_server_addr, tcp_server_port)
udp_server_address = (udp_server_addr, udp_server_port)


class Client:
    pass

def getUserName():
    while True:
        user_name = input("Enter User Name --> ")
        if len(user_name) == 0:
            continue
        user_name_size = len(user_name.encode('utf-8'))
        break
    return user_name, user_name_size

# オペレーション
def getOperation():
    while True:
        # ルームを作るか、参加するかを質問
        user_choice = input("Would you like to create a new room or join an existing one? (Type 'create' or 'join') --> ")
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
        # ルーム名の記述
        room_name = input("Enter Your Room Name --> ")
        if len(room_name) == 0:
            logging.info("room_name length is 0 error")
            continue
        room_name_size = len(room_name.encode('utf-8'))
        return room_name, room_name_size

# tcrpヘッダーの作成
def createTcrpHeader(room_name,room_name_size,user_name,user_name_size):
    try:
        tcp_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        tcp_socket.bind((user_ip,0))
        tcp_socket.connect(tcp_server_address)

        operation = getOperation()
        state = 0

        payload = user_name.encode('utf-8')

        trcp_header = (
            len(room_name).to_bytes(1, 'big') +
            operation.to_bytes(1, 'big') +
            state.to_bytes(1, 'big') +
            len(payload).to_bytes(29, 'big')
        )

        if operation == 2:
            logging.info("trcp_header:%s",trcp_header)
        tcp_socket.send(trcp_header + room_name.encode('utf-8') + payload) #リクエストをTCPサーバへ送信

        if operation == 1:
            receive_password_setting = tcp_socket.recv(1024) #OP==1のとき，TCPサーバからpasswordを設定するか確認するメッセージが届く．
            rsize = receive_password_setting[0]
            logging.info(receive_password_setting[32+rsize:].decode('utf-8'))
            
            while True:
                password_message = input('Enter no or password (more than 2 characters) --> ') 
                
                if len(password_message) <= 1: 
                    continue
                if password_message.lower() == "no":
                    break
                if password_message:
                    break
            tcp_socket.send(len(room_name).to_bytes(1, 'big')+operation.to_bytes(1, 'big')+state.to_bytes(1, 'big')+len(password_message.encode('utf-8')).to_bytes(29, 'big')+room_name.encode('utf-8') + password_message.encode('utf-8')) #TCPサーバに対してpassword設定を送信

        elif operation == 2:
            receive_password_setting = tcp_socket.recv(1024) #OPが2のとき，passwordが必要であればTCPサーバから"Need Password" 不要であれば" "空文字が送信される
            rsize = receive_password_setting[0]
            if receive_password_setting[32+rsize:].decode('utf-8') != " ":   #roomにパスワードが設定されていないとき" "を受信する
                password_message = input("enter room password --> ")        
            else:
                password_message = ""      

            tcp_socket.send(len(room_name).to_bytes(1, 'big')+operation.to_bytes(1, 'big')+state.to_bytes(1, 'big')+len(password_message.encode('utf-8')).to_bytes(29, 'big')+room_name.encode('utf-8') + password_message.encode('utf-8')) #TCPサーバに対してパスワード設定を送信

        responsed_status_code_header = tcp_socket.recv(32) #ステータスコードのヘッダーの受け取り
        logging.debug("code:::%s",responsed_status_code_header)
        responsed_room_name_size = responsed_status_code_header[0]
        #responsed_state = responsed_status_code_header[2]
        responsed_payload_size = int.from_bytes(responsed_status_code_header[3:32],'big') 

        responsed_status_code = tcp_socket.recv(responsed_room_name_size+responsed_payload_size)#ステータスコード本体の受け取り
        #responsed_room_name = responsed_status_code[0:respnsed_room_name_size]].decode('utf-8')
        responsed_payload = responsed_status_code[responsed_room_name_size:len(responsed_status_code)].decode('utf-8')

        logging.info("Status Code:%s",responsed_payload) 

        responsed_token = tcp_socket.recv(1024) #ステータスコードに続いて，tokenがTCPサーバから送信される．もし，エラーであれば "No Token" を受信する．
        responsed_room_name_size = responsed_token[0]
        #responsed_state = responsed_token[2]
        #responsed_payload_size = int.from_bytes(responsed_token[3:32],'big')
        #responsed_room_name = responsed_token[32:32+responsed_room_name_size].decode('utf-8')
        responsed_payload = responsed_token[32+responsed_room_name_size:len(responsed_token)].decode('utf-8')

        logging.debug("responsed_token:%s",responsed_payload) 

        return responsed_payload #受信したトークン

    except Exception as e:
        e_type,e_object,e_traceback = sys.exc_info()
        logging.info("Error:%s",e)
        logging.info("line %s",e_traceback.tb_lineno)

    finally:
        tcp_socket.close()    

# udp側の処理

def create_message_header(room_name,token):
        logging.debug("room_name:%s token:%s",room_name,token)
        return len(room_name).to_bytes(1,'big') + len(token.encode('utf-8')).to_bytes(1,'big')

def generate_message():
    message = input("Enter Your Message --> ")
    return message

def generate_udp_data(room_name,token,is_ini_message): #is_ini_message == True なら初回udpサーバへの接続メッセージ生成
    #header:RoomNameSize(1)+TokenSize(1)
    #body: RoomName + Token + Message
    header = create_message_header(room_name,token)
    if is_ini_message:
        message = "New User:"+user_name+ " Joined"
    else:
        message = user_name +" :"+ generate_message()

    body = room_name.encode('utf-8')+token.encode('utf-8')+message.encode('utf-8')

    return header + body


def create_udp_socket():
    sock = socket.socket(socket.AF_INET,socket.SOCK_DGRAM)
    sock.bind((user_ip,int(user_udp_port))) #bind はあくまでローカルで動作させるための記述

    return sock

def send_messages(room_name,udp_sock):
    try:
         while room_name in room_name_token:
            message = generate_udp_data(room_name,room_name_token[room_name],False) 
            logging.debug("sendto udp from cliet: data:%s",message)
            udp_sock.sendto(message,udp_server_address)
         logging.debug("send_messages finish")

    except OSError as e:     #receive側でsocket closeしているので，
        if e.errno == errno.EBADF:
            logging.info("Socket Already Closed")
        else:
            logging.info("Error:%s",e)

    except Exception as e:
        e_type,e_object,e_traceback = sys.exc_info()
        logging.info("Error:%s",e)
        logging.info("line %s",e_traceback.tb_lineno)


def receive_messages(udp_sock):
    logging.debug("receive_messages is called")

    try:
        while True:
            message,_ = udp_sock.recvfrom(4094)
            room_name_size = message[0]
            token_size = message[1]
            logging.debug("receive message from udp server:%s",message)
            logging.info("\n receive message:%s \n",message[2+room_name_size+token_size:len(message)].decode('utf-8'))
            if token_size == 0: #ホストが退出したか，自身がサーバから削除された
                logging.info("Finish Room")
                del room_name_token[message[2:2+room_name_size].decode('utf-8')] #clientの所持する辞書から　削除されたroom名:token のtokenを削除しておく
                time.sleep(1)
#                start_client(udp_sock)
                udp_sock.close()
                break

    except Exception as e:
        e_type,e_object,e_traceback = sys.exc_info()
        logging.info("Error:%s",e)
        logging.info("line %s",e_traceback.tb_lineno)
        udp_sock.close()

    finally:
        udp_sock.close()


def start_client():
    try:
        udp_sock = create_udp_socket()
        user_name, user_name_size = getUserName()
        thread1 = threading.Thread(target=receive_messages,args=(udp_sock,),daemon=True) #メッセージ受信用のスレッド
        thread1.start()

        token = "No token"
        while token == "No token":
            room_name,room_name_size = getRoomInfo()
            token = createTcrpHeader(room_name,room_name_size,user_name,user_name_size) #TCPサーバと通信 生成したtoken・トークンエラー"No Token" が戻る
            logging.debug("token:%s",token)
        room_name_token[room_name] = token #クライアントがtokenを所持しているroomの管理を行う辞書の更新

        logging.debug("room_name_token:%s",room_name_token)

        while True:
            # ルーム名の記述
            room_name = input("Enter Your Room Name To Join Chat Room--> ")
            if not room_name:  # 空入力のチェック
                logging.info("Enter Your Room Name")
                continue

            # クライアントが指定したルーム名に対する token を所持していない場合はエラー
            if room_name not in room_name_token.keys():
                logging.info("No Token Error")
                continue
            break   

        logging.debug("Initial message is sent to udp server:room:%s",room_name)
        initial_config_message = generate_udp_data(room_name,token,True) #初回の設定用メッセージならTrue
        udp_sock.sendto(initial_config_message,udp_server_address)#udpチャットルームにjoinした瞬間にサーバへパケット送信して，udpサーバにこのクライアントのポート伝達

        logging.info("Enterd Room")
        send_messages(room_name,udp_sock)#chatの開始

    except Exception as e:
        e_type,e_object,e_traceback = sys.exc_info()
        logging.info("Error:%s",e)
        logging.info("line %s",e_traceback.tb_lineno)
    
    finally:
            udp_sock.close()




if __name__ == "__main__":
    start_client()
