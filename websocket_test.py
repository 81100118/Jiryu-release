import websocket
import json

try:
    import thread
except ImportError:
    import _thread as thread

import time

def on_message(ws, message):
    print('recv ' + message)
    try:
        print(json.loads(message))
    except:
        pass

def on_error(ws, error):
    print('error')
    print(error)

def on_close(ws):
    print("closed")

def on_open(ws):
    def run():
        msg_to_send = '{"tag":"HELO","name":"NoName","sx":"M"}'
        send(ws, msg_to_send)
        for _ in range(3):
            send(ws, '<Z/>')
            send(ws, '<PXR v="' + '1' + '" />')
            time.sleep(10)
        send(ws, '<BYE/>')
        ws.close()
    thread.start_new_thread(run, ())

def send(ws, msg):
    ws.send(msg)
    print('sent ' + msg)


if __name__ == '__main__':
    websocket.enableTrace(True)
    ws = websocket.WebSocketApp('wss://b-ww.mjv.jp', header=['Pragma: no-cache','Cache-Control: no-cache','User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/81.0.4044.138 Safari/537.36','Origin: https://tenhou.net','Accept-Encoding: gzip, deflate, br','Accept-Language: zh-CN,zh;q=0.9,en-US;q=0.8,en;q=0.7,zh-TW;q=0.6,ja;q=0.5','Sec-WebSocket-Extensions: permessage-deflate; client_max_window_bits'], on_message = on_message, on_error= on_error, on_close= on_close)#, suppress_origin = True)
    ws.on_open = on_open
    ws.run_forever(suppress_origin=True)
