import socket
import threading
import logging

class Client:
    def __init__(self):
        self.tcp_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.server_address = ('127.0.0.1', 9000)
        self.udp_server_address = ('127.0.0.1', 12345)

    def tcp_communication(self):
        user_name = input("Enter your name: ")
        room_name = input("Enter room name: ")
        operation = input("Create or join a room? (create/join): ").lower()
        udp_port = int(input("Enter local UDP port: "))  # 先にポート番号を聞いておく（重要）

        self.local_udp_port = udp_port

        # TCP接続開始
        self.tcp_socket.connect(self.server_address)

        operation_code = 1 if operation == "create" else 2
        state = 0
        payload = f"{user_name},{udp_port}".encode('utf-8')  # ← ここでUDPポートを送信

        header = (
            len(room_name.encode('utf-8')).to_bytes(1, 'big') +
            operation_code.to_bytes(1, 'big') +
            state.to_bytes(1, 'big') +
            len(payload).to_bytes(29, 'big')
        )

        self.tcp_socket.send(header + room_name.encode('utf-8') + payload)

        # サーバからレスポンス受け取り (ステータスコード、トークン)
        status_response_header = self.tcp_socket.recv(32)
        payload_size = int.from_bytes(status_response_header[3:], 'big')
        status_response_body = self.tcp_socket.recv(payload_size + status_response_header[0])

        logging.info("Status response: %s", status_response_body.decode('utf-8'))

        # トークンの受け取り
        token_response_header = self.tcp_socket.recv(32)
        token_payload_size = int.from_bytes(token_response_header[3:], 'big')
        token_response_body = self.tcp_socket.recv(token_payload_size + token_response_header[0])
        token = token_response_body[token_response_header[0]:].decode('utf-8')

        logging.info("Received token: %s", token)

        self.tcp_socket.close()

        return room_name, token

    def start_udp(self, room_name, token):
        # 事前に聞いたUDPポートでソケットをbind
        self.udp_socket.bind(('0.0.0.0', self.local_udp_port))

        threading.Thread(target=self.udp_receive_messages, daemon=True).start()
        self.udp_send_messages(room_name, token)

    def udp_receive_messages(self):
        while True:
            message, _ = self.udp_socket.recvfrom(4096)
            logging.info("Received UDP message: %s", message.decode('utf-8'))

    def udp_send_messages(self, room_name, token):
        header = len(room_name.encode('utf-8')).to_bytes(1, 'big') + len(token.encode('utf-8')).to_bytes(1, 'big')
        while True:
            message = input("Enter your message: ")
            body = room_name.encode('utf-8') + token.encode('utf-8') + message.encode('utf-8')
            self.udp_socket.sendto(header + body, self.udp_server_address)

    def run(self):
        room_name, token = self.tcp_communication()
        self.start_udp(room_name, token)


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG, format="%(asctime)s - %(levelname)s - %(message)s")
    client = Client()
    client.run()
