import asyncio
import os

import websockets
import json
from kline.kliner import KlineService

def get_all_futures():
    # 获取所有期货基本信息
    with open(os.path.join(os.path.dirname(__file__), "futures.json"), "r", encoding="utf-8") as file:
        futures = json.load(file)
        return_data = []
        for item in futures:
            if item["exchange"] != "cffex":
                return_data.append(item)
        return return_data


def get_tickets(code=None):
    # 获取所有期货其它信息
    ks = KlineService()
    tikcets = ks.load_ticket(code,prex="tf_futures_trade")
    return tikcets


async def send_data(websocket, path):
    # 发送数据

    message = await websocket.recv()
    # 判断是否是指定的消息
    if "bind_tf_futures_trade" in str(message):
        # 循环发送数据
        while True:
                data = {"event": "onready","data": {"ticket":get_tickets()}}
                await websocket.send(json.dumps(data))
                await asyncio.sleep(1)

if __name__ == '__main__':
    # 创建一个WebSocket服务器，监听端口8765
    start_server = websockets.serve(send_data, '0.0.0.0', 8765)

    asyncio.get_event_loop().run_until_complete(start_server)

    asyncio.get_event_loop().run_forever()