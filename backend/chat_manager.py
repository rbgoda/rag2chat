from collections import deque
from threading import Lock

class ChatManager:
def __init__(self, max_history=5):
self.chats = {}
self.max_history = max_history
self.lock = Lock()

def add_message(self, session_id, role, content):
with self.lock:
if session_id not in self.chats:
self.chats[session_id] = deque(maxlen=self.max_history * 2)
self.chats[session_id].append({"role": role, "content": content})

def get_history(self, session_id):
with self.lock:
return list(self.chats.get(session_id, []))
