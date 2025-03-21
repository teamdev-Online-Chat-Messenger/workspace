#以下のコードはchat_gpt使用して作成しているので意図しない動作している可能性があります


import unittest
import pickle
import os
from server import Room, Server  # server.py に本体コードがある前提

class TestRoom(unittest.TestCase):

    def setUp(self):
        self.room = Room("test_room", "host_user")

    def test_generate_token(self):
        token_host = self.room.generate_token(True, "host_user")
        token_guest = self.room.generate_token(False, "guest_user")

        self.assertTrue(token_host.startswith("host"))
        self.assertNotEqual(token_host, token_guest)

    def test_setting_room(self):
        token, share_data = self.room.setting_room(True, "host_user", "192.168.1.1")

        self.assertIn(token, self.room.token_ip)
        self.assertEqual(self.room.token_ip[token], "192.168.1.1")
        self.assertEqual(self.room.token_user[token], "host_user")

        room_key = ("test_room", "192.168.1.1")
        self.assertIn(room_key, share_data)
        self.assertIn("192.168.1.1", share_data[room_key])

class TestServer(unittest.TestCase):

    def setUp(self):
        self.server = Server("127.0.0.1", 9000)

    def test_find_room(self):
        room = Room("test_room", "host_user")
        self.server.room_list.append(room)

        found_room = self.server.find_room("test_room")
        self.assertIsNotNone(found_room)
        self.assertEqual(found_room.room_name, "test_room")

        not_found_room = self.server.find_room("nonexistent_room")
        self.assertIsNone(not_found_room)

    def test_make_message(self):
        message = self.server.make_message("test_room", 1, 2, "Test message")
        self.assertIsInstance(message, bytes)

    def test_pickle_save_load(self):
        room = Room("test_room", "host_user")
        token, share_data = room.setting_room(True, "host_user", "192.168.1.1")
        self.server.share_data_list.append(share_data)

        with open("rooms.pkl", "wb") as f:
            print(self.server.share_data_list)
            pickle.dump(self.server.share_data_list, f)

        with open("rooms.pkl", "rb") as f:
            loaded_data = pickle.load(f)
            print("Loaded data:", loaded_data)
        self.assertEqual(self.server.share_data_list, loaded_data)

    def tearDown(self):
        if os.path.exists("rooms.pkl"):
            os.remove("rooms.pkl")

if __name__ == "__main__":
    unittest.main()
