import socket 
import time
import threading
import secrets

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
            return "host"+secrets.token_hex(16)+user_name #host用のtoken
        else:
            return secrets.token_hex(16)+user_name

    def setting_room(self,is_host,user_name,ip_address): #tokenの生成・ユーザの記録・IPの記録を行う．戻り値は生成したtoken
        token = self.generate_token(is_host,user_name)
        self.token_ip[token] = ip_address
        self.token_user[token] = user_name
        self.token_time[token] = time.time()
      
        if is_host:
            self.host_token = token     #hostに関する記録処理はhashmap上手に利用すれば，host_user,host_tokenのうちどちらかのみ利用すればいいが，今は楽なので，両方記述している．

        #print("return token:",token)
        return token


    def manage_user(self): #メッセージ送信最終時刻から一定時間経過していたら，ルームからそのユーザを除外する udp側で処理?（udpでのメッセージ最終送信時刻を追跡する必要があるから）
        print("test")

class Server:
    def __init__(self,server_ip,server_port):
        self.CLIENT_NUM = 10
        self.HEADER_SIZE = 32
        self.udp_socket = None
        self.server_address = (server_ip,server_port)
        self.room_list = []

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
            print("make_message message ---- ", message)
            
            if message is None:
                message = "No token"
            message_enc = message.encode('utf-8')
           
            operation_payload_size = len(message_enc).to_bytes(29,'big')
            #headerとbodyの結合
            print("operation_payload_size ",operation_payload_size)
            data = room_name_size + operation_byte + state_byte + operation_payload_size + room_name_enc + message_enc   
            #print(data)
            return data
        
        except Exception as e:
            print(e)

        
    
    def receive_response(self,client_socket,client_address): 
        #リクエストを受信し，処理を行う
        try:
            with client_socket:
                header = client_socket.recv(self.HEADER_SIZE)#headerの受信
                while len(header) < self.HEADER_SIZE: #万が一ヘッダーサイズ分読み取れていない場合の処理
                    additional_message = client_socket.recv(self.HEADER_SIZE - len(header))
                    header += additional_message

                room_name_size = header[0] 
                operation = header[1] #要素1つのときバイト列数値変換する必要あったか忘れたので，確認する
                state = header[2]
                operation_payload_size = int.from_bytes(header[3:len(header)],'big') 

                #room_name_sizeをbyte列で受信する
                body_message = client_socket.recv(room_name_size + operation_payload_size)#bodyメッセージ受信
                
                room_name = body_message[0:room_name_size].decode('utf-8')
                operation_payload = body_message[room_name_size:len(body_message)].decode('utf-8')

                print("client request: room name:",room_name," operation:",operation," state:",state)

                token = None
                #operationに対応した処理
                if operation == 1: #ルーム生成などのセッティング
                    host_user_name = operation_payload #operation==1のときの，operation_payloadにはユーザ名が入っている．このユーザがRoomのホストとなる．
                    new_room = Room(room_name,host_user_name) 
                    print("host_user_name:",host_user_name)
                    token = new_room.setting_room(True,host_user_name,client_address[1]) #生成したtokenを受け取る
                    self.room_list.append(new_room) #ルームの登録
                
                    status_code = "OP1OK"  #ステータスコード送信処理

                elif operation == 2: #ユーザのルーム参加
                    room = self.find_room(room_name)
                    if  room is not None:
                        user_name = operation_payload 
                        token = room.setting_room(False,user_name,client_address[1])
                        
                        status_code = "OP2OK"  #ステータスコード

                    else:
                        status_code = " Room not found Error" #ステータス
                        token = None

                #print("room_name ",room_name," operation ",operation," state ",state," status_code ",status_code," token ",token)
                
                client_socket.send(self.make_message(room_name,operation,state+1,status_code)) #ステータスコード送信処理（room_name,operation,status,messageが引数）
                client_socket.send(self.make_message(room_name,operation,state+2,token)) #tokenをクライアントに送信する（TCRPの形式に沿ってメッセージを送信するのでroom_name + tokenの形）ので，クライアント側でtokenのみ抽出する必要がある．

        except ConnectionError:
            print("client disconnected")
        
        finally:
            client_socket.close()

    def start_server(self): 
        #serverの起動
        print("starting server...")
        #TCPソケットの生成
        try:
            with socket.socket(socket.AF_INET,socket.SOCK_STREAM) as s:
                s.bind(self.server_address) 
                s.listen(self.CLIENT_NUM)
                while True:
                        client_socket,addr = s.accept() #接続受付
                        print("accepted client:address::",addr)

#                        self.receive_response(client_socket,addr)
                        thread = threading.Thread(target = self.receive_response,args = (client_socket,addr))
                        thread.start()

        finally:
            print("server stopped")


my_server = Server("127.0.0.1",9000)
my_server.start_server()











