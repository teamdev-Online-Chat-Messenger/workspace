import socket
import time
import threading
import secrets
import pickle

import logging

logging.basicConfig(level = logging.DEBUG, format="%(asctime)s - %(levelname)s - %(message)s")


#host addr  , client addr (room_nameの中に書き込めばいい)
#rooms = {}  # {(room_name,host_addr) : {addr: (token, last_active), ...}}
#ローカルのファイルに　　上記形式で　データ書き込めれば，実装の詳細はあまり関係ない（オブジェクトを管理するわけではないから）
#したがって，　room_lists に，[{(Room.room_name,Room.host_addr):{addr:(token,last_active),...}}]を登録していく
#登録するたびに，room_lists のローカルファイルへの書き込みを行う

class Room:
    def __init__(self,room_name,host_user):
        #hashmap初期化
        self.room_name = room_name
        self.host_user = host_user
        self.host_token = None
        self.token_ip = {}
        self.token_user = {}
        self.token_time = {} #tokenとメッセージ最終送信時刻

    def generate_token(self,is_host,user_name):
        if is_host:
            return secrets.token_hex(16)+"_host_token_"+user_name #host用のtoken
        else:
            return secrets.token_hex(16)+user_name

    def setting_room(self,is_host,user_name,address): #tokenの生成・ユーザの記録・IPの記録を行う．戻り値は生成したtoken
        token = self.generate_token(is_host,user_name)
        self.token_ip[token] = address # (address,port) の記録
        self.token_user[token] = user_name
        self.token_time[token] = time.time()

        if is_host:
            self.host_token = token     #hostに関する記録処理はhashmap上手に利用すれば，host_user,host_tokenのうちどちらかのみ利用すればいいが，今は楽なので，両方記述している．

        share_data_content = {"host_addr":self.token_ip[self.host_token],"clients":{address:(token,time.time())}} #UDPサーバーと共有するデータ


        return token,share_data_content

class Server:
    def __init__(self,server_ip,server_port):
        self.CLIENT_NUM = 10
        self.HEADER_SIZE = 32
        self.udp_socket = None
        self.server_address = (server_ip,server_port)
        self.room_list = []
        self.share_data_list = {} #udpと共有するデータリスト

    def find_room(self,user_room_name):
        for r in self.room_list:
            if r.room_name == user_room_name:
                return r
        return None

    def make_message(self,room_name,operation,state,message): #メッセージをTCRP に沿って処理 @staticにしていいかも
        #header作成
        try:
            room_name_enc = room_name.encode('utf-8') #room_nameのエンコード
            room_name_size = len(room_name_enc).to_bytes(1,'big') #数値からバイトへ
            operation_byte = operation.to_bytes(1,'big')
            state_byte = state.to_bytes(1,'big')
            logging.debug("Message content:%s",message)

            if message is None:
                message = "No token"
            message_enc = message.encode('utf-8')

            operation_payload_size = len(message_enc).to_bytes(29,'big')
            #headerとbodyの結合
            data = room_name_size + operation_byte + state_byte + operation_payload_size + room_name_enc + message_enc

            logging.debug(" send ----> header + Messsage content :%s",data)

            return data

        except Exception as e:
            print(e)



    def receive_response(self,client_socket,client_address):
        #リクエストを受信し，処理を行う
        print("\n")
        try:
            with client_socket:
                header = client_socket.recv(self.HEADER_SIZE) #headerの受信
                logging.info("receive header from client:%s",header)
                while len(header) < self.HEADER_SIZE: #万が一ヘッダーサイズ分読み取れていない場合の処理
                    additional_message = client_socket.recv(self.HEADER_SIZE - len(header))
                    header += additional_message

                room_name_size = header[0]
                operation = header[1]
                state = header[2]
                operation_payload_size = int.from_bytes(header[3:len(header)],'big') #29バイト列から，数値へ変換

                #room_name_sizeをbyte列で受信する
                body_message = client_socket.recv(room_name_size + operation_payload_size)#bodyメッセージ受信

                room_name = body_message[0:room_name_size].decode('utf-8')
                operation_payload = body_message[room_name_size:len(body_message)].decode('utf-8')
                logging.debug("receive payload from client: room_name:%s operation:%s state:%s payload:%s", room_name, operation, state, operation_payload)

                # このようにしてUDPポート番号も受け取るよう修正
                user_name, client_udp_port = operation_payload.split(",")
                client_udp_port = int(client_udp_port)

                # 正しいUDPアドレス（クライアントから取得したポート番号）でpickle保存
                udp_client_address = (client_address[0], client_udp_port)

                token = None
                #operationに対応した処理
                if operation == 1: #ルーム生成などのセッティング
                    host_user_name = user_name #operation==1のときの，operation_payloadにはユーザ名が入っている．このユーザがRoomのホストとなる．
                    new_room = Room(room_name,host_user_name)
                    token,share_data_content = new_room.setting_room(True,host_user_name,udp_client_address) #生成したtokenを受け取る＋TCPサーバと共有するRoom管理オブジェクトを受け取る．
                    self.room_list.append(new_room) #ルームの登録

                    self.share_data_list[room_name] = {
                      "host_addr": udp_client_address,
                      "clients": {
                        udp_client_address: (token, time.time())
                      }
                    }
