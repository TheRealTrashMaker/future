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



data_prere = {'ask': 80450.0, 'asm': 4.0, 'bid': 80650.0, 'bim': 2.0, 'open': 80700.0, 'close': 81950.0, 'nv': 129.0, 'high': 81450.0, 'low': 79900.0, 'wave': -1.65, 'price': 0.0, 'volume': 129.0, 'position': 129.0, 'digit': 4, 'code': 'LC2508', 'code2': 'LC2508'}
data_PR2507 = {'ask': 6072.0, 'asm': 1.0, 'bid': 6090.0, 'bim': 1.0, 'open': 6114.0, 'close': 6146.0, 'nv': 6.0, 'high': 6114.0, 'low': 6044.0, 'wave': -0.91, 'price': 6080.0, 'volume': 6.0, 'position': 6.0, 'digit': 4, 'code': 'PR2507', 'code2': 'PR2507'}
data_CU2411 = {'ask': 75300.0, 'asm': 8.0, 'bid': 75310.0, 'bim': 11.0, 'open': 75800.0, 'close': 75760.0, 'nv': 41924.0, 'high': 75840.0, 'low': 75100.0, 'wave': -0.59, 'price': 0.0, 'volume': 41924.0, 'position': 41924.0, 'digit': 4, 'code': 'CU2411', 'code2': 'CU2411'}
async def send_data(websocket, path):
    ks = KlineService()
    # 等待接收客户端发送的消息
    message = await websocket.recv()
    # 判断是否是指定的消息
    if "bind_tf_futures_trade" in str(message):
        # 循环发送数据
        # codes = get_all_futures()
        while True:
            # 这里可以替换为你想要发送的数据
            # for i in codes:
                data = {"event": "onready","data": get_tickets()}
                await websocket.send(json.dumps(data))
                await asyncio.sleep(1)
            # await asyncio.sleep(1)  # 每秒发送一次

if __name__ == '__main__':
    # get_tickets()



    start_server = websockets.serve(send_data, '0.0.0.0', 8765)

    asyncio.get_event_loop().run_until_complete(start_server)

    asyncio.get_event_loop().run_forever()