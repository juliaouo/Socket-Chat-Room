from tkinter import messagebox
from PIL import ImageTk, Image
import tkinter as tk
import struct
import json
import time
import threading
import socket

# 歡迎視窗 GUI
class Welcome:
    def __init__(self):
        self.window = tk.Tk()
        self.user = tk.StringVar()
        
        self.window.title('歡迎')
        self.window.geometry('320x240')
        self.window.resizable(width=False, height=False)
        # 設定背景圖片
        self.canvas = tk.Canvas(self.window, width=500, height=500, bd=0, highlightthickness=0)
        self.photo = ImageTk.PhotoImage(Image.open('source/bg.gif'))
        self.canvas.create_image(0, 0, image=self.photo)
        self.canvas.pack()
        
        self.label1 = tk.Label(self.window, text='請輸入用戶名')
        self.label1.place(relx=0.37, rely=0.1, height=30, width=85)    
        self.entry_user = tk.Entry(self.window)
        self.entry_user.place(relx=0.23, rely=0.25, height=25, relwidth=0.55)
        self.entry_user.configure(textvariable=self.user)
        
        self.btn_enter = tk.Button(self.window, text='進入聊天室', command=click_enter)
        self.btn_enter.place(relx=0.37, rely=0.6, height=32, width=88)

    def show(self):
        self.window.mainloop()

    def destroy(self):
        self.window.destroy()

# 聊天視窗 GUI
class ChatRoom:
    closed_fc = None
    def __init__(self):
        self.window = tk.Tk()
        self.window.title('聊天室')
        self.window.geometry('480x320')
        self.window.protocol('WM_DELETE_WINDOW', self.destroy)
        self.window.resizable(width=False, height=False)
        # 設定背景圖片
        self.canvas = tk.Canvas(self.window, width=500, height=500, bd=0, highlightthickness=0)
        self.photo = ImageTk.PhotoImage(Image.open('source/bg.gif'))
        self.canvas.create_image(0, 0, image=self.photo)
        self.canvas.pack()

        self.msg = tk.StringVar()
        self.name = tk.StringVar()

        self.user_list = tk.Listbox(self.window)
        self.user_list.place(relx=0.75, rely=0.15, relheight=0.72, relwidth=0.23)

        self.label1 = tk.Label(self.window, text='在線成員')
        self.label1.place(relx=0.76, rely=0.075, height=21, width=101)

        self.history = tk.Text(self.window, state='disabled')
        self.history.place(relx=0.03, rely=0.15, relheight=0.63, relwidth=0.696)

        self.entry_msg = tk.Entry(self.window, textvariable=self.msg)
        self.entry_msg.place(relx=0.03, rely=0.805, height=24, relwidth=0.59)

        self.btn_send = tk.Button(self.window, text='傳送')
        self.btn_send.place(relx=0.63, rely=0.8, height=28, width=45)

        self.label2 = tk.Label(self.window)
        self.label2.place(relx=0.24, rely=0.075, height=20, width=140)
        self.label2.configure(textvariable=self.name)

    def show(self):
        self.window.mainloop()

    def destroy(self):
        try:
            self.closed_fc()
        except:
            pass
        self.window.destroy()

# 初始化
wel_window = None
chat_window = None
my_socket = None
user_name = ''
current_session = ''
users = {}

PORT = 7000
FORMAT = 'utf-8'
SERVER = socket.gethostbyname(socket.gethostname()) #Server IP
ADDR = (SERVER, PORT)

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

# 關閉 socket
def close_socket():
    # 送出關閉訊息
    send(my_socket, {'cmd': 'close'})
    # 關閉所有通道後關閉連接
    my_socket.shutdown(2)
    my_socket.close()

# 點擊進入聊天室
def click_enter():
    global my_socket, user_name, wel_window, chat_window
    my_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    my_socket.settimeout(5)

    if wel_window.user.get() != '':
        my_socket.connect(ADDR)
        send(my_socket, {'cmd': 'enter', 'user': wel_window.user.get()})
        server_response = recv(my_socket)

        if server_response['response'] == 'ok':
            user_name = wel_window.user.get()
            wel_window.destroy()
    
            chat_window = ChatRoom()
            chat_window.closed_fc = close_socket
            chat_window.window.title(f'{user_name} 的聊天室')
            chat_window.name.set(f'歡迎來到聊天室！{user_name}')

            chat_window.btn_send.configure(command=click_send)
            chat_window.user_list.bind('<<ListboxSelect>>', select_session)

            # 獲取所有在線用戶與公共聊天紀錄請求
            send(my_socket, {'cmd': 'get_users'})
            send(my_socket, {'cmd': 'get_history', 'peer': ''})

            t = threading.Thread(target=recv_async, args=())
            t.setDaemon(True)
            t.start()
            chat_window.show()
        elif server_response['response'] == 'fail':
            messagebox.showerror('警告', server_response['reason'])
            close_socket()
    else:
        messagebox.showerror('警告', '用戶名不能為空！')

