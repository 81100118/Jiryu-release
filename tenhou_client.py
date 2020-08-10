import websocket
import json
from urllib.parse import unquote
import utils
import threading
import random
import time

authenticated = False
client = None
PXR = 0
voluntarily_close = False

def on_error(ws, error):
    print('error')
    print(error)

def on_close(ws):
    global authenticated
    authenticated = False
    print("connection closed")
    global voluntarily_close
    if voluntarily_close:
        voluntarily_close = False
    else:
        client.onCloseFunc()

def on_open(ws):
    print('connection opened')

def on_message(ws, message):
    print('recv: ' + message)
    try:
        j = json.loads(message)
        process_message(j)
    except Exception as e:
        print(e)

def process_message(message):
    # message :: dict
    if message['tag'] == 'HELO':
        '''example: 
        {"tag":"HELO",
        "uname":"%53%42",
        "PF4":"14,370,1865.42,1289.0,144,124,133,120,37,5276,1243,692,1869,898",
        "PF3":"17,490,2176.99,4421.0,545,550,459,0,109,13734,4005,1801,3222,3041","expire":"20200609","expiredays":"10",
        "ratingscale":"PF3=1.000000&PF4=1.000000&PF01C=0.582222&PF02C=0.501632&PF03C=0.414869&PF11C=0.823386&PF12C=0.709416&PF13C=0.586714&PF23C=0.378722&PF33C=0.535594&PF1C00=8.000000",
        "rr":"PF3=262,0&PF4=0,0&PF01C=0,0&PF02C=0,0&PF03C=0,0&PF11C=0,0&PF12C=0,0&PF13C=0,0&PF23C=0,0&PF33C=0,0&PF1C00=0,0"}
        '''
        '''
        if 'expire' in message:
            print('尊贵的会员，欢迎登录！')
            print('友情提醒：您的会员将在' + message['expire'] + '到期，请及时续费')
        print('昵称：', unquote(message['uname']))
        if 'PF4' in message:
            print('四麻战绩：', message['PF4'])
        if 'PF3' in message:
            print('三麻战绩：', message['PF3'])
        global client
        client.playerData = utils.PlayerData()
        client.playerData.decode(message)
        print('和了率：', client.playerData.yonmaStat['countAgari'] / client.playerData.yonmaStat['countKyoku'] if client.playerData.yonmaStat['countKyoku'] > 0 else 'NAN')
        '''
        global authenticated
        authenticated = True
    elif message['tag'] == 'LN':
        if 'n' in message:
            num_online = [0,0,0,0]
            tmp = message['n'].split(',')
            for i in range(len(tmp)):
                num_online[i] = int(tmp[i])
            print('总在线人数：' + str(num_online[0]) + ' 当前房间在线人数：' + str(num_online[1])\
                + ' 待机中：' + str(num_online[2]) + ' 对战中：' + str(num_online[1] - num_online[2])\
                + ' 终局：' + str(num_online[3]))
    elif message['tag'] == 'CHAT':
        if 'lobby' in message:
            # 切换个室成功
            if message['lobby'][0] == 'C':
                client.lobby = int(message['lobby'][1:])
            else:
                client.lobby = int(message['lobby'])
            print('切换到个室' + message['lobby'])
        else:
            # 可能是聊天消息
            uname = message['uname']
            text = message['text']
            print('聊天消息：' + uname + ': ' + text)
    elif message['tag'] == 'GO':
        pass
    elif message['tag'] == 'SAIKAI':
        authenticated = True
    client.processFunc(message)

def send(ws, msg):
    try:
        if isinstance(msg, dict):
            ws.send(json.dumps(msg))
            print('sent json: ' + json.dumps(msg))
        else:
            ws.send(msg)
            print('sent string: ' + msg)
    except:
        print('SEND ERROR:')
        print(msg)

class HeartbeatLoopThread(threading.Thread):
    def __init__(self, ws):
        super().__init__()
        self.ws = ws
    def run(self):
        #counter = 0
        #print('----------------------------------------')
        #print(self.ws.sock.connected)
        if self.ws.sock and self.ws.sock.connected:
            send(self.ws, '<Z/>')
            if PXR != 0:
                send(self.ws, '<PXR v="' + str(PXR) + '" />')
            timer = threading.Timer(10, self.run)
            timer.start()
        '''
        while(authenticated):
            counter += 1
            if counter == 10:
                send(self.ws, '<Z/>')
                # send(self.ws, '<PXR v="' + '1' + '" />')
            time.sleep(1)
        '''

class MainLoopThread(threading.Thread):
    def __init__(self, ws):
        super().__init__()
        self.ws = ws
    def run(self):
        print('main loop starts')
        self.ws.run_forever(suppress_origin=True)
        print('main loop ends')


