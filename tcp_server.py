import socket 
import time
import threading
import uuid 
import pickle
import json
import logging
import sys

logging.basicConfig(level = logging.DEBUG, format="%(asctime)s - %(levelname)s - %(message)s")
PICKLE_FILE="rooms.pkl" #TCPサーバとUDPサーバで管理するオブジェクト共有（ 生成された部屋名やそのホスト，ユーザ，トークン，最終オンライン時刻の管理）

HEADER_SIZE = 32 #ヘッダーサイズ

lock = threading.Lock()

class Room:
    def __init__(self,room_name):
        self.room_name = room_name
        self.host_token = None
        self.token_ip = {} 
        self.token_user = {}
        self.token_time = {} #tokenとメッセージ最終送信時刻
       
    def generate_token(self,is_host,user_name): 
        if is_host:
            return str(uuid.uuid1())+"_host_token_"+user_name #host用のtoken
        else:
            return str(uuid.uuid1())+user_name

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


    def load_rooms(self): #udpサーバが書き込んだpickleを読み込むためのメソッド
        try:
            with open(PICKLE_FILE, 'rb') as f:
                rooms = pickle.load(f)
                return rooms
        except FileNotFoundError:
            return {}

    
    def create_message(self,room_name,operation,state,message): #メッセージをTCRP に沿って処理 
        try:
            #header作成
            room_name_size = len(room_name.encode('utf-8')).to_bytes(1,'big') #数値からバイトへ
            operation_byte = operation.to_bytes(1,'big')
            state_byte = state.to_bytes(1,'big')
            
            #tcpサーバで承認に失敗しtoken=Noneの際には，No tokenをメッセージに入れる
            if message is None:
                message = "No token"  

            operation_payload_size = len(message.encode('utf-8')).to_bytes(29,'big')
            
            #headerとbodyの結合
            data = room_name_size + operation_byte + state_byte + operation_payload_size + room_name.encode('utf-8') + message.encode('utf-8')   
            
            return data
        
        except Exception as e:
            logging.info("%s",e)
    
    def receive_response(self,client_socket,client_address): #クライアントからのリクエストを受信し，処理を行う
            with client_socket:
                    status_code = "" 
                    while not(status_code == "OP1OK" or status_code == "OP2OK"): #ステータスコードが正常なもの以外は，相手クライアントとの接続を維持して，再度ステータスコードが正常になるまで，通信を続ける
                        try:

                            header = client_socket.recv(HEADER_SIZE) #headerの受信
                            while len(header) < HEADER_SIZE: #万が一ヘッダーサイズ分読み取れていない場合の処理
                                additional_message = client_socket.recv(HEADER_SIZE - len(header))
                                header += additional_message
                            room_name_size = header[0] 
                            operation = header[1]
                            state = header[2]
                            operation_payload_size = int.from_bytes(header[3:len(header)],'big') 

                            body_message = client_socket.recv(room_name_size + operation_payload_size)#bodyメッセージ(RoomNameとPayload)受信                            
                            room_name = body_message[0:room_name_size].decode('utf-8')
                            operation_payload = body_message[room_name_size:len(body_message)].decode('utf-8')
                          
                            token = None
                            
                            self.share_data_list = self.load_rooms() #udpサーバーが書き込んだ共有データの読み込み
                            


                            new_password_map = {} #ルーム用パスワード記録の更新（UDPサーバ側で削除されたルームのパスワードは削除）
                            for room_name in self.room_password.keys():
                                if room_name in self.share_data_list.keys():
                                    new_password_map[room_name] = self.room_password[room_name]
                            self.room_password = new_password_map

                            
                            #operationに対応した処理
                            if operation == 1: #ルーム生成などのセッティング
                                if room_name in self.share_data_list: #すでに登録済みの部屋名
                                    status_code = "ROOM ALREADY EXIST ERROR"
                                else:
                                    host_user_name = operation_payload #operation==1のときの，operation_payloadにはユーザ名が入っている．このユーザがroomのホストとなる．
                                    new_room = Room(room_name) #roomの作成
                                    token,share_data_content = new_room.setting_room(True,host_user_name,client_address) #生成したtokenを受け取る＋UDPサーバと共有する管理辞書のvalueを受け取る．
                                    self.room_list.append(new_room) #ルームの登録
                                    self.share_data_list[room_name] = share_data_content #UDPサーバと共有する辞書に，新たなroom情報を書き込む
                                    
                                    status_code = "OP1OK"  #正常に処理した場合のステータスコード（メッセージ）

                                    temp_message = "setting password ?? (Enter no or password)"
                                    client_socket.send(self.create_message(room_name,0,state+1,temp_message)) #パスワード設定有無をクライアントへ送信
                                    recv_password_data = client_socket.recv(1024) #パスワード(no or password)をクライアントから受信
                                    room_size = recv_password_data[0]
                                    password = recv_password_data[32+room_size:32+len(recv_password_data)].decode('utf-8')

                                    rooms_info  = self.load_rooms()

                                    if room_name in rooms_info: #クライアントがルーム作成時にパスワード入力している間に，他のクライアントが同一名のルームを作成完了したら，完了していない方はエラーとする
                                        status_code = "ROOM ALREADY EXIST ERROR"

                                    else:
                                        logging.debug("tcp server receive password from client:%s",password)
                                        if password.lower() != 'no':
                                            self.room_password[room_name] = password  #roomに対するパスワードの設定
                                            logging.debug("room_password:%s",self.room_password) 

                                        logging.debug("UDPと共有するデータ:%s",self.share_data_list)
                                        #シェアするデータをシリアライズ化してlocal fileにデータ書き込む
                                        with lock:
                                            with open("rooms.pkl","wb") as f:
                                                    pickle.dump(self.share_data_list,f)
                    


                            elif operation == 2: #ユーザのルーム参加
                                room = self.find_room(room_name) #ユーザが指定したroomを取得・存在しなければNone
                                if room is None:
                                    temp_message = "ROOM NOT FOUND"
                                    client_socket.send(self.create_message(room_name,0,state+1,temp_message))
                                    status_code = "ROOM NOT FOUND"
                                    token = None
                                else:
                                    user_name = operation_payload 
                                    #passwordを要求
                                    if room_name in self.room_password.keys():
                                        temp_message = "need password..."
                                        client_socket.send(self.create_message(room_name,0,state+1,temp_message)) #passwordをクライアントへ要求するメッセージを送信                                  
                                        recv_password_data = client_socket.recv(1024) #クライアントからpassword の取得（password未設定の場合クライアントからは""が送信される．より良い処理方法があると考えられるが，現状愚直に実装する）           
                                        room_size = recv_password_data[0]
                                        password = recv_password_data[32+room_size:32+len(recv_password_data)].decode('utf-8')
                                        if password == self.room_password[room_name]: #passwordが正解であれば，通常通りtokenを生成して，クライアントへ送信
                                            token,share_data_content = room.setting_room(False,user_name,client_address)
                                            self.share_data_list[room_name]["clients"][client_address[0]]= (token,time.time())

                                            logging.debug("TCP と共有するデータ:%s",self.share_data_list)
                                            with lock:
                                                with open("rooms.pkl","wb") as f:
                                                    pickle.dump(self.share_data_list,f)
                                            status_code = "OP2OK"  #ステータスメッセージ

                                        else: #passwordを間違えていれば，status_codeはエラー かつ token = None とする"
                                            logging.info("incorrect password")
                                            status_code = " INCORRECT PASSWORD"
                                            token = None                
                                    
                                    else: #passwordがルームに設定されていないとき
                                        temp_message = " "
                                        client_socket.send(self.create_message(room_name,0,state+1,temp_message)) #passwordが設定されていなくても，recvをクライアント側で記述しているので，空文字送信することで，クライアント側の処理をすすめる
                                        recv_password_data = client_socket.recv(1024) #クライアントからpassword の取得（password未設定の場合クライアントからは""が送信される．より良い処理方法があると考えられるが，現状愚直に実装する）           
                                        room_size = recv_password_data[0]
                                        password = recv_password_data[32+room_size:32+len(recv_password_data)].decode('utf-8')
                                        token,share_data_content = room.setting_room(False,user_name,client_address)
                                        self.share_data_list[room_name]["clients"][client_address[0]]= (token,time.time())
                                        with lock:
                                            with open("rooms.pkl","wb") as f:
                                                pickle.dump(self.share_data_list,f)
                                        status_code = "OP2OK"  #ステータスメッセージ
                            else:
                                    status_code = " INVALID OP ERROR"
                
                            client_socket.send(self.create_message(room_name,0,state+1,status_code)) #ステータスコード送信処理（room_name,operation,status,messageが引数）
                            time.sleep(0.5)
                            client_socket.send(self.create_message(room_name,0,state+2,token)) #tokenをクライアントに送信する（TCRPの形式に沿ってメッセージを送信するのでroom_name + tokenの形）ので，クライアント側でtokenのみ抽出する必要がある．
                    
                        except ConnectionError:
                            logging.info("client disconnected")
                            break
                              
                        except Exception as e:
                            e_type,e_object,e_traceback = sys.exc_info()
                            logging.info("Error:%s",e)
                            logging.info("line %s",e_traceback.tb_lineno)
                            status_code = " BAD STATUS"
                            token = None
                            client_socket.send(self.create_message(room_name,0,state+1,status_code)) #ステータスコード送信処理（room_name,operation,status,messageが引数）
                            client_socket.send(self.create_message(room_name,0,state+2,token))
                            continue


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

