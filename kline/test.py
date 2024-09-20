import requests
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from kliner import KlineService

# 获取所有期货的名称
def get_all_futures():
    response = requests.get('http://127.0.0.1:5626/future/futures')
    return response.json()

# 获取单个期货的K线信息并存储
def fetch_single_kline_data(future_code, ks):
    try:
        # 获取该期货的1分钟K线信息
        kline_info = requests.get(f'http://127.0.0.1:5626/future/kline_1m/{future_code}').json()
        # 使用KlineService存储K线信息
        ks.save_klines(klines=kline_info, prex='future', cycle='1分钟', code=future_code)
        print(f"{future_code} 数据已保存")
    except Exception as e:
        print(f"获取 {future_code} 数据失败: {e}")

# 并发获取所有期货的K线数据1
def fetch_all_kline_data(ks):
    futures_list_pre = get_all_futures()
    futures_list = []
    for future in futures_list_pre:
        futures_list.append(future['symbol'])
    # 使用ThreadPoolExecutor进行并发请求
    with ThreadPoolExecutor(max_workers=800) as executor:
        future_to_code = {executor.submit(fetch_single_kline_data, future_code, ks): future_code for future_code in futures_list}

        for future in as_completed(future_to_code):
            future_code = future_to_code[future]
            try:
                future.result()
            except Exception as exc:
                print(f'{future_code} 生成时出现异常: {exc}')

if __name__ == '__main__':
    ks = KlineService()

    try:
        while True:
            fetch_all_kline_data(ks)
            # 设置更新间隔，这里是1秒
    except KeyboardInterrupt:
        print("程序终止")
