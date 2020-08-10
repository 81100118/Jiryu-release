# -*- coding: utf-8 -*-
from client10080 import TenhouClient
import tkinter as tk
import logging

window = tk.Tk()
window.title('地龍')
window.geometry('1024x768')  # 这里的乘是小x

def setupLogging():
    logger = logging.getLogger('tenhou')
    logger.setLevel(logging.DEBUG)
    ch = logging.StreamHandler()
    ch.setLevel(logging.DEBUG)
    formatter = logging.Formatter('%(asctime)s %(levelname)s: %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
    ch.setFormatter(formatter)
    logger.addHandler(ch)

def connectAndLogin():
    client = TenhouClient()
    client.connect()
    uname = client.authenticate(id_entry.get())
    print('ok')
    if uname != None:
        login_status_label.config(text = "你的名字是：" + uname)
        client.end_game()
    else:
        login_status_label.config(text = '失败')
        login_status_label.update()
        client.end_game()

setupLogging()

# 第4步，在图形界面上设定标签
title = tk.Label(window, text='地龍', fg='white', bg='green', font=('mincho', 48), width=6, height=2)
id_entry = tk.Entry(window, font=('consolas', 16), width=20)
login_button = tk.Button(window, font=('default font', 16), text='登录', command=connectAndLogin)
login_status_label = tk.Label(window, text='请输入ID', font=('default font', 16), height=2)
# 说明： bg为背景，font为字体，width为长，height为高，这里的长和高是字符的长和高，比如height=2,就是标签有2个字符这么高


# 第5步，放置标签

title.pack()    # Label内容content区域放置位置，自动调节尺寸
id_entry.pack(anchor='center')
login_button.pack(anchor='center')
login_status_label.pack(anchor='center')
# 放置lable的方法有：1）l.pack(); 2)l.place();

 

# 第6步，主窗口循环显示

window.mainloop()
