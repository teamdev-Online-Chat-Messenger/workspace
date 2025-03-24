import socket 
import time
import threading
import secrets
import pickle
import json
import logging
import sys

logging.basicConfig(level = logging.DEBUG, format="%(asctime)s - %(levelname)s - %(message)s")
PICKLE_FILE="rooms.pkl" #TCPサーバとUDPサーバで管理するオブジェクト共有（ 生成された部屋名やそのホスト，ユーザ，トークン，最終オンライン時刻の管理）

class Room:
    def __init__(self,room_name,host_user):
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
        self.token_ip[token] = address[0] # (address,port) の記録
        self.token_user[token] = user_name
        self.token_time[token] = time.time()
      
        if is_host:
            self.host_token = token     
        share_data_content = {"host_addr":self.token_ip[self.host_token],"clients":{address[0]:(token,time.time())}} #UDPサーバーと共有するデータ
    
        return token,share_data_content

class Server:
    def __init__(self,server_ip,server_port):
        
        self.CLIENT_NUM = 10
        self.HEADER_SIZE = 32
        self.udp_socket = None
        self.server_address = (server_ip,server_port)
        self.room_list = []
        self.share_data_list = {} #udpと共有するデータリスト
        self.room_password = {}

    def find_room(self,user_room_name):
        for r in self.room_list:
            if r.room_name == user_room_name:
                return r
        return None
    
    def make_message(self,room_name,operation,state,tkn): #メッセージをTCRP に沿って処理 
        #header作成
        try:
            room_name_enc = room_name.encode('utf-8') #room_nameのエンコード
            room_name_size = len(room_name_enc).to_bytes(1,'big') #数値からバイトへ
            operation_byte = operation.to_bytes(1,'big')
            state_byte = state.to_bytes(1,'big')
            
            if tkn is None:
                tkn = "No token"
            message_enc = tkn.encode('utf-8')
           
            operation_payload_size = len(message_enc).to_bytes(29,'big')
            #headerとbodyの結合
            data = room_name_size + operation_byte + state_byte + operation_payload_size + room_name_enc + message_enc   
            
            return data
        
        except Exception as e:
            print(e)

    def load_rooms(self):
        try:
            with open(PICKLE_FILE, 'rb') as f:
                rooms = pickle.load(f)
                return rooms
        except FileNotFoundError:
            return {}

    
    def receive_response(self,client_socket,client_address): 
        #リクエストを受信し，処理を行う
        try:
            with client_socket:
                    status_code = ""
                    while not(status_code == "OP1OK" or status_code == "OP2OK"): #ステータスコードが正常なもの以外は，相手クライアントとの接続を残して，再度正常になるまで，通信を続ける
                        try:
                            header = client_socket.recv(self.HEADER_SIZE) #headerの受信
                            while len(header) < self.HEADER_SIZE: #万が一ヘッダーサイズ分読み取れていない場合の処理
                                additional_message = client_socket.recv(self.HEADER_SIZE - len(header))
                                header += additional_message
                            logging.info("header-->%s",header)
                            
                            room_name_size = header[0] 
                            operation = header[1]
                            state = header[2]
                            operation_payload_size = int.from_bytes(header[3:len(header)],'big') 

                            body_message = client_socket.recv(room_name_size + operation_payload_size)#bodyメッセージ(RoomNameとPayload)受信
                            
                            room_name = body_message[0:room_name_size].decode('utf-8')
                            operation_payload = body_message[room_name_size:len(body_message)].decode('utf-8')
                          
                            token = None
                            
                            #udpサーバーが書き込んだ共有データの読み込み
                            self.share_data_list = self.load_rooms()
                            
                            renew_setting_password = {}  #ルーム用パスワード記録の更新（削除されたルームのパスワードは記録しない）
                            for rname in self.room_password.keys():
                                if rname in self.share_data_list.keys():
                                    renew_setting_password[rname] = self.room_password[rname]
                            self.room_password = renew_setting_password

                            
                            #operationに対応した処理
                            if operation == 1: #ルーム生成などのセッティング
                                if room_name in self.share_data_list: #すでに登録済みの部屋名
                                    status_code = "ROOM EXIST ERROR"
                                else:
                                    host_user_name = operation_payload #operation==1のときの，operation_payloadにはユーザ名が入っている．このユーザがroomのホストとなる．
                                    new_room = Room(room_name,host_user_name) #roomの作成
                                    token,share_data_content = new_room.setting_room(True,host_user_name,client_address) #生成したtokenを受け取る＋UDPサーバと共有する管理辞書のvalueを受け取る．
                                    self.room_list.append(new_room) #ルームの登録
                                    self.share_data_list[room_name] = share_data_content #UDPサーバと共有する辞書に，新たなroom情報を書き込む
                                    logging.debug("UDPと共有するデータ:%s",self.share_data_list)
                                    #シェアするデータをシリアライズ化してlocal fileにデータ書き込む
                                    with open("rooms.pkl","wb") as f:
                                            pickle.dump(self.share_data_list,f)
                    
                                    status_code = "OP1OK"  #正常に処理した場合のステータスコード（メッセージ）

                                    temp_message = "setting password ?? (Enter no or password)"
                                    client_socket.send(self.make_message(room_name,0,state+1,temp_message)) #パスワード設定有無をクライアントへ送信
                                    recv_password_data = client_socket.recv(1024) #パスワード(no or password)をクライアントから受信
                                    room_size = recv_password_data[0]
                                    password = recv_password_data[32+room_size:32+len(recv_password_data)].decode('utf-8')

                                    logging.debug("tcp server receive password from client:%s",password)
                                    if password.lower() != 'no':
                                        self.room_password[room_name] = password  #roomに対するパスワードの設定
                                        logging.debug("room_password:%s",self.room_password) 

                            elif operation == 2: #ユーザのルーム参加
                                room = self.find_room(room_name) #ユーザが指定したroomを取得・存在しなければNone
                                if room is None:
                                    temp_message = "ROOM NOT FOUND"
                                    client_socket.send(self.make_message(room_name,0,state+1,temp_message))
                                    status_code = "ROOM NOT FOUND"
                                    token = None
                                else:
                                    user_name = operation_payload 
                                    #passwordを要求
                                    if room_name in self.room_password.keys():
                                        temp_message = "need password..."
                                        client_socket.send(self.make_message(room_name,0,state+1,temp_message)) #passwordをクライアントへ要求するメッセージを送信                                  
                                        recv_password_data = client_socket.recv(1024) #クライアントからpassword の取得（password未設定の場合クライアントからは""が送信される．より良い処理方法があると考えられるが，現状愚直に実装する）           
                                        room_size = recv_password_data[0]
                                        password = recv_password_data[32+room_size:32+len(recv_password_data)].decode('utf-8')
                                        if password == self.room_password[room_name]: #passwordが正解であれば，通常通りtokenを生成して，クライアントへ送信
                                            token,share_data_content = room.setting_room(False,user_name,client_address)
                                            self.share_data_list[room_name]["clients"][client_address[0]]= (token,time.time())

                                            logging.debug("TCP と共有するデータ:%s",self.share_data_list)
                                            with open("rooms.pkl","wb") as f:
                                                pickle.dump(self.share_data_list,f)
                                            status_code = "OP2OK"  #ステータスメッセージ

                                        else: #passwordを間違えていれば，status_codeはエラー かつ token = None とする"
                                            logging.info("incorrect password")
                                            status_code = " INCORRECT PASSWORD"
                                            token = None                
                                    
                                    else: #passwordがルームに設定されていないとき
                                        temp_message = " "
                                        client_socket.send(self.make_message(room_name,0,state+1,temp_message)) #passwordが設定されていなくても，recvをクライアント側で記述しているので，空文字送信することで，クライアント側の処理をすすめる
                                        recv_password_data = client_socket.recv(1024) #クライアントからpassword の取得（password未設定の場合クライアントからは""が送信される．より良い処理方法があると考えられるが，現状愚直に実装する）           
                                        room_size = recv_password_data[0]
                                        password = recv_password_data[32+room_size:32+len(recv_password_data)].decode('utf-8')
                                        token,share_data_content = room.setting_room(False,user_name,client_address)
                                        self.share_data_list[room_name]["clients"][client_address[0]]= (token,time.time())
                                        with open("rooms.pkl","wb") as f:
                                            pickle.dump(self.share_data_list,f)
                                        status_code = "OP2OK"  #ステータスメッセージ
                            else:
                                    status_code = " INVALID OP ERROR"
                
                            client_socket.send(self.make_message(room_name,0,state+1,status_code)) #ステータスコード送信処理（room_name,operation,status,messageが引数）
                            client_socket.send(self.make_message(room_name,0,state+2,token)) #tokenをクライアントに送信する（TCRPの形式に沿ってメッセージを送信するのでroom_name + tokenの形）ので，クライアント側でtokenのみ抽出する必要がある．
                    
                        except ConnectionError:
                            print("client disconnected")
                              
                        except Exception as e:
                            e_type,e_object,e_traceback = sys.exc_info()
                            logging.info("Error:%s",e)
                            logging.info("line %s",e_traceback.tb_lineno)
                            status_code = " BAD STATUS"
                            token = None
                            client_socket.send(self.make_message(room_name,0,state+1,status_code)) #ステータスコード送信処理（room_name,operation,status,messageが引数）
                            client_socket.send(self.make_message(room_name,0,state+2,token))
                            continue
        finally:
            logging.debug("connection closed")

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
                        thread = threading.Thread(target = self.receive_response,args = (client_socket,addr)) #各クライアントと通信を行うためのスレッド
                        thread.start()
        except Exception as e:
            e_type,e_object,e_traceback = sys.exc_info()
            logging.info("Error:%s",e)
            logging.info("line %s",e_traceback.tb_lineno)

if __name__ == "__main__":
    my_server = Server("127.0.0.1",9000)
    my_server.start_server()