# 點擊傳送            
def click_send():
    global my_socket, user_name, current_session, chat_window
    if chat_window.msg.get() != '':
        my_socket.send(pack(json.dumps({'cmd': 'chat', 'peer': current_session, 'msg': chat_window.msg.get()}).encode(FORMAT)))
        add_history(user_name, time.strftime('%m月%d日%H:%M', time.localtime(time.time())), chat_window.msg.get())
        chat_window.msg.set('')
    else:
        messagebox.showinfo('警告', '訊息為空，請輸入訊息！')

# 印出聊天紀錄
def add_history(sender, time, msg):
    # 設為可寫
    chat_window.history['state'] = 'normal'
    chat_window.history.insert('end', f'{sender} - {time}\n')
    chat_window.history.insert('end', msg + '\n\n')
    chat_window.history.see('end')
    # 設為唯讀
    chat_window.history['state'] = 'disabled'

# 點擊聊天室列表成員事件
def select_session(event):
    global current_session, chat_window, user_name, users
    w = event.widget
    changed = False
    # 選取到的聊天室
    if len(w.curselection()) != 0:
        index = int(w.curselection()[0])
        if index != 0:
            # 切換聊天對象 (非公共聊天室)
            if current_session != w.get(index).rstrip(' (*)'):
                changed = True
                current_session = w.get(index).rstrip(' (*)')
                chat_window.name.set(f'{current_session}')
                users[current_session] = False
                refresh_user_list()
        elif index == 0:
            # 切換到公共聊天室
            if current_session != '':
                changed = True
                current_session = ''
                chat_window.name.set('公共聊天室')
                users[''] = False
                refresh_user_list()
        if changed:
            # 切換聊天紀錄
            my_socket.send(pack(json.dumps({'cmd': 'get_history', 'peer': current_session}).encode(FORMAT)))

def peer_enter(peer):
    # 設為可寫
    chat_window.history['state'] = 'normal'
    chat_window.history.insert('end', f'{peer} 進入聊天室\n\n')
    chat_window.history.see('end')
    # 設為唯讀
    chat_window.history['state'] = 'disabled'

def peer_leave(peer):
    # 設為可寫
    chat_window.history['state'] = 'normal'
    chat_window.history.insert('end', f'{peer} 離開聊天室\n\n')
    chat_window.history.see('end')
    # 設為唯讀
    chat_window.history['state'] = 'disabled'

# thead 處理
def recv_async():
    global my_socket, users, chat_window, current_session
    while True:
        data = recv(my_socket)
        # 獲得在線列表
        if data['type'] == 'get_users':
            users = {}
            for user in [''] + data['data']:
                users[user] = False
            refresh_user_list()
        # 獲得聊天紀錄
        elif data['type'] == 'get_history':
            if data['peer'] == current_session:
                # 清空之前的聊天紀錄
                chat_window.history['state'] = 'normal'
                chat_window.history.delete('1.0', 'end')
                chat_window.history['state'] = 'disabled'
                # 更新成最新版本紀錄
                for history_data in data['data']:
                    add_history(history_data[0], history_data[1], history_data[2])
        # 加入新成員
        elif data['type'] == 'peer_joined':
            users[data['peer']] = False
            if current_session == '':
                peer_enter(data['peer'])
            refresh_user_list()
        # 成員離開
        elif data['type'] == 'peer_left':
            if data['peer'] in users:
                del users[data['peer']]
            if current_session == '':
                peer_leave(data['peer'])
            if data['peer'] == current_session:
                current_session = ''
                chat_window.name.set('公共聊天室')
                users[''] = False
                my_socket.send(pack(json.dumps({'cmd': 'get_history', 'peer': ''}).encode(FORMAT)))
            refresh_user_list()
        elif data['type'] == 'msg':
            # 收到非公共聊天室成員訊息，若為當前聊天室印出訊息, 非當前聊天室設 True (表示有未查看的消息)
            if data['peer'] == current_session:
                add_history(data['peer'], time.strftime('%m月%d日%H:%M', time.localtime(time.time())), data['msg'])
            else:
                users[data['peer']] = True
                refresh_user_list()
        elif data['type'] == 'global_msg':
            # 收到公共聊天室成員訊息
            if current_session == '':
                add_history(data['peer'], time.strftime('%m月%d日%H:%M', time.localtime(time.time())), data['msg'])
            else:
                users[''] = True
                refresh_user_list()

def refresh_user_list():
    chat_window.user_list.delete(0, 'end')
    for user in users.keys():
        name = '公共聊天室' if user == '' else user
        # 若有未查看的新訊息則加 ' (*)' 提示新訊息
        if users[user]:
            name += ' (*)'
        chat_window.user_list.insert('end', name)

wel_window = Welcome()
wel_window.show()