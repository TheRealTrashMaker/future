import asyncio
import os

import websockets
import json
from kline.kliner import KlineService

def get_all_futures():
    with open(os.path.join(os.path.dirname(__file__), "futures.json"), "r", encoding="utf-8") as file:
        futures = json.load(file)
        return_data = []
        for item in futures:
            if item["exchange"] != "cffex":
                return_data.append(item)
        return return_data


def get_tickets(code=None):
    ks = KlineService()
    tikcets = ks.load_ticket(code)
    return tikcets

async def send_data(websocket, path):
    ks = KlineService()
    # 等待接收客户端发送的消息
    message = await websocket.recv()
    # 判断是否是指定的消息
    if "bind_tf_futures_trade" in str(message):
        # 循环发送数据
        codes = get_all_futures()
        while True:
            # 这里可以替换为你想要发送的数据
            for i in codes:
                data = {"event": "ticket", "data": get_tickets(code=i["symbol"])}
                await websocket.send(json.dumps(data))
            await asyncio.sleep(1)  # 每秒发送一次

if __name__ == '__main__':
    # get_tickets()



    start_server = websockets.serve(send_data, '0.0.0.0', 8765)

    asyncio.get_event_loop().run_until_complete(start_server)

    asyncio.get_event_loop().run_forever()