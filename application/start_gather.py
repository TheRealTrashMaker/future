import asyncio
import websockets
import json
from datetime import datetime

# 模拟数据库查询和处理函数
async def query_database():
    # 这里应该是数据库查询和处理的代码
    return [
        {'id': 1, 'code2': 'HKEXHHI2009', 'code': 'HHI', 'zoom_size': 1, 'unit_price': 100},
        {'id': 2, 'code2': 'HKEXHSI2009', 'code': 'HSI', 'zoom_size': 1, 'unit_price': 200},
    ]

# 模拟数据处理函数
async def process_data(data):
    # 这里应该是数据处理的代码
    print(f"Processing data: {data}")
    return {'res': 'ok'}

# 监听持仓单和挂单
async def listen_orders():
    while True:
        start = datetime.now()
        orders = await query_database()
        if orders:
            for order in orders:
                # 这里应该是监听订单的代码
                print(f"Listening to order: {order}")
        print(f"Checked orders in {datetime.now() - start}")
        await asyncio.sleep(3)  # 每3秒检查一次

# 处理连接
async def handle_connection(connection):
    async for message in connection:
        print(f"Received task data: {message}")
        result = await process_data(message)
        await connection.send(json.dumps(result))

# WebSocket 服务端
async def websocket_server():
    async with websockets.serve(handle_connection, "0.0.0.0", 3246):
        await asyncio.Future()  # 运行服务直到被取消

# WebSocket 客户端
async def websocket_client():
    uri = "ws://118.190.243.214:10145/connect/json/2B9E69D98E034A0B806CA60402EE60CD"
    async with websockets.connect(uri) as connection:
        await connection.send("/fields/FS,S1,S1V,B1,B1V,O,YC,NV,H,L,ZF,P,Tick,M,S,C")
        await connection.send("/subrout/CNCF")
        await connection.send("/sub/HKEXHHI2009,HKEXHSI2009,HKEXMHI2009,NYMEXCL2011,COMEXGC2012,COMEXSI2012,COMEXHG2012,NYMEXNG2011,CBOTYM2011,CMENQ2012,CMEES2012,CMEAD2012,CMEGBP2012,CMECD2012,CMEEC,EUREXDAX2012,SGXCN2009,CFFEXIF2010,CFFEXIH2010,CFFEXIC2010")

        while True:
            message = await connection.recv()
            print(f"Received message: {message}")
            # 这里可以发送消息到TaskWorker进行处理
            # 例如：await websocket.send(message)

async def main():
    await asyncio.gather(
        websocket_server(),
        websocket_client(),
        listen_orders()
    )

if __name__ == "__main__":
    asyncio.run(main())