class TenhouClient:
    def __init__(self):
        global authenticated
        authenticated = False
        self.mainLoopThread = None
        self.playerData = None
        self.lobby = 0
        self.processFunc = lambda: 1
        self.onCloseFunc = lambda: 1
    def init(self):
        # connect to tenhou
        websocket.enableTrace(True)
        h = ['Pragma: no-cache',
        'Cache-Control: no-cache',
        'User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/81.0.4044.138 Safari/537.36',
        'Origin: https://tenhou.net',
        'Accept-Encoding: gzip, deflate, br',
        'Accept-Language: zh-CN,zh;q=0.9,en-US;q=0.8,en;q=0.7,zh-TW;q=0.6,ja;q=0.5',
        'Sec-WebSocket-Extensions: permessage-deflate; client_max_window_bits']
        self.ws = websocket.WebSocketApp('wss://b-ww.mjv.jp', header = h, on_message = on_message, on_error= on_error, on_close= on_close)#, suppress_origin = True)
        self.ws.on_open = on_open
        # thread.start_new_thread(self.ws.run_forever, (), {'suppress_origin' : True})
        self.mainLoopThread = MainLoopThread(self.ws)
        self.mainLoopThread.start()
        counter = 0
        while not (self.ws.sock and self.ws.sock.connected):
            counter += 1
            time.sleep(0.1)
            if counter == 50:
                return False
        print('done')
        return True
    def login(self, name, sx='M', gpid = None):
        if authenticated:
            return
        msg_to_send = {'tag': 'HELO', 'name': name, 'sx': sx}
        if gpid:
            msg_to_send['gpid'] = gpid
        # msg_to_send = '{"tag":"HELO","name":"' + name + '","sx":"' + sx + '"}'
        send(self.ws, msg_to_send)
        counter = 0
        while not authenticated:
            counter += 1
            time.sleep(0.1)
            if counter == 50:
                return False
        self.heartbeatLoopThread = HeartbeatLoopThread(self.ws)
        self.heartbeatLoopThread.start()
        #print('我醒了')
        #send(self.ws, '<PXR v="' + '1' + '" />')
        #send(self.ws, '<Z/>')
        return True
    def logout(self):
        global authenticated
        if not authenticated:
            return
        send(self.ws, '<BYE/>')
        authenticated = False
        self.heartbeatLoopThread.join()
        time.sleep(1)
    def gotoLobby(self, lobby):
        # int -> None
        # 等待，直到收到成功进入lobby的消息 # 不等待 谁调用谁等
        if not authenticated:
            return
        send(self.ws, {'tag' : 'LOBBY', 'id' : lobby})
        #self.lobby = lobby
    def gotoChampionshipLobby(self, lobby):
        # int -> None
        if not authenticated:
            return
        send(self.ws, {'tag' : 'CS', 'lobby' : 'C' + str(lobby).rjust(8, '0')})
    def pxr(self):
        send(self.ws, '<PXR v="' + str(PXR) + '" />')
    def join(self, lobby, rule):
        # int -> int -> None
        # example: lobby=0, rule=17. Will send {"tag":"JOIN","t":"0,17"}
        send(self.ws, {'tag': 'JOIN', 't': str(lobby) + ',' + str(rule)})
    def cancelJoin(self):
        send(self.ws, {'tag': 'JOIN'})
    def gok(self):
        send(self.ws, {'tag': 'GOK'})
    def ready(self):
        # 相当于在对局开始时、小局结束时等点击OK按钮
        send(self.ws, {'tag': 'NEXTREADY'})
    def discard(self, tilecode):
        # 出牌 example: {"tag":"D","p":115}
        send(self.ws, {'tag': 'D', 'p': tilecode})
    def reach(self):
        # 立直(只发声不弃牌)
        send(self.ws, {'tag': 'REACH'})
    def kita(self):
        # 拔北 注意拔北不能选哪张北 服务器拔哪张就是哪张
        send(self.ws, {'tag': 'N', 'type': 10})
    def chi(self, tilecode0, tilecode1):
        # TODO
        send(self.ws, {'tag': 'N', 'type': 3, 'hai0': tilecode0, 'hai1': tilecode1})
    def pon(self, tilecode0, tilecode1):
        # example: {"tag":"N","type":1,"hai0":110,"hai1":111}
        send(self.ws, {'tag': 'N', 'type': 1, 'hai0': tilecode0, 'hai1': tilecode1})
    def daiminkan(self):
        send(self.ws, {'tag': 'N', 'type': 2})
    def ankan(self, tilecode):
        # 暗杠的tilecode的offset应为0
        send(self.ws, {'tag': 'N', 'type': 4, 'hai': tilecode})
    def kakan(self, tilecode):
        send(self.ws, {'tag': 'N', 'type': 5, 'hai': tilecode})
    def ron(self):
        send(self.ws, {'tag': 'N', 'type': 6})
    def tsumo(self):
        #TODO
        send(self.ws, {'tag': 'N', 'type': 7})
    def ninenine(self):
        # 推99
        send(self.ws, {'tag': 'N', 'type': 9})
    def passTile(self):
        # pass被python占用了。。只能换个名字
        send(self.ws, {'tag': 'N'})
    def disconnect(self):
        global voluntarily_close
        voluntarily_close = True
        self.ws.close()
    def registerProcessFunc(self, function):
        self.processFunc = function
    def registerOnCloseFunc(self, function):
        self.onCloseFunc = function

if __name__ == '__main__':
    #global client
    client = TenhouClient()
    client.init()
    # time.sleep(1)
    #client.login('ID052A39F5-E8JJH5fS')
    client.login('NoName')
    lobby = 1717
    client.gotoLobby(lobby)
    while client.lobby != lobby:
        time.sleep(0.1)
    time.sleep(random.randint(15,25))
    client.logout()
    client.disconnect()

