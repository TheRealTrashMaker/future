import json
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from kliner import KlineService
import requests


# 获取所有期货的名称
def get_all_futures():
    with open(os.path.join(os.path.dirname(__file__), "futures.json"), "r", encoding="utf-8") as file:
        futures = json.load(file)
        return_data = []
        for item in futures:
            if item["exchange"] != "cffex":
                return_data.append(item)
        return return_data


# 获取单个期货的K线信息并存储
def fetch_single_kline_data(future_code, ks):
    try:
        # 获取该期货的1分钟K线信息
        kline_info = requests.get(f'http://127.0.0.1:5626/future/kline_1m/{future_code}').json()
        # 使用KlineService存储K线信息
        ks.save_klines(klines=kline_info, prex='tf_futures_trade', cycle=1, code=future_code)
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


def get_futures_prices():
    headers = {
        "Accept": "*/*",
        "Accept-Language": "zh-CN,zh;q=0.9",
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "Pragma": "no-cache",
        "Referer": "https://finance.sina.com.cn/futuremarket/",
        "Sec-Fetch-Dest": "script",
        "Sec-Fetch-Mode": "no-cors",
        "Sec-Fetch-Site": "cross-site",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36",
        "sec-ch-ua": "\"Google Chrome\";v=\"129\", \"Not=A?Brand\";v=\"8\", \"Chromium\";v=\"129\"",
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": "\"Windows\""
    }
    futures = get_all_futures()
    # print(futures)
    futures_list_str = ""
    for item in futures:
        futures_list_str = futures_list_str + "nf_" + item["symbol"] + ","
    url = f"https://hq.sinajs.cn/rn={time.time() * 1000}&list={futures_list_str}"
    response = requests.get(url, headers=headers)
    return response.text


def get_all_ticket():
    '''

    :return:

    # return_data = {
    #     'ask' = 0, # 卖一价
    # 'asm' = > 0, # 卖一量
    # 'bid' = > 0, # 买一价
    # 'bim' = > 0, # 买一量
    # 'open' = > 0, # 开盘价
    # 'close' = > 0, # 收盘价
    # 'nv' = > 0, # 最新成交量
    # 'high' = > 0, # 最高价
    # 'low' = > 0, # 最低价
    # 'wave' = > 0, # 涨幅
    # 'price' = > 0, # 当前价
    # 'volume' = > 0, # 交易量
    # 'position' = 0, # 交易量
    # 'digit' = 4,
    # }

    # 返回顺序（郑商 大商 上期 广期 普通期货） 0.名字 1.时分秒 2.开盘价  3.最高价  4.最低价  5.结算价 6.买价   7.卖价    8.最新价  9.不知道 10.昨结     11.买量, 12.卖量,     13.持仓量  14.成交量
    # "                  PTA2501,225959,4850.000,4870.000,4778.000,4798.000,4798.000,4800.000,4798.000,4818.000,4862.000    ,92,       133,    1346345.000,455290

    # 返回顺序（中金 指数期货,国债期货） 0.开盘价     1.最高价      2.最低价    3.最新价     4.成交量   5.不知道        6.持仓量      7.最新价   8.不知道   9.不知道    10.不知道   11.       12.
    #                               ['3197.400', '3197.400', '3173.000', '3185.000', '28818', '91807601.000', '18462.000', '3185.000', '0.000', '3838.400', '2559.200', '0.000', '0.000', '3198.400', '3198.800', '40295.000', '3185.000', '156', '0.000', '0', '0.000', '0', '0.000', '0', '0.000', '0', '3185.200', '88', '0.000', '0', '0.000', '0', '0.000', '0', '0.000', '0', '2024-09-20', '15:00:00', '400', '0', '', '', '', '', '', '', '', '', '3185.773', '沪深300指数期货2409']
    '''
    unclean_futures = get_futures_prices()
    all_futures = get_all_futures()
    return_data = []
    for i in range(len(all_futures)):
        clean_futures = unclean_futures.split("\nvar")[i].split('"')[1].split(",")
        try:
            return_pre_data = {
                "B1": float(clean_futures[6]),
                "B1V": float(clean_futures[12]),
                "S1": float(clean_futures[7]),
                "S1V": float(clean_futures[11]),
                "O": float(clean_futures[2]),
                "YC": float(clean_futures[10]),
                "nv": float(clean_futures[14]),
                "H": float(clean_futures[3]),
                "L": float(clean_futures[4]),
                "wave": float(str(round(((float(clean_futures[8]) - float(clean_futures[10])) / float(clean_futures[10])) * 100, 2))),
                "P": float(clean_futures[5]),
                "volume": float(clean_futures[14]),
                "position": float(clean_futures[14]),
                "digit": 4,
                "code": all_futures[i]["symbol"]
            }
            return_data.append(return_pre_data)
        except:
            # print(unclean_futures.split("\nvar")[i])
            pass
    return return_data

"""
                                    $ticket['ask'] = $symbol['B1'];
                                    $ticket['asm'] = $symbol['B1V'];
                                    $ticket['bid'] = $symbol['S1'];
                                    $ticket['bim'] = $symbol['S1V'];
                                    $ticket['open'] = $symbol['O'];
                                    $ticket['close'] = $symbol['YC'];
                                    $ticket['high'] = $symbol['H'];
                                    $ticket['low'] = $symbol['L'];

                                    $ticket['price'] = $symbol['P'];
                                    $ticket['volume'] = $symbol['B1V']+$symbol['S1V'];
                                    $ticket['position'] = $symbol['HD'];
                                    $ticket['limit_up'] = 0;
                                    $ticket['limit_dn'] = 0;
                                    $ticket['cleaning'] = 0;
                                    $ticket['close_past'] = $symbol['YC'];//昨收
                                    $ticket['position_past'] = $symbol['YJS'];//昨持
                                    $ticket['cleaning_past'] = $symbol['YHD'];//昨结

                                    $ticket['tm'] = $symbol['Tick'];
                                    $ticket['ctm'] = $symbol['Tick'];
                                    $ticket['ctmfmt'] = date('Y-m-d H:i:s', $symbol['Tick']);
                                    $ticket['wave'] = $symbol['ZF'];
                                    $tmpModelList[$symbol['FS']]['ticekt'] = $ticket;"""
def fetch_all_ticket_data(ks):
    try:
        # prex='tf_futures_trade'
        all_tickets = get_all_ticket()
        # 使用KlineService存储K线信息
        for ticket in all_tickets:
            try:
                #, prex='tf_futures_trade'
                ks.save_ticket(ticket=ticket, prex="trade")

            except Exception as e:
                print(f"保存ticket 数据失败: {e}")
        print(f"所有ticket 数据已保存")
    except Exception as e:
        print(f"保存ticket 数据失败: {e}")

if __name__ == '__main__':
    ks = KlineService()
    # print(get_all_ticket())
    try:
        while True:
            fetch_single_kline_data(future_code="PR2507", ks=ks)
            fetch_all_ticket_data(ks)
            time.sleep(1)
            print("正在更新数据...", time.time())
            # 设置更新间隔，这里是1秒
    except KeyboardInterrupt:
        print("程序终止")