#share_data_content = {"host_addr":(ip,port),"clients":{(ip1,port1),...}}"
                    #joinの場合はルームオブジェクトの，オブジェクト取り出し，　rooms[room_name]で取り出せる辞書型を定義している必要がある．　この辞書の，rooms[room_name][host_addr] と rooms[room_name][clients][(ipaddr,port)] = (token,last_active) を追加する．
                    logging.debug("TCP と共有するデータ:%s",self.share_data_list)
                    #シェアするデータをシリアライズ化してlocal fileにデータ書き込む
                    with open("rooms.pkl","wb") as f:
                            pickle.dump(self.share_data_list,f)

                    status_code = "OP1OK"  #ステータスコード

                elif operation == 2: #ユーザのルーム参加
                    room = self.find_room(room_name)
                    if  room is not None:
                        user_name, client_udp_port = operation_payload.split(",")
                        client_udp_port = int(client_udp_port)

                        udp_client_address = (client_address[0], client_udp_port)
                        token,share_data_content = room.setting_room(False,user_name,client_address)
                        #シェアするデータをデシリアライズ化してlocal fileにデータ書き込む

                        self.share_data_list[room_name]["clients"][udp_client_address] = (token, time.time())

                        logging.debug("TCP と共有するデータ:%s",self.share_data_list)
                        with open("rooms.pkl","wb") as f:
                            pickle.dump(self.share_data_list,f)

                        status_code = "OP2OK"  #ステータスコード

                    else:
                        status_code = " Room not found Error" #ステータス
                        token = None


                client_socket.send(self.make_message(room_name,0,state+1,status_code)) #ステータスコード送信処理（room_name,operation,status,messageが引数）
                client_socket.send(self.make_message(room_name,0,state+2,token)) #tokenをクライアントに送信する（TCRPの形式に沿ってメッセージを送信するのでroom_name + tokenの形）ので，クライアント側でtokenのみ抽出する必要がある．

        except ConnectionError:
            print("client disconnected")

        finally:
            client_socket.close()

    def start_server(self):
        #serverの起動
        logging.info("starting")
        #TCPソケットの生成
        try:
            with socket.socket(socket.AF_INET,socket.SOCK_STREAM) as s:
                s.bind(self.server_address)
                s.listen(self.CLIENT_NUM)
                while True:
                        client_socket,addr = s.accept() #接続受付
                        logging.info(f"accepted client address:{addr}")
#                        self.receive_response(client_socket,addr)
                        thread = threading.Thread(target = self.receive_response,args = (client_socket,addr))
                        thread.start()

        finally:
            logging.info("server stopped")

if __name__ == "__main__":
    my_server = Server("127.0.0.1",9000)
    my_server.start_server()
