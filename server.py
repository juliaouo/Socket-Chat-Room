import socket
import pickle
import struct
import json
import threading
import time

# 初始化
PORT = 7000
FORMAT = 'utf-8'
SERVER = socket.gethostbyname(socket.gethostname())
ADDR = (SERVER, PORT)

# 所有用戶及聊天紀錄
users = {}
history = {}


def load_users():
    try:
        return pickle.load(open('users.pickle', 'rb'))
    except:
        return {}


def register(user):
    if user not in users.keys():
        users[user] = True
        save_users()


def save_users():
    pickle.dump(users, open('users.pickle', 'wb'))


def load_history():
    try:
        return pickle.load(open('history.pickle', 'rb'))
    except:
        return {}

# 添加新聊天紀錄並保存
def add_history(sender, receiver, msg):
    global users, history
    if receiver == '':
        key = ('','')
    else:
        key = (sender, receiver) if (receiver, sender) not in history.keys() else (receiver, sender)
    if key not in history.keys():
        history[key] = []
    history[key].append((sender, time.strftime('%m月%d日%H:%M', time.localtime(time.time())), msg))
    save_history()

# 獲取聊天紀錄
def get_history(sender, receiver):
    global users, history
    if receiver == '':
        key = ('','')
    else:
        key = (sender, receiver) if (receiver, sender) not in history.keys() else (receiver, sender)
    return history[key] if key in history.keys() else []
    

def save_history():
    pickle.dump(history, open('history.pickle', 'wb'))    

# 打包成二進制並加上資料長度資訊避免黏包
def pack(data):
    return struct.pack('>H', len(data)) + data

# 將資料送出
def send(socket, data_dict):
    socket.send(pack(json.dumps(data_dict).encode('utf-8')))

# 將收到的資料還原
def recv(socket):
    data = b''
    # 取得資料長度
    surplus = struct.unpack('>H', socket.recv(2))[0]
    socket.settimeout(5)
    while surplus:
        recv_data = socket.recv(1024 if surplus > 1024 else surplus)
        data += recv_data
        surplus -= len(recv_data)
    socket.settimeout(None)
    return json.loads(data)

# 接受 client 連線
def accept_client():
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.bind(ADDR)
    print(f'Server: {SERVER} start listening...')
    server.listen(5)
    while True:
        request, client_address = server.accept()
        # 創建新 thread 來完成 client 請求
        thread = threading.Thread(target=process_request, args=(request, client_address))
        thread.setDaemon(True)
        thread.start()

# thread 處理
def process_request(request, client_address):
    Handler(request, client_address)

class Handler:
    # 存目前連線的 client
    clients = {}
    
    
    def __init__(self, request, client_address):
        self.request = request
        self.client_address = client_address
        self.setup()
        try:
            self.handle()
        finally:
            self.finish()


    def setup(self):
        self.user = ''
        self.authed = False
        self.connect = True


    def handle(self):
        while self.connect:
            data = recv(self.request)
            # 尚未授權進入
            if not self.authed:
                self.user = data['user']
                register(self.user)
                if data['cmd'] == 'enter':
                    if self.user in Handler.clients.keys():
                        # 若已登入回報錯誤
                        send(self.request, {'response': 'fail', 'reason': '用戶已登入！'})
                    else:
                        send(self.request, {'response': 'ok'})
                        self.authed = True
                        for user in Handler.clients.keys():
                            send(Handler.clients[user].request, {'type': 'peer_joined', 'peer': self.user})
                        Handler.clients[self.user] = self
            else:
                # 返回在線用戶列表
                if data['cmd'] == 'get_users':
                    users = []
                    for user in Handler.clients.keys():
                        if user != self.user:
                            users.append(user)
                    send(self.request, {'type': 'get_users', 'data': users})
                # 返回歷史聊天紀錄
                elif data['cmd'] == 'get_history':
                    send(self.request, {'type': 'get_history', 'peer': data['peer'], 'data': get_history(self.user, data['peer'])})
                # 傳送當前用戶的訊息給聊天對象 (非公共)，並紀錄
                elif data['cmd'] == 'chat' and data['peer'] != '':
                    send(Handler.clients[data['peer']].request, {'type': 'msg', 'peer': self.user, 'msg': data['msg']})
                    add_history(self.user, data['peer'], data['msg'])
                # 傳送當前用戶的訊息給公共聊天室
                elif data['cmd'] == 'chat' and data['peer'] == '':
                    for user in Handler.clients.keys():
                        if user != self.user:
                            send(Handler.clients[user].request, {'type': 'global_msg', 'peer': self.user, 'msg': data['msg']})
                    add_history(self.user, '', data['msg'])
                # client 關閉
                elif data['cmd'] == 'close':
                    self.finish()
                    self.connect = False
        self.request.shutdown(2)
        self.request.close()

    # 刪除在線列表的該用戶並告知其他用戶
    def finish(self):
        if self.authed:
            self.authed = False
            if self.user in Handler.clients.keys():
                del Handler.clients[self.user]
            for user in Handler.clients.keys():
                send(Handler.clients[user].request, {'type': 'peer_left', 'peer': self.user})
                
                
# 載入歷史用戶和聊天紀錄                
users = load_users()
history = load_history()

app = accept_client()