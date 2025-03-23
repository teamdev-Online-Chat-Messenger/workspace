import pickle

with open("rooms.pkl", "rb") as f:
    data = pickle.load(f)
    print(data)
