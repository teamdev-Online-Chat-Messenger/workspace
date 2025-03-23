# workspace
workspace for online_chat_messenger

# remote-procedure-call

## 概要
チャットメッセンジャー


## 実行方法

### サーバー側

TCPサーバーの起動
```
python3 tcp_server.py
```
UDPサーバーの起動
```
python3 udp_server.py
```

### クライアント側
```
python3 client.py
```

####　ルームの作成および参加（ホスト）
はじめに，ホストユーザはIPアドレスを選択する．（現在ローカルの1台のPCで簡易的に作成した状態であるため，ローカルループバックアドレスを用いているためこの操作が必要）
<br>
続いて利用するポート番号を選択する．
<br>
次に作成するルーム名を入力して，createを入力．そして，TCPサーバからステータスメッセージとチャットルームのためにトークンを受け取る．
<br>
最後に，上記で入力したルーム名を再度打ち込み入室が完了し，メッセージの受信・送信が可能となる．
<br>


```
Enter IP Address (127.0.0.2~) --> 127.0.0.2
Enter Port for UDP --> 9000
Enter User Name --> test_user1
Enter Your Room Name --> test_room1
Would you like to create a new room or join an existing one? (Type 'create' or 'join') --> create
Creating a new chat room...
2025-03-23 22:44:57,576 - INFO - Status Code:OP1OK
2025-03-23 22:44:57,576 - INFO - token:::0b810fd92c7448f0580dfc6c6beb53ab_host_token_test_user1
Enter Your Room Name To Join Chat Room--> test_room1
Enter Your Message -->
```

#### ルームへの参加（ホスト以外のユーザ）
```




```



## 実際の動作(写真)

![image](./img/)
![image](./img/)
