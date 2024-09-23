import json
import os
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import timedelta, datetime
from decimal import Decimal

import requests

from kliner import KlineService

def get_kline_by_minutes(symbol, minutes):
    if minutes not in "1,10,15,30,45,60":
        return {"error":"仅支持分钟1,10,15,30,45,60"}
    headers = {
        "Accept": "*/*",
        "Accept-Language": "zh-CN,zh;q=0.9",
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "Pragma": "no-cache",
        "Referer": f"https://finance.sina.com.cn/futures/quotes/{symbol}.shtml",
        "Sec-Fetch-Dest": "script",
        "Sec-Fetch-Mode": "no-cors",
        "Sec-Fetch-Site": "same-site",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
        "sec-ch-ua": "\"Chromium\";v=\"128\", \"Not;A=Brand\";v=\"24\", \"Google Chrome\";v=\"128\"",
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": "\"Windows\""
    }
    url = f"https://stock2.finance.sina.com.cn/futures/api/jsonp.php/var%20_{symbol}_{minutes}_{time.time() * 1000}=/InnerFuturesNewService.getFewMinLine"
    params = {
        "symbol": symbol,
        "type": minutes
    }
    response = requests.get(url, headers=headers, params=params)
    try:
        unclean_data = re.findall("\((.*)\)", response.text)[0]
        return_data = []
        for item in json.loads(unclean_data):
            date_time_obj = datetime.strptime(item["d"], '%Y-%m-%d %H:%M:%S')
            # 将datetime对象转换为十位数时间戳
            timestamp = int(date_time_obj.timestamp())
            return_data.append({
                "open": float(item["o"]),
                "close": item["c"],
                "high": item["h"],
                "low": item["l"],
                "ctm": str(timestamp),
                'ctmfmt': datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S'),
                "volume": item["v"],
                'wave': 0
            })
        return return_data
    except:
        return None


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
def fetch_single_kline_data(kline_type,future_code, ks):
    if kline_type not in "1,10,15,30,45,60":
        return {"error":"仅支持分钟1,10,15,30,45,60"}
    try:
        # 获取该期货的1分钟K线信息
        kline_info = get_kline_by_minutes(symbol=future_code, minutes=kline_type)
        # 使用KlineService存储K线信息
        ks.save_klines(klines=kline_info, prex='tf_futures_trade', cycle=kline_type, code=future_code)
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
    futures_list_str = ""
    for item in futures:
        futures_list_str = futures_list_str + "nf_" + item["symbol"] + ","
    url = f"https://hq.sinajs.cn/rn={time.time() * 1000}&list={futures_list_str}"
    response = requests.get(url, headers=headers)
    return response.text


def convert_timedelta_to_serializable(data):
    if isinstance(data, dict):
        return {key: convert_timedelta_to_serializable(value) for key, value in data.items()}
    elif isinstance(data, list):
        return [convert_timedelta_to_serializable(item) for item in data]
    elif isinstance(data, timedelta):
        return data.total_seconds()  # 转换为秒数
    else:
        return data


# 递归函数遍历字典或列表，将 Decimal 转换为 float
def convert_decimal_to_float(data):
    if isinstance(data, dict):
        # 遍历字典中的每一对键值
        return {key: convert_decimal_to_float(value) for key, value in data.items()}
    elif isinstance(data, list):
        # 如果是列表，遍历列表中的每一项
        return [convert_decimal_to_float(item) for item in data]
    elif isinstance(data, Decimal):
        # 如果是 Decimal 类型，转换为 float
        return float(data)
    else:
        # 如果是其他类型，保持不变
        return data


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
    # "                                   PTA2501,225959,4850.000,4870.000,4778.000,4798.000,4798.000,4800.000,4798.000,4818.000,4862.000    ,92,       133,    1346345.000,455290

    # 返回顺序（中金 指数期货,国债期货） 0.开盘价     1.最高价      2.最低价    3.最新价     4.成交量   5.不知道        6.持仓量      7.最新价   8.不知道   9.不知道    10.不知道   11.       12.
    #                               ['3197.400', '3197.400', '3173.000', '3185.000', '28818', '91807601.000', '18462.000', '3185.000', '0.000', '3838.400', '2559.200', '0.000', '0.000', '3198.400', '3198.800', '40295.000', '3185.000', '156', '0.000', '0', '0.000', '0', '0.000', '0', '0.000', '0', '3185.200', '88', '0.000', '0', '0.000', '0', '0.000', '0', '0.000', '0', '2024-09-20', '15:00:00', '400', '0', '', '', '', '', '', '', '', '', '3185.773', '沪深300指数期货2409']
    '''
    unclean_futures = get_futures_prices()
    all_futures = get_all_futures()
    # mysqlconn = mysql_conn()
    return_data = []
    for i in range(len(all_futures)):
        clean_futures = unclean_futures.split("\nvar")[i].split('"')[1].split(",")


        try:
            timer_date = unclean_futures.split("\nvar")[i].split('"')[1].split(",,,,,,,,,")[0].split(",")[-2]
            timer_time = clean_futures[1]
            fmt_time = f"{timer_date} {timer_time[0:2]}:{timer_time[2:4]}:{timer_time[4:6]}"
            date_time = datetime.strptime(fmt_time, "%Y-%m-%d %H:%M:%S")
            timestamp = int(time.mktime(date_time.timetuple()))
            # tickets = convert_timedelta_to_serializable(convert_decimal_to_float(mysqlconn.get_single_symbol_info(all_futures[i]["symbol"])))
            return_pre_data = {
                "ask": float(clean_futures[6]),
                "asm": float(clean_futures[12]),
                "bid": float(clean_futures[7]),
                "bim": float(clean_futures[11]),
                "open": float(clean_futures[2]),
                "close": float(clean_futures[10]),
                "nv": float(clean_futures[14]),
                "high": float(clean_futures[3]),
                "low": float(clean_futures[4]),
                "wave": float(str(round(((float(clean_futures[8]) - float(clean_futures[10])) / float(clean_futures[10])) * 100, 2))),
                "price": float(clean_futures[8]),
                "volume": float(clean_futures[14]),
                "position": float(clean_futures[9]),
                "digit": 4,
                "code": all_futures[i]["symbol"],
                "code2": all_futures[i]["symbol"],
                "ctm": f"{timestamp}",
                "ctmfmt": fmt_time
            }
            # tickets["ticket"] = return_pre_data
            return_data.append(return_pre_data)
        except:
            # print(unclean_futures.split("\nvar")[i])
            pass

    return return_data


"""
$ticket['ask'] = $symbol['B1'];
                                    $ticket['asm'] = $symbol['B1V'];
                                    $ticket['ask2'] = $symbol['B2'];
                                    $ticket['asm2'] = $symbol['B2V'];
                                    $ticket['ask3'] = $symbol['B3'];
                                    $ticket['asm3'] = $symbol['B3V'];
                                    $ticket['ask4'] = $symbol['B4'];
                                    $ticket['asm4'] = $symbol['B4V'];
                                    $ticket['ask5'] = $symbol['B5'];
                                    $ticket['asm5'] = $symbol['B5V'];
                                    $ticket['bid'] = $symbol['S1'];
                                    $ticket['bim'] = $symbol['S1V'];
                                    $ticket['bid2'] = $symbol['S2'];
                                    $ticket['bim2'] = $symbol['S2V'];
                                    $ticket['bid3'] = $symbol['S3'];
                                    $ticket['bim3'] = $symbol['S3V'];
                                    $ticket['bid4'] = $symbol['S4'];
                                    $ticket['bim4'] = $symbol['S4V'];
                                    $ticket['bid5'] = $symbol['S5'];
                                    $ticket['bim5'] = $symbol['S5V'];
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
        all_tickets = get_all_ticket()
        # 使用KlineService存储K线信息
        for ticket in all_tickets:
            try:
                # , prex='tf_futures_trade'
                ks.save_ticket(ticket=ticket, prex="tf_futures_trade")

            except Exception as e:
                print(f"保存ticket 数据失败: {e}")
        print(f"所有ticket 数据已保存")
    except Exception as e:
        print(f"保存ticket 数据失败: {e}")


def save_kline_data_by_redis(prex='tf_futures_trade', ks=None):
    keys = ks.match_search_keys()
    for key in keys:
        print(key)
        try:
            kline_type = key.split("_")[3]
        except:
            return {"error":"该redis数据的键名不符合规范"}
        try:
            future_code = key.split("_")[2]

            fetch_single_kline_data(kline_type=kline_type,future_code=future_code, ks=ks)

        except Exception as e:
            print(f"保存kline 数据失败: {e}")
        print(f"保存kline 数据成功")
        time.sleep(1)

def write_ready_data(ks):

    value = [
    {
        "close": "4804.000",
        "ctm": "1726641540",
        "ctmfmt": "2024-09-18 14:39:00",
        "high": "4804.000",
        "low": "4804.000",
        "open": "4804.000",
        "volume": "104",
        "wave": 0
    },
    {
        "close": "4804.000",
        "ctm": "1726641600",
        "ctmfmt": "2024-09-18 14:40:00",
        "high": "4806.000",
        "low": "4802.000",
        "open": "4806.000",
        "volume": "780",
        "wave": 0
    },
    {
        "close": "4802.000",
        "ctm": "1726641660",
        "ctmfmt": "2024-09-18 14:41:00",
        "high": "4804.000",
        "low": "4802.000",
        "open": "4804.000",
        "volume": "236",
        "wave": 0
    },
    {
        "close": "4810.000",
        "ctm": "1726641720",
        "ctmfmt": "2024-09-18 14:42:00",
        "high": "4810.000",
        "low": "4804.000",
        "open": "4804.000",
        "volume": "2223",
        "wave": 0
    },
    {
        "close": "4802.000",
        "ctm": "1726641780",
        "ctmfmt": "2024-09-18 14:43:00",
        "high": "4804.000",
        "low": "4800.000",
        "open": "4802.000",
        "volume": "476",
        "wave": 0
    },
    {
        "close": "4804.000",
        "ctm": "1726641840",
        "ctmfmt": "2024-09-18 14:44:00",
        "high": "4806.000",
        "low": "4802.000",
        "open": "4802.000",
        "volume": "1376",
        "wave": 0
    },
    {
        "close": "4796.000",
        "ctm": "1726641900",
        "ctmfmt": "2024-09-18 14:45:00",
        "high": "4800.000",
        "low": "4796.000",
        "open": "4800.000",
        "volume": "1330",
        "wave": 0
    },
    {
        "close": "4794.000",
        "ctm": "1726641960",
        "ctmfmt": "2024-09-18 14:46:00",
        "high": "4798.000",
        "low": "4794.000",
        "open": "4798.000",
        "volume": "2691",
        "wave": 0
    },
    {
        "close": "4794.000",
        "ctm": "1726642020",
        "ctmfmt": "2024-09-18 14:47:00",
        "high": "4794.000",
        "low": "4794.000",
        "open": "4794.000",
        "volume": "3",
        "wave": 0
    },
    {
        "close": "4790.000",
        "ctm": "1726642080",
        "ctmfmt": "2024-09-18 14:48:00",
        "high": "4794.000",
        "low": "4790.000",
        "open": "4794.000",
        "volume": "1198",
        "wave": 0
    },
    {
        "close": "4788.000",
        "ctm": "1726642140",
        "ctmfmt": "2024-09-18 14:49:00",
        "high": "4790.000",
        "low": "4788.000",
        "open": "4788.000",
        "volume": "538",
        "wave": 0
    },
    {
        "close": "4788.000",
        "ctm": "1726642200",
        "ctmfmt": "2024-09-18 14:50:00",
        "high": "4788.000",
        "low": "4788.000",
        "open": "4788.000",
        "volume": "6",
        "wave": 0
    },
    {
        "close": "4784.000",
        "ctm": "1726642260",
        "ctmfmt": "2024-09-18 14:51:00",
        "high": "4788.000",
        "low": "4784.000",
        "open": "4788.000",
        "volume": "1265",
        "wave": 0
    },
    {
        "close": "4776.000",
        "ctm": "1726642320",
        "ctmfmt": "2024-09-18 14:52:00",
        "high": "4782.000",
        "low": "4776.000",
        "open": "4782.000",
        "volume": "4313",
        "wave": 0
    },
    {
        "close": "4762.000",
        "ctm": "1726642380",
        "ctmfmt": "2024-09-18 14:53:00",
        "high": "4764.000",
        "low": "4762.000",
        "open": "4764.000",
        "volume": "4317",
        "wave": 0
    },
    {
        "close": "4756.000",
        "ctm": "1726642440",
        "ctmfmt": "2024-09-18 14:54:00",
        "high": "4760.000",
        "low": "4756.000",
        "open": "4760.000",
        "volume": "2012",
        "wave": 0
    },
    {
        "close": "4760.000",
        "ctm": "1726642500",
        "ctmfmt": "2024-09-18 14:55:00",
        "high": "4764.000",
        "low": "4754.000",
        "open": "4756.000",
        "volume": "5550",
        "wave": 0
    },
    {
        "close": "4766.000",
        "ctm": "1726642560",
        "ctmfmt": "2024-09-18 14:56:00",
        "high": "4766.000",
        "low": "4764.000",
        "open": "4766.000",
        "volume": "437",
        "wave": 0
    },
    {
        "close": "4766.000",
        "ctm": "1726642620",
        "ctmfmt": "2024-09-18 14:57:00",
        "high": "4770.000",
        "low": "4764.000",
        "open": "4766.000",
        "volume": "5888",
        "wave": 0
    },
    {
        "close": "4768.000",
        "ctm": "1726642680",
        "ctmfmt": "2024-09-18 14:58:00",
        "high": "4768.000",
        "low": "4764.000",
        "open": "4764.000",
        "volume": "3479",
        "wave": 0
    },
    {
        "close": "4768.000",
        "ctm": "1726642740",
        "ctmfmt": "2024-09-18 14:59:00",
        "high": "4770.000",
        "low": "4764.000",
        "open": "4770.000",
        "volume": "9752",
        "wave": 0
    },
    {
        "close": "4766.000",
        "ctm": "1726642800",
        "ctmfmt": "2024-09-18 15:00:00",
        "high": "4768.000",
        "low": "4754.000",
        "open": "4766.000",
        "volume": "12258",
        "wave": 0
    },
    {
        "close": "4786.000",
        "ctm": "1726664460",
        "ctmfmt": "2024-09-18 21:01:00",
        "high": "4788.000",
        "low": "4774.000",
        "open": "4774.000",
        "volume": "26237",
        "wave": 0
    },
    {
        "close": "4784.000",
        "ctm": "1726664520",
        "ctmfmt": "2024-09-18 21:02:00",
        "high": "4792.000",
        "low": "4784.000",
        "open": "4786.000",
        "volume": "11067",
        "wave": 0
    },
    {
        "close": "4774.000",
        "ctm": "1726664580",
        "ctmfmt": "2024-09-18 21:03:00",
        "high": "4786.000",
        "low": "4772.000",
        "open": "4784.000",
        "volume": "8400",
        "wave": 0
    },
    {
        "close": "4774.000",
        "ctm": "1726664640",
        "ctmfmt": "2024-09-18 21:04:00",
        "high": "4778.000",
        "low": "4772.000",
        "open": "4772.000",
        "volume": "3913",
        "wave": 0
    },
    {
        "close": "4774.000",
        "ctm": "1726664700",
        "ctmfmt": "2024-09-18 21:05:00",
        "high": "4780.000",
        "low": "4772.000",
        "open": "4776.000",
        "volume": "4801",
        "wave": 0
    },
    {
        "close": "4774.000",
        "ctm": "1726664760",
        "ctmfmt": "2024-09-18 21:06:00",
        "high": "4782.000",
        "low": "4772.000",
        "open": "4772.000",
        "volume": "5627",
        "wave": 0
    },
    {
        "close": "4770.000",
        "ctm": "1726664820",
        "ctmfmt": "2024-09-18 21:07:00",
        "high": "4776.000",
        "low": "4768.000",
        "open": "4774.000",
        "volume": "6813",
        "wave": 0
    },
    {
        "close": "4772.000",
        "ctm": "1726664880",
        "ctmfmt": "2024-09-18 21:08:00",
        "high": "4774.000",
        "low": "4770.000",
        "open": "4770.000",
        "volume": "2975",
        "wave": 0
    },
    {
        "close": "4766.000",
        "ctm": "1726664940",
        "ctmfmt": "2024-09-18 21:09:00",
        "high": "4772.000",
        "low": "4766.000",
        "open": "4772.000",
        "volume": "6129",
        "wave": 0
    },
    {
        "close": "4766.000",
        "ctm": "1726665000",
        "ctmfmt": "2024-09-18 21:10:00",
        "high": "4768.000",
        "low": "4762.000",
        "open": "4766.000",
        "volume": "4708",
        "wave": 0
    },
    {
        "close": "4760.000",
        "ctm": "1726665060",
        "ctmfmt": "2024-09-18 21:11:00",
        "high": "4768.000",
        "low": "4760.000",
        "open": "4766.000",
        "volume": "5522",
        "wave": 0
    },
    {
        "close": "4762.000",
        "ctm": "1726665120",
        "ctmfmt": "2024-09-18 21:12:00",
        "high": "4766.000",
        "low": "4758.000",
        "open": "4760.000",
        "volume": "6419",
        "wave": 0
    },
    {
        "close": "4762.000",
        "ctm": "1726665180",
        "ctmfmt": "2024-09-18 21:13:00",
        "high": "4762.000",
        "low": "4758.000",
        "open": "4762.000",
        "volume": "4876",
        "wave": 0
    },
    {
        "close": "4766.000",
        "ctm": "1726665240",
        "ctmfmt": "2024-09-18 21:14:00",
        "high": "4770.000",
        "low": "4762.000",
        "open": "4762.000",
        "volume": "4594",
        "wave": 0
    },
    {
        "close": "4760.000",
        "ctm": "1726665300",
        "ctmfmt": "2024-09-18 21:15:00",
        "high": "4766.000",
        "low": "4758.000",
        "open": "4766.000",
        "volume": "4409",
        "wave": 0
    },
    {
        "close": "4760.000",
        "ctm": "1726665360",
        "ctmfmt": "2024-09-18 21:16:00",
        "high": "4764.000",
        "low": "4756.000",
        "open": "4760.000",
        "volume": "4599",
        "wave": 0
    },
    {
        "close": "4768.000",
        "ctm": "1726665420",
        "ctmfmt": "2024-09-18 21:17:00",
        "high": "4768.000",
        "low": "4760.000",
        "open": "4760.000",
        "volume": "5053",
        "wave": 0
    },
    {
        "close": "4780.000",
        "ctm": "1726665480",
        "ctmfmt": "2024-09-18 21:18:00",
        "high": "4782.000",
        "low": "4768.000",
        "open": "4768.000",
        "volume": "7048",
        "wave": 0
    },
    {
        "close": "4778.000",
        "ctm": "1726665540",
        "ctmfmt": "2024-09-18 21:19:00",
        "high": "4780.000",
        "low": "4774.000",
        "open": "4778.000",
        "volume": "4627",
        "wave": 0
    },
    {
        "close": "4768.000",
        "ctm": "1726665600",
        "ctmfmt": "2024-09-18 21:20:00",
        "high": "4778.000",
        "low": "4768.000",
        "open": "4776.000",
        "volume": "4387",
        "wave": 0
    },
    {
        "close": "4766.000",
        "ctm": "1726665660",
        "ctmfmt": "2024-09-18 21:21:00",
        "high": "4770.000",
        "low": "4766.000",
        "open": "4768.000",
        "volume": "2983",
        "wave": 0
    },
    {
        "close": "4762.000",
        "ctm": "1726665720",
        "ctmfmt": "2024-09-18 21:22:00",
        "high": "4766.000",
        "low": "4760.000",
        "open": "4766.000",
        "volume": "4378",
        "wave": 0
    },
    {
        "close": "4762.000",
        "ctm": "1726665780",
        "ctmfmt": "2024-09-18 21:23:00",
        "high": "4764.000",
        "low": "4758.000",
        "open": "4762.000",
        "volume": "4105",
        "wave": 0
    },
    {
        "close": "4756.000",
        "ctm": "1726665840",
        "ctmfmt": "2024-09-18 21:24:00",
        "high": "4762.000",
        "low": "4756.000",
        "open": "4762.000",
        "volume": "155882",
        "wave": 0
    },
    {
        "close": "4756.000",
        "ctm": "1726665900",
        "ctmfmt": "2024-09-18 21:25:00",
        "high": "4760.000",
        "low": "4750.000",
        "open": "4756.000",
        "volume": "8957",
        "wave": 0
    },
    {
        "close": "4742.000",
        "ctm": "1726665960",
        "ctmfmt": "2024-09-18 21:26:00",
        "high": "4754.000",
        "low": "4742.000",
        "open": "4754.000",
        "volume": "12123",
        "wave": 0
    },
    {
        "close": "4746.000",
        "ctm": "1726666020",
        "ctmfmt": "2024-09-18 21:27:00",
        "high": "4748.000",
        "low": "4742.000",
        "open": "4742.000",
        "volume": "7861",
        "wave": 0
    },
    {
        "close": "4734.000",
        "ctm": "1726666080",
        "ctmfmt": "2024-09-18 21:28:00",
        "high": "4746.000",
        "low": "4734.000",
        "open": "4746.000",
        "volume": "8913",
        "wave": 0
    },
    {
        "close": "4734.000",
        "ctm": "1726666140",
        "ctmfmt": "2024-09-18 21:29:00",
        "high": "4736.000",
        "low": "4732.000",
        "open": "4736.000",
        "volume": "5799",
        "wave": 0
    },
    {
        "close": "4732.000",
        "ctm": "1726666200",
        "ctmfmt": "2024-09-18 21:30:00",
        "high": "4736.000",
        "low": "4728.000",
        "open": "4732.000",
        "volume": "8629",
        "wave": 0
    },
    {
        "close": "4734.000",
        "ctm": "1726666260",
        "ctmfmt": "2024-09-18 21:31:00",
        "high": "4738.000",
        "low": "4730.000",
        "open": "4732.000",
        "volume": "5960",
        "wave": 0
    },
    {
        "close": "4726.000",
        "ctm": "1726666320",
        "ctmfmt": "2024-09-18 21:32:00",
        "high": "4734.000",
        "low": "4722.000",
        "open": "4734.000",
        "volume": "5743",
        "wave": 0
    },
    {
        "close": "4722.000",
        "ctm": "1726666380",
        "ctmfmt": "2024-09-18 21:33:00",
        "high": "4730.000",
        "low": "4722.000",
        "open": "4726.000",
        "volume": "6944",
        "wave": 0
    },
    {
        "close": "4724.000",
        "ctm": "1726666440",
        "ctmfmt": "2024-09-18 21:34:00",
        "high": "4726.000",
        "low": "4718.000",
        "open": "4722.000",
        "volume": "13031",
        "wave": 0
    },
    {
        "close": "4722.000",
        "ctm": "1726666500",
        "ctmfmt": "2024-09-18 21:35:00",
        "high": "4728.000",
        "low": "4722.000",
        "open": "4722.000",
        "volume": "6173",
        "wave": 0
    },
    {
        "close": "4720.000",
        "ctm": "1726666560",
        "ctmfmt": "2024-09-18 21:36:00",
        "high": "4724.000",
        "low": "4716.000",
        "open": "4722.000",
        "volume": "6965",
        "wave": 0
    },
    {
        "close": "4718.000",
        "ctm": "1726666620",
        "ctmfmt": "2024-09-18 21:37:00",
        "high": "4722.000",
        "low": "4716.000",
        "open": "4722.000",
        "volume": "2740",
        "wave": 0
    },
    {
        "close": "4728.000",
        "ctm": "1726666680",
        "ctmfmt": "2024-09-18 21:38:00",
        "high": "4730.000",
        "low": "4720.000",
        "open": "4720.000",
        "volume": "6944",
        "wave": 0
    },
    {
        "close": "4726.000",
        "ctm": "1726666740",
        "ctmfmt": "2024-09-18 21:39:00",
        "high": "4730.000",
        "low": "4722.000",
        "open": "4728.000",
        "volume": "3438",
        "wave": 0
    },
    {
        "close": "4724.000",
        "ctm": "1726666800",
        "ctmfmt": "2024-09-18 21:40:00",
        "high": "4728.000",
        "low": "4722.000",
        "open": "4724.000",
        "volume": "2172",
        "wave": 0
    },
    {
        "close": "4720.000",
        "ctm": "1726666860",
        "ctmfmt": "2024-09-18 21:41:00",
        "high": "4730.000",
        "low": "4720.000",
        "open": "4724.000",
        "volume": "3693",
        "wave": 0
    },
    {
        "close": "4720.000",
        "ctm": "1726666920",
        "ctmfmt": "2024-09-18 21:42:00",
        "high": "4724.000",
        "low": "4718.000",
        "open": "4720.000",
        "volume": "4113",
        "wave": 0
    },
    {
        "close": "4728.000",
        "ctm": "1726666980",
        "ctmfmt": "2024-09-18 21:43:00",
        "high": "4728.000",
        "low": "4720.000",
        "open": "4720.000",
        "volume": "1451",
        "wave": 0
    },
    {
        "close": "4724.000",
        "ctm": "1726667040",
        "ctmfmt": "2024-09-18 21:44:00",
        "high": "4728.000",
        "low": "4720.000",
        "open": "4726.000",
        "volume": "2427",
        "wave": 0
    },
    {
        "close": "4728.000",
        "ctm": "1726667100",
        "ctmfmt": "2024-09-18 21:45:00",
        "high": "4728.000",
        "low": "4720.000",
        "open": "4724.000",
        "volume": "3967",
        "wave": 0
    },
    {
        "close": "4726.000",
        "ctm": "1726667160",
        "ctmfmt": "2024-09-18 21:46:00",
        "high": "4728.000",
        "low": "4722.000",
        "open": "4726.000",
        "volume": "2979",
        "wave": 0
    },
    {
        "close": "4730.000",
        "ctm": "1726667220",
        "ctmfmt": "2024-09-18 21:47:00",
        "high": "4730.000",
        "low": "4722.000",
        "open": "4726.000",
        "volume": "2660",
        "wave": 0
    },
    {
        "close": "4734.000",
        "ctm": "1726667280",
        "ctmfmt": "2024-09-18 21:48:00",
        "high": "4738.000",
        "low": "4728.000",
        "open": "4728.000",
        "volume": "7816",
        "wave": 0
    },
    {
        "close": "4728.000",
        "ctm": "1726667340",
        "ctmfmt": "2024-09-18 21:49:00",
        "high": "4736.000",
        "low": "4728.000",
        "open": "4732.000",
        "volume": "5555",
        "wave": 0
    },
    {
        "close": "4732.000",
        "ctm": "1726667400",
        "ctmfmt": "2024-09-18 21:50:00",
        "high": "4732.000",
        "low": "4726.000",
        "open": "4730.000",
        "volume": "3460",
        "wave": 0
    },
    {
        "close": "4730.000",
        "ctm": "1726667460",
        "ctmfmt": "2024-09-18 21:51:00",
        "high": "4730.000",
        "low": "4724.000",
        "open": "4730.000",
        "volume": "4127",
        "wave": 0
    },
    {
        "close": "4730.000",
        "ctm": "1726667520",
        "ctmfmt": "2024-09-18 21:52:00",
        "high": "4732.000",
        "low": "4730.000",
        "open": "4732.000",
        "volume": "1281",
        "wave": 0
    },
    {
        "close": "4722.000",
        "ctm": "1726667580",
        "ctmfmt": "2024-09-18 21:53:00",
        "high": "4728.000",
        "low": "4720.000",
        "open": "4728.000",
        "volume": "3682",
        "wave": 0
    },
    {
        "close": "4716.000",
        "ctm": "1726667640",
        "ctmfmt": "2024-09-18 21:54:00",
        "high": "4724.000",
        "low": "4716.000",
        "open": "4720.000",
        "volume": "5162",
        "wave": 0
    },
    {
        "close": "4722.000",
        "ctm": "1726667700",
        "ctmfmt": "2024-09-18 21:55:00",
        "high": "4722.000",
        "low": "4716.000",
        "open": "4718.000",
        "volume": "3596",
        "wave": 0
    },
    {
        "close": "4716.000",
        "ctm": "1726667760",
        "ctmfmt": "2024-09-18 21:56:00",
        "high": "4720.000",
        "low": "4714.000",
        "open": "4720.000",
        "volume": "6484",
        "wave": 0
    },
    {
        "close": "4718.000",
        "ctm": "1726667820",
        "ctmfmt": "2024-09-18 21:57:00",
        "high": "4718.000",
        "low": "4712.000",
        "open": "4716.000",
        "volume": "2856",
        "wave": 0
    },
    {
        "close": "4720.000",
        "ctm": "1726667880",
        "ctmfmt": "2024-09-18 21:58:00",
        "high": "4722.000",
        "low": "4716.000",
        "open": "4718.000",
        "volume": "3042",
        "wave": 0
    },
    {
        "close": "4718.000",
        "ctm": "1726667940",
        "ctmfmt": "2024-09-18 21:59:00",
        "high": "4726.000",
        "low": "4714.000",
        "open": "4722.000",
        "volume": "4876",
        "wave": 0
    },
    {
        "close": "4716.000",
        "ctm": "1726668000",
        "ctmfmt": "2024-09-18 22:00:00",
        "high": "4718.000",
        "low": "4714.000",
        "open": "4716.000",
        "volume": "5721",
        "wave": 0
    },
    {
        "close": "4712.000",
        "ctm": "1726668060",
        "ctmfmt": "2024-09-18 22:01:00",
        "high": "4718.000",
        "low": "4712.000",
        "open": "4716.000",
        "volume": "7053",
        "wave": 0
    },
    {
        "close": "4716.000",
        "ctm": "1726668120",
        "ctmfmt": "2024-09-18 22:02:00",
        "high": "4718.000",
        "low": "4708.000",
        "open": "4712.000",
        "volume": "13257",
        "wave": 0
    },
    {
        "close": "4720.000",
        "ctm": "1726668180",
        "ctmfmt": "2024-09-18 22:03:00",
        "high": "4724.000",
        "low": "4716.000",
        "open": "4718.000",
        "volume": "6514",
        "wave": 0
    },
    {
        "close": "4720.000",
        "ctm": "1726668240",
        "ctmfmt": "2024-09-18 22:04:00",
        "high": "4720.000",
        "low": "4716.000",
        "open": "4720.000",
        "volume": "1885",
        "wave": 0
    },
    {
        "close": "4722.000",
        "ctm": "1726668300",
        "ctmfmt": "2024-09-18 22:05:00",
        "high": "4722.000",
        "low": "4718.000",
        "open": "4718.000",
        "volume": "1240",
        "wave": 0
    },
    {
        "close": "4720.000",
        "ctm": "1726668360",
        "ctmfmt": "2024-09-18 22:06:00",
        "high": "4724.000",
        "low": "4718.000",
        "open": "4720.000",
        "volume": "1669",
        "wave": 0
    },
    {
        "close": "4718.000",
        "ctm": "1726668420",
        "ctmfmt": "2024-09-18 22:07:00",
        "high": "4722.000",
        "low": "4716.000",
        "open": "4720.000",
        "volume": "1967",
        "wave": 0
    },
    {
        "close": "4716.000",
        "ctm": "1726668480",
        "ctmfmt": "2024-09-18 22:08:00",
        "high": "4720.000",
        "low": "4714.000",
        "open": "4718.000",
        "volume": "1953",
        "wave": 0
    },
    {
        "close": "4726.000",
        "ctm": "1726668540",
        "ctmfmt": "2024-09-18 22:09:00",
        "high": "4726.000",
        "low": "4716.000",
        "open": "4716.000",
        "volume": "3081",
        "wave": 0
    },
    {
        "close": "4732.000",
        "ctm": "1726668600",
        "ctmfmt": "2024-09-18 22:10:00",
        "high": "4732.000",
        "low": "4726.000",
        "open": "4726.000",
        "volume": "6140",
        "wave": 0
    },
    {
        "close": "4742.000",
        "ctm": "1726668660",
        "ctmfmt": "2024-09-18 22:11:00",
        "high": "4742.000",
        "low": "4732.000",
        "open": "4732.000",
        "volume": "10459",
        "wave": 0
    },
    {
        "close": "4748.000",
        "ctm": "1726668720",
        "ctmfmt": "2024-09-18 22:12:00",
        "high": "4752.000",
        "low": "4740.000",
        "open": "4742.000",
        "volume": "9713",
        "wave": 0
    },
    {
        "close": "4752.000",
        "ctm": "1726668780",
        "ctmfmt": "2024-09-18 22:13:00",
        "high": "4754.000",
        "low": "4748.000",
        "open": "4748.000",
        "volume": "7159",
        "wave": 0
    },
    {
        "close": "4748.000",
        "ctm": "1726668840",
        "ctmfmt": "2024-09-18 22:14:00",
        "high": "4752.000",
        "low": "4746.000",
        "open": "4750.000",
        "volume": "6364",
        "wave": 0
    },
    {
        "close": "4752.000",
        "ctm": "1726668900",
        "ctmfmt": "2024-09-18 22:15:00",
        "high": "4752.000",
        "low": "4746.000",
        "open": "4748.000",
        "volume": "3675",
        "wave": 0
    },
    {
        "close": "4754.000",
        "ctm": "1726668960",
        "ctmfmt": "2024-09-18 22:16:00",
        "high": "4756.000",
        "low": "4748.000",
        "open": "4750.000",
        "volume": "10148",
        "wave": 0
    },
    {
        "close": "4750.000",
        "ctm": "1726669020",
        "ctmfmt": "2024-09-18 22:17:00",
        "high": "4758.000",
        "low": "4750.000",
        "open": "4754.000",
        "volume": "5529",
        "wave": 0
    },
    {
        "close": "4756.000",
        "ctm": "1726669080",
        "ctmfmt": "2024-09-18 22:18:00",
        "high": "4758.000",
        "low": "4750.000",
        "open": "4750.000",
        "volume": "4477",
        "wave": 0
    },
    {
        "close": "4758.000",
        "ctm": "1726669140",
        "ctmfmt": "2024-09-18 22:19:00",
        "high": "4758.000",
        "low": "4754.000",
        "open": "4756.000",
        "volume": "3394",
        "wave": 0
    },
    {
        "close": "4752.000",
        "ctm": "1726669200",
        "ctmfmt": "2024-09-18 22:20:00",
        "high": "4758.000",
        "low": "4750.000",
        "open": "4756.000",
        "volume": "2170",
        "wave": 0
    },
    {
        "close": "4742.000",
        "ctm": "1726669260",
        "ctmfmt": "2024-09-18 22:21:00",
        "high": "4752.000",
        "low": "4742.000",
        "open": "4752.000",
        "volume": "5972",
        "wave": 0
    },
    {
        "close": "4740.000",
        "ctm": "1726669320",
        "ctmfmt": "2024-09-18 22:22:00",
        "high": "4744.000",
        "low": "4738.000",
        "open": "4742.000",
        "volume": "4524",
        "wave": 0
    },
    {
        "close": "4738.000",
        "ctm": "1726669380",
        "ctmfmt": "2024-09-18 22:23:00",
        "high": "4742.000",
        "low": "4736.000",
        "open": "4742.000",
        "volume": "1502",
        "wave": 0
    },
    {
        "close": "4738.000",
        "ctm": "1726669440",
        "ctmfmt": "2024-09-18 22:24:00",
        "high": "4742.000",
        "low": "4734.000",
        "open": "4736.000",
        "volume": "3538",
        "wave": 0
    },
    {
        "close": "4738.000",
        "ctm": "1726669500",
        "ctmfmt": "2024-09-18 22:25:00",
        "high": "4740.000",
        "low": "4736.000",
        "open": "4738.000",
        "volume": "1422",
        "wave": 0
    },
    {
        "close": "4746.000",
        "ctm": "1726669560",
        "ctmfmt": "2024-09-18 22:26:00",
        "high": "4748.000",
        "low": "4736.000",
        "open": "4738.000",
        "volume": "7165",
        "wave": 0
    },
    {
        "close": "4746.000",
        "ctm": "1726669620",
        "ctmfmt": "2024-09-18 22:27:00",
        "high": "4746.000",
        "low": "4742.000",
        "open": "4746.000",
        "volume": "1992",
        "wave": 0
    },
    {
        "close": "4746.000",
        "ctm": "1726669680",
        "ctmfmt": "2024-09-18 22:28:00",
        "high": "4748.000",
        "low": "4744.000",
        "open": "4746.000",
        "volume": "1502",
        "wave": 0
    },
    {
        "close": "4746.000",
        "ctm": "1726669740",
        "ctmfmt": "2024-09-18 22:29:00",
        "high": "4752.000",
        "low": "4744.000",
        "open": "4746.000",
        "volume": "2136",
        "wave": 0
    },
    {
        "close": "4746.000",
        "ctm": "1726669800",
        "ctmfmt": "2024-09-18 22:30:00",
        "high": "4746.000",
        "low": "4742.000",
        "open": "4746.000",
        "volume": "1097",
        "wave": 0
    },
    {
        "close": "4760.000",
        "ctm": "1726669860",
        "ctmfmt": "2024-09-18 22:31:00",
        "high": "4764.000",
        "low": "4750.000",
        "open": "4750.000",
        "volume": "8418",
        "wave": 0
    },
    {
        "close": "4766.000",
        "ctm": "1726669920",
        "ctmfmt": "2024-09-18 22:32:00",
        "high": "4766.000",
        "low": "4758.000",
        "open": "4758.000",
        "volume": "1331",
        "wave": 0
    },
    {
        "close": "4762.000",
        "ctm": "1726669980",
        "ctmfmt": "2024-09-18 22:33:00",
        "high": "4766.000",
        "low": "4760.000",
        "open": "4764.000",
        "volume": "3751",
        "wave": 0
    },
    {
        "close": "4762.000",
        "ctm": "1726670040",
        "ctmfmt": "2024-09-18 22:34:00",
        "high": "4768.000",
        "low": "4762.000",
        "open": "4764.000",
        "volume": "5657",
        "wave": 0
    },
    {
        "close": "4768.000",
        "ctm": "1726670100",
        "ctmfmt": "2024-09-18 22:35:00",
        "high": "4770.000",
        "low": "4762.000",
        "open": "4762.000",
        "volume": "3844",
        "wave": 0
    },
    {
        "close": "4764.000",
        "ctm": "1726670160",
        "ctmfmt": "2024-09-18 22:36:00",
        "high": "4770.000",
        "low": "4762.000",
        "open": "4768.000",
        "volume": "5968",
        "wave": 0
    },
    {
        "close": "4762.000",
        "ctm": "1726670220",
        "ctmfmt": "2024-09-18 22:37:00",
        "high": "4766.000",
        "low": "4760.000",
        "open": "4766.000",
        "volume": "3417",
        "wave": 0
    },
    {
        "close": "4768.000",
        "ctm": "1726670280",
        "ctmfmt": "2024-09-18 22:38:00",
        "high": "4770.000",
        "low": "4760.000",
        "open": "4762.000",
        "volume": "3275",
        "wave": 0
    },
    {
        "close": "4766.000",
        "ctm": "1726670340",
        "ctmfmt": "2024-09-18 22:39:00",
        "high": "4770.000",
        "low": "4762.000",
        "open": "4768.000",
        "volume": "1715",
        "wave": 0
    },
    {
        "close": "4766.000",
        "ctm": "1726670400",
        "ctmfmt": "2024-09-18 22:40:00",
        "high": "4768.000",
        "low": "4764.000",
        "open": "4766.000",
        "volume": "554241",
        "wave": 0
    },
    {
        "close": "4766.000",
        "ctm": "1726670460",
        "ctmfmt": "2024-09-18 22:41:00",
        "high": "4766.000",
        "low": "4764.000",
        "open": "4766.000",
        "volume": "477",
        "wave": 0
    },
    {
        "close": "4770.000",
        "ctm": "1726670520",
        "ctmfmt": "2024-09-18 22:42:00",
        "high": "4774.000",
        "low": "4764.000",
        "open": "4764.000",
        "volume": "5689",
        "wave": 0
    },
    {
        "close": "4768.000",
        "ctm": "1726670580",
        "ctmfmt": "2024-09-18 22:43:00",
        "high": "4772.000",
        "low": "4768.000",
        "open": "4770.000",
        "volume": "1763",
        "wave": 0
    },
    {
        "close": "4756.000",
        "ctm": "1726670640",
        "ctmfmt": "2024-09-18 22:44:00",
        "high": "4770.000",
        "low": "4756.000",
        "open": "4770.000",
        "volume": "4909",
        "wave": 0
    },
    {
        "close": "4758.000",
        "ctm": "1726670700",
        "ctmfmt": "2024-09-18 22:45:00",
        "high": "4760.000",
        "low": "4756.000",
        "open": "4756.000",
        "volume": "2568",
        "wave": 0
    },
    {
        "close": "4758.000",
        "ctm": "1726670760",
        "ctmfmt": "2024-09-18 22:46:00",
        "high": "4760.000",
        "low": "4756.000",
        "open": "4758.000",
        "volume": "1653",
        "wave": 0
    },
    {
        "close": "4762.000",
        "ctm": "1726670820",
        "ctmfmt": "2024-09-18 22:47:00",
        "high": "4764.000",
        "low": "4756.000",
        "open": "4758.000",
        "volume": "2180",
        "wave": 0
    },
    {
        "close": "4760.000",
        "ctm": "1726670880",
        "ctmfmt": "2024-09-18 22:48:00",
        "high": "4762.000",
        "low": "4758.000",
        "open": "4762.000",
        "volume": "761",
        "wave": 0
    },
    {
        "close": "4758.000",
        "ctm": "1726670940",
        "ctmfmt": "2024-09-18 22:49:00",
        "high": "4762.000",
        "low": "4756.000",
        "open": "4762.000",
        "volume": "1223",
        "wave": 0
    },
    {
        "close": "4756.000",
        "ctm": "1726671000",
        "ctmfmt": "2024-09-18 22:50:00",
        "high": "4758.000",
        "low": "4754.000",
        "open": "4758.000",
        "volume": "2180",
        "wave": 0
    },
    {
        "close": "4746.000",
        "ctm": "1726671060",
        "ctmfmt": "2024-09-18 22:51:00",
        "high": "4758.000",
        "low": "4746.000",
        "open": "4756.000",
        "volume": "4011",
        "wave": 0
    },
    {
        "close": "4744.000",
        "ctm": "1726671120",
        "ctmfmt": "2024-09-18 22:52:00",
        "high": "4750.000",
        "low": "4742.000",
        "open": "4748.000",
        "volume": "3725",
        "wave": 0
    },
    {
        "close": "4748.000",
        "ctm": "1726671180",
        "ctmfmt": "2024-09-18 22:53:00",
        "high": "4750.000",
        "low": "4744.000",
        "open": "4746.000",
        "volume": "1534",
        "wave": 0
    },
    {
        "close": "4746.000",
        "ctm": "1726671240",
        "ctmfmt": "2024-09-18 22:54:00",
        "high": "4750.000",
        "low": "4746.000",
        "open": "4748.000",
        "volume": "1457",
        "wave": 0
    },
    {
        "close": "4744.000",
        "ctm": "1726671300",
        "ctmfmt": "2024-09-18 22:55:00",
        "high": "4746.000",
        "low": "4742.000",
        "open": "4746.000",
        "volume": "2211",
        "wave": 0
    },
    {
        "close": "4740.000",
        "ctm": "1726671360",
        "ctmfmt": "2024-09-18 22:56:00",
        "high": "4746.000",
        "low": "4740.000",
        "open": "4744.000",
        "volume": "2085",
        "wave": 0
    },
    {
        "close": "4740.000",
        "ctm": "1726671420",
        "ctmfmt": "2024-09-18 22:57:00",
        "high": "4742.000",
        "low": "4738.000",
        "open": "4742.000",
        "volume": "2582",
        "wave": 0
    },
    {
        "close": "4744.000",
        "ctm": "1726671480",
        "ctmfmt": "2024-09-18 22:58:00",
        "high": "4744.000",
        "low": "4740.000",
        "open": "4740.000",
        "volume": "1913",
        "wave": 0
    },
    {
        "close": "4748.000",
        "ctm": "1726671540",
        "ctmfmt": "2024-09-18 22:59:00",
        "high": "4750.000",
        "low": "4742.000",
        "open": "4742.000",
        "volume": "3423",
        "wave": 0
    },
    {
        "close": "4758.000",
        "ctm": "1726671600",
        "ctmfmt": "2024-09-18 23:00:00",
        "high": "4762.000",
        "low": "4748.000",
        "open": "4750.000",
        "volume": "5660",
        "wave": 0
    },
    {
        "close": "4768.000",
        "ctm": "1726707660",
        "ctmfmt": "2024-09-19 09:01:00",
        "high": "4782.000",
        "low": "4750.000",
        "open": "4750.000",
        "volume": "19891",
        "wave": 0
    },
    {
        "close": "4762.000",
        "ctm": "1726707720",
        "ctmfmt": "2024-09-19 09:02:00",
        "high": "4770.000",
        "low": "4762.000",
        "open": "4770.000",
        "volume": "10264",
        "wave": 0
    },
    {
        "close": "4766.000",
        "ctm": "1726707780",
        "ctmfmt": "2024-09-19 09:03:00",
        "high": "4766.000",
        "low": "4758.000",
        "open": "4760.000",
        "volume": "5752",
        "wave": 0
    },
    {
        "close": "4760.000",
        "ctm": "1726707840",
        "ctmfmt": "2024-09-19 09:04:00",
        "high": "4764.000",
        "low": "4760.000",
        "open": "4764.000",
        "volume": "4826",
        "wave": 0
    },
    {
        "close": "4762.000",
        "ctm": "1726707900",
        "ctmfmt": "2024-09-19 09:05:00",
        "high": "4766.000",
        "low": "4760.000",
        "open": "4760.000",
        "volume": "4039",
        "wave": 0
    },
    {
        "close": "4762.000",
        "ctm": "1726707960",
        "ctmfmt": "2024-09-19 09:06:00",
        "high": "4766.000",
        "low": "4756.000",
        "open": "4762.000",
        "volume": "9651",
        "wave": 0
    },
    {
        "close": "4764.000",
        "ctm": "1726708020",
        "ctmfmt": "2024-09-19 09:07:00",
        "high": "4766.000",
        "low": "4760.000",
        "open": "4762.000",
        "volume": "3657",
        "wave": 0
    },
    {
        "close": "4762.000",
        "ctm": "1726708080",
        "ctmfmt": "2024-09-19 09:08:00",
        "high": "4766.000",
        "low": "4760.000",
        "open": "4764.000",
        "volume": "4363",
        "wave": 0
    },
    {
        "close": "4760.000",
        "ctm": "1726708140",
        "ctmfmt": "2024-09-19 09:09:00",
        "high": "4764.000",
        "low": "4756.000",
        "open": "4760.000",
        "volume": "3075",
        "wave": 0
    },
    {
        "close": "4760.000",
        "ctm": "1726708200",
        "ctmfmt": "2024-09-19 09:10:00",
        "high": "4762.000",
        "low": "4756.000",
        "open": "4760.000",
        "volume": "4667",
        "wave": 0
    },
    {
        "close": "4766.000",
        "ctm": "1726708260",
        "ctmfmt": "2024-09-19 09:11:00",
        "high": "4766.000",
        "low": "4756.000",
        "open": "4762.000",
        "volume": "6632",
        "wave": 0
    },
    {
        "close": "4768.000",
        "ctm": "1726708320",
        "ctmfmt": "2024-09-19 09:12:00",
        "high": "4770.000",
        "low": "4762.000",
        "open": "4768.000",
        "volume": "4091",
        "wave": 0
    },
    {
        "close": "4770.000",
        "ctm": "1726708380",
        "ctmfmt": "2024-09-19 09:13:00",
        "high": "4772.000",
        "low": "4768.000",
        "open": "4772.000",
        "volume": "1152",
        "wave": 0
    },
    {
        "close": "4766.000",
        "ctm": "1726708440",
        "ctmfmt": "2024-09-19 09:14:00",
        "high": "4772.000",
        "low": "4764.000",
        "open": "4770.000",
        "volume": "3147",
        "wave": 0
    },
    {
        "close": "4770.000",
        "ctm": "1726708500",
        "ctmfmt": "2024-09-19 09:15:00",
        "high": "4770.000",
        "low": "4766.000",
        "open": "4766.000",
        "volume": "1221",
        "wave": 0
    },
    {
        "close": "4766.000",
        "ctm": "1726708560",
        "ctmfmt": "2024-09-19 09:16:00",
        "high": "4768.000",
        "low": "4762.000",
        "open": "4764.000",
        "volume": "2958",
        "wave": 0
    },
    {
        "close": "4764.000",
        "ctm": "1726708620",
        "ctmfmt": "2024-09-19 09:17:00",
        "high": "4764.000",
        "low": "4762.000",
        "open": "4762.000",
        "volume": "498",
        "wave": 0
    },
    {
        "close": "4762.000",
        "ctm": "1726708680",
        "ctmfmt": "2024-09-19 09:18:00",
        "high": "4768.000",
        "low": "4762.000",
        "open": "4766.000",
        "volume": "2264",
        "wave": 0
    },
    {
        "close": "4762.000",
        "ctm": "1726708740",
        "ctmfmt": "2024-09-19 09:19:00",
        "high": "4762.000",
        "low": "4760.000",
        "open": "4762.000",
        "volume": "17",
        "wave": 0
    },
    {
        "close": "4758.000",
        "ctm": "1726708800",
        "ctmfmt": "2024-09-19 09:20:00",
        "high": "4758.000",
        "low": "4758.000",
        "open": "4758.000",
        "volume": "713048",
        "wave": 0
    },
    {
        "close": "4748.000",
        "ctm": "1726708860",
        "ctmfmt": "2024-09-19 09:21:00",
        "high": "4754.000",
        "low": "4746.000",
        "open": "4754.000",
        "volume": "6528",
        "wave": 0
    },
    {
        "close": "4748.000",
        "ctm": "1726708920",
        "ctmfmt": "2024-09-19 09:22:00",
        "high": "4750.000",
        "low": "4742.000",
        "open": "4748.000",
        "volume": "4990",
        "wave": 0
    },
    {
        "close": "4740.000",
        "ctm": "1726708980",
        "ctmfmt": "2024-09-19 09:23:00",
        "high": "4748.000",
        "low": "4740.000",
        "open": "4746.000",
        "volume": "4501",
        "wave": 0
    },
    {
        "close": "4732.000",
        "ctm": "1726709040",
        "ctmfmt": "2024-09-19 09:24:00",
        "high": "4742.000",
        "low": "4728.000",
        "open": "4740.000",
        "volume": "9426",
        "wave": 0
    },
    {
        "close": "4732.000",
        "ctm": "1726709100",
        "ctmfmt": "2024-09-19 09:25:00",
        "high": "4738.000",
        "low": "4732.000",
        "open": "4734.000",
        "volume": "3815",
        "wave": 0
    },
    {
        "close": "4726.000",
        "ctm": "1726709160",
        "ctmfmt": "2024-09-19 09:26:00",
        "high": "4734.000",
        "low": "4726.000",
        "open": "4732.000",
        "volume": "7778",
        "wave": 0
    },
    {
        "close": "4724.000",
        "ctm": "1726709220",
        "ctmfmt": "2024-09-19 09:27:00",
        "high": "4728.000",
        "low": "4724.000",
        "open": "4726.000",
        "volume": "1528",
        "wave": 0
    },
    {
        "close": "4718.000",
        "ctm": "1726709280",
        "ctmfmt": "2024-09-19 09:28:00",
        "high": "4720.000",
        "low": "4716.000",
        "open": "4718.000",
        "volume": "4255",
        "wave": 0
    },
    {
        "close": "4716.000",
        "ctm": "1726709340",
        "ctmfmt": "2024-09-19 09:29:00",
        "high": "4720.000",
        "low": "4714.000",
        "open": "4716.000",
        "volume": "5456",
        "wave": 0
    },
    {
        "close": "4714.000",
        "ctm": "1726709400",
        "ctmfmt": "2024-09-19 09:30:00",
        "high": "4718.000",
        "low": "4710.000",
        "open": "4714.000",
        "volume": "10274",
        "wave": 0
    },
    {
        "close": "4722.000",
        "ctm": "1726709460",
        "ctmfmt": "2024-09-19 09:31:00",
        "high": "4724.000",
        "low": "4716.000",
        "open": "4716.000",
        "volume": "7568",
        "wave": 0
    },
    {
        "close": "4722.000",
        "ctm": "1726709520",
        "ctmfmt": "2024-09-19 09:32:00",
        "high": "4728.000",
        "low": "4720.000",
        "open": "4720.000",
        "volume": "3613",
        "wave": 0
    },
    {
        "close": "4726.000",
        "ctm": "1726709580",
        "ctmfmt": "2024-09-19 09:33:00",
        "high": "4726.000",
        "low": "4722.000",
        "open": "4722.000",
        "volume": "1689",
        "wave": 0
    },
    {
        "close": "4714.000",
        "ctm": "1726709640",
        "ctmfmt": "2024-09-19 09:34:00",
        "high": "4714.000",
        "low": "4712.000",
        "open": "4714.000",
        "volume": "2058",
        "wave": 0
    },
    {
        "close": "4714.000",
        "ctm": "1726709700",
        "ctmfmt": "2024-09-19 09:35:00",
        "high": "4716.000",
        "low": "4710.000",
        "open": "4714.000",
        "volume": "9584",
        "wave": 0
    },
    {
        "close": "4714.000",
        "ctm": "1726709760",
        "ctmfmt": "2024-09-19 09:36:00",
        "high": "4718.000",
        "low": "4714.000",
        "open": "4716.000",
        "volume": "3585",
        "wave": 0
    },
    {
        "close": "4718.000",
        "ctm": "1726709820",
        "ctmfmt": "2024-09-19 09:37:00",
        "high": "4718.000",
        "low": "4716.000",
        "open": "4718.000",
        "volume": "747",
        "wave": 0
    },
    {
        "close": "4712.000",
        "ctm": "1726709880",
        "ctmfmt": "2024-09-19 09:38:00",
        "high": "4718.000",
        "low": "4710.000",
        "open": "4718.000",
        "volume": "3557",
        "wave": 0
    },
    {
        "close": "4716.000",
        "ctm": "1726709940",
        "ctmfmt": "2024-09-19 09:39:00",
        "high": "4718.000",
        "low": "4716.000",
        "open": "4718.000",
        "volume": "812",
        "wave": 0
    },
    {
        "close": "4714.000",
        "ctm": "1726710000",
        "ctmfmt": "2024-09-19 09:40:00",
        "high": "4718.000",
        "low": "4712.000",
        "open": "4716.000",
        "volume": "4393",
        "wave": 0
    },
    {
        "close": "4710.000",
        "ctm": "1726710060",
        "ctmfmt": "2024-09-19 09:41:00",
        "high": "4716.000",
        "low": "4710.000",
        "open": "4712.000",
        "volume": "4356",
        "wave": 0
    },
    {
        "close": "4710.000",
        "ctm": "1726710120",
        "ctmfmt": "2024-09-19 09:42:00",
        "high": "4710.000",
        "low": "4706.000",
        "open": "4710.000",
        "volume": "6915",
        "wave": 0
    },
    {
        "close": "4712.000",
        "ctm": "1726710180",
        "ctmfmt": "2024-09-19 09:43:00",
        "high": "4714.000",
        "low": "4708.000",
        "open": "4710.000",
        "volume": "4703",
        "wave": 0
    },
    {
        "close": "4712.000",
        "ctm": "1726710240",
        "ctmfmt": "2024-09-19 09:44:00",
        "high": "4714.000",
        "low": "4708.000",
        "open": "4714.000",
        "volume": "6606",
        "wave": 0
    },
    {
        "close": "4712.000",
        "ctm": "1726710300",
        "ctmfmt": "2024-09-19 09:45:00",
        "high": "4714.000",
        "low": "4708.000",
        "open": "4710.000",
        "volume": "2416",
        "wave": 0
    },
    {
        "close": "4718.000",
        "ctm": "1726710360",
        "ctmfmt": "2024-09-19 09:46:00",
        "high": "4720.000",
        "low": "4712.000",
        "open": "4712.000",
        "volume": "3453",
        "wave": 0
    },
    {
        "close": "4712.000",
        "ctm": "1726710420",
        "ctmfmt": "2024-09-19 09:47:00",
        "high": "4720.000",
        "low": "4710.000",
        "open": "4718.000",
        "volume": "4686",
        "wave": 0
    },
    {
        "close": "4710.000",
        "ctm": "1726710480",
        "ctmfmt": "2024-09-19 09:48:00",
        "high": "4712.000",
        "low": "4706.000",
        "open": "4712.000",
        "volume": "3024",
        "wave": 0
    },
    {
        "close": "4700.000",
        "ctm": "1726710540",
        "ctmfmt": "2024-09-19 09:49:00",
        "high": "4708.000",
        "low": "4700.000",
        "open": "4708.000",
        "volume": "7642",
        "wave": 0
    },
    {
        "close": "4700.000",
        "ctm": "1726710600",
        "ctmfmt": "2024-09-19 09:50:00",
        "high": "4702.000",
        "low": "4696.000",
        "open": "4700.000",
        "volume": "8377",
        "wave": 0
    },
    {
        "close": "4702.000",
        "ctm": "1726710660",
        "ctmfmt": "2024-09-19 09:51:00",
        "high": "4704.000",
        "low": "4698.000",
        "open": "4698.000",
        "volume": "4861",
        "wave": 0
    },
    {
        "close": "4708.000",
        "ctm": "1726710720",
        "ctmfmt": "2024-09-19 09:52:00",
        "high": "4708.000",
        "low": "4702.000",
        "open": "4702.000",
        "volume": "3420",
        "wave": 0
    },
    {
        "close": "4708.000",
        "ctm": "1726710780",
        "ctmfmt": "2024-09-19 09:53:00",
        "high": "4710.000",
        "low": "4704.000",
        "open": "4706.000",
        "volume": "2671",
        "wave": 0
    },
    {
        "close": "4722.000",
        "ctm": "1726710840",
        "ctmfmt": "2024-09-19 09:54:00",
        "high": "4726.000",
        "low": "4708.000",
        "open": "4708.000",
        "volume": "9361",
        "wave": 0
    },
    {
        "close": "4720.000",
        "ctm": "1726710900",
        "ctmfmt": "2024-09-19 09:55:00",
        "high": "4728.000",
        "low": "4720.000",
        "open": "4724.000",
        "volume": "5905",
        "wave": 0
    },
    {
        "close": "4722.000",
        "ctm": "1726710960",
        "ctmfmt": "2024-09-19 09:56:00",
        "high": "4728.000",
        "low": "4722.000",
        "open": "4722.000",
        "volume": "3419",
        "wave": 0
    },
    {
        "close": "4728.000",
        "ctm": "1726711020",
        "ctmfmt": "2024-09-19 09:57:00",
        "high": "4728.000",
        "low": "4722.000",
        "open": "4722.000",
        "volume": "2674",
        "wave": 0
    },
    {
        "close": "4736.000",
        "ctm": "1726711080",
        "ctmfmt": "2024-09-19 09:58:00",
        "high": "4736.000",
        "low": "4728.000",
        "open": "4732.000",
        "volume": "7250",
        "wave": 0
    },
    {
        "close": "4732.000",
        "ctm": "1726711140",
        "ctmfmt": "2024-09-19 09:59:00",
        "high": "4740.000",
        "low": "4732.000",
        "open": "4738.000",
        "volume": "4047",
        "wave": 0
    },
    {
        "close": "4744.000",
        "ctm": "1726711200",
        "ctmfmt": "2024-09-19 10:00:00",
        "high": "4744.000",
        "low": "4732.000",
        "open": "4732.000",
        "volume": "7115",
        "wave": 0
    },
    {
        "close": "4742.000",
        "ctm": "1726711260",
        "ctmfmt": "2024-09-19 10:01:00",
        "high": "4744.000",
        "low": "4738.000",
        "open": "4744.000",
        "volume": "5047",
        "wave": 0
    },
    {
        "close": "4756.000",
        "ctm": "1726711320",
        "ctmfmt": "2024-09-19 10:02:00",
        "high": "4756.000",
        "low": "4756.000",
        "open": "4756.000",
        "volume": "484",
        "wave": 0
    },
    {
        "close": "4752.000",
        "ctm": "1726711380",
        "ctmfmt": "2024-09-19 10:03:00",
        "high": "4756.000",
        "low": "4752.000",
        "open": "4756.000",
        "volume": "7461",
        "wave": 0
    },
    {
        "close": "4764.000",
        "ctm": "1726711440",
        "ctmfmt": "2024-09-19 10:04:00",
        "high": "4766.000",
        "low": "4752.000",
        "open": "4752.000",
        "volume": "7869",
        "wave": 0
    },
    {
        "close": "4770.000",
        "ctm": "1726711500",
        "ctmfmt": "2024-09-19 10:05:00",
        "high": "4770.000",
        "low": "4762.000",
        "open": "4762.000",
        "volume": "7712",
        "wave": 0
    },
    {
        "close": "4758.000",
        "ctm": "1726711560",
        "ctmfmt": "2024-09-19 10:06:00",
        "high": "4766.000",
        "low": "4756.000",
        "open": "4766.000",
        "volume": "7124",
        "wave": 0
    },
    {
        "close": "4758.000",
        "ctm": "1726711620",
        "ctmfmt": "2024-09-19 10:07:00",
        "high": "4762.000",
        "low": "4758.000",
        "open": "4758.000",
        "volume": "5882",
        "wave": 0
    },
    {
        "close": "4764.000",
        "ctm": "1726711680",
        "ctmfmt": "2024-09-19 10:08:00",
        "high": "4768.000",
        "low": "4756.000",
        "open": "4758.000",
        "volume": "8969",
        "wave": 0
    },
    {
        "close": "4768.000",
        "ctm": "1726711740",
        "ctmfmt": "2024-09-19 10:09:00",
        "high": "4768.000",
        "low": "4762.000",
        "open": "4764.000",
        "volume": "3885",
        "wave": 0
    },
    {
        "close": "4766.000",
        "ctm": "1726711800",
        "ctmfmt": "2024-09-19 10:10:00",
        "high": "4770.000",
        "low": "4766.000",
        "open": "4768.000",
        "volume": "2887",
        "wave": 0
    },
    {
        "close": "4766.000",
        "ctm": "1726711860",
        "ctmfmt": "2024-09-19 10:11:00",
        "high": "4768.000",
        "low": "4762.000",
        "open": "4766.000",
        "volume": "3581",
        "wave": 0
    },
    {
        "close": "4776.000",
        "ctm": "1726711920",
        "ctmfmt": "2024-09-19 10:12:00",
        "high": "4778.000",
        "low": "4766.000",
        "open": "4766.000",
        "volume": "8082",
        "wave": 0
    },
    {
        "close": "4764.000",
        "ctm": "1726711980",
        "ctmfmt": "2024-09-19 10:13:00",
        "high": "4772.000",
        "low": "4764.000",
        "open": "4772.000",
        "volume": "5316",
        "wave": 0
    },
    {
        "close": "4766.000",
        "ctm": "1726712040",
        "ctmfmt": "2024-09-19 10:14:00",
        "high": "4768.000",
        "low": "4762.000",
        "open": "4762.000",
        "volume": "2040",
        "wave": 0
    },
    {
        "close": "4770.000",
        "ctm": "1726712100",
        "ctmfmt": "2024-09-19 10:15:00",
        "high": "4770.000",
        "low": "4764.000",
        "open": "4766.000",
        "volume": "2925",
        "wave": 0
    },
    {
        "close": "4812.000",
        "ctm": "1726713060",
        "ctmfmt": "2024-09-19 10:31:00",
        "high": "4814.000",
        "low": "4774.000",
        "open": "4774.000",
        "volume": "46342",
        "wave": 0
    },
    {
        "close": "4820.000",
        "ctm": "1726713120",
        "ctmfmt": "2024-09-19 10:32:00",
        "high": "4826.000",
        "low": "4806.000",
        "open": "4814.000",
        "volume": "32670",
        "wave": 0
    },
    {
        "close": "4814.000",
        "ctm": "1726713180",
        "ctmfmt": "2024-09-19 10:33:00",
        "high": "4818.000",
        "low": "4810.000",
        "open": "4816.000",
        "volume": "14269",
        "wave": 0
    },
    {
        "close": "4802.000",
        "ctm": "1726713240",
        "ctmfmt": "2024-09-19 10:34:00",
        "high": "4812.000",
        "low": "4800.000",
        "open": "4810.000",
        "volume": "9303",
        "wave": 0
    },
    {
        "close": "4808.000",
        "ctm": "1726713300",
        "ctmfmt": "2024-09-19 10:35:00",
        "high": "4812.000",
        "low": "4802.000",
        "open": "4802.000",
        "volume": "8758",
        "wave": 0
    },
    {
        "close": "4814.000",
        "ctm": "1726713360",
        "ctmfmt": "2024-09-19 10:36:00",
        "high": "4816.000",
        "low": "4804.000",
        "open": "4804.000",
        "volume": "8612",
        "wave": 0
    },
    {
        "close": "4824.000",
        "ctm": "1726713420",
        "ctmfmt": "2024-09-19 10:37:00",
        "high": "4824.000",
        "low": "4812.000",
        "open": "4812.000",
        "volume": "12306",
        "wave": 0
    },
    {
        "close": "4818.000",
        "ctm": "1726713480",
        "ctmfmt": "2024-09-19 10:38:00",
        "high": "4826.000",
        "low": "4816.000",
        "open": "4822.000",
        "volume": "13348",
        "wave": 0
    },
    {
        "close": "4822.000",
        "ctm": "1726713540",
        "ctmfmt": "2024-09-19 10:39:00",
        "high": "4830.000",
        "low": "4818.000",
        "open": "4818.000",
        "volume": "19081",
        "wave": 0
    },
    {
        "close": "4828.000",
        "ctm": "1726713600",
        "ctmfmt": "2024-09-19 10:40:00",
        "high": "4828.000",
        "low": "4818.000",
        "open": "4822.000",
        "volume": "5759",
        "wave": 0
    },
    {
        "close": "4834.000",
        "ctm": "1726713660",
        "ctmfmt": "2024-09-19 10:41:00",
        "high": "4840.000",
        "low": "4828.000",
        "open": "4828.000",
        "volume": "15341",
        "wave": 0
    },
    {
        "close": "4840.000",
        "ctm": "1726713720",
        "ctmfmt": "2024-09-19 10:42:00",
        "high": "4842.000",
        "low": "4834.000",
        "open": "4838.000",
        "volume": "9237",
        "wave": 0
    },
    {
        "close": "4828.000",
        "ctm": "1726713780",
        "ctmfmt": "2024-09-19 10:43:00",
        "high": "4840.000",
        "low": "4828.000",
        "open": "4838.000",
        "volume": "8117",
        "wave": 0
    },
    {
        "close": "4832.000",
        "ctm": "1726713840",
        "ctmfmt": "2024-09-19 10:44:00",
        "high": "4832.000",
        "low": "4828.000",
        "open": "4830.000",
        "volume": "2224",
        "wave": 0
    },
    {
        "close": "4832.000",
        "ctm": "1726713900",
        "ctmfmt": "2024-09-19 10:45:00",
        "high": "4838.000",
        "low": "4832.000",
        "open": "4832.000",
        "volume": "4940",
        "wave": 0
    },
    {
        "close": "4836.000",
        "ctm": "1726713960",
        "ctmfmt": "2024-09-19 10:46:00",
        "high": "4836.000",
        "low": "4830.000",
        "open": "4834.000",
        "volume": "8468",
        "wave": 0
    },
    {
        "close": "4838.000",
        "ctm": "1726714020",
        "ctmfmt": "2024-09-19 10:47:00",
        "high": "4840.000",
        "low": "4834.000",
        "open": "4836.000",
        "volume": "4387",
        "wave": 0
    },
    {
        "close": "4852.000",
        "ctm": "1726714080",
        "ctmfmt": "2024-09-19 10:48:00",
        "high": "4852.000",
        "low": "4840.000",
        "open": "4840.000",
        "volume": "11359",
        "wave": 0
    },
    {
        "close": "4842.000",
        "ctm": "1726714140",
        "ctmfmt": "2024-09-19 10:49:00",
        "high": "4842.000",
        "low": "4842.000",
        "open": "4842.000",
        "volume": "12",
        "wave": 0
    },
    {
        "close": "4840.000",
        "ctm": "1726714200",
        "ctmfmt": "2024-09-19 10:50:00",
        "high": "4848.000",
        "low": "4840.000",
        "open": "4844.000",
        "volume": "7617",
        "wave": 0
    },
    {
        "close": "4844.000",
        "ctm": "1726714260",
        "ctmfmt": "2024-09-19 10:51:00",
        "high": "4846.000",
        "low": "4838.000",
        "open": "4840.000",
        "volume": "3657",
        "wave": 0
    },
    {
        "close": "4842.000",
        "ctm": "1726714320",
        "ctmfmt": "2024-09-19 10:52:00",
        "high": "4846.000",
        "low": "4840.000",
        "open": "4842.000",
        "volume": "3445",
        "wave": 0
    },
    {
        "close": "4828.000",
        "ctm": "1726714380",
        "ctmfmt": "2024-09-19 10:53:00",
        "high": "4844.000",
        "low": "4824.000",
        "open": "4844.000",
        "volume": "10758",
        "wave": 0
    },
    {
        "close": "4820.000",
        "ctm": "1726714440",
        "ctmfmt": "2024-09-19 10:54:00",
        "high": "4830.000",
        "low": "4818.000",
        "open": "4828.000",
        "volume": "11871",
        "wave": 0
    },
    {
        "close": "4828.000",
        "ctm": "1726714500",
        "ctmfmt": "2024-09-19 10:55:00",
        "high": "4828.000",
        "low": "4818.000",
        "open": "4820.000",
        "volume": "7812",
        "wave": 0
    },
    {
        "close": "4836.000",
        "ctm": "1726714560",
        "ctmfmt": "2024-09-19 10:56:00",
        "high": "4836.000",
        "low": "4828.000",
        "open": "4828.000",
        "volume": "5379",
        "wave": 0
    },
    {
        "close": "4838.000",
        "ctm": "1726714620",
        "ctmfmt": "2024-09-19 10:57:00",
        "high": "4842.000",
        "low": "4834.000",
        "open": "4834.000",
        "volume": "5523",
        "wave": 0
    },
    {
        "close": "4832.000",
        "ctm": "1726714680",
        "ctmfmt": "2024-09-19 10:58:00",
        "high": "4838.000",
        "low": "4832.000",
        "open": "4838.000",
        "volume": "3539",
        "wave": 0
    },
    {
        "close": "4832.000",
        "ctm": "1726714740",
        "ctmfmt": "2024-09-19 10:59:00",
        "high": "4838.000",
        "low": "4828.000",
        "open": "4834.000",
        "volume": "2416",
        "wave": 0
    },
    {
        "close": "4834.000",
        "ctm": "1726714800",
        "ctmfmt": "2024-09-19 11:00:00",
        "high": "4834.000",
        "low": "4830.000",
        "open": "4830.000",
        "volume": "2583",
        "wave": 0
    },
    {
        "close": "4826.000",
        "ctm": "1726714860",
        "ctmfmt": "2024-09-19 11:01:00",
        "high": "4836.000",
        "low": "4824.000",
        "open": "4836.000",
        "volume": "3698",
        "wave": 0
    },
    {
        "close": "4826.000",
        "ctm": "1726714920",
        "ctmfmt": "2024-09-19 11:02:00",
        "high": "4830.000",
        "low": "4824.000",
        "open": "4826.000",
        "volume": "2335",
        "wave": 0
    },
    {
        "close": "4818.000",
        "ctm": "1726714980",
        "ctmfmt": "2024-09-19 11:03:00",
        "high": "4824.000",
        "low": "4818.000",
        "open": "4824.000",
        "volume": "3475",
        "wave": 0
    },
    {
        "close": "4816.000",
        "ctm": "1726715040",
        "ctmfmt": "2024-09-19 11:04:00",
        "high": "4820.000",
        "low": "4812.000",
        "open": "4818.000",
        "volume": "4873",
        "wave": 0
    },
    {
        "close": "4818.000",
        "ctm": "1726715100",
        "ctmfmt": "2024-09-19 11:05:00",
        "high": "4820.000",
        "low": "4814.000",
        "open": "4814.000",
        "volume": "6500",
        "wave": 0
    },
    {
        "close": "4814.000",
        "ctm": "1726715160",
        "ctmfmt": "2024-09-19 11:06:00",
        "high": "4818.000",
        "low": "4814.000",
        "open": "4816.000",
        "volume": "1710",
        "wave": 0
    },
    {
        "close": "4820.000",
        "ctm": "1726715220",
        "ctmfmt": "2024-09-19 11:07:00",
        "high": "4820.000",
        "low": "4814.000",
        "open": "4814.000",
        "volume": "2810",
        "wave": 0
    },
    {
        "close": "4826.000",
        "ctm": "1726715280",
        "ctmfmt": "2024-09-19 11:08:00",
        "high": "4826.000",
        "low": "4818.000",
        "open": "4818.000",
        "volume": "2118",
        "wave": 0
    },
    {
        "close": "4822.000",
        "ctm": "1726715340",
        "ctmfmt": "2024-09-19 11:09:00",
        "high": "4826.000",
        "low": "4820.000",
        "open": "4826.000",
        "volume": "1897",
        "wave": 0
    },
    {
        "close": "4814.000",
        "ctm": "1726715400",
        "ctmfmt": "2024-09-19 11:10:00",
        "high": "4822.000",
        "low": "4814.000",
        "open": "4822.000",
        "volume": "2047",
        "wave": 0
    },
    {
        "close": "4818.000",
        "ctm": "1726715460",
        "ctmfmt": "2024-09-19 11:11:00",
        "high": "4820.000",
        "low": "4814.000",
        "open": "4816.000",
        "volume": "1593",
        "wave": 0
    },
    {
        "close": "4822.000",
        "ctm": "1726715520",
        "ctmfmt": "2024-09-19 11:12:00",
        "high": "4822.000",
        "low": "4818.000",
        "open": "4818.000",
        "volume": "2317",
        "wave": 0
    },
    {
        "close": "4818.000",
        "ctm": "1726715580",
        "ctmfmt": "2024-09-19 11:13:00",
        "high": "4822.000",
        "low": "4818.000",
        "open": "4820.000",
        "volume": "1424",
        "wave": 0
    },
    {
        "close": "4818.000",
        "ctm": "1726715640",
        "ctmfmt": "2024-09-19 11:14:00",
        "high": "4822.000",
        "low": "4816.000",
        "open": "4818.000",
        "volume": "2822",
        "wave": 0
    },
    {
        "close": "4822.000",
        "ctm": "1726715700",
        "ctmfmt": "2024-09-19 11:15:00",
        "high": "4822.000",
        "low": "4818.000",
        "open": "4818.000",
        "volume": "1707",
        "wave": 0
    },
    {
        "close": "4824.000",
        "ctm": "1726715760",
        "ctmfmt": "2024-09-19 11:16:00",
        "high": "4824.000",
        "low": "4818.000",
        "open": "4822.000",
        "volume": "1440",
        "wave": 0
    },
    {
        "close": "4830.000",
        "ctm": "1726715820",
        "ctmfmt": "2024-09-19 11:17:00",
        "high": "4832.000",
        "low": "4822.000",
        "open": "4824.000",
        "volume": "3572",
        "wave": 0
    },
    {
        "close": "4826.000",
        "ctm": "1726715880",
        "ctmfmt": "2024-09-19 11:18:00",
        "high": "4832.000",
        "low": "4824.000",
        "open": "4832.000",
        "volume": "3037",
        "wave": 0
    },
    {
        "close": "4832.000",
        "ctm": "1726715940",
        "ctmfmt": "2024-09-19 11:19:00",
        "high": "4832.000",
        "low": "4824.000",
        "open": "4826.000",
        "volume": "2172",
        "wave": 0
    },
    {
        "close": "4832.000",
        "ctm": "1726716000",
        "ctmfmt": "2024-09-19 11:20:00",
        "high": "4834.000",
        "low": "4830.000",
        "open": "4830.000",
        "volume": "2595",
        "wave": 0
    },
    {
        "close": "4838.000",
        "ctm": "1726716060",
        "ctmfmt": "2024-09-19 11:21:00",
        "high": "4842.000",
        "low": "4832.000",
        "open": "4834.000",
        "volume": "5296",
        "wave": 0
    },
    {
        "close": "4842.000",
        "ctm": "1726716120",
        "ctmfmt": "2024-09-19 11:22:00",
        "high": "4842.000",
        "low": "4836.000",
        "open": "4838.000",
        "volume": "2316",
        "wave": 0
    },
    {
        "close": "4836.000",
        "ctm": "1726716180",
        "ctmfmt": "2024-09-19 11:23:00",
        "high": "4842.000",
        "low": "4834.000",
        "open": "4842.000",
        "volume": "2518",
        "wave": 0
    },
    {
        "close": "4838.000",
        "ctm": "1726716240",
        "ctmfmt": "2024-09-19 11:24:00",
        "high": "4838.000",
        "low": "4834.000",
        "open": "4834.000",
        "volume": "1433",
        "wave": 0
    },
    {
        "close": "4838.000",
        "ctm": "1726716300",
        "ctmfmt": "2024-09-19 11:25:00",
        "high": "4838.000",
        "low": "4834.000",
        "open": "4838.000",
        "volume": "1118",
        "wave": 0
    },
    {
        "close": "4836.000",
        "ctm": "1726716360",
        "ctmfmt": "2024-09-19 11:26:00",
        "high": "4842.000",
        "low": "4834.000",
        "open": "4838.000",
        "volume": "3281",
        "wave": 0
    },
    {
        "close": "4840.000",
        "ctm": "1726716420",
        "ctmfmt": "2024-09-19 11:27:00",
        "high": "4842.000",
        "low": "4834.000",
        "open": "4834.000",
        "volume": "3393",
        "wave": 0
    },
    {
        "close": "4836.000",
        "ctm": "1726716480",
        "ctmfmt": "2024-09-19 11:28:00",
        "high": "4840.000",
        "low": "4836.000",
        "open": "4838.000",
        "volume": "1581",
        "wave": 0
    },
    {
        "close": "4836.000",
        "ctm": "1726716540",
        "ctmfmt": "2024-09-19 11:29:00",
        "high": "4836.000",
        "low": "4836.000",
        "open": "4836.000",
        "volume": "534",
        "wave": 0
    },
    {
        "close": "4842.000",
        "ctm": "1726716600",
        "ctmfmt": "2024-09-19 11:30:00",
        "high": "4846.000",
        "low": "4836.000",
        "open": "4836.000",
        "volume": "3848",
        "wave": 0
    },
    {
        "close": "4848.000",
        "ctm": "1726723860",
        "ctmfmt": "2024-09-19 13:31:00",
        "high": "4856.000",
        "low": "4844.000",
        "open": "4852.000",
        "volume": "12299",
        "wave": 0
    },
    {
        "close": "4846.000",
        "ctm": "1726723920",
        "ctmfmt": "2024-09-19 13:32:00",
        "high": "4850.000",
        "low": "4844.000",
        "open": "4848.000",
        "volume": "3268",
        "wave": 0
    },
    {
        "close": "4848.000",
        "ctm": "1726723980",
        "ctmfmt": "2024-09-19 13:33:00",
        "high": "4850.000",
        "low": "4846.000",
        "open": "4848.000",
        "volume": "1885",
        "wave": 0
    },
    {
        "close": "4852.000",
        "ctm": "1726724040",
        "ctmfmt": "2024-09-19 13:34:00",
        "high": "4852.000",
        "low": "4846.000",
        "open": "4848.000",
        "volume": "3275",
        "wave": 0
    },
    {
        "close": "4850.000",
        "ctm": "1726724100",
        "ctmfmt": "2024-09-19 13:35:00",
        "high": "4856.000",
        "low": "4848.000",
        "open": "4852.000",
        "volume": "5255",
        "wave": 0
    },
    {
        "close": "4860.000",
        "ctm": "1726724160",
        "ctmfmt": "2024-09-19 13:36:00",
        "high": "4860.000",
        "low": "4850.000",
        "open": "4850.000",
        "volume": "8188",
        "wave": 0
    },
    {
        "close": "4862.000",
        "ctm": "1726724220",
        "ctmfmt": "2024-09-19 13:37:00",
        "high": "4864.000",
        "low": "4860.000",
        "open": "4860.000",
        "volume": "1816",
        "wave": 0
    },
    {
        "close": "4854.000",
        "ctm": "1726724280",
        "ctmfmt": "2024-09-19 13:38:00",
        "high": "4862.000",
        "low": "4854.000",
        "open": "4862.000",
        "volume": "505",
        "wave": 0
    },
    {
        "close": "4854.000",
        "ctm": "1726724340",
        "ctmfmt": "2024-09-19 13:39:00",
        "high": "4856.000",
        "low": "4852.000",
        "open": "4854.000",
        "volume": "2448",
        "wave": 0
    },
    {
        "close": "4850.000",
        "ctm": "1726724400",
        "ctmfmt": "2024-09-19 13:40:00",
        "high": "4854.000",
        "low": "4850.000",
        "open": "4854.000",
        "volume": "2644",
        "wave": 0
    },
    {
        "close": "4856.000",
        "ctm": "1726724460",
        "ctmfmt": "2024-09-19 13:41:00",
        "high": "4856.000",
        "low": "4850.000",
        "open": "4850.000",
        "volume": "2015",
        "wave": 0
    },
    {
        "close": "4860.000",
        "ctm": "1726724520",
        "ctmfmt": "2024-09-19 13:42:00",
        "high": "4862.000",
        "low": "4856.000",
        "open": "4856.000",
        "volume": "7389",
        "wave": 0
    },
    {
        "close": "4870.000",
        "ctm": "1726724580",
        "ctmfmt": "2024-09-19 13:43:00",
        "high": "4870.000",
        "low": "4858.000",
        "open": "4858.000",
        "volume": "10015",
        "wave": 0
    },
    {
        "close": "4866.000",
        "ctm": "1726724640",
        "ctmfmt": "2024-09-19 13:44:00",
        "high": "4872.000",
        "low": "4864.000",
        "open": "4870.000",
        "volume": "6060",
        "wave": 0
    },
    {
        "close": "4866.000",
        "ctm": "1726724700",
        "ctmfmt": "2024-09-19 13:45:00",
        "high": "4870.000",
        "low": "4864.000",
        "open": "4864.000",
        "volume": "3368",
        "wave": 0
    },
    {
        "close": "4864.000",
        "ctm": "1726724760",
        "ctmfmt": "2024-09-19 13:46:00",
        "high": "4868.000",
        "low": "4860.000",
        "open": "4864.000",
        "volume": "5458",
        "wave": 0
    },
    {
        "close": "4858.000",
        "ctm": "1726724820",
        "ctmfmt": "2024-09-19 13:47:00",
        "high": "4864.000",
        "low": "4858.000",
        "open": "4864.000",
        "volume": "4905",
        "wave": 0
    },
    {
        "close": "4858.000",
        "ctm": "1726724880",
        "ctmfmt": "2024-09-19 13:48:00",
        "high": "4862.000",
        "low": "4858.000",
        "open": "4858.000",
        "volume": "2678",
        "wave": 0
    },
    {
        "close": "4854.000",
        "ctm": "1726724940",
        "ctmfmt": "2024-09-19 13:49:00",
        "high": "4856.000",
        "low": "4854.000",
        "open": "4854.000",
        "volume": "867",
        "wave": 0
    },
    {
        "close": "4856.000",
        "ctm": "1726725000",
        "ctmfmt": "2024-09-19 13:50:00",
        "high": "4858.000",
        "low": "4854.000",
        "open": "4854.000",
        "volume": "2270",
        "wave": 0
    },
    {
        "close": "4862.000",
        "ctm": "1726725060",
        "ctmfmt": "2024-09-19 13:51:00",
        "high": "4862.000",
        "low": "4856.000",
        "open": "4856.000",
        "volume": "1341",
        "wave": 0
    },
    {
        "close": "4854.000",
        "ctm": "1726725120",
        "ctmfmt": "2024-09-19 13:52:00",
        "high": "4856.000",
        "low": "4854.000",
        "open": "4854.000",
        "volume": "1320",
        "wave": 0
    },
    {
        "close": "4852.000",
        "ctm": "1726725180",
        "ctmfmt": "2024-09-19 13:53:00",
        "high": "4854.000",
        "low": "4852.000",
        "open": "4854.000",
        "volume": "153",
        "wave": 0
    },
    {
        "close": "4856.000",
        "ctm": "1726725240",
        "ctmfmt": "2024-09-19 13:54:00",
        "high": "4856.000",
        "low": "4854.000",
        "open": "4854.000",
        "volume": "49",
        "wave": 0
    },
    {
        "close": "4854.000",
        "ctm": "1726725300",
        "ctmfmt": "2024-09-19 13:55:00",
        "high": "4858.000",
        "low": "4854.000",
        "open": "4856.000",
        "volume": "1465",
        "wave": 0
    },
    {
        "close": "4856.000",
        "ctm": "1726725360",
        "ctmfmt": "2024-09-19 13:56:00",
        "high": "4858.000",
        "low": "4856.000",
        "open": "4856.000",
        "volume": "690",
        "wave": 0
    },
    {
        "close": "4858.000",
        "ctm": "1726725420",
        "ctmfmt": "2024-09-19 13:57:00",
        "high": "4860.000",
        "low": "4856.000",
        "open": "4858.000",
        "volume": "1097",
        "wave": 0
    },
    {
        "close": "4860.000",
        "ctm": "1726725480",
        "ctmfmt": "2024-09-19 13:58:00",
        "high": "4860.000",
        "low": "4858.000",
        "open": "4860.000",
        "volume": "404",
        "wave": 0
    },
    {
        "close": "4862.000",
        "ctm": "1726725540",
        "ctmfmt": "2024-09-19 13:59:00",
        "high": "4862.000",
        "low": "4858.000",
        "open": "4860.000",
        "volume": "1163",
        "wave": 0
    },
    {
        "close": "4860.000",
        "ctm": "1726725600",
        "ctmfmt": "2024-09-19 14:00:00",
        "high": "4862.000",
        "low": "4858.000",
        "open": "4862.000",
        "volume": "817",
        "wave": 0
    },
    {
        "close": "4864.000",
        "ctm": "1726725660",
        "ctmfmt": "2024-09-19 14:01:00",
        "high": "4864.000",
        "low": "4860.000",
        "open": "4862.000",
        "volume": "1997",
        "wave": 0
    },
    {
        "close": "4868.000",
        "ctm": "1726725720",
        "ctmfmt": "2024-09-19 14:02:00",
        "high": "4868.000",
        "low": "4864.000",
        "open": "4864.000",
        "volume": "1636",
        "wave": 0
    },
    {
        "close": "4862.000",
        "ctm": "1726725780",
        "ctmfmt": "2024-09-19 14:03:00",
        "high": "4866.000",
        "low": "4862.000",
        "open": "4866.000",
        "volume": "573",
        "wave": 0
    },
    {
        "close": "4864.000",
        "ctm": "1726725840",
        "ctmfmt": "2024-09-19 14:04:00",
        "high": "4864.000",
        "low": "4860.000",
        "open": "4862.000",
        "volume": "1125",
        "wave": 0
    },
    {
        "close": "4862.000",
        "ctm": "1726725900",
        "ctmfmt": "2024-09-19 14:05:00",
        "high": "4864.000",
        "low": "4860.000",
        "open": "4864.000",
        "volume": "482",
        "wave": 0
    },
    {
        "close": "4864.000",
        "ctm": "1726725960",
        "ctmfmt": "2024-09-19 14:06:00",
        "high": "4864.000",
        "low": "4862.000",
        "open": "4864.000",
        "volume": "327",
        "wave": 0
    },
    {
        "close": "4870.000",
        "ctm": "1726726020",
        "ctmfmt": "2024-09-19 14:07:00",
        "high": "4870.000",
        "low": "4866.000",
        "open": "4866.000",
        "volume": "437",
        "wave": 0
    },
    {
        "close": "4874.000",
        "ctm": "1726726080",
        "ctmfmt": "2024-09-19 14:08:00",
        "high": "4874.000",
        "low": "4868.000",
        "open": "4870.000",
        "volume": "6523",
        "wave": 0
    },
    {
        "close": "4872.000",
        "ctm": "1726726140",
        "ctmfmt": "2024-09-19 14:09:00",
        "high": "4874.000",
        "low": "4870.000",
        "open": "4872.000",
        "volume": "3096",
        "wave": 0
    },
    {
        "close": "4868.000",
        "ctm": "1726726200",
        "ctmfmt": "2024-09-19 14:10:00",
        "high": "4868.000",
        "low": "4868.000",
        "open": "4868.000",
        "volume": "10",
        "wave": 0
    },
    {
        "close": "4864.000",
        "ctm": "1726726260",
        "ctmfmt": "2024-09-19 14:11:00",
        "high": "4866.000",
        "low": "4864.000",
        "open": "4866.000",
        "volume": "1812",
        "wave": 0
    },
    {
        "close": "4862.000",
        "ctm": "1726726320",
        "ctmfmt": "2024-09-19 14:12:00",
        "high": "4866.000",
        "low": "4862.000",
        "open": "4866.000",
        "volume": "2250",
        "wave": 0
    },
    {
        "close": "4866.000",
        "ctm": "1726726380",
        "ctmfmt": "2024-09-19 14:13:00",
        "high": "4866.000",
        "low": "4864.000",
        "open": "4866.000",
        "volume": "1261",
        "wave": 0
    },
    {
        "close": "4868.000",
        "ctm": "1726726440",
        "ctmfmt": "2024-09-19 14:14:00",
        "high": "4870.000",
        "low": "4868.000",
        "open": "4870.000",
        "volume": "1143",
        "wave": 0
    },
    {
        "close": "4872.000",
        "ctm": "1726726500",
        "ctmfmt": "2024-09-19 14:15:00",
        "high": "4872.000",
        "low": "4870.000",
        "open": "4872.000",
        "volume": "477",
        "wave": 0
    },
    {
        "close": "4878.000",
        "ctm": "1726726560",
        "ctmfmt": "2024-09-19 14:16:00",
        "high": "4878.000",
        "low": "4876.000",
        "open": "4876.000",
        "volume": "1488",
        "wave": 0
    },
    {
        "close": "4870.000",
        "ctm": "1726726620",
        "ctmfmt": "2024-09-19 14:17:00",
        "high": "4872.000",
        "low": "4870.000",
        "open": "4870.000",
        "volume": "122",
        "wave": 0
    },
    {
        "close": "4868.000",
        "ctm": "1726726680",
        "ctmfmt": "2024-09-19 14:18:00",
        "high": "4870.000",
        "low": "4866.000",
        "open": "4870.000",
        "volume": "1332",
        "wave": 0
    },
    {
        "close": "4868.000",
        "ctm": "1726726740",
        "ctmfmt": "2024-09-19 14:19:00",
        "high": "4868.000",
        "low": "4868.000",
        "open": "4868.000",
        "volume": "6",
        "wave": 0
    },
    {
        "close": "4870.000",
        "ctm": "1726726800",
        "ctmfmt": "2024-09-19 14:20:00",
        "high": "4870.000",
        "low": "4868.000",
        "open": "4868.000",
        "volume": "332",
        "wave": 0
    },
    {
        "close": "4876.000",
        "ctm": "1726726860",
        "ctmfmt": "2024-09-19 14:21:00",
        "high": "4876.000",
        "low": "4868.000",
        "open": "4870.000",
        "volume": "2872",
        "wave": 0
    },
    {
        "close": "4872.000",
        "ctm": "1726726920",
        "ctmfmt": "2024-09-19 14:22:00",
        "high": "4874.000",
        "low": "4872.000",
        "open": "4874.000",
        "volume": "2505",
        "wave": 0
    },
    {
        "close": "4872.000",
        "ctm": "1726726980",
        "ctmfmt": "2024-09-19 14:23:00",
        "high": "4878.000",
        "low": "4872.000",
        "open": "4872.000",
        "volume": "2110",
        "wave": 0
    },
    {
        "close": "4870.000",
        "ctm": "1726727040",
        "ctmfmt": "2024-09-19 14:24:00",
        "high": "4874.000",
        "low": "4870.000",
        "open": "4874.000",
        "volume": "3433",
        "wave": 0
    },
    {
        "close": "4876.000",
        "ctm": "1726727100",
        "ctmfmt": "2024-09-19 14:25:00",
        "high": "4876.000",
        "low": "4870.000",
        "open": "4870.000",
        "volume": "1646",
        "wave": 0
    },
    {
        "close": "4878.000",
        "ctm": "1726727160",
        "ctmfmt": "2024-09-19 14:26:00",
        "high": "4878.000",
        "low": "4874.000",
        "open": "4876.000",
        "volume": "889",
        "wave": 0
    },
    {
        "close": "4874.000",
        "ctm": "1726727220",
        "ctmfmt": "2024-09-19 14:27:00",
        "high": "4880.000",
        "low": "4874.000",
        "open": "4878.000",
        "volume": "3579",
        "wave": 0
    },
    {
        "close": "4874.000",
        "ctm": "1726727280",
        "ctmfmt": "2024-09-19 14:28:00",
        "high": "4874.000",
        "low": "4872.000",
        "open": "4872.000",
        "volume": "377",
        "wave": 0
    },
    {
        "close": "4878.000",
        "ctm": "1726727340",
        "ctmfmt": "2024-09-19 14:29:00",
        "high": "4878.000",
        "low": "4876.000",
        "open": "4876.000",
        "volume": "243",
        "wave": 0
    },
    {
        "close": "4878.000",
        "ctm": "1726727400",
        "ctmfmt": "2024-09-19 14:30:00",
        "high": "4878.000",
        "low": "4878.000",
        "open": "4878.000",
        "volume": "97",
        "wave": 0
    },
    {
        "close": "4878.000",
        "ctm": "1726727460",
        "ctmfmt": "2024-09-19 14:31:00",
        "high": "4880.000",
        "low": "4878.000",
        "open": "4878.000",
        "volume": "349",
        "wave": 0
    },
    {
        "close": "4874.000",
        "ctm": "1726727520",
        "ctmfmt": "2024-09-19 14:32:00",
        "high": "4876.000",
        "low": "4874.000",
        "open": "4876.000",
        "volume": "857",
        "wave": 0
    },
    {
        "close": "4876.000",
        "ctm": "1726727580",
        "ctmfmt": "2024-09-19 14:33:00",
        "high": "4876.000",
        "low": "4876.000",
        "open": "4876.000",
        "volume": "69",
        "wave": 0
    },
    {
        "close": "4878.000",
        "ctm": "1726727640",
        "ctmfmt": "2024-09-19 14:34:00",
        "high": "4880.000",
        "low": "4876.000",
        "open": "4876.000",
        "volume": "1641",
        "wave": 0
    },
    {
        "close": "4884.000",
        "ctm": "1726727700",
        "ctmfmt": "2024-09-19 14:35:00",
        "high": "4886.000",
        "low": "4878.000",
        "open": "4878.000",
        "volume": "5609",
        "wave": 0
    },
    {
        "close": "4882.000",
        "ctm": "1726727760",
        "ctmfmt": "2024-09-19 14:36:00",
        "high": "4886.000",
        "low": "4880.000",
        "open": "4884.000",
        "volume": "3488",
        "wave": 0
    },
    {
        "close": "4880.000",
        "ctm": "1726727820",
        "ctmfmt": "2024-09-19 14:37:00",
        "high": "4882.000",
        "low": "4878.000",
        "open": "4880.000",
        "volume": "408",
        "wave": 0
    },
    {
        "close": "4878.000",
        "ctm": "1726727880",
        "ctmfmt": "2024-09-19 14:38:00",
        "high": "4882.000",
        "low": "4876.000",
        "open": "4882.000",
        "volume": "2048",
        "wave": 0
    },
    {
        "close": "4872.000",
        "ctm": "1726727940",
        "ctmfmt": "2024-09-19 14:39:00",
        "high": "4878.000",
        "low": "4870.000",
        "open": "4876.000",
        "volume": "2548",
        "wave": 0
    },
    {
        "close": "4876.000",
        "ctm": "1726728000",
        "ctmfmt": "2024-09-19 14:40:00",
        "high": "4878.000",
        "low": "4872.000",
        "open": "4872.000",
        "volume": "2329",
        "wave": 0
    },
    {
        "close": "4876.000",
        "ctm": "1726728060",
        "ctmfmt": "2024-09-19 14:41:00",
        "high": "4878.000",
        "low": "4876.000",
        "open": "4878.000",
        "volume": "669",
        "wave": 0
    },
    {
        "close": "4874.000",
        "ctm": "1726728120",
        "ctmfmt": "2024-09-19 14:42:00",
        "high": "4876.000",
        "low": "4874.000",
        "open": "4874.000",
        "volume": "62",
        "wave": 0
    },
    {
        "close": "4872.000",
        "ctm": "1726728180",
        "ctmfmt": "2024-09-19 14:43:00",
        "high": "4876.000",
        "low": "4872.000",
        "open": "4876.000",
        "volume": "493",
        "wave": 0
    },
    {
        "close": "4870.000",
        "ctm": "1726728240",
        "ctmfmt": "2024-09-19 14:44:00",
        "high": "4872.000",
        "low": "4868.000",
        "open": "4872.000",
        "volume": "3099",
        "wave": 0
    },
    {
        "close": "4874.000",
        "ctm": "1726728300",
        "ctmfmt": "2024-09-19 14:45:00",
        "high": "4874.000",
        "low": "4872.000",
        "open": "4872.000",
        "volume": "123",
        "wave": 0
    },
    {
        "close": "4872.000",
        "ctm": "1726728360",
        "ctmfmt": "2024-09-19 14:46:00",
        "high": "4876.000",
        "low": "4872.000",
        "open": "4874.000",
        "volume": "1299",
        "wave": 0
    },
    {
        "close": "4872.000",
        "ctm": "1726728420",
        "ctmfmt": "2024-09-19 14:47:00",
        "high": "4874.000",
        "low": "4870.000",
        "open": "4874.000",
        "volume": "1498",
        "wave": 0
    },
    {
        "close": "4874.000",
        "ctm": "1726728480",
        "ctmfmt": "2024-09-19 14:48:00",
        "high": "4874.000",
        "low": "4870.000",
        "open": "4870.000",
        "volume": "1399",
        "wave": 0
    },
    {
        "close": "4880.000",
        "ctm": "1726728540",
        "ctmfmt": "2024-09-19 14:49:00",
        "high": "4882.000",
        "low": "4872.000",
        "open": "4874.000",
        "volume": "2987",
        "wave": 0
    },
    {
        "close": "4882.000",
        "ctm": "1726728600",
        "ctmfmt": "2024-09-19 14:50:00",
        "high": "4884.000",
        "low": "4880.000",
        "open": "4880.000",
        "volume": "1988",
        "wave": 0
    },
    {
        "close": "4886.000",
        "ctm": "1726728660",
        "ctmfmt": "2024-09-19 14:51:00",
        "high": "4888.000",
        "low": "4882.000",
        "open": "4882.000",
        "volume": "6205",
        "wave": 0
    },
    {
        "close": "4886.000",
        "ctm": "1726728720",
        "ctmfmt": "2024-09-19 14:52:00",
        "high": "4888.000",
        "low": "4884.000",
        "open": "4886.000",
        "volume": "2434",
        "wave": 0
    },
    {
        "close": "4884.000",
        "ctm": "1726728780",
        "ctmfmt": "2024-09-19 14:53:00",
        "high": "4886.000",
        "low": "4884.000",
        "open": "4886.000",
        "volume": "174",
        "wave": 0
    },
    {
        "close": "4882.000",
        "ctm": "1726728840",
        "ctmfmt": "2024-09-19 14:54:00",
        "high": "4882.000",
        "low": "4882.000",
        "open": "4882.000",
        "volume": "586",
        "wave": 0
    },
    {
        "close": "4886.000",
        "ctm": "1726728900",
        "ctmfmt": "2024-09-19 14:55:00",
        "high": "4886.000",
        "low": "4882.000",
        "open": "4884.000",
        "volume": "1912",
        "wave": 0
    },
    {
        "close": "4880.000",
        "ctm": "1726728960",
        "ctmfmt": "2024-09-19 14:56:00",
        "high": "4882.000",
        "low": "4880.000",
        "open": "4882.000",
        "volume": "88",
        "wave": 0
    },
    {
        "close": "4884.000",
        "ctm": "1726729020",
        "ctmfmt": "2024-09-19 14:57:00",
        "high": "4886.000",
        "low": "4882.000",
        "open": "4884.000",
        "volume": "799",
        "wave": 0
    },
    {
        "close": "4886.000",
        "ctm": "1726729080",
        "ctmfmt": "2024-09-19 14:58:00",
        "high": "4886.000",
        "low": "4882.000",
        "open": "4886.000",
        "volume": "2926",
        "wave": 0
    },
    {
        "close": "4882.000",
        "ctm": "1726729140",
        "ctmfmt": "2024-09-19 14:59:00",
        "high": "4888.000",
        "low": "4882.000",
        "open": "4884.000",
        "volume": "3988",
        "wave": 0
    },
    {
        "close": "4882.000",
        "ctm": "1726729200",
        "ctmfmt": "2024-09-19 15:00:00",
        "high": "4884.000",
        "low": "4878.000",
        "open": "4884.000",
        "volume": "7788",
        "wave": 0
    },
    {
        "close": "4886.000",
        "ctm": "1726750860",
        "ctmfmt": "2024-09-19 21:01:00",
        "high": "4890.000",
        "low": "4874.000",
        "open": "4890.000",
        "volume": "948750",
        "wave": 0
    },
    {
        "close": "4878.000",
        "ctm": "1726750920",
        "ctmfmt": "2024-09-19 21:02:00",
        "high": "4888.000",
        "low": "4876.000",
        "open": "4888.000",
        "volume": "527482",
        "wave": 0
    },
    {
        "close": "4872.000",
        "ctm": "1726750980",
        "ctmfmt": "2024-09-19 21:03:00",
        "high": "4878.000",
        "low": "4870.000",
        "open": "4876.000",
        "volume": "431658",
        "wave": 0
    },
    {
        "close": "4878.000",
        "ctm": "1726751040",
        "ctmfmt": "2024-09-19 21:04:00",
        "high": "4878.000",
        "low": "4872.000",
        "open": "4874.000",
        "volume": "320032",
        "wave": 0
    },
    {
        "close": "4876.000",
        "ctm": "1726751100",
        "ctmfmt": "2024-09-19 21:05:00",
        "high": "4878.000",
        "low": "4872.000",
        "open": "4878.000",
        "volume": "236610",
        "wave": 0
    },
    {
        "close": "4874.000",
        "ctm": "1726751160",
        "ctmfmt": "2024-09-19 21:06:00",
        "high": "4878.000",
        "low": "4872.000",
        "open": "4874.000",
        "volume": "186728",
        "wave": 0
    },
    {
        "close": "4870.000",
        "ctm": "1726751220",
        "ctmfmt": "2024-09-19 21:07:00",
        "high": "4876.000",
        "low": "4866.000",
        "open": "4876.000",
        "volume": "288160",
        "wave": 0
    },
    {
        "close": "4872.000",
        "ctm": "1726751280",
        "ctmfmt": "2024-09-19 21:08:00",
        "high": "4876.000",
        "low": "4870.000",
        "open": "4870.000",
        "volume": "129224",
        "wave": 0
    },
    {
        "close": "4874.000",
        "ctm": "1726751340",
        "ctmfmt": "2024-09-19 21:09:00",
        "high": "4878.000",
        "low": "4872.000",
        "open": "4874.000",
        "volume": "176683",
        "wave": 0
    },
    {
        "close": "4870.000",
        "ctm": "1726751400",
        "ctmfmt": "2024-09-19 21:10:00",
        "high": "4876.000",
        "low": "4870.000",
        "open": "4874.000",
        "volume": "131053",
        "wave": 0
    },
    {
        "close": "4868.000",
        "ctm": "1726751460",
        "ctmfmt": "2024-09-19 21:11:00",
        "high": "4874.000",
        "low": "4866.000",
        "open": "4870.000",
        "volume": "188125",
        "wave": 0
    },
    {
        "close": "4866.000",
        "ctm": "1726751520",
        "ctmfmt": "2024-09-19 21:12:00",
        "high": "4868.000",
        "low": "4864.000",
        "open": "4868.000",
        "volume": "284246",
        "wave": 0
    },
    {
        "close": "4870.000",
        "ctm": "1726751580",
        "ctmfmt": "2024-09-19 21:13:00",
        "high": "4870.000",
        "low": "4866.000",
        "open": "4866.000",
        "volume": "123698",
        "wave": 0
    },
    {
        "close": "4868.000",
        "ctm": "1726751640",
        "ctmfmt": "2024-09-19 21:14:00",
        "high": "4870.000",
        "low": "4866.000",
        "open": "4868.000",
        "volume": "126791",
        "wave": 0
    },
    {
        "close": "4868.000",
        "ctm": "1726751700",
        "ctmfmt": "2024-09-19 21:15:00",
        "high": "4870.000",
        "low": "4864.000",
        "open": "4870.000",
        "volume": "93553",
        "wave": 0
    },
    {
        "close": "4856.000",
        "ctm": "1726751760",
        "ctmfmt": "2024-09-19 21:16:00",
        "high": "4868.000",
        "low": "4856.000",
        "open": "4866.000",
        "volume": "421291",
        "wave": 0
    },
    {
        "close": "4860.000",
        "ctm": "1726751820",
        "ctmfmt": "2024-09-19 21:17:00",
        "high": "4862.000",
        "low": "4858.000",
        "open": "4858.000",
        "volume": "5404",
        "wave": 0
    },
    {
        "close": "4856.000",
        "ctm": "1726751880",
        "ctmfmt": "2024-09-19 21:18:00",
        "high": "4860.000",
        "low": "4854.000",
        "open": "4860.000",
        "volume": "195447",
        "wave": 0
    },
    {
        "close": "4854.000",
        "ctm": "1726751940",
        "ctmfmt": "2024-09-19 21:19:00",
        "high": "4858.000",
        "low": "4854.000",
        "open": "4856.000",
        "volume": "138471",
        "wave": 0
    },
    {
        "close": "4864.000",
        "ctm": "1726752000",
        "ctmfmt": "2024-09-19 21:20:00",
        "high": "4866.000",
        "low": "4854.000",
        "open": "4854.000",
        "volume": "223464",
        "wave": 0
    },
    {
        "close": "4866.000",
        "ctm": "1726752060",
        "ctmfmt": "2024-09-19 21:21:00",
        "high": "4870.000",
        "low": "4862.000",
        "open": "4864.000",
        "volume": "302796",
        "wave": 0
    },
    {
        "close": "4864.000",
        "ctm": "1726752120",
        "ctmfmt": "2024-09-19 21:22:00",
        "high": "4866.000",
        "low": "4860.000",
        "open": "4864.000",
        "volume": "96918",
        "wave": 0
    },
    {
        "close": "4858.000",
        "ctm": "1726752180",
        "ctmfmt": "2024-09-19 21:23:00",
        "high": "4868.000",
        "low": "4856.000",
        "open": "4864.000",
        "volume": "201706",
        "wave": 0
    },
    {
        "close": "4852.000",
        "ctm": "1726752240",
        "ctmfmt": "2024-09-19 21:24:00",
        "high": "4858.000",
        "low": "4852.000",
        "open": "4858.000",
        "volume": "326003",
        "wave": 0
    },
    {
        "close": "4860.000",
        "ctm": "1726752300",
        "ctmfmt": "2024-09-19 21:25:00",
        "high": "4860.000",
        "low": "4854.000",
        "open": "4856.000",
        "volume": "138358",
        "wave": 0
    },
    {
        "close": "4856.000",
        "ctm": "1726752360",
        "ctmfmt": "2024-09-19 21:26:00",
        "high": "4862.000",
        "low": "4856.000",
        "open": "4858.000",
        "volume": "106336",
        "wave": 0
    },
    {
        "close": "4854.000",
        "ctm": "1726752420",
        "ctmfmt": "2024-09-19 21:27:00",
        "high": "4860.000",
        "low": "4854.000",
        "open": "4856.000",
        "volume": "160286",
        "wave": 0
    },
    {
        "close": "4856.000",
        "ctm": "1726752480",
        "ctmfmt": "2024-09-19 21:28:00",
        "high": "4858.000",
        "low": "4852.000",
        "open": "4854.000",
        "volume": "164249",
        "wave": 0
    },
    {
        "close": "4858.000",
        "ctm": "1726752540",
        "ctmfmt": "2024-09-19 21:29:00",
        "high": "4860.000",
        "low": "4854.000",
        "open": "4858.000",
        "volume": "109721",
        "wave": 0
    },
    {
        "close": "4858.000",
        "ctm": "1726752600",
        "ctmfmt": "2024-09-19 21:30:00",
        "high": "4862.000",
        "low": "4856.000",
        "open": "4858.000",
        "volume": "107834",
        "wave": 0
    },
    {
        "close": "4858.000",
        "ctm": "1726752660",
        "ctmfmt": "2024-09-19 21:31:00",
        "high": "4860.000",
        "low": "4856.000",
        "open": "4860.000",
        "volume": "49946",
        "wave": 0
    },
    {
        "close": "4858.000",
        "ctm": "1726752720",
        "ctmfmt": "2024-09-19 21:32:00",
        "high": "4862.000",
        "low": "4856.000",
        "open": "4856.000",
        "volume": "83726",
        "wave": 0
    },
    {
        "close": "4858.000",
        "ctm": "1726752780",
        "ctmfmt": "2024-09-19 21:33:00",
        "high": "4862.000",
        "low": "4856.000",
        "open": "4858.000",
        "volume": "47354",
        "wave": 0
    },
    {
        "close": "4856.000",
        "ctm": "1726752840",
        "ctmfmt": "2024-09-19 21:34:00",
        "high": "4858.000",
        "low": "4852.000",
        "open": "4858.000",
        "volume": "125615",
        "wave": 0
    },
    {
        "close": "4854.000",
        "ctm": "1726752900",
        "ctmfmt": "2024-09-19 21:35:00",
        "high": "4856.000",
        "low": "4854.000",
        "open": "4856.000",
        "volume": "33428",
        "wave": 0
    },
    {
        "close": "4856.000",
        "ctm": "1726752960",
        "ctmfmt": "2024-09-19 21:36:00",
        "high": "4858.000",
        "low": "4852.000",
        "open": "4856.000",
        "volume": "59552",
        "wave": 0
    },
    {
        "close": "4860.000",
        "ctm": "1726753020",
        "ctmfmt": "2024-09-19 21:37:00",
        "high": "4862.000",
        "low": "4856.000",
        "open": "4858.000",
        "volume": "86313",
        "wave": 0
    },
    {
        "close": "4872.000",
        "ctm": "1726753080",
        "ctmfmt": "2024-09-19 21:38:00",
        "high": "4872.000",
        "low": "4858.000",
        "open": "4860.000",
        "volume": "254417",
        "wave": 0
    },
    {
        "close": "4870.000",
        "ctm": "1726753140",
        "ctmfmt": "2024-09-19 21:39:00",
        "high": "4870.000",
        "low": "4866.000",
        "open": "4870.000",
        "volume": "161457",
        "wave": 0
    },
    {
        "close": "4874.000",
        "ctm": "1726753200",
        "ctmfmt": "2024-09-19 21:40:00",
        "high": "4874.000",
        "low": "4868.000",
        "open": "4870.000",
        "volume": "304575",
        "wave": 0
    },
    {
        "close": "4886.000",
        "ctm": "1726753260",
        "ctmfmt": "2024-09-19 21:41:00",
        "high": "4886.000",
        "low": "4872.000",
        "open": "4874.000",
        "volume": "673966",
        "wave": 0
    },
    {
        "close": "4878.000",
        "ctm": "1726753320",
        "ctmfmt": "2024-09-19 21:42:00",
        "high": "4886.000",
        "low": "4878.000",
        "open": "4886.000",
        "volume": "138774",
        "wave": 0
    },
    {
        "close": "4876.000",
        "ctm": "1726753380",
        "ctmfmt": "2024-09-19 21:43:00",
        "high": "4880.000",
        "low": "4874.000",
        "open": "4878.000",
        "volume": "138811",
        "wave": 0
    },
    {
        "close": "4870.000",
        "ctm": "1726753440",
        "ctmfmt": "2024-09-19 21:44:00",
        "high": "4876.000",
        "low": "4870.000",
        "open": "4876.000",
        "volume": "87720",
        "wave": 0
    },
    {
        "close": "4868.000",
        "ctm": "1726753500",
        "ctmfmt": "2024-09-19 21:45:00",
        "high": "4870.000",
        "low": "4866.000",
        "open": "4868.000",
        "volume": "144010",
        "wave": 0
    },
    {
        "close": "4868.000",
        "ctm": "1726753560",
        "ctmfmt": "2024-09-19 21:46:00",
        "high": "4870.000",
        "low": "4868.000",
        "open": "4868.000",
        "volume": "78106",
        "wave": 0
    },
    {
        "close": "4874.000",
        "ctm": "1726753620",
        "ctmfmt": "2024-09-19 21:47:00",
        "high": "4874.000",
        "low": "4868.000",
        "open": "4868.000",
        "volume": "55547",
        "wave": 0
    },
    {
        "close": "4878.000",
        "ctm": "1726753680",
        "ctmfmt": "2024-09-19 21:48:00",
        "high": "4878.000",
        "low": "4872.000",
        "open": "4874.000",
        "volume": "81060",
        "wave": 0
    },
    {
        "close": "4872.000",
        "ctm": "1726753740",
        "ctmfmt": "2024-09-19 21:49:00",
        "high": "4878.000",
        "low": "4872.000",
        "open": "4878.000",
        "volume": "109680",
        "wave": 0
    },
    {
        "close": "4866.000",
        "ctm": "1726753800",
        "ctmfmt": "2024-09-19 21:50:00",
        "high": "4874.000",
        "low": "4864.000",
        "open": "4872.000",
        "volume": "167096",
        "wave": 0
    },
    {
        "close": "4864.000",
        "ctm": "1726753860",
        "ctmfmt": "2024-09-19 21:51:00",
        "high": "4868.000",
        "low": "4862.000",
        "open": "4866.000",
        "volume": "103184",
        "wave": 0
    },
    {
        "close": "4860.000",
        "ctm": "1726753920",
        "ctmfmt": "2024-09-19 21:52:00",
        "high": "4864.000",
        "low": "4858.000",
        "open": "4862.000",
        "volume": "183198",
        "wave": 0
    },
    {
        "close": "4866.000",
        "ctm": "1726753980",
        "ctmfmt": "2024-09-19 21:53:00",
        "high": "4868.000",
        "low": "4862.000",
        "open": "4862.000",
        "volume": "133419",
        "wave": 0
    },
    {
        "close": "4868.000",
        "ctm": "1726754040",
        "ctmfmt": "2024-09-19 21:54:00",
        "high": "4870.000",
        "low": "4864.000",
        "open": "4866.000",
        "volume": "110640",
        "wave": 0
    },
    {
        "close": "4868.000",
        "ctm": "1726754100",
        "ctmfmt": "2024-09-19 21:55:00",
        "high": "4872.000",
        "low": "4866.000",
        "open": "4868.000",
        "volume": "87881",
        "wave": 0
    },
    {
        "close": "4870.000",
        "ctm": "1726754160",
        "ctmfmt": "2024-09-19 21:56:00",
        "high": "4870.000",
        "low": "4866.000",
        "open": "4868.000",
        "volume": "99778",
        "wave": 0
    },
    {
        "close": "4874.000",
        "ctm": "1726754220",
        "ctmfmt": "2024-09-19 21:57:00",
        "high": "4876.000",
        "low": "4870.000",
        "open": "4870.000",
        "volume": "113783",
        "wave": 0
    },
    {
        "close": "4870.000",
        "ctm": "1726754280",
        "ctmfmt": "2024-09-19 21:58:00",
        "high": "4874.000",
        "low": "4868.000",
        "open": "4874.000",
        "volume": "75170",
        "wave": 0
    },
    {
        "close": "4868.000",
        "ctm": "1726754340",
        "ctmfmt": "2024-09-19 21:59:00",
        "high": "4872.000",
        "low": "4868.000",
        "open": "4870.000",
        "volume": "57974",
        "wave": 0
    },
    {
        "close": "4868.000",
        "ctm": "1726754400",
        "ctmfmt": "2024-09-19 22:00:00",
        "high": "4870.000",
        "low": "4866.000",
        "open": "4868.000",
        "volume": "67260",
        "wave": 0
    },
    {
        "close": "4870.000",
        "ctm": "1726754460",
        "ctmfmt": "2024-09-19 22:01:00",
        "high": "4872.000",
        "low": "4866.000",
        "open": "4866.000",
        "volume": "106849",
        "wave": 0
    },
    {
        "close": "4870.000",
        "ctm": "1726754520",
        "ctmfmt": "2024-09-19 22:02:00",
        "high": "4872.000",
        "low": "4866.000",
        "open": "4870.000",
        "volume": "73328",
        "wave": 0
    },
    {
        "close": "4866.000",
        "ctm": "1726754580",
        "ctmfmt": "2024-09-19 22:03:00",
        "high": "4870.000",
        "low": "4864.000",
        "open": "4870.000",
        "volume": "108087",
        "wave": 0
    },
    {
        "close": "4872.000",
        "ctm": "1726754640",
        "ctmfmt": "2024-09-19 22:04:00",
        "high": "4872.000",
        "low": "4866.000",
        "open": "4866.000",
        "volume": "60464",
        "wave": 0
    },
    {
        "close": "4878.000",
        "ctm": "1726754700",
        "ctmfmt": "2024-09-19 22:05:00",
        "high": "4878.000",
        "low": "4872.000",
        "open": "4872.000",
        "volume": "115465",
        "wave": 0
    },
    {
        "close": "4872.000",
        "ctm": "1726754760",
        "ctmfmt": "2024-09-19 22:06:00",
        "high": "4878.000",
        "low": "4872.000",
        "open": "4878.000",
        "volume": "148866",
        "wave": 0
    },
    {
        "close": "4872.000",
        "ctm": "1726754820",
        "ctmfmt": "2024-09-19 22:07:00",
        "high": "4874.000",
        "low": "4870.000",
        "open": "4872.000",
        "volume": "33395",
        "wave": 0
    },
    {
        "close": "4874.000",
        "ctm": "1726754880",
        "ctmfmt": "2024-09-19 22:08:00",
        "high": "4878.000",
        "low": "4872.000",
        "open": "4872.000",
        "volume": "63969",
        "wave": 0
    },
    {
        "close": "4876.000",
        "ctm": "1726754940",
        "ctmfmt": "2024-09-19 22:09:00",
        "high": "4878.000",
        "low": "4872.000",
        "open": "4872.000",
        "volume": "79504",
        "wave": 0
    },
    {
        "close": "4876.000",
        "ctm": "1726755000",
        "ctmfmt": "2024-09-19 22:10:00",
        "high": "4878.000",
        "low": "4874.000",
        "open": "4874.000",
        "volume": "50984",
        "wave": 0
    },
    {
        "close": "4872.000",
        "ctm": "1726755060",
        "ctmfmt": "2024-09-19 22:11:00",
        "high": "4876.000",
        "low": "4872.000",
        "open": "4874.000",
        "volume": "68034",
        "wave": 0
    },
    {
        "close": "4874.000",
        "ctm": "1726755120",
        "ctmfmt": "2024-09-19 22:12:00",
        "high": "4876.000",
        "low": "4872.000",
        "open": "4872.000",
        "volume": "27441",
        "wave": 0
    },
    {
        "close": "4876.000",
        "ctm": "1726755180",
        "ctmfmt": "2024-09-19 22:13:00",
        "high": "4878.000",
        "low": "4872.000",
        "open": "4872.000",
        "volume": "26378",
        "wave": 0
    },
    {
        "close": "4874.000",
        "ctm": "1726755240",
        "ctmfmt": "2024-09-19 22:14:00",
        "high": "4876.000",
        "low": "4872.000",
        "open": "4876.000",
        "volume": "25641",
        "wave": 0
    },
    {
        "close": "4874.000",
        "ctm": "1726755300",
        "ctmfmt": "2024-09-19 22:15:00",
        "high": "4876.000",
        "low": "4872.000",
        "open": "4874.000",
        "volume": "46512",
        "wave": 0
    },
    {
        "close": "4878.000",
        "ctm": "1726755360",
        "ctmfmt": "2024-09-19 22:16:00",
        "high": "4878.000",
        "low": "4872.000",
        "open": "4874.000",
        "volume": "54483",
        "wave": 0
    },
    {
        "close": "4870.000",
        "ctm": "1726755420",
        "ctmfmt": "2024-09-19 22:17:00",
        "high": "4878.000",
        "low": "4870.000",
        "open": "4878.000",
        "volume": "113078",
        "wave": 0
    },
    {
        "close": "4876.000",
        "ctm": "1726755480",
        "ctmfmt": "2024-09-19 22:18:00",
        "high": "4876.000",
        "low": "4870.000",
        "open": "4870.000",
        "volume": "76257",
        "wave": 0
    },
    {
        "close": "4878.000",
        "ctm": "1726755540",
        "ctmfmt": "2024-09-19 22:19:00",
        "high": "4878.000",
        "low": "4874.000",
        "open": "4876.000",
        "volume": "48063",
        "wave": 0
    },
    {
        "close": "4884.000",
        "ctm": "1726755600",
        "ctmfmt": "2024-09-19 22:20:00",
        "high": "4886.000",
        "low": "4876.000",
        "open": "4878.000",
        "volume": "169006",
        "wave": 0
    },
    {
        "close": "4882.000",
        "ctm": "1726755660",
        "ctmfmt": "2024-09-19 22:21:00",
        "high": "4886.000",
        "low": "4880.000",
        "open": "4884.000",
        "volume": "131328",
        "wave": 0
    },
    {
        "close": "4880.000",
        "ctm": "1726755720",
        "ctmfmt": "2024-09-19 22:22:00",
        "high": "4884.000",
        "low": "4878.000",
        "open": "4882.000",
        "volume": "74612",
        "wave": 0
    },
    {
        "close": "4878.000",
        "ctm": "1726755780",
        "ctmfmt": "2024-09-19 22:23:00",
        "high": "4882.000",
        "low": "4878.000",
        "open": "4880.000",
        "volume": "26808",
        "wave": 0
    },
    {
        "close": "4878.000",
        "ctm": "1726755840",
        "ctmfmt": "2024-09-19 22:24:00",
        "high": "4878.000",
        "low": "4876.000",
        "open": "4878.000",
        "volume": "26867",
        "wave": 0
    },
    {
        "close": "4878.000",
        "ctm": "1726755900",
        "ctmfmt": "2024-09-19 22:25:00",
        "high": "4878.000",
        "low": "4872.000",
        "open": "4878.000",
        "volume": "55471",
        "wave": 0
    },
    {
        "close": "4882.000",
        "ctm": "1726755960",
        "ctmfmt": "2024-09-19 22:26:00",
        "high": "4884.000",
        "low": "4878.000",
        "open": "4878.000",
        "volume": "65959",
        "wave": 0
    },
    {
        "close": "4882.000",
        "ctm": "1726756020",
        "ctmfmt": "2024-09-19 22:27:00",
        "high": "4882.000",
        "low": "4878.000",
        "open": "4882.000",
        "volume": "64941",
        "wave": 0
    },
    {
        "close": "4882.000",
        "ctm": "1726756080",
        "ctmfmt": "2024-09-19 22:28:00",
        "high": "4884.000",
        "low": "4880.000",
        "open": "4882.000",
        "volume": "46489",
        "wave": 0
    },
    {
        "close": "4876.000",
        "ctm": "1726756140",
        "ctmfmt": "2024-09-19 22:29:00",
        "high": "4882.000",
        "low": "4876.000",
        "open": "4882.000",
        "volume": "50650",
        "wave": 0
    },
    {
        "close": "4878.000",
        "ctm": "1726756200",
        "ctmfmt": "2024-09-19 22:30:00",
        "high": "4880.000",
        "low": "4876.000",
        "open": "4876.000",
        "volume": "28443",
        "wave": 0
    },
    {
        "close": "4886.000",
        "ctm": "1726756260",
        "ctmfmt": "2024-09-19 22:31:00",
        "high": "4886.000",
        "low": "4876.000",
        "open": "4878.000",
        "volume": "68180",
        "wave": 0
    },
    {
        "close": "4882.000",
        "ctm": "1726756320",
        "ctmfmt": "2024-09-19 22:32:00",
        "high": "4886.000",
        "low": "4880.000",
        "open": "4886.000",
        "volume": "43695",
        "wave": 0
    },
    {
        "close": "4882.000",
        "ctm": "1726756380",
        "ctmfmt": "2024-09-19 22:33:00",
        "high": "4882.000",
        "low": "4878.000",
        "open": "4882.000",
        "volume": "40210",
        "wave": 0
    },
    {
        "close": "4882.000",
        "ctm": "1726756440",
        "ctmfmt": "2024-09-19 22:34:00",
        "high": "4882.000",
        "low": "4878.000",
        "open": "4880.000",
        "volume": "37699",
        "wave": 0
    },
    {
        "close": "4880.000",
        "ctm": "1726756500",
        "ctmfmt": "2024-09-19 22:35:00",
        "high": "4884.000",
        "low": "4878.000",
        "open": "4884.000",
        "volume": "38425",
        "wave": 0
    },
    {
        "close": "4882.000",
        "ctm": "1726756560",
        "ctmfmt": "2024-09-19 22:36:00",
        "high": "4884.000",
        "low": "4878.000",
        "open": "4880.000",
        "volume": "35478",
        "wave": 0
    },
    {
        "close": "4876.000",
        "ctm": "1726756620",
        "ctmfmt": "2024-09-19 22:37:00",
        "high": "4882.000",
        "low": "4874.000",
        "open": "4882.000",
        "volume": "55718",
        "wave": 0
    },
    {
        "close": "4878.000",
        "ctm": "1726756680",
        "ctmfmt": "2024-09-19 22:38:00",
        "high": "4882.000",
        "low": "4874.000",
        "open": "4876.000",
        "volume": "51441",
        "wave": 0
    },
    {
        "close": "4876.000",
        "ctm": "1726756740",
        "ctmfmt": "2024-09-19 22:39:00",
        "high": "4880.000",
        "low": "4876.000",
        "open": "4878.000",
        "volume": "21071",
        "wave": 0
    },
    {
        "close": "4876.000",
        "ctm": "1726756800",
        "ctmfmt": "2024-09-19 22:40:00",
        "high": "4882.000",
        "low": "4876.000",
        "open": "4876.000",
        "volume": "42026",
        "wave": 0
    },
    {
        "close": "4876.000",
        "ctm": "1726756860",
        "ctmfmt": "2024-09-19 22:41:00",
        "high": "4882.000",
        "low": "4876.000",
        "open": "4878.000",
        "volume": "28593",
        "wave": 0
    },
    {
        "close": "4880.000",
        "ctm": "1726756920",
        "ctmfmt": "2024-09-19 22:42:00",
        "high": "4880.000",
        "low": "4876.000",
        "open": "4876.000",
        "volume": "33007",
        "wave": 0
    },
    {
        "close": "4874.000",
        "ctm": "1726756980",
        "ctmfmt": "2024-09-19 22:43:00",
        "high": "4880.000",
        "low": "4872.000",
        "open": "4880.000",
        "volume": "63376",
        "wave": 0
    },
    {
        "close": "4876.000",
        "ctm": "1726757040",
        "ctmfmt": "2024-09-19 22:44:00",
        "high": "4876.000",
        "low": "4872.000",
        "open": "4874.000",
        "volume": "45794",
        "wave": 0
    },
    {
        "close": "4878.000",
        "ctm": "1726757100",
        "ctmfmt": "2024-09-19 22:45:00",
        "high": "4878.000",
        "low": "4874.000",
        "open": "4876.000",
        "volume": "38352",
        "wave": 0
    },
    {
        "close": "4872.000",
        "ctm": "1726757160",
        "ctmfmt": "2024-09-19 22:46:00",
        "high": "4878.000",
        "low": "4870.000",
        "open": "4876.000",
        "volume": "90334",
        "wave": 0
    },
    {
        "close": "4868.000",
        "ctm": "1726757220",
        "ctmfmt": "2024-09-19 22:47:00",
        "high": "4872.000",
        "low": "4868.000",
        "open": "4872.000",
        "volume": "95629",
        "wave": 0
    },
    {
        "close": "4870.000",
        "ctm": "1726757280",
        "ctmfmt": "2024-09-19 22:48:00",
        "high": "4874.000",
        "low": "4868.000",
        "open": "4870.000",
        "volume": "58136",
        "wave": 0
    },
    {
        "close": "4874.000",
        "ctm": "1726757340",
        "ctmfmt": "2024-09-19 22:49:00",
        "high": "4874.000",
        "low": "4870.000",
        "open": "4870.000",
        "volume": "34699",
        "wave": 0
    },
    {
        "close": "4874.000",
        "ctm": "1726757400",
        "ctmfmt": "2024-09-19 22:50:00",
        "high": "4876.000",
        "low": "4872.000",
        "open": "4874.000",
        "volume": "54760",
        "wave": 0
    },
    {
        "close": "4878.000",
        "ctm": "1726757460",
        "ctmfmt": "2024-09-19 22:51:00",
        "high": "4880.000",
        "low": "4874.000",
        "open": "4874.000",
        "volume": "50387",
        "wave": 0
    },
    {
        "close": "4878.000",
        "ctm": "1726757520",
        "ctmfmt": "2024-09-19 22:52:00",
        "high": "4880.000",
        "low": "4876.000",
        "open": "4876.000",
        "volume": "22063",
        "wave": 0
    },
    {
        "close": "4876.000",
        "ctm": "1726757580",
        "ctmfmt": "2024-09-19 22:53:00",
        "high": "4882.000",
        "low": "4876.000",
        "open": "4878.000",
        "volume": "74382",
        "wave": 0
    },
    {
        "close": "4878.000",
        "ctm": "1726757640",
        "ctmfmt": "2024-09-19 22:54:00",
        "high": "4880.000",
        "low": "4876.000",
        "open": "4876.000",
        "volume": "36398",
        "wave": 0
    },
    {
        "close": "4878.000",
        "ctm": "1726757700",
        "ctmfmt": "2024-09-19 22:55:00",
        "high": "4878.000",
        "low": "4876.000",
        "open": "4878.000",
        "volume": "15977",
        "wave": 0
    },
    {
        "close": "4878.000",
        "ctm": "1726757760",
        "ctmfmt": "2024-09-19 22:56:00",
        "high": "4880.000",
        "low": "4874.000",
        "open": "4876.000",
        "volume": "71776",
        "wave": 0
    },
    {
        "close": "4878.000",
        "ctm": "1726757820",
        "ctmfmt": "2024-09-19 22:57:00",
        "high": "4880.000",
        "low": "4876.000",
        "open": "4878.000",
        "volume": "38723",
        "wave": 0
    },
    {
        "close": "4878.000",
        "ctm": "1726757880",
        "ctmfmt": "2024-09-19 22:58:00",
        "high": "4880.000",
        "low": "4876.000",
        "open": "4878.000",
        "volume": "42048",
        "wave": 0
    },
    {
        "close": "4882.000",
        "ctm": "1726757940",
        "ctmfmt": "2024-09-19 22:59:00",
        "high": "4882.000",
        "low": "4876.000",
        "open": "4876.000",
        "volume": "56690",
        "wave": 0
    },
    {
        "close": "4886.000",
        "ctm": "1726758000",
        "ctmfmt": "2024-09-19 23:00:00",
        "high": "4886.000",
        "low": "4878.000",
        "open": "4882.000",
        "volume": "100820",
        "wave": 0
    },
    {
        "close": "4872.000",
        "ctm": "1726794060",
        "ctmfmt": "2024-09-20 09:01:00",
        "high": "4886.000",
        "low": "4870.000",
        "open": "4886.000",
        "volume": "352424",
        "wave": 0
    },
    {
        "close": "4860.000",
        "ctm": "1726794120",
        "ctmfmt": "2024-09-20 09:02:00",
        "high": "4872.000",
        "low": "4858.000",
        "open": "4872.000",
        "volume": "322351",
        "wave": 0
    },
    {
        "close": "4856.000",
        "ctm": "1726794180",
        "ctmfmt": "2024-09-20 09:03:00",
        "high": "4864.000",
        "low": "4854.000",
        "open": "4860.000",
        "volume": "233475",
        "wave": 0
    },
    {
        "close": "4848.000",
        "ctm": "1726794240",
        "ctmfmt": "2024-09-20 09:04:00",
        "high": "4856.000",
        "low": "4846.000",
        "open": "4854.000",
        "volume": "359010",
        "wave": 0
    },
    {
        "close": "4844.000",
        "ctm": "1726794300",
        "ctmfmt": "2024-09-20 09:05:00",
        "high": "4848.000",
        "low": "4844.000",
        "open": "4848.000",
        "volume": "196230",
        "wave": 0
    },
    {
        "close": "4846.000",
        "ctm": "1726794360",
        "ctmfmt": "2024-09-20 09:06:00",
        "high": "4852.000",
        "low": "4844.000",
        "open": "4844.000",
        "volume": "164070",
        "wave": 0
    },
    {
        "close": "4840.000",
        "ctm": "1726794420",
        "ctmfmt": "2024-09-20 09:07:00",
        "high": "4846.000",
        "low": "4838.000",
        "open": "4846.000",
        "volume": "419672",
        "wave": 0
    },
    {
        "close": "4840.000",
        "ctm": "1726794480",
        "ctmfmt": "2024-09-20 09:08:00",
        "high": "4842.000",
        "low": "4836.000",
        "open": "4838.000",
        "volume": "259521",
        "wave": 0
    },
    {
        "close": "4838.000",
        "ctm": "1726794540",
        "ctmfmt": "2024-09-20 09:09:00",
        "high": "4844.000",
        "low": "4836.000",
        "open": "4842.000",
        "volume": "150162",
        "wave": 0
    },
    {
        "close": "4836.000",
        "ctm": "1726794600",
        "ctmfmt": "2024-09-20 09:10:00",
        "high": "4838.000",
        "low": "4832.000",
        "open": "4836.000",
        "volume": "375782",
        "wave": 0
    },
    {
        "close": "4832.000",
        "ctm": "1726794660",
        "ctmfmt": "2024-09-20 09:11:00",
        "high": "4838.000",
        "low": "4826.000",
        "open": "4836.000",
        "volume": "289853",
        "wave": 0
    },
    {
        "close": "4826.000",
        "ctm": "1726794720",
        "ctmfmt": "2024-09-20 09:12:00",
        "high": "4830.000",
        "low": "4824.000",
        "open": "4830.000",
        "volume": "274874",
        "wave": 0
    },
    {
        "close": "4832.000",
        "ctm": "1726794780",
        "ctmfmt": "2024-09-20 09:13:00",
        "high": "4834.000",
        "low": "4828.000",
        "open": "4828.000",
        "volume": "258496",
        "wave": 0
    },
    {
        "close": "4834.000",
        "ctm": "1726794840",
        "ctmfmt": "2024-09-20 09:14:00",
        "high": "4838.000",
        "low": "4830.000",
        "open": "4832.000",
        "volume": "175511",
        "wave": 0
    },
    {
        "close": "4838.000",
        "ctm": "1726794900",
        "ctmfmt": "2024-09-20 09:15:00",
        "high": "4840.000",
        "low": "4834.000",
        "open": "4836.000",
        "volume": "142552",
        "wave": 0
    },
    {
        "close": "4840.000",
        "ctm": "1726794960",
        "ctmfmt": "2024-09-20 09:16:00",
        "high": "4842.000",
        "low": "4836.000",
        "open": "4838.000",
        "volume": "329856",
        "wave": 0
    },
    {
        "close": "4850.000",
        "ctm": "1726795020",
        "ctmfmt": "2024-09-20 09:17:00",
        "high": "4850.000",
        "low": "4840.000",
        "open": "4840.000",
        "volume": "6627",
        "wave": 0
    },
    {
        "close": "4842.000",
        "ctm": "1726795080",
        "ctmfmt": "2024-09-20 09:18:00",
        "high": "4852.000",
        "low": "4842.000",
        "open": "4850.000",
        "volume": "11896",
        "wave": 0
    },
    {
        "close": "4846.000",
        "ctm": "1726795140",
        "ctmfmt": "2024-09-20 09:19:00",
        "high": "4850.000",
        "low": "4842.000",
        "open": "4842.000",
        "volume": "95283",
        "wave": 0
    },
    {
        "close": "4838.000",
        "ctm": "1726795200",
        "ctmfmt": "2024-09-20 09:20:00",
        "high": "4846.000",
        "low": "4838.000",
        "open": "4846.000",
        "volume": "168345",
        "wave": 0
    },
    {
        "close": "4834.000",
        "ctm": "1726795260",
        "ctmfmt": "2024-09-20 09:21:00",
        "high": "4842.000",
        "low": "4834.000",
        "open": "4838.000",
        "volume": "99413",
        "wave": 0
    },
    {
        "close": "4836.000",
        "ctm": "1726795320",
        "ctmfmt": "2024-09-20 09:22:00",
        "high": "4836.000",
        "low": "4830.000",
        "open": "4834.000",
        "volume": "117599",
        "wave": 0
    },
    {
        "close": "4846.000",
        "ctm": "1726795380",
        "ctmfmt": "2024-09-20 09:23:00",
        "high": "4846.000",
        "low": "4836.000",
        "open": "4836.000",
        "volume": "131838",
        "wave": 0
    },
    {
        "close": "4842.000",
        "ctm": "1726795440",
        "ctmfmt": "2024-09-20 09:24:00",
        "high": "4848.000",
        "low": "4842.000",
        "open": "4846.000",
        "volume": "75651",
        "wave": 0
    },
    {
        "close": "4844.000",
        "ctm": "1726795500",
        "ctmfmt": "2024-09-20 09:25:00",
        "high": "4846.000",
        "low": "4842.000",
        "open": "4842.000",
        "volume": "78871",
        "wave": 0
    },
    {
        "close": "4846.000",
        "ctm": "1726795560",
        "ctmfmt": "2024-09-20 09:26:00",
        "high": "4848.000",
        "low": "4844.000",
        "open": "4846.000",
        "volume": "50960",
        "wave": 0
    },
    {
        "close": "4848.000",
        "ctm": "1726795620",
        "ctmfmt": "2024-09-20 09:27:00",
        "high": "4850.000",
        "low": "4846.000",
        "open": "4848.000",
        "volume": "66800",
        "wave": 0
    },
    {
        "close": "4850.000",
        "ctm": "1726795680",
        "ctmfmt": "2024-09-20 09:28:00",
        "high": "4850.000",
        "low": "4846.000",
        "open": "4848.000",
        "volume": "65000",
        "wave": 0
    },
    {
        "close": "4854.000",
        "ctm": "1726795740",
        "ctmfmt": "2024-09-20 09:29:00",
        "high": "4858.000",
        "low": "4850.000",
        "open": "4850.000",
        "volume": "164079",
        "wave": 0
    },
    {
        "close": "4850.000",
        "ctm": "1726795800",
        "ctmfmt": "2024-09-20 09:30:00",
        "high": "4854.000",
        "low": "4848.000",
        "open": "4854.000",
        "volume": "82170",
        "wave": 0
    },
    {
        "close": "4844.000",
        "ctm": "1726795860",
        "ctmfmt": "2024-09-20 09:31:00",
        "high": "4852.000",
        "low": "4844.000",
        "open": "4850.000",
        "volume": "61675",
        "wave": 0
    },
    {
        "close": "4840.000",
        "ctm": "1726795920",
        "ctmfmt": "2024-09-20 09:32:00",
        "high": "4844.000",
        "low": "4838.000",
        "open": "4840.000",
        "volume": "110450",
        "wave": 0
    },
    {
        "close": "4838.000",
        "ctm": "1726795980",
        "ctmfmt": "2024-09-20 09:33:00",
        "high": "4840.000",
        "low": "4836.000",
        "open": "4840.000",
        "volume": "81702",
        "wave": 0
    },
    {
        "close": "4844.000",
        "ctm": "1726796040",
        "ctmfmt": "2024-09-20 09:34:00",
        "high": "4846.000",
        "low": "4838.000",
        "open": "4838.000",
        "volume": "53304",
        "wave": 0
    },
    {
        "close": "4840.000",
        "ctm": "1726796100",
        "ctmfmt": "2024-09-20 09:35:00",
        "high": "4846.000",
        "low": "4840.000",
        "open": "4844.000",
        "volume": "42720",
        "wave": 0
    },
    {
        "close": "4842.000",
        "ctm": "1726796160",
        "ctmfmt": "2024-09-20 09:36:00",
        "high": "4844.000",
        "low": "4840.000",
        "open": "4842.000",
        "volume": "57522",
        "wave": 0
    },
    {
        "close": "4852.000",
        "ctm": "1726796220",
        "ctmfmt": "2024-09-20 09:37:00",
        "high": "4852.000",
        "low": "4840.000",
        "open": "4842.000",
        "volume": "49646",
        "wave": 0
    },
    {
        "close": "4844.000",
        "ctm": "1726796280",
        "ctmfmt": "2024-09-20 09:38:00",
        "high": "4854.000",
        "low": "4844.000",
        "open": "4852.000",
        "volume": "44574",
        "wave": 0
    },
    {
        "close": "4844.000",
        "ctm": "1726796340",
        "ctmfmt": "2024-09-20 09:39:00",
        "high": "4846.000",
        "low": "4842.000",
        "open": "4842.000",
        "volume": "33968",
        "wave": 0
    },
    {
        "close": "4840.000",
        "ctm": "1726796400",
        "ctmfmt": "2024-09-20 09:40:00",
        "high": "4844.000",
        "low": "4838.000",
        "open": "4844.000",
        "volume": "57592",
        "wave": 0
    },
    {
        "close": "4846.000",
        "ctm": "1726796460",
        "ctmfmt": "2024-09-20 09:41:00",
        "high": "4846.000",
        "low": "4840.000",
        "open": "4840.000",
        "volume": "46368",
        "wave": 0
    },
    {
        "close": "4844.000",
        "ctm": "1726796520",
        "ctmfmt": "2024-09-20 09:42:00",
        "high": "4848.000",
        "low": "4844.000",
        "open": "4844.000",
        "volume": "40636",
        "wave": 0
    },
    {
        "close": "4842.000",
        "ctm": "1726796580",
        "ctmfmt": "2024-09-20 09:43:00",
        "high": "4842.000",
        "low": "4842.000",
        "open": "4842.000",
        "volume": "44",
        "wave": 0
    },
    {
        "close": "4840.000",
        "ctm": "1726796640",
        "ctmfmt": "2024-09-20 09:44:00",
        "high": "4842.000",
        "low": "4840.000",
        "open": "4842.000",
        "volume": "23499",
        "wave": 0
    },
    {
        "close": "4840.000",
        "ctm": "1726796700",
        "ctmfmt": "2024-09-20 09:45:00",
        "high": "4842.000",
        "low": "4840.000",
        "open": "4842.000",
        "volume": "25894",
        "wave": 0
    },
    {
        "close": "4846.000",
        "ctm": "1726796760",
        "ctmfmt": "2024-09-20 09:46:00",
        "high": "4848.000",
        "low": "4840.000",
        "open": "4840.000",
        "volume": "40348",
        "wave": 0
    },
    {
        "close": "4850.000",
        "ctm": "1726796820",
        "ctmfmt": "2024-09-20 09:47:00",
        "high": "4852.000",
        "low": "4848.000",
        "open": "4848.000",
        "volume": "65143",
        "wave": 0
    },
    {
        "close": "4846.000",
        "ctm": "1726796880",
        "ctmfmt": "2024-09-20 09:48:00",
        "high": "4850.000",
        "low": "4846.000",
        "open": "4848.000",
        "volume": "14417",
        "wave": 0
    },
    {
        "close": "4850.000",
        "ctm": "1726796940",
        "ctmfmt": "2024-09-20 09:49:00",
        "high": "4850.000",
        "low": "4846.000",
        "open": "4848.000",
        "volume": "46746",
        "wave": 0
    },
    {
        "close": "4840.000",
        "ctm": "1726797000",
        "ctmfmt": "2024-09-20 09:50:00",
        "high": "4854.000",
        "low": "4840.000",
        "open": "4852.000",
        "volume": "138759",
        "wave": 0
    },
    {
        "close": "4842.000",
        "ctm": "1726797060",
        "ctmfmt": "2024-09-20 09:51:00",
        "high": "4844.000",
        "low": "4840.000",
        "open": "4842.000",
        "volume": "25924",
        "wave": 0
    },
    {
        "close": "4840.000",
        "ctm": "1726797120",
        "ctmfmt": "2024-09-20 09:52:00",
        "high": "4842.000",
        "low": "4838.000",
        "open": "4842.000",
        "volume": "53558",
        "wave": 0
    },
    {
        "close": "4832.000",
        "ctm": "1726797180",
        "ctmfmt": "2024-09-20 09:53:00",
        "high": "4838.000",
        "low": "4832.000",
        "open": "4838.000",
        "volume": "93109",
        "wave": 0
    },
    {
        "close": "4834.000",
        "ctm": "1726797240",
        "ctmfmt": "2024-09-20 09:54:00",
        "high": "4836.000",
        "low": "4832.000",
        "open": "4832.000",
        "volume": "67883",
        "wave": 0
    },
    {
        "close": "4834.000",
        "ctm": "1726797300",
        "ctmfmt": "2024-09-20 09:55:00",
        "high": "4838.000",
        "low": "4832.000",
        "open": "4836.000",
        "volume": "27560",
        "wave": 0
    },
    {
        "close": "4834.000",
        "ctm": "1726797360",
        "ctmfmt": "2024-09-20 09:56:00",
        "high": "4838.000",
        "low": "4832.000",
        "open": "4834.000",
        "volume": "51668",
        "wave": 0
    },
    {
        "close": "4836.000",
        "ctm": "1726797420",
        "ctmfmt": "2024-09-20 09:57:00",
        "high": "4836.000",
        "low": "4832.000",
        "open": "4834.000",
        "volume": "26280",
        "wave": 0
    },
    {
        "close": "4836.000",
        "ctm": "1726797480",
        "ctmfmt": "2024-09-20 09:58:00",
        "high": "4840.000",
        "low": "4834.000",
        "open": "4836.000",
        "volume": "34140",
        "wave": 0
    },
    {
        "close": "4838.000",
        "ctm": "1726797540",
        "ctmfmt": "2024-09-20 09:59:00",
        "high": "4838.000",
        "low": "4834.000",
        "open": "4836.000",
        "volume": "13440",
        "wave": 0
    },
    {
        "close": "4830.000",
        "ctm": "1726797600",
        "ctmfmt": "2024-09-20 10:00:00",
        "high": "4836.000",
        "low": "4830.000",
        "open": "4836.000",
        "volume": "53979",
        "wave": 0
    },
    {
        "close": "4832.000",
        "ctm": "1726797660",
        "ctmfmt": "2024-09-20 10:01:00",
        "high": "4834.000",
        "low": "4830.000",
        "open": "4830.000",
        "volume": "62100",
        "wave": 0
    },
    {
        "close": "4826.000",
        "ctm": "1726797720",
        "ctmfmt": "2024-09-20 10:02:00",
        "high": "4834.000",
        "low": "4824.000",
        "open": "4832.000",
        "volume": "92122",
        "wave": 0
    },
    {
        "close": "4824.000",
        "ctm": "1726797780",
        "ctmfmt": "2024-09-20 10:03:00",
        "high": "4826.000",
        "low": "4820.000",
        "open": "4824.000",
        "volume": "124585",
        "wave": 0
    },
    {
        "close": "4824.000",
        "ctm": "1726797840",
        "ctmfmt": "2024-09-20 10:04:00",
        "high": "4826.000",
        "low": "4822.000",
        "open": "4822.000",
        "volume": "42845",
        "wave": 0
    },
    {
        "close": "4824.000",
        "ctm": "1726797900",
        "ctmfmt": "2024-09-20 10:05:00",
        "high": "4826.000",
        "low": "4820.000",
        "open": "4822.000",
        "volume": "47715",
        "wave": 0
    },
    {
        "close": "4828.000",
        "ctm": "1726797960",
        "ctmfmt": "2024-09-20 10:06:00",
        "high": "4830.000",
        "low": "4824.000",
        "open": "4826.000",
        "volume": "46987",
        "wave": 0
    },
    {
        "close": "4828.000",
        "ctm": "1726798020",
        "ctmfmt": "2024-09-20 10:07:00",
        "high": "4828.000",
        "low": "4826.000",
        "open": "4826.000",
        "volume": "42921",
        "wave": 0
    },
    {
        "close": "4828.000",
        "ctm": "1726798080",
        "ctmfmt": "2024-09-20 10:08:00",
        "high": "4832.000",
        "low": "4826.000",
        "open": "4826.000",
        "volume": "34105",
        "wave": 0
    },
    {
        "close": "4838.000",
        "ctm": "1726798140",
        "ctmfmt": "2024-09-20 10:09:00",
        "high": "4838.000",
        "low": "4828.000",
        "open": "4830.000",
        "volume": "42544",
        "wave": 0
    },
    {
        "close": "4838.000",
        "ctm": "1726798200",
        "ctmfmt": "2024-09-20 10:10:00",
        "high": "4846.000",
        "low": "4838.000",
        "open": "4838.000",
        "volume": "81738",
        "wave": 0
    },
    {
        "close": "4842.000",
        "ctm": "1726798260",
        "ctmfmt": "2024-09-20 10:11:00",
        "high": "4844.000",
        "low": "4836.000",
        "open": "4840.000",
        "volume": "28494",
        "wave": 0
    },
    {
        "close": "4848.000",
        "ctm": "1726798320",
        "ctmfmt": "2024-09-20 10:12:00",
        "high": "4850.000",
        "low": "4840.000",
        "open": "4842.000",
        "volume": "61848",
        "wave": 0
    },
    {
        "close": "4848.000",
        "ctm": "1726798380",
        "ctmfmt": "2024-09-20 10:13:00",
        "high": "4850.000",
        "low": "4846.000",
        "open": "4846.000",
        "volume": "4413",
        "wave": 0
    },
    {
        "close": "4856.000",
        "ctm": "1726798440",
        "ctmfmt": "2024-09-20 10:14:00",
        "high": "4856.000",
        "low": "4848.000",
        "open": "4848.000",
        "volume": "66168",
        "wave": 0
    },
    {
        "close": "4854.000",
        "ctm": "1726798500",
        "ctmfmt": "2024-09-20 10:15:00",
        "high": "4856.000",
        "low": "4852.000",
        "open": "4856.000",
        "volume": "49100",
        "wave": 0
    },
    {
        "close": "4866.000",
        "ctm": "1726799460",
        "ctmfmt": "2024-09-20 10:31:00",
        "high": "4876.000",
        "low": "4854.000",
        "open": "4854.000",
        "volume": "341281",
        "wave": 0
    },
    {
        "close": "4856.000",
        "ctm": "1726799520",
        "ctmfmt": "2024-09-20 10:32:00",
        "high": "4868.000",
        "low": "4856.000",
        "open": "4866.000",
        "volume": "101535",
        "wave": 0
    },
    {
        "close": "4858.000",
        "ctm": "1726799580",
        "ctmfmt": "2024-09-20 10:33:00",
        "high": "4858.000",
        "low": "4850.000",
        "open": "4854.000",
        "volume": "67904",
        "wave": 0
    },
    {
        "close": "4860.000",
        "ctm": "1726799640",
        "ctmfmt": "2024-09-20 10:34:00",
        "high": "4860.000",
        "low": "4856.000",
        "open": "4858.000",
        "volume": "23808",
        "wave": 0
    },
    {
        "close": "4862.000",
        "ctm": "1726799700",
        "ctmfmt": "2024-09-20 10:35:00",
        "high": "4864.000",
        "low": "4858.000",
        "open": "4860.000",
        "volume": "32400",
        "wave": 0
    },
    {
        "close": "4864.000",
        "ctm": "1726799760",
        "ctmfmt": "2024-09-20 10:36:00",
        "high": "4866.000",
        "low": "4862.000",
        "open": "4862.000",
        "volume": "62761",
        "wave": 0
    },
    {
        "close": "4862.000",
        "ctm": "1726799820",
        "ctmfmt": "2024-09-20 10:37:00",
        "high": "4866.000",
        "low": "4860.000",
        "open": "4864.000",
        "volume": "24379",
        "wave": 0
    },
    {
        "close": "4866.000",
        "ctm": "1726799880",
        "ctmfmt": "2024-09-20 10:38:00",
        "high": "4866.000",
        "low": "4858.000",
        "open": "4860.000",
        "volume": "34833",
        "wave": 0
    },
    {
        "close": "4860.000",
        "ctm": "1726799940",
        "ctmfmt": "2024-09-20 10:39:00",
        "high": "4866.000",
        "low": "4858.000",
        "open": "4866.000",
        "volume": "19178",
        "wave": 0
    },
    {
        "close": "4858.000",
        "ctm": "1726800000",
        "ctmfmt": "2024-09-20 10:40:00",
        "high": "4864.000",
        "low": "4858.000",
        "open": "4858.000",
        "volume": "769078",
        "wave": 0
    },
    {
        "close": "4856.000",
        "ctm": "1726800060",
        "ctmfmt": "2024-09-20 10:41:00",
        "high": "4860.000",
        "low": "4854.000",
        "open": "4860.000",
        "volume": "19470",
        "wave": 0
    },
    {
        "close": "4856.000",
        "ctm": "1726800120",
        "ctmfmt": "2024-09-20 10:42:00",
        "high": "4860.000",
        "low": "4854.000",
        "open": "4856.000",
        "volume": "28365",
        "wave": 0
    },
    {
        "close": "4856.000",
        "ctm": "1726800180",
        "ctmfmt": "2024-09-20 10:43:00",
        "high": "4858.000",
        "low": "4852.000",
        "open": "4856.000",
        "volume": "30090",
        "wave": 0
    },
    {
        "close": "4862.000",
        "ctm": "1726800240",
        "ctmfmt": "2024-09-20 10:44:00",
        "high": "4862.000",
        "low": "4856.000",
        "open": "4858.000",
        "volume": "22353",
        "wave": 0
    },
    {
        "close": "4862.000",
        "ctm": "1726800300",
        "ctmfmt": "2024-09-20 10:45:00",
        "high": "4864.000",
        "low": "4860.000",
        "open": "4862.000",
        "volume": "18354",
        "wave": 0
    },
    {
        "close": "4854.000",
        "ctm": "1726800360",
        "ctmfmt": "2024-09-20 10:46:00",
        "high": "4862.000",
        "low": "4852.000",
        "open": "4860.000",
        "volume": "36736",
        "wave": 0
    },
    {
        "close": "4854.000",
        "ctm": "1726800420",
        "ctmfmt": "2024-09-20 10:47:00",
        "high": "4854.000",
        "low": "4852.000",
        "open": "4854.000",
        "volume": "19544",
        "wave": 0
    },
    {
        "close": "4856.000",
        "ctm": "1726800480",
        "ctmfmt": "2024-09-20 10:48:00",
        "high": "4858.000",
        "low": "4854.000",
        "open": "4854.000",
        "volume": "6930",
        "wave": 0
    },
    {
        "close": "4852.000",
        "ctm": "1726800540",
        "ctmfmt": "2024-09-20 10:49:00",
        "high": "4856.000",
        "low": "4850.000",
        "open": "4856.000",
        "volume": "25998",
        "wave": 0
    },
    {
        "close": "4854.000",
        "ctm": "1726800600",
        "ctmfmt": "2024-09-20 10:50:00",
        "high": "4856.000",
        "low": "4852.000",
        "open": "4854.000",
        "volume": "23798",
        "wave": 0
    },
    {
        "close": "4854.000",
        "ctm": "1726800660",
        "ctmfmt": "2024-09-20 10:51:00",
        "high": "4854.000",
        "low": "4852.000",
        "open": "4854.000",
        "volume": "1365",
        "wave": 0
    },
    {
        "close": "4848.000",
        "ctm": "1726800720",
        "ctmfmt": "2024-09-20 10:52:00",
        "high": "4854.000",
        "low": "4846.000",
        "open": "4854.000",
        "volume": "30766",
        "wave": 0
    },
    {
        "close": "4854.000",
        "ctm": "1726800780",
        "ctmfmt": "2024-09-20 10:53:00",
        "high": "4854.000",
        "low": "4846.000",
        "open": "4846.000",
        "volume": "22256",
        "wave": 0
    },
    {
        "close": "4854.000",
        "ctm": "1726800840",
        "ctmfmt": "2024-09-20 10:54:00",
        "high": "4860.000",
        "low": "4852.000",
        "open": "4854.000",
        "volume": "21918",
        "wave": 0
    },
    {
        "close": "4852.000",
        "ctm": "1726800900",
        "ctmfmt": "2024-09-20 10:55:00",
        "high": "4856.000",
        "low": "4852.000",
        "open": "4854.000",
        "volume": "13065",
        "wave": 0
    },
    {
        "close": "4848.000",
        "ctm": "1726800960",
        "ctmfmt": "2024-09-20 10:56:00",
        "high": "4852.000",
        "low": "4848.000",
        "open": "4850.000",
        "volume": "19838",
        "wave": 0
    },
    {
        "close": "4848.000",
        "ctm": "1726801020",
        "ctmfmt": "2024-09-20 10:57:00",
        "high": "4850.000",
        "low": "4848.000",
        "open": "4848.000",
        "volume": "9542",
        "wave": 0
    },
    {
        "close": "4852.000",
        "ctm": "1726801080",
        "ctmfmt": "2024-09-20 10:58:00",
        "high": "4852.000",
        "low": "4846.000",
        "open": "4848.000",
        "volume": "25558",
        "wave": 0
    },
    {
        "close": "4850.000",
        "ctm": "1726801140",
        "ctmfmt": "2024-09-20 10:59:00",
        "high": "4852.000",
        "low": "4848.000",
        "open": "4852.000",
        "volume": "18135",
        "wave": 0
    },
    {
        "close": "4854.000",
        "ctm": "1726801200",
        "ctmfmt": "2024-09-20 11:00:00",
        "high": "4856.000",
        "low": "4850.000",
        "open": "4852.000",
        "volume": "17147",
        "wave": 0
    },
    {
        "close": "4866.000",
        "ctm": "1726801260",
        "ctmfmt": "2024-09-20 11:01:00",
        "high": "4866.000",
        "low": "4856.000",
        "open": "4856.000",
        "volume": "46137",
        "wave": 0
    },
    {
        "close": "4866.000",
        "ctm": "1726801320",
        "ctmfmt": "2024-09-20 11:02:00",
        "high": "4870.000",
        "low": "4862.000",
        "open": "4864.000",
        "volume": "77736",
        "wave": 0
    },
    {
        "close": "4864.000",
        "ctm": "1726801380",
        "ctmfmt": "2024-09-20 11:03:00",
        "high": "4866.000",
        "low": "4862.000",
        "open": "4864.000",
        "volume": "27913",
        "wave": 0
    },
    {
        "close": "4870.000",
        "ctm": "1726801440",
        "ctmfmt": "2024-09-20 11:04:00",
        "high": "4870.000",
        "low": "4864.000",
        "open": "4866.000",
        "volume": "120132",
        "wave": 0
    },
    {
        "close": "4872.000",
        "ctm": "1726801500",
        "ctmfmt": "2024-09-20 11:05:00",
        "high": "4874.000",
        "low": "4864.000",
        "open": "4870.000",
        "volume": "51307",
        "wave": 0
    },
    {
        "close": "4870.000",
        "ctm": "1726801560",
        "ctmfmt": "2024-09-20 11:06:00",
        "high": "4876.000",
        "low": "4868.000",
        "open": "4872.000",
        "volume": "118260",
        "wave": 0
    },
    {
        "close": "4866.000",
        "ctm": "1726801620",
        "ctmfmt": "2024-09-20 11:07:00",
        "high": "4870.000",
        "low": "4864.000",
        "open": "4868.000",
        "volume": "12756",
        "wave": 0
    },
    {
        "close": "4866.000",
        "ctm": "1726801680",
        "ctmfmt": "2024-09-20 11:08:00",
        "high": "4868.000",
        "low": "4860.000",
        "open": "4864.000",
        "volume": "53820",
        "wave": 0
    },
    {
        "close": "4868.000",
        "ctm": "1726801740",
        "ctmfmt": "2024-09-20 11:09:00",
        "high": "4870.000",
        "low": "4864.000",
        "open": "4868.000",
        "volume": "16668",
        "wave": 0
    },
    {
        "close": "4870.000",
        "ctm": "1726801800",
        "ctmfmt": "2024-09-20 11:10:00",
        "high": "4872.000",
        "low": "4868.000",
        "open": "4870.000",
        "volume": "14916",
        "wave": 0
    },
    {
        "close": "4874.000",
        "ctm": "1726801860",
        "ctmfmt": "2024-09-20 11:11:00",
        "high": "4876.000",
        "low": "4868.000",
        "open": "4868.000",
        "volume": "21285",
        "wave": 0
    },
    {
        "close": "4880.000",
        "ctm": "1726801920",
        "ctmfmt": "2024-09-20 11:12:00",
        "high": "4884.000",
        "low": "4872.000",
        "open": "4874.000",
        "volume": "129327",
        "wave": 0
    },
    {
        "close": "4878.000",
        "ctm": "1726801980",
        "ctmfmt": "2024-09-20 11:13:00",
        "high": "4880.000",
        "low": "4876.000",
        "open": "4880.000",
        "volume": "27038",
        "wave": 0
    },
    {
        "close": "4876.000",
        "ctm": "1726802040",
        "ctmfmt": "2024-09-20 11:14:00",
        "high": "4878.000",
        "low": "4874.000",
        "open": "4876.000",
        "volume": "25430",
        "wave": 0
    },
    {
        "close": "4874.000",
        "ctm": "1726802100",
        "ctmfmt": "2024-09-20 11:15:00",
        "high": "4874.000",
        "low": "4872.000",
        "open": "4874.000",
        "volume": "880",
        "wave": 0
    },
    {
        "close": "4872.000",
        "ctm": "1726802160",
        "ctmfmt": "2024-09-20 11:16:00",
        "high": "4878.000",
        "low": "4872.000",
        "open": "4876.000",
        "volume": "16489",
        "wave": 0
    },
    {
        "close": "4876.000",
        "ctm": "1726802220",
        "ctmfmt": "2024-09-20 11:17:00",
        "high": "4876.000",
        "low": "4872.000",
        "open": "4874.000",
        "volume": "5685",
        "wave": 0
    },
    {
        "close": "4888.000",
        "ctm": "1726802280",
        "ctmfmt": "2024-09-20 11:18:00",
        "high": "4888.000",
        "low": "4876.000",
        "open": "4876.000",
        "volume": "82900",
        "wave": 0
    },
    {
        "close": "4884.000",
        "ctm": "1726802340",
        "ctmfmt": "2024-09-20 11:19:00",
        "high": "4886.000",
        "low": "4882.000",
        "open": "4884.000",
        "volume": "3506",
        "wave": 0
    },
    {
        "close": "4882.000",
        "ctm": "1726802400",
        "ctmfmt": "2024-09-20 11:20:00",
        "high": "4884.000",
        "low": "4878.000",
        "open": "4882.000",
        "volume": "22437",
        "wave": 0
    },
    {
        "close": "4880.000",
        "ctm": "1726802460",
        "ctmfmt": "2024-09-20 11:21:00",
        "high": "4882.000",
        "low": "4878.000",
        "open": "4880.000",
        "volume": "12080",
        "wave": 0
    },
    {
        "close": "4882.000",
        "ctm": "1726802520",
        "ctmfmt": "2024-09-20 11:22:00",
        "high": "4882.000",
        "low": "4878.000",
        "open": "4880.000",
        "volume": "12830",
        "wave": 0
    },
    {
        "close": "4880.000",
        "ctm": "1726802580",
        "ctmfmt": "2024-09-20 11:23:00",
        "high": "4880.000",
        "low": "4876.000",
        "open": "4880.000",
        "volume": "18770",
        "wave": 0
    },
    {
        "close": "4878.000",
        "ctm": "1726802640",
        "ctmfmt": "2024-09-20 11:24:00",
        "high": "4882.000",
        "low": "4878.000",
        "open": "4880.000",
        "volume": "9970",
        "wave": 0
    },
    {
        "close": "4876.000",
        "ctm": "1726802700",
        "ctmfmt": "2024-09-20 11:25:00",
        "high": "4880.000",
        "low": "4874.000",
        "open": "4880.000",
        "volume": "10110",
        "wave": 0
    },
    {
        "close": "4874.000",
        "ctm": "1726802760",
        "ctmfmt": "2024-09-20 11:26:00",
        "high": "4878.000",
        "low": "4874.000",
        "open": "4876.000",
        "volume": "11192",
        "wave": 0
    },
    {
        "close": "4876.000",
        "ctm": "1726802820",
        "ctmfmt": "2024-09-20 11:27:00",
        "high": "4878.000",
        "low": "4874.000",
        "open": "4874.000",
        "volume": "9361",
        "wave": 0
    },
    {
        "close": "4874.000",
        "ctm": "1726802880",
        "ctmfmt": "2024-09-20 11:28:00",
        "high": "4878.000",
        "low": "4872.000",
        "open": "4878.000",
        "volume": "17739",
        "wave": 0
    },
    {
        "close": "4870.000",
        "ctm": "1726802940",
        "ctmfmt": "2024-09-20 11:29:00",
        "high": "4876.000",
        "low": "4870.000",
        "open": "4874.000",
        "volume": "31689",
        "wave": 0
    },
    {
        "close": "4870.000",
        "ctm": "1726803000",
        "ctmfmt": "2024-09-20 11:30:00",
        "high": "4876.000",
        "low": "4870.000",
        "open": "4870.000",
        "volume": "47415",
        "wave": 0
    },
    {
        "close": "4854.000",
        "ctm": "1726810260",
        "ctmfmt": "2024-09-20 13:31:00",
        "high": "4870.000",
        "low": "4854.000",
        "open": "4870.000",
        "volume": "92949",
        "wave": 0
    },
    {
        "close": "4854.000",
        "ctm": "1726810320",
        "ctmfmt": "2024-09-20 13:32:00",
        "high": "4856.000",
        "low": "4850.000",
        "open": "4856.000",
        "volume": "42781",
        "wave": 0
    },
    {
        "close": "4852.000",
        "ctm": "1726810380",
        "ctmfmt": "2024-09-20 13:33:00",
        "high": "4856.000",
        "low": "4850.000",
        "open": "4854.000",
        "volume": "25774",
        "wave": 0
    },
    {
        "close": "4854.000",
        "ctm": "1726810440",
        "ctmfmt": "2024-09-20 13:34:00",
        "high": "4854.000",
        "low": "4848.000",
        "open": "4850.000",
        "volume": "36531",
        "wave": 0
    },
    {
        "close": "4858.000",
        "ctm": "1726810500",
        "ctmfmt": "2024-09-20 13:35:00",
        "high": "4858.000",
        "low": "4854.000",
        "open": "4856.000",
        "volume": "31697",
        "wave": 0
    },
    {
        "close": "4862.000",
        "ctm": "1726810560",
        "ctmfmt": "2024-09-20 13:36:00",
        "high": "4864.000",
        "low": "4858.000",
        "open": "4858.000",
        "volume": "26945",
        "wave": 0
    },
    {
        "close": "4860.000",
        "ctm": "1726810620",
        "ctmfmt": "2024-09-20 13:37:00",
        "high": "4864.000",
        "low": "4860.000",
        "open": "4862.000",
        "volume": "16409",
        "wave": 0
    },
    {
        "close": "4858.000",
        "ctm": "1726810680",
        "ctmfmt": "2024-09-20 13:38:00",
        "high": "4862.000",
        "low": "4856.000",
        "open": "4860.000",
        "volume": "20608",
        "wave": 0
    },
    {
        "close": "4856.000",
        "ctm": "1726810740",
        "ctmfmt": "2024-09-20 13:39:00",
        "high": "4858.000",
        "low": "4854.000",
        "open": "4856.000",
        "volume": "22160",
        "wave": 0
    },
    {
        "close": "4854.000",
        "ctm": "1726810800",
        "ctmfmt": "2024-09-20 13:40:00",
        "high": "4860.000",
        "low": "4852.000",
        "open": "4858.000",
        "volume": "42272",
        "wave": 0
    },
    {
        "close": "4852.000",
        "ctm": "1726810860",
        "ctmfmt": "2024-09-20 13:41:00",
        "high": "4856.000",
        "low": "4850.000",
        "open": "4854.000",
        "volume": "30942",
        "wave": 0
    },
    {
        "close": "4848.000",
        "ctm": "1726810920",
        "ctmfmt": "2024-09-20 13:42:00",
        "high": "4852.000",
        "low": "4848.000",
        "open": "4852.000",
        "volume": "28377",
        "wave": 0
    },
    {
        "close": "4848.000",
        "ctm": "1726810980",
        "ctmfmt": "2024-09-20 13:43:00",
        "high": "4850.000",
        "low": "4846.000",
        "open": "4848.000",
        "volume": "27720",
        "wave": 0
    },
    {
        "close": "4852.000",
        "ctm": "1726811040",
        "ctmfmt": "2024-09-20 13:44:00",
        "high": "4854.000",
        "low": "4848.000",
        "open": "4850.000",
        "volume": "18417",
        "wave": 0
    },
    {
        "close": "4854.000",
        "ctm": "1726811100",
        "ctmfmt": "2024-09-20 13:45:00",
        "high": "4856.000",
        "low": "4852.000",
        "open": "4852.000",
        "volume": "12859",
        "wave": 0
    },
    {
        "close": "4852.000",
        "ctm": "1726811160",
        "ctmfmt": "2024-09-20 13:46:00",
        "high": "4856.000",
        "low": "4852.000",
        "open": "4856.000",
        "volume": "13488",
        "wave": 0
    },
    {
        "close": "4852.000",
        "ctm": "1726811220",
        "ctmfmt": "2024-09-20 13:47:00",
        "high": "4856.000",
        "low": "4850.000",
        "open": "4852.000",
        "volume": "16348",
        "wave": 0
    },
    {
        "close": "4850.000",
        "ctm": "1726811280",
        "ctmfmt": "2024-09-20 13:48:00",
        "high": "4852.000",
        "low": "4850.000",
        "open": "4852.000",
        "volume": "4273",
        "wave": 0
    },
    {
        "close": "4850.000",
        "ctm": "1726811340",
        "ctmfmt": "2024-09-20 13:49:00",
        "high": "4852.000",
        "low": "4848.000",
        "open": "4850.000",
        "volume": "10509",
        "wave": 0
    },
    {
        "close": "4846.000",
        "ctm": "1726811400",
        "ctmfmt": "2024-09-20 13:50:00",
        "high": "4850.000",
        "low": "4844.000",
        "open": "4850.000",
        "volume": "27480",
        "wave": 0
    },
    {
        "close": "4846.000",
        "ctm": "1726811460",
        "ctmfmt": "2024-09-20 13:51:00",
        "high": "4850.000",
        "low": "4846.000",
        "open": "4846.000",
        "volume": "15224",
        "wave": 0
    },
    {
        "close": "4852.000",
        "ctm": "1726811520",
        "ctmfmt": "2024-09-20 13:52:00",
        "high": "4852.000",
        "low": "4846.000",
        "open": "4846.000",
        "volume": "10760",
        "wave": 0
    },
    {
        "close": "4856.000",
        "ctm": "1726811580",
        "ctmfmt": "2024-09-20 13:53:00",
        "high": "4860.000",
        "low": "4850.000",
        "open": "4850.000",
        "volume": "38456",
        "wave": 0
    },
    {
        "close": "4852.000",
        "ctm": "1726811640",
        "ctmfmt": "2024-09-20 13:54:00",
        "high": "4854.000",
        "low": "4852.000",
        "open": "4854.000",
        "volume": "9560",
        "wave": 0
    },
    {
        "close": "4858.000",
        "ctm": "1726811700",
        "ctmfmt": "2024-09-20 13:55:00",
        "high": "4860.000",
        "low": "4852.000",
        "open": "4852.000",
        "volume": "12144",
        "wave": 0
    },
    {
        "close": "4858.000",
        "ctm": "1726811760",
        "ctmfmt": "2024-09-20 13:56:00",
        "high": "4860.000",
        "low": "4856.000",
        "open": "4860.000",
        "volume": "6936",
        "wave": 0
    },
    {
        "close": "4868.000",
        "ctm": "1726811820",
        "ctmfmt": "2024-09-20 13:57:00",
        "high": "4870.000",
        "low": "4858.000",
        "open": "4858.000",
        "volume": "51062",
        "wave": 0
    },
    {
        "close": "4860.000",
        "ctm": "1726811880",
        "ctmfmt": "2024-09-20 13:58:00",
        "high": "4868.000",
        "low": "4858.000",
        "open": "4868.000",
        "volume": "20216",
        "wave": 0
    },
    {
        "close": "4860.000",
        "ctm": "1726811940",
        "ctmfmt": "2024-09-20 13:59:00",
        "high": "4862.000",
        "low": "4858.000",
        "open": "4860.000",
        "volume": "11046",
        "wave": 0
    },
    {
        "close": "4862.000",
        "ctm": "1726812000",
        "ctmfmt": "2024-09-20 14:00:00",
        "high": "4862.000",
        "low": "4856.000",
        "open": "4858.000",
        "volume": "9387",
        "wave": 0
    },
    {
        "close": "4860.000",
        "ctm": "1726812060",
        "ctmfmt": "2024-09-20 14:01:00",
        "high": "4862.000",
        "low": "4858.000",
        "open": "4860.000",
        "volume": "8526",
        "wave": 0
    },
    {
        "close": "4864.000",
        "ctm": "1726812120",
        "ctmfmt": "2024-09-20 14:02:00",
        "high": "4866.000",
        "low": "4858.000",
        "open": "4860.000",
        "volume": "13202",
        "wave": 0
    },
    {
        "close": "4866.000",
        "ctm": "1726812180",
        "ctmfmt": "2024-09-20 14:03:00",
        "high": "4870.000",
        "low": "4864.000",
        "open": "4866.000",
        "volume": "22946",
        "wave": 0
    },
    {
        "close": "4864.000",
        "ctm": "1726812240",
        "ctmfmt": "2024-09-20 14:04:00",
        "high": "4866.000",
        "low": "4860.000",
        "open": "4864.000",
        "volume": "10661",
        "wave": 0
    },
    {
        "close": "4866.000",
        "ctm": "1726812300",
        "ctmfmt": "2024-09-20 14:05:00",
        "high": "4866.000",
        "low": "4860.000",
        "open": "4864.000",
        "volume": "9463",
        "wave": 0
    },
    {
        "close": "4868.000",
        "ctm": "1726812360",
        "ctmfmt": "2024-09-20 14:06:00",
        "high": "4870.000",
        "low": "4864.000",
        "open": "4868.000",
        "volume": "11946",
        "wave": 0
    },
    {
        "close": "4868.000",
        "ctm": "1726812420",
        "ctmfmt": "2024-09-20 14:07:00",
        "high": "4872.000",
        "low": "4866.000",
        "open": "4866.000",
        "volume": "12432",
        "wave": 0
    },
    {
        "close": "4870.000",
        "ctm": "1726812480",
        "ctmfmt": "2024-09-20 14:08:00",
        "high": "4872.000",
        "low": "4868.000",
        "open": "4870.000",
        "volume": "9548",
        "wave": 0
    },
    {
        "close": "4870.000",
        "ctm": "1726812540",
        "ctmfmt": "2024-09-20 14:09:00",
        "high": "4872.000",
        "low": "4868.000",
        "open": "4868.000",
        "volume": "988744",
        "wave": 0
    },
    {
        "close": "4868.000",
        "ctm": "1726812600",
        "ctmfmt": "2024-09-20 14:10:00",
        "high": "4872.000",
        "low": "4868.000",
        "open": "4872.000",
        "volume": "6990",
        "wave": 0
    },
    {
        "close": "4866.000",
        "ctm": "1726812660",
        "ctmfmt": "2024-09-20 14:11:00",
        "high": "4870.000",
        "low": "4866.000",
        "open": "4868.000",
        "volume": "8100",
        "wave": 0
    },
    {
        "close": "4862.000",
        "ctm": "1726812720",
        "ctmfmt": "2024-09-20 14:12:00",
        "high": "4866.000",
        "low": "4862.000",
        "open": "4866.000",
        "volume": "8151",
        "wave": 0
    },
    {
        "close": "4862.000",
        "ctm": "1726812780",
        "ctmfmt": "2024-09-20 14:13:00",
        "high": "4866.000",
        "low": "4862.000",
        "open": "4862.000",
        "volume": "11678",
        "wave": 0
    },
    {
        "close": "4858.000",
        "ctm": "1726812840",
        "ctmfmt": "2024-09-20 14:14:00",
        "high": "4864.000",
        "low": "4858.000",
        "open": "4862.000",
        "volume": "21507",
        "wave": 0
    },
    {
        "close": "4862.000",
        "ctm": "1726812900",
        "ctmfmt": "2024-09-20 14:15:00",
        "high": "4864.000",
        "low": "4858.000",
        "open": "4858.000",
        "volume": "10478",
        "wave": 0
    },
    {
        "close": "4854.000",
        "ctm": "1726812960",
        "ctmfmt": "2024-09-20 14:16:00",
        "high": "4856.000",
        "low": "4852.000",
        "open": "4854.000",
        "volume": "27800",
        "wave": 0
    },
    {
        "close": "4850.000",
        "ctm": "1726813020",
        "ctmfmt": "2024-09-20 14:17:00",
        "high": "4854.000",
        "low": "4850.000",
        "open": "4854.000",
        "volume": "20253",
        "wave": 0
    },
    {
        "close": "4852.000",
        "ctm": "1726813080",
        "ctmfmt": "2024-09-20 14:18:00",
        "high": "4856.000",
        "low": "4850.000",
        "open": "4850.000",
        "volume": "2001",
        "wave": 0
    },
    {
        "close": "4856.000",
        "ctm": "1726813140",
        "ctmfmt": "2024-09-20 14:19:00",
        "high": "4856.000",
        "low": "4850.000",
        "open": "4856.000",
        "volume": "8037",
        "wave": 0
    },
    {
        "close": "4860.000",
        "ctm": "1726813200",
        "ctmfmt": "2024-09-20 14:20:00",
        "high": "4860.000",
        "low": "4854.000",
        "open": "4856.000",
        "volume": "7461",
        "wave": 0
    },
    {
        "close": "4862.000",
        "ctm": "1726813260",
        "ctmfmt": "2024-09-20 14:21:00",
        "high": "4864.000",
        "low": "4858.000",
        "open": "4860.000",
        "volume": "12110",
        "wave": 0
    },
    {
        "close": "4866.000",
        "ctm": "1726813320",
        "ctmfmt": "2024-09-20 14:22:00",
        "high": "4866.000",
        "low": "4862.000",
        "open": "4864.000",
        "volume": "10460",
        "wave": 0
    },
    {
        "close": "4866.000",
        "ctm": "1726813380",
        "ctmfmt": "2024-09-20 14:23:00",
        "high": "4870.000",
        "low": "4862.000",
        "open": "4866.000",
        "volume": "11977",
        "wave": 0
    },
    {
        "close": "4872.000",
        "ctm": "1726813440",
        "ctmfmt": "2024-09-20 14:24:00",
        "high": "4872.000",
        "low": "4866.000",
        "open": "4868.000",
        "volume": "13565",
        "wave": 0
    },
    {
        "close": "4876.000",
        "ctm": "1726813500",
        "ctmfmt": "2024-09-20 14:25:00",
        "high": "4876.000",
        "low": "4870.000",
        "open": "4870.000",
        "volume": "32335",
        "wave": 0
    },
    {
        "close": "4876.000",
        "ctm": "1726813560",
        "ctmfmt": "2024-09-20 14:26:00",
        "high": "4880.000",
        "low": "4874.000",
        "open": "4874.000",
        "volume": "35130",
        "wave": 0
    },
    {
        "close": "4872.000",
        "ctm": "1726813620",
        "ctmfmt": "2024-09-20 14:27:00",
        "high": "4874.000",
        "low": "4872.000",
        "open": "4872.000",
        "volume": "490",
        "wave": 0
    },
    {
        "close": "4872.000",
        "ctm": "1726813680",
        "ctmfmt": "2024-09-20 14:28:00",
        "high": "4876.000",
        "low": "4870.000",
        "open": "4872.000",
        "volume": "5593",
        "wave": 0
    },
    {
        "close": "4872.000",
        "ctm": "1726813740",
        "ctmfmt": "2024-09-20 14:29:00",
        "high": "4876.000",
        "low": "4872.000",
        "open": "4874.000",
        "volume": "5698",
        "wave": 0
    },
    {
        "close": "4872.000",
        "ctm": "1726813800",
        "ctmfmt": "2024-09-20 14:30:00",
        "high": "4876.000",
        "low": "4872.000",
        "open": "4872.000",
        "volume": "6913",
        "wave": 0
    },
    {
        "close": "4874.000",
        "ctm": "1726813860",
        "ctmfmt": "2024-09-20 14:31:00",
        "high": "4876.000",
        "low": "4872.000",
        "open": "4876.000",
        "volume": "3734",
        "wave": 0
    },
    {
        "close": "4876.000",
        "ctm": "1726813920",
        "ctmfmt": "2024-09-20 14:32:00",
        "high": "4878.000",
        "low": "4874.000",
        "open": "4874.000",
        "volume": "6224",
        "wave": 0
    },
    {
        "close": "4872.000",
        "ctm": "1726813980",
        "ctmfmt": "2024-09-20 14:33:00",
        "high": "4878.000",
        "low": "4872.000",
        "open": "4876.000",
        "volume": "4064",
        "wave": 0
    },
    {
        "close": "4868.000",
        "ctm": "1726814040",
        "ctmfmt": "2024-09-20 14:34:00",
        "high": "4874.000",
        "low": "4868.000",
        "open": "4872.000",
        "volume": "9232",
        "wave": 0
    },
    {
        "close": "4874.000",
        "ctm": "1726814100",
        "ctmfmt": "2024-09-20 14:35:00",
        "high": "4874.000",
        "low": "4868.000",
        "open": "4868.000",
        "volume": "7876",
        "wave": 0
    },
    {
        "close": "4866.000",
        "ctm": "1726814160",
        "ctmfmt": "2024-09-20 14:36:00",
        "high": "4872.000",
        "low": "4866.000",
        "open": "4872.000",
        "volume": "9984",
        "wave": 0
    },
    {
        "close": "4868.000",
        "ctm": "1726814220",
        "ctmfmt": "2024-09-20 14:37:00",
        "high": "4870.000",
        "low": "4864.000",
        "open": "4864.000",
        "volume": "5531",
        "wave": 0
    },
    {
        "close": "4862.000",
        "ctm": "1726814280",
        "ctmfmt": "2024-09-20 14:38:00",
        "high": "4870.000",
        "low": "4862.000",
        "open": "4870.000",
        "volume": "8648",
        "wave": 0
    },
    {
        "close": "4862.000",
        "ctm": "1726814340",
        "ctmfmt": "2024-09-20 14:39:00",
        "high": "4864.000",
        "low": "4860.000",
        "open": "4864.000",
        "volume": "6405",
        "wave": 0
    },
    {
        "close": "4868.000",
        "ctm": "1726814400",
        "ctmfmt": "2024-09-20 14:40:00",
        "high": "4868.000",
        "low": "4862.000",
        "open": "4864.000",
        "volume": "3894",
        "wave": 0
    },
    {
        "close": "4868.000",
        "ctm": "1726814460",
        "ctmfmt": "2024-09-20 14:41:00",
        "high": "4868.000",
        "low": "4864.000",
        "open": "4868.000",
        "volume": "4176",
        "wave": 0
    },
    {
        "close": "4868.000",
        "ctm": "1726814520",
        "ctmfmt": "2024-09-20 14:42:00",
        "high": "4870.000",
        "low": "4868.000",
        "open": "4868.000",
        "volume": "2112",
        "wave": 0
    },
    {
        "close": "4870.000",
        "ctm": "1726814580",
        "ctmfmt": "2024-09-20 14:43:00",
        "high": "4870.000",
        "low": "4866.000",
        "open": "4870.000",
        "volume": "3735",
        "wave": 0
    },
    {
        "close": "4872.000",
        "ctm": "1726814640",
        "ctmfmt": "2024-09-20 14:44:00",
        "high": "4872.000",
        "low": "4868.000",
        "open": "4870.000",
        "volume": "9900",
        "wave": 0
    },
    {
        "close": "4872.000",
        "ctm": "1726814700",
        "ctmfmt": "2024-09-20 14:45:00",
        "high": "4872.000",
        "low": "4868.000",
        "open": "4870.000",
        "volume": "4611",
        "wave": 0
    },
    {
        "close": "4874.000",
        "ctm": "1726814760",
        "ctmfmt": "2024-09-20 14:46:00",
        "high": "4876.000",
        "low": "4870.000",
        "open": "4872.000",
        "volume": "9174",
        "wave": 0
    },
    {
        "close": "4872.000",
        "ctm": "1726814820",
        "ctmfmt": "2024-09-20 14:47:00",
        "high": "4876.000",
        "low": "4870.000",
        "open": "4874.000",
        "volume": "4875",
        "wave": 0
    },
    {
        "close": "4872.000",
        "ctm": "1726814880",
        "ctmfmt": "2024-09-20 14:48:00",
        "high": "4876.000",
        "low": "4870.000",
        "open": "4870.000",
        "volume": "8403",
        "wave": 0
    },
    {
        "close": "4876.000",
        "ctm": "1726814940",
        "ctmfmt": "2024-09-20 14:49:00",
        "high": "4876.000",
        "low": "4870.000",
        "open": "4874.000",
        "volume": "5265",
        "wave": 0
    },
    {
        "close": "4876.000",
        "ctm": "1726815000",
        "ctmfmt": "2024-09-20 14:50:00",
        "high": "4878.000",
        "low": "4874.000",
        "open": "4874.000",
        "volume": "4593",
        "wave": 0
    },
    {
        "close": "4878.000",
        "ctm": "1726815060",
        "ctmfmt": "2024-09-20 14:51:00",
        "high": "4880.000",
        "low": "4874.000",
        "open": "4876.000",
        "volume": "3424",
        "wave": 0
    },
    {
        "close": "4880.000",
        "ctm": "1726815120",
        "ctmfmt": "2024-09-20 14:52:00",
        "high": "4880.000",
        "low": "4876.000",
        "open": "4876.000",
        "volume": "1980",
        "wave": 0
    },
    {
        "close": "4876.000",
        "ctm": "1726815180",
        "ctmfmt": "2024-09-20 14:53:00",
        "high": "4880.000",
        "low": "4874.000",
        "open": "4880.000",
        "volume": "2240",
        "wave": 0
    },
    {
        "close": "4878.000",
        "ctm": "1726815240",
        "ctmfmt": "2024-09-20 14:54:00",
        "high": "4878.000",
        "low": "4874.000",
        "open": "4874.000",
        "volume": "1260",
        "wave": 0
    },
    {
        "close": "4876.000",
        "ctm": "1726815300",
        "ctmfmt": "2024-09-20 14:55:00",
        "high": "4878.000",
        "low": "4874.000",
        "open": "4876.000",
        "volume": "4008",
        "wave": 0
    },
    {
        "close": "4876.000",
        "ctm": "1726815360",
        "ctmfmt": "2024-09-20 14:56:00",
        "high": "4878.000",
        "low": "4874.000",
        "open": "4876.000",
        "volume": "1506",
        "wave": 0
    },
    {
        "close": "4874.000",
        "ctm": "1726815420",
        "ctmfmt": "2024-09-20 14:57:00",
        "high": "4876.000",
        "low": "4874.000",
        "open": "4876.000",
        "volume": "1863",
        "wave": 0
    },
    {
        "close": "4868.000",
        "ctm": "1726815480",
        "ctmfmt": "2024-09-20 14:58:00",
        "high": "4874.000",
        "low": "4868.000",
        "open": "4874.000",
        "volume": "6622",
        "wave": 0
    },
    {
        "close": "4870.000",
        "ctm": "1726815540",
        "ctmfmt": "2024-09-20 14:59:00",
        "high": "4872.000",
        "low": "4868.000",
        "open": "4870.000",
        "volume": "4825",
        "wave": 0
    },
    {
        "close": "4866.000",
        "ctm": "1726815600",
        "ctmfmt": "2024-09-20 15:00:00",
        "high": "4872.000",
        "low": "4866.000",
        "open": "4870.000",
        "volume": "8715",
        "wave": 0
    },
    {
        "close": "4852.000",
        "ctm": "1726837260",
        "ctmfmt": "2024-09-20 21:01:00",
        "high": "4868.000",
        "low": "4848.000",
        "open": "4856.000",
        "volume": "961703",
        "wave": 0
    },
    {
        "close": "4838.000",
        "ctm": "1726837320",
        "ctmfmt": "2024-09-20 21:02:00",
        "high": "4852.000",
        "low": "4838.000",
        "open": "4852.000",
        "volume": "499144",
        "wave": 0
    },
    {
        "close": "4842.000",
        "ctm": "1726837380",
        "ctmfmt": "2024-09-20 21:03:00",
        "high": "4842.000",
        "low": "4830.000",
        "open": "4836.000",
        "volume": "443287",
        "wave": 0
    },
    {
        "close": "4838.000",
        "ctm": "1726837440",
        "ctmfmt": "2024-09-20 21:04:00",
        "high": "4846.000",
        "low": "4836.000",
        "open": "4842.000",
        "volume": "403144",
        "wave": 0
    },
    {
        "close": "4844.000",
        "ctm": "1726837500",
        "ctmfmt": "2024-09-20 21:05:00",
        "high": "4846.000",
        "low": "4840.000",
        "open": "4840.000",
        "volume": "233177",
        "wave": 0
    },
    {
        "close": "4856.000",
        "ctm": "1726837560",
        "ctmfmt": "2024-09-20 21:06:00",
        "high": "4856.000",
        "low": "4844.000",
        "open": "4844.000",
        "volume": "196082",
        "wave": 0
    },
    {
        "close": "4854.000",
        "ctm": "1726837620",
        "ctmfmt": "2024-09-20 21:07:00",
        "high": "4858.000",
        "low": "4852.000",
        "open": "4856.000",
        "volume": "195284",
        "wave": 0
    },
    {
        "close": "4852.000",
        "ctm": "1726837680",
        "ctmfmt": "2024-09-20 21:08:00",
        "high": "4858.000",
        "low": "4852.000",
        "open": "4856.000",
        "volume": "148606",
        "wave": 0
    },
    {
        "close": "4856.000",
        "ctm": "1726837740",
        "ctmfmt": "2024-09-20 21:09:00",
        "high": "4856.000",
        "low": "4848.000",
        "open": "4852.000",
        "volume": "122232",
        "wave": 0
    },
    {
        "close": "4854.000",
        "ctm": "1726837800",
        "ctmfmt": "2024-09-20 21:10:00",
        "high": "4858.000",
        "low": "4852.000",
        "open": "4854.000",
        "volume": "141448",
        "wave": 0
    },
    {
        "close": "4848.000",
        "ctm": "1726837860",
        "ctmfmt": "2024-09-20 21:11:00",
        "high": "4856.000",
        "low": "4848.000",
        "open": "4856.000",
        "volume": "160167",
        "wave": 0
    },
    {
        "close": "4852.000",
        "ctm": "1726837920",
        "ctmfmt": "2024-09-20 21:12:00",
        "high": "4854.000",
        "low": "4848.000",
        "open": "4848.000",
        "volume": "122743",
        "wave": 0
    },
    {
        "close": "4848.000",
        "ctm": "1726837980",
        "ctmfmt": "2024-09-20 21:13:00",
        "high": "4854.000",
        "low": "4848.000",
        "open": "4852.000",
        "volume": "94578",
        "wave": 0
    },
    {
        "close": "4854.000",
        "ctm": "1726838040",
        "ctmfmt": "2024-09-20 21:14:00",
        "high": "4854.000",
        "low": "4848.000",
        "open": "4848.000",
        "volume": "117158",
        "wave": 0
    },
    {
        "close": "4850.000",
        "ctm": "1726838100",
        "ctmfmt": "2024-09-20 21:15:00",
        "high": "4854.000",
        "low": "4850.000",
        "open": "4854.000",
        "volume": "200448",
        "wave": 0
    },
    {
        "close": "4848.000",
        "ctm": "1726838160",
        "ctmfmt": "2024-09-20 21:16:00",
        "high": "4854.000",
        "low": "4848.000",
        "open": "4850.000",
        "volume": "94961",
        "wave": 0
    },
    {
        "close": "4840.000",
        "ctm": "1726838220",
        "ctmfmt": "2024-09-20 21:17:00",
        "high": "4850.000",
        "low": "4840.000",
        "open": "4848.000",
        "volume": "185636",
        "wave": 0
    },
    {
        "close": "4834.000",
        "ctm": "1726838280",
        "ctmfmt": "2024-09-20 21:18:00",
        "high": "4842.000",
        "low": "4834.000",
        "open": "4840.000",
        "volume": "210401",
        "wave": 0
    },
    {
        "close": "4836.000",
        "ctm": "1726838340",
        "ctmfmt": "2024-09-20 21:19:00",
        "high": "4838.000",
        "low": "4832.000",
        "open": "4836.000",
        "volume": "163091",
        "wave": 0
    },
    {
        "close": "4836.000",
        "ctm": "1726838400",
        "ctmfmt": "2024-09-20 21:20:00",
        "high": "4838.000",
        "low": "4832.000",
        "open": "4836.000",
        "volume": "135860",
        "wave": 0
    },
    {
        "close": "4834.000",
        "ctm": "1726838460",
        "ctmfmt": "2024-09-20 21:21:00",
        "high": "4838.000",
        "low": "4832.000",
        "open": "4836.000",
        "volume": "90995",
        "wave": 0
    },
    {
        "close": "4842.000",
        "ctm": "1726838520",
        "ctmfmt": "2024-09-20 21:22:00",
        "high": "4842.000",
        "low": "4832.000",
        "open": "4834.000",
        "volume": "127919",
        "wave": 0
    },
    {
        "close": "4844.000",
        "ctm": "1726838580",
        "ctmfmt": "2024-09-20 21:23:00",
        "high": "4848.000",
        "low": "4842.000",
        "open": "4842.000",
        "volume": "161336",
        "wave": 0
    },
    {
        "close": "4836.000",
        "ctm": "1726838640",
        "ctmfmt": "2024-09-20 21:24:00",
        "high": "4844.000",
        "low": "4832.000",
        "open": "4842.000",
        "volume": "101539",
        "wave": 0
    },
    {
        "close": "4834.000",
        "ctm": "1726838700",
        "ctmfmt": "2024-09-20 21:25:00",
        "high": "4836.000",
        "low": "4832.000",
        "open": "4836.000",
        "volume": "84439",
        "wave": 0
    },
    {
        "close": "4836.000",
        "ctm": "1726838760",
        "ctmfmt": "2024-09-20 21:26:00",
        "high": "4838.000",
        "low": "4832.000",
        "open": "4834.000",
        "volume": "87220",
        "wave": 0
    },
    {
        "close": "4832.000",
        "ctm": "1726838820",
        "ctmfmt": "2024-09-20 21:27:00",
        "high": "4836.000",
        "low": "4832.000",
        "open": "4836.000",
        "volume": "101289",
        "wave": 0
    },
    {
        "close": "4834.000",
        "ctm": "1726838880",
        "ctmfmt": "2024-09-20 21:28:00",
        "high": "4834.000",
        "low": "4832.000",
        "open": "4834.000",
        "volume": "125187",
        "wave": 0
    },
    {
        "close": "4832.000",
        "ctm": "1726838940",
        "ctmfmt": "2024-09-20 21:29:00",
        "high": "4834.000",
        "low": "4832.000",
        "open": "4834.000",
        "volume": "60584",
        "wave": 0
    },
    {
        "close": "4834.000",
        "ctm": "1726839000",
        "ctmfmt": "2024-09-20 21:30:00",
        "high": "4836.000",
        "low": "4832.000",
        "open": "4832.000",
        "volume": "64339",
        "wave": 0
    },
    {
        "close": "4834.000",
        "ctm": "1726839060",
        "ctmfmt": "2024-09-20 21:31:00",
        "high": "4836.000",
        "low": "4832.000",
        "open": "4834.000",
        "volume": "82218",
        "wave": 0
    },
    {
        "close": "4832.000",
        "ctm": "1726839120",
        "ctmfmt": "2024-09-20 21:32:00",
        "high": "4834.000",
        "low": "4828.000",
        "open": "4832.000",
        "volume": "11312",
        "wave": 0
    },
    {
        "close": "4832.000",
        "ctm": "1726839180",
        "ctmfmt": "2024-09-20 21:33:00",
        "high": "4836.000",
        "low": "4832.000",
        "open": "4834.000",
        "volume": "92753",
        "wave": 0
    },
    {
        "close": "4838.000",
        "ctm": "1726839240",
        "ctmfmt": "2024-09-20 21:34:00",
        "high": "4838.000",
        "low": "4834.000",
        "open": "4834.000",
        "volume": "47440",
        "wave": 0
    },
    {
        "close": "4828.000",
        "ctm": "1726839300",
        "ctmfmt": "2024-09-20 21:35:00",
        "high": "4836.000",
        "low": "4828.000",
        "open": "4836.000",
        "volume": "90538",
        "wave": 0
    },
    {
        "close": "4830.000",
        "ctm": "1726839360",
        "ctmfmt": "2024-09-20 21:36:00",
        "high": "4832.000",
        "low": "4828.000",
        "open": "4830.000",
        "volume": "122146",
        "wave": 0
    },
    {
        "close": "4832.000",
        "ctm": "1726839420",
        "ctmfmt": "2024-09-20 21:37:00",
        "high": "4834.000",
        "low": "4830.000",
        "open": "4830.000",
        "volume": "48664",
        "wave": 0
    },
    {
        "close": "4830.000",
        "ctm": "1726839480",
        "ctmfmt": "2024-09-20 21:38:00",
        "high": "4832.000",
        "low": "4828.000",
        "open": "4832.000",
        "volume": "41078",
        "wave": 0
    },
    {
        "close": "4828.000",
        "ctm": "1726839540",
        "ctmfmt": "2024-09-20 21:39:00",
        "high": "4830.000",
        "low": "4826.000",
        "open": "4830.000",
        "volume": "96251",
        "wave": 0
    },
    {
        "close": "4828.000",
        "ctm": "1726839600",
        "ctmfmt": "2024-09-20 21:40:00",
        "high": "4830.000",
        "low": "4826.000",
        "open": "4828.000",
        "volume": "75911",
        "wave": 0
    },
    {
        "close": "4832.000",
        "ctm": "1726839660",
        "ctmfmt": "2024-09-20 21:41:00",
        "high": "4832.000",
        "low": "4826.000",
        "open": "4828.000",
        "volume": "116764",
        "wave": 0
    },
    {
        "close": "4830.000",
        "ctm": "1726839720",
        "ctmfmt": "2024-09-20 21:42:00",
        "high": "4832.000",
        "low": "4828.000",
        "open": "4830.000",
        "volume": "71231",
        "wave": 0
    },
    {
        "close": "4830.000",
        "ctm": "1726839780",
        "ctmfmt": "2024-09-20 21:43:00",
        "high": "4832.000",
        "low": "4828.000",
        "open": "4830.000",
        "volume": "36611",
        "wave": 0
    },
    {
        "close": "4824.000",
        "ctm": "1726839840",
        "ctmfmt": "2024-09-20 21:44:00",
        "high": "4830.000",
        "low": "4824.000",
        "open": "4830.000",
        "volume": "140581",
        "wave": 0
    },
    {
        "close": "4816.000",
        "ctm": "1726839900",
        "ctmfmt": "2024-09-20 21:45:00",
        "high": "4822.000",
        "low": "4816.000",
        "open": "4822.000",
        "volume": "399329",
        "wave": 0
    },
    {
        "close": "4816.000",
        "ctm": "1726839960",
        "ctmfmt": "2024-09-20 21:46:00",
        "high": "4818.000",
        "low": "4814.000",
        "open": "4816.000",
        "volume": "147872",
        "wave": 0
    },
    {
        "close": "4804.000",
        "ctm": "1726840020",
        "ctmfmt": "2024-09-20 21:47:00",
        "high": "4816.000",
        "low": "4804.000",
        "open": "4816.000",
        "volume": "342799",
        "wave": 0
    },
    {
        "close": "4804.000",
        "ctm": "1726840080",
        "ctmfmt": "2024-09-20 21:48:00",
        "high": "4808.000",
        "low": "4802.000",
        "open": "4804.000",
        "volume": "221255",
        "wave": 0
    },
    {
        "close": "4796.000",
        "ctm": "1726840140",
        "ctmfmt": "2024-09-20 21:49:00",
        "high": "4806.000",
        "low": "4794.000",
        "open": "4804.000",
        "volume": "405440",
        "wave": 0
    },
    {
        "close": "4802.000",
        "ctm": "1726840200",
        "ctmfmt": "2024-09-20 21:50:00",
        "high": "4804.000",
        "low": "4796.000",
        "open": "4796.000",
        "volume": "209042",
        "wave": 0
    },
    {
        "close": "4804.000",
        "ctm": "1726840260",
        "ctmfmt": "2024-09-20 21:51:00",
        "high": "4806.000",
        "low": "4798.000",
        "open": "4804.000",
        "volume": "118930",
        "wave": 0
    },
    {
        "close": "4804.000",
        "ctm": "1726840320",
        "ctmfmt": "2024-09-20 21:52:00",
        "high": "4806.000",
        "low": "4800.000",
        "open": "4804.000",
        "volume": "99782",
        "wave": 0
    },
    {
        "close": "4800.000",
        "ctm": "1726840380",
        "ctmfmt": "2024-09-20 21:53:00",
        "high": "4804.000",
        "low": "4798.000",
        "open": "4802.000",
        "volume": "130061",
        "wave": 0
    },
    {
        "close": "4792.000",
        "ctm": "1726840440",
        "ctmfmt": "2024-09-20 21:54:00",
        "high": "4800.000",
        "low": "4792.000",
        "open": "4798.000",
        "volume": "141942",
        "wave": 0
    },
    {
        "close": "4798.000",
        "ctm": "1726840500",
        "ctmfmt": "2024-09-20 21:55:00",
        "high": "4800.000",
        "low": "4792.000",
        "open": "4792.000",
        "volume": "86326",
        "wave": 0
    },
    {
        "close": "4796.000",
        "ctm": "1726840560",
        "ctmfmt": "2024-09-20 21:56:00",
        "high": "4800.000",
        "low": "4796.000",
        "open": "4798.000",
        "volume": "56137",
        "wave": 0
    },
    {
        "close": "4792.000",
        "ctm": "1726840620",
        "ctmfmt": "2024-09-20 21:57:00",
        "high": "4798.000",
        "low": "4792.000",
        "open": "4796.000",
        "volume": "117311",
        "wave": 0
    },
    {
        "close": "4790.000",
        "ctm": "1726840680",
        "ctmfmt": "2024-09-20 21:58:00",
        "high": "4794.000",
        "low": "4790.000",
        "open": "4792.000",
        "volume": "93077",
        "wave": 0
    },
    {
        "close": "4794.000",
        "ctm": "1726840740",
        "ctmfmt": "2024-09-20 21:59:00",
        "high": "4796.000",
        "low": "4790.000",
        "open": "4790.000",
        "volume": "91638",
        "wave": 0
    },
    {
        "close": "4788.000",
        "ctm": "1726840800",
        "ctmfmt": "2024-09-20 22:00:00",
        "high": "4796.000",
        "low": "4788.000",
        "open": "4794.000",
        "volume": "125460",
        "wave": 0
    },
    {
        "close": "4788.000",
        "ctm": "1726840860",
        "ctmfmt": "2024-09-20 22:01:00",
        "high": "4792.000",
        "low": "4788.000",
        "open": "4790.000",
        "volume": "122603",
        "wave": 0
    },
    {
        "close": "4788.000",
        "ctm": "1726840920",
        "ctmfmt": "2024-09-20 22:02:00",
        "high": "4790.000",
        "low": "4784.000",
        "open": "4788.000",
        "volume": "161717",
        "wave": 0
    },
    {
        "close": "4796.000",
        "ctm": "1726840980",
        "ctmfmt": "2024-09-20 22:03:00",
        "high": "4798.000",
        "low": "4788.000",
        "open": "4790.000",
        "volume": "185687",
        "wave": 0
    },
    {
        "close": "4780.000",
        "ctm": "1726841040",
        "ctmfmt": "2024-09-20 22:04:00",
        "high": "4796.000",
        "low": "4780.000",
        "open": "4796.000",
        "volume": "285593",
        "wave": 0
    },
    {
        "close": "4784.000",
        "ctm": "1726841100",
        "ctmfmt": "2024-09-20 22:05:00",
        "high": "4788.000",
        "low": "4780.000",
        "open": "4780.000",
        "volume": "155786",
        "wave": 0
    },
    {
        "close": "4786.000",
        "ctm": "1726841160",
        "ctmfmt": "2024-09-20 22:06:00",
        "high": "4788.000",
        "low": "4784.000",
        "open": "4786.000",
        "volume": "43259",
        "wave": 0
    },
    {
        "close": "4792.000",
        "ctm": "1726841220",
        "ctmfmt": "2024-09-20 22:07:00",
        "high": "4794.000",
        "low": "4784.000",
        "open": "4786.000",
        "volume": "114255",
        "wave": 0
    },
    {
        "close": "4792.000",
        "ctm": "1726841280",
        "ctmfmt": "2024-09-20 22:08:00",
        "high": "4794.000",
        "low": "4792.000",
        "open": "4794.000",
        "volume": "60255",
        "wave": 0
    },
    {
        "close": "4804.000",
        "ctm": "1726841340",
        "ctmfmt": "2024-09-20 22:09:00",
        "high": "4804.000",
        "low": "4792.000",
        "open": "4794.000",
        "volume": "148174",
        "wave": 0
    },
    {
        "close": "4794.000",
        "ctm": "1726841400",
        "ctmfmt": "2024-09-20 22:10:00",
        "high": "4802.000",
        "low": "4794.000",
        "open": "4800.000",
        "volume": "413657",
        "wave": 0
    },
    {
        "close": "4796.000",
        "ctm": "1726841460",
        "ctmfmt": "2024-09-20 22:11:00",
        "high": "4802.000",
        "low": "4794.000",
        "open": "4794.000",
        "volume": "81248",
        "wave": 0
    },
    {
        "close": "4798.000",
        "ctm": "1726841520",
        "ctmfmt": "2024-09-20 22:12:00",
        "high": "4798.000",
        "low": "4794.000",
        "open": "4798.000",
        "volume": "54735",
        "wave": 0
    },
    {
        "close": "4794.000",
        "ctm": "1726841580",
        "ctmfmt": "2024-09-20 22:13:00",
        "high": "4796.000",
        "low": "4790.000",
        "open": "4796.000",
        "volume": "39823",
        "wave": 0
    },
    {
        "close": "4796.000",
        "ctm": "1726841640",
        "ctmfmt": "2024-09-20 22:14:00",
        "high": "4796.000",
        "low": "4792.000",
        "open": "4794.000",
        "volume": "73519",
        "wave": 0
    },
    {
        "close": "4798.000",
        "ctm": "1726841700",
        "ctmfmt": "2024-09-20 22:15:00",
        "high": "4800.000",
        "low": "4796.000",
        "open": "4796.000",
        "volume": "33612",
        "wave": 0
    },
    {
        "close": "4798.000",
        "ctm": "1726841760",
        "ctmfmt": "2024-09-20 22:16:00",
        "high": "4802.000",
        "low": "4796.000",
        "open": "4798.000",
        "volume": "56144",
        "wave": 0
    },
    {
        "close": "4802.000",
        "ctm": "1726841820",
        "ctmfmt": "2024-09-20 22:17:00",
        "high": "4806.000",
        "low": "4800.000",
        "open": "4800.000",
        "volume": "86375",
        "wave": 0
    },
    {
        "close": "4806.000",
        "ctm": "1726841880",
        "ctmfmt": "2024-09-20 22:18:00",
        "high": "4808.000",
        "low": "4802.000",
        "open": "4802.000",
        "volume": "129425",
        "wave": 0
    },
    {
        "close": "4802.000",
        "ctm": "1726841940",
        "ctmfmt": "2024-09-20 22:19:00",
        "high": "4806.000",
        "low": "4802.000",
        "open": "4806.000",
        "volume": "98422",
        "wave": 0
    },
    {
        "close": "4800.000",
        "ctm": "1726842000",
        "ctmfmt": "2024-09-20 22:20:00",
        "high": "4802.000",
        "low": "4800.000",
        "open": "4802.000",
        "volume": "50084",
        "wave": 0
    },
    {
        "close": "4806.000",
        "ctm": "1726842060",
        "ctmfmt": "2024-09-20 22:21:00",
        "high": "4808.000",
        "low": "4800.000",
        "open": "4800.000",
        "volume": "70200",
        "wave": 0
    },
    {
        "close": "4808.000",
        "ctm": "1726842120",
        "ctmfmt": "2024-09-20 22:22:00",
        "high": "4808.000",
        "low": "4804.000",
        "open": "4806.000",
        "volume": "49567",
        "wave": 0
    },
    {
        "close": "4808.000",
        "ctm": "1726842180",
        "ctmfmt": "2024-09-20 22:23:00",
        "high": "4812.000",
        "low": "4806.000",
        "open": "4808.000",
        "volume": "108592",
        "wave": 0
    },
    {
        "close": "4806.000",
        "ctm": "1726842240",
        "ctmfmt": "2024-09-20 22:24:00",
        "high": "4810.000",
        "low": "4804.000",
        "open": "4810.000",
        "volume": "30744",
        "wave": 0
    },
    {
        "close": "4802.000",
        "ctm": "1726842300",
        "ctmfmt": "2024-09-20 22:25:00",
        "high": "4806.000",
        "low": "4800.000",
        "open": "4806.000",
        "volume": "41370",
        "wave": 0
    },
    {
        "close": "4802.000",
        "ctm": "1726842360",
        "ctmfmt": "2024-09-20 22:26:00",
        "high": "4802.000",
        "low": "4800.000",
        "open": "4800.000",
        "volume": "77148",
        "wave": 0
    },
    {
        "close": "4796.000",
        "ctm": "1726842420",
        "ctmfmt": "2024-09-20 22:27:00",
        "high": "4802.000",
        "low": "4796.000",
        "open": "4802.000",
        "volume": "3113",
        "wave": 0
    },
    {
        "close": "4802.000",
        "ctm": "1726842480",
        "ctmfmt": "2024-09-20 22:28:00",
        "high": "4802.000",
        "low": "4796.000",
        "open": "4798.000",
        "volume": "56828",
        "wave": 0
    },
    {
        "close": "4798.000",
        "ctm": "1726842540",
        "ctmfmt": "2024-09-20 22:29:00",
        "high": "4806.000",
        "low": "4798.000",
        "open": "4802.000",
        "volume": "46409",
        "wave": 0
    },
    {
        "close": "4796.000",
        "ctm": "1726842600",
        "ctmfmt": "2024-09-20 22:30:00",
        "high": "4800.000",
        "low": "4794.000",
        "open": "4798.000",
        "volume": "73690",
        "wave": 0
    },
    {
        "close": "4800.000",
        "ctm": "1726842660",
        "ctmfmt": "2024-09-20 22:31:00",
        "high": "4802.000",
        "low": "4796.000",
        "open": "4796.000",
        "volume": "56559",
        "wave": 0
    },
    {
        "close": "4806.000",
        "ctm": "1726842720",
        "ctmfmt": "2024-09-20 22:32:00",
        "high": "4806.000",
        "low": "4800.000",
        "open": "4800.000",
        "volume": "35178",
        "wave": 0
    },
    {
        "close": "4804.000",
        "ctm": "1726842780",
        "ctmfmt": "2024-09-20 22:33:00",
        "high": "4810.000",
        "low": "4804.000",
        "open": "4804.000",
        "volume": "51752",
        "wave": 0
    },
    {
        "close": "4806.000",
        "ctm": "1726842840",
        "ctmfmt": "2024-09-20 22:34:00",
        "high": "4806.000",
        "low": "4804.000",
        "open": "4804.000",
        "volume": "35223",
        "wave": 0
    },
    {
        "close": "4802.000",
        "ctm": "1726842900",
        "ctmfmt": "2024-09-20 22:35:00",
        "high": "4806.000",
        "low": "4802.000",
        "open": "4804.000",
        "volume": "16214",
        "wave": 0
    },
    {
        "close": "4796.000",
        "ctm": "1726842960",
        "ctmfmt": "2024-09-20 22:36:00",
        "high": "4802.000",
        "low": "4796.000",
        "open": "4800.000",
        "volume": "60709",
        "wave": 0
    },
    {
        "close": "4796.000",
        "ctm": "1726843020",
        "ctmfmt": "2024-09-20 22:37:00",
        "high": "4800.000",
        "low": "4796.000",
        "open": "4800.000",
        "volume": "14876",
        "wave": 0
    },
    {
        "close": "4796.000",
        "ctm": "1726843080",
        "ctmfmt": "2024-09-20 22:38:00",
        "high": "4798.000",
        "low": "4794.000",
        "open": "4796.000",
        "volume": "40793",
        "wave": 0
    },
    {
        "close": "4796.000",
        "ctm": "1726843140",
        "ctmfmt": "2024-09-20 22:39:00",
        "high": "4798.000",
        "low": "4794.000",
        "open": "4794.000",
        "volume": "46117",
        "wave": 0
    },
    {
        "close": "4794.000",
        "ctm": "1726843200",
        "ctmfmt": "2024-09-20 22:40:00",
        "high": "4798.000",
        "low": "4794.000",
        "open": "4796.000",
        "volume": "37610",
        "wave": 0
    },
    {
        "close": "4796.000",
        "ctm": "1726843260",
        "ctmfmt": "2024-09-20 22:41:00",
        "high": "4798.000",
        "low": "4794.000",
        "open": "4794.000",
        "volume": "36496",
        "wave": 0
    },
    {
        "close": "4800.000",
        "ctm": "1726843320",
        "ctmfmt": "2024-09-20 22:42:00",
        "high": "4800.000",
        "low": "4796.000",
        "open": "4796.000",
        "volume": "23278",
        "wave": 0
    },
    {
        "close": "4802.000",
        "ctm": "1726843380",
        "ctmfmt": "2024-09-20 22:43:00",
        "high": "4804.000",
        "low": "4798.000",
        "open": "4800.000",
        "volume": "50765",
        "wave": 0
    },
    {
        "close": "4800.000",
        "ctm": "1726843440",
        "ctmfmt": "2024-09-20 22:44:00",
        "high": "4804.000",
        "low": "4798.000",
        "open": "4800.000",
        "volume": "36508",
        "wave": 0
    },
    {
        "close": "4802.000",
        "ctm": "1726843500",
        "ctmfmt": "2024-09-20 22:45:00",
        "high": "4806.000",
        "low": "4798.000",
        "open": "4802.000",
        "volume": "50663",
        "wave": 0
    },
    {
        "close": "4802.000",
        "ctm": "1726843560",
        "ctmfmt": "2024-09-20 22:46:00",
        "high": "4802.000",
        "low": "4798.000",
        "open": "4802.000",
        "volume": "45862",
        "wave": 0
    },
    {
        "close": "4798.000",
        "ctm": "1726843620",
        "ctmfmt": "2024-09-20 22:47:00",
        "high": "4806.000",
        "low": "4798.000",
        "open": "4802.000",
        "volume": "44618",
        "wave": 0
    },
    {
        "close": "4800.000",
        "ctm": "1726843680",
        "ctmfmt": "2024-09-20 22:48:00",
        "high": "4800.000",
        "low": "4796.000",
        "open": "4798.000",
        "volume": "19997",
        "wave": 0
    },
    {
        "close": "4800.000",
        "ctm": "1726843740",
        "ctmfmt": "2024-09-20 22:49:00",
        "high": "4802.000",
        "low": "4796.000",
        "open": "4800.000",
        "volume": "27099",
        "wave": 0
    },
    {
        "close": "4800.000",
        "ctm": "1726843800",
        "ctmfmt": "2024-09-20 22:50:00",
        "high": "4802.000",
        "low": "4798.000",
        "open": "4800.000",
        "volume": "21758",
        "wave": 0
    },
    {
        "close": "4800.000",
        "ctm": "1726843860",
        "ctmfmt": "2024-09-20 22:51:00",
        "high": "4802.000",
        "low": "4798.000",
        "open": "4798.000",
        "volume": "20842",
        "wave": 0
    },
    {
        "close": "4796.000",
        "ctm": "1726843920",
        "ctmfmt": "2024-09-20 22:52:00",
        "high": "4800.000",
        "low": "4796.000",
        "open": "4798.000",
        "volume": "11242",
        "wave": 0
    },
    {
        "close": "4794.000",
        "ctm": "1726843980",
        "ctmfmt": "2024-09-20 22:53:00",
        "high": "4798.000",
        "low": "4792.000",
        "open": "4796.000",
        "volume": "74878",
        "wave": 0
    },
    {
        "close": "4796.000",
        "ctm": "1726844040",
        "ctmfmt": "2024-09-20 22:54:00",
        "high": "4796.000",
        "low": "4792.000",
        "open": "4794.000",
        "volume": "45789",
        "wave": 0
    },
    {
        "close": "4798.000",
        "ctm": "1726844100",
        "ctmfmt": "2024-09-20 22:55:00",
        "high": "4798.000",
        "low": "4796.000",
        "open": "4796.000",
        "volume": "19975",
        "wave": 0
    },
    {
        "close": "4798.000",
        "ctm": "1726844160",
        "ctmfmt": "2024-09-20 22:56:00",
        "high": "4800.000",
        "low": "4794.000",
        "open": "4796.000",
        "volume": "59647",
        "wave": 0
    },
    {
        "close": "4800.000",
        "ctm": "1726844220",
        "ctmfmt": "2024-09-20 22:57:00",
        "high": "4800.000",
        "low": "4796.000",
        "open": "4798.000",
        "volume": "44310",
        "wave": 0
    },
    {
        "close": "4800.000",
        "ctm": "1726844280",
        "ctmfmt": "2024-09-20 22:58:00",
        "high": "4802.000",
        "low": "4798.000",
        "open": "4800.000",
        "volume": "60450",
        "wave": 0
    },
    {
        "close": "4798.000",
        "ctm": "1726844340",
        "ctmfmt": "2024-09-20 22:59:00",
        "high": "4802.000",
        "low": "4796.000",
        "open": "4802.000",
        "volume": "62606",
        "wave": 0
    },
    {
        "close": "4792.000",
        "ctm": "1726844400",
        "ctmfmt": "2024-09-20 23:00:00",
        "high": "4802.000",
        "low": "4792.000",
        "open": "4798.000",
        "volume": "128663",
        "wave": 0
    },
    {
        "close": "4796.000",
        "ctm": "1727053260",
        "ctmfmt": "2024-09-23 09:01:00",
        "high": "4800.000",
        "low": "4784.000",
        "open": "4792.000",
        "volume": "401913",
        "wave": 0
    },
    {
        "close": "4798.000",
        "ctm": "1727053320",
        "ctmfmt": "2024-09-23 09:02:00",
        "high": "4798.000",
        "low": "4790.000",
        "open": "4794.000",
        "volume": "99282",
        "wave": 0
    },
    {
        "close": "4810.000",
        "ctm": "1727053380",
        "ctmfmt": "2024-09-23 09:03:00",
        "high": "4810.000",
        "low": "4798.000",
        "open": "4798.000",
        "volume": "183939",
        "wave": 0
    },
    {
        "close": "4820.000",
        "ctm": "1727053440",
        "ctmfmt": "2024-09-23 09:04:00",
        "high": "4820.000",
        "low": "4810.000",
        "open": "4810.000",
        "volume": "311068",
        "wave": 0
    },
    {
        "close": "4818.000",
        "ctm": "1727053500",
        "ctmfmt": "2024-09-23 09:05:00",
        "high": "4820.000",
        "low": "4812.000",
        "open": "4820.000",
        "volume": "177140",
        "wave": 0
    },
    {
        "close": "4826.000",
        "ctm": "1727053560",
        "ctmfmt": "2024-09-23 09:06:00",
        "high": "4828.000",
        "low": "4818.000",
        "open": "4818.000",
        "volume": "187132",
        "wave": 0
    },
    {
        "close": "4822.000",
        "ctm": "1727053620",
        "ctmfmt": "2024-09-23 09:07:00",
        "high": "4828.000",
        "low": "4820.000",
        "open": "4826.000",
        "volume": "95808",
        "wave": 0
    },
    {
        "close": "4820.000",
        "ctm": "1727053680",
        "ctmfmt": "2024-09-23 09:08:00",
        "high": "4824.000",
        "low": "4818.000",
        "open": "4824.000",
        "volume": "54682",
        "wave": 0
    },
    {
        "close": "4822.000",
        "ctm": "1727053740",
        "ctmfmt": "2024-09-23 09:09:00",
        "high": "4822.000",
        "low": "4818.000",
        "open": "4820.000",
        "volume": "65212",
        "wave": 0
    },
    {
        "close": "4820.000",
        "ctm": "1727053800",
        "ctmfmt": "2024-09-23 09:10:00",
        "high": "4822.000",
        "low": "4814.000",
        "open": "4822.000",
        "volume": "60467",
        "wave": 0
    },
    {
        "close": "4808.000",
        "ctm": "1727053860",
        "ctmfmt": "2024-09-23 09:11:00",
        "high": "4820.000",
        "low": "4808.000",
        "open": "4820.000",
        "volume": "78432",
        "wave": 0
    },
    {
        "close": "4808.000",
        "ctm": "1727053920",
        "ctmfmt": "2024-09-23 09:12:00",
        "high": "4812.000",
        "low": "4804.000",
        "open": "4804.000",
        "volume": "120005",
        "wave": 0
    },
    {
        "close": "4810.000",
        "ctm": "1727053980",
        "ctmfmt": "2024-09-23 09:13:00",
        "high": "4810.000",
        "low": "4804.000",
        "open": "4810.000",
        "volume": "58973",
        "wave": 0
    },
    {
        "close": "4820.000",
        "ctm": "1727054040",
        "ctmfmt": "2024-09-23 09:14:00",
        "high": "4824.000",
        "low": "4810.000",
        "open": "4810.000",
        "volume": "109854",
        "wave": 0
    },
    {
        "close": "4830.000",
        "ctm": "1727054100",
        "ctmfmt": "2024-09-23 09:15:00",
        "high": "4830.000",
        "low": "4820.000",
        "open": "4820.000",
        "volume": "95203",
        "wave": 0
    },
    {
        "close": "4824.000",
        "ctm": "1727054160",
        "ctmfmt": "2024-09-23 09:16:00",
        "high": "4834.000",
        "low": "4824.000",
        "open": "4830.000",
        "volume": "5255",
        "wave": 0
    },
    {
        "close": "4818.000",
        "ctm": "1727054220",
        "ctmfmt": "2024-09-23 09:17:00",
        "high": "4818.000",
        "low": "4818.000",
        "open": "4818.000",
        "volume": "192",
        "wave": 0
    },
    {
        "close": "4818.000",
        "ctm": "1727054280",
        "ctmfmt": "2024-09-23 09:18:00",
        "high": "4820.000",
        "low": "4816.000",
        "open": "4818.000",
        "volume": "38256",
        "wave": 0
    },
    {
        "close": "4814.000",
        "ctm": "1727054340",
        "ctmfmt": "2024-09-23 09:19:00",
        "high": "4818.000",
        "low": "4806.000",
        "open": "4816.000",
        "volume": "81468",
        "wave": 0
    },
    {
        "close": "4808.000",
        "ctm": "1727054400",
        "ctmfmt": "2024-09-23 09:20:00",
        "high": "4814.000",
        "low": "4808.000",
        "open": "4814.000",
        "volume": "51818",
        "wave": 0
    },
    {
        "close": "4812.000",
        "ctm": "1727054460",
        "ctmfmt": "2024-09-23 09:21:00",
        "high": "4812.000",
        "low": "4806.000",
        "open": "4808.000",
        "volume": "42799",
        "wave": 0
    },
    {
        "close": "4808.000",
        "ctm": "1727054520",
        "ctmfmt": "2024-09-23 09:22:00",
        "high": "4812.000",
        "low": "4806.000",
        "open": "4808.000",
        "volume": "59077",
        "wave": 0
    },
    {
        "close": "4812.000",
        "ctm": "1727054580",
        "ctmfmt": "2024-09-23 09:23:00",
        "high": "4812.000",
        "low": "4810.000",
        "open": "4810.000",
        "volume": "23925",
        "wave": 0
    },
    {
        "close": "4818.000",
        "ctm": "1727054640",
        "ctmfmt": "2024-09-23 09:24:00",
        "high": "4820.000",
        "low": "4812.000",
        "open": "4812.000",
        "volume": "41437",
        "wave": 0
    },
    {
        "close": "4818.000",
        "ctm": "1727054700",
        "ctmfmt": "2024-09-23 09:25:00",
        "high": "4820.000",
        "low": "4814.000",
        "open": "4820.000",
        "volume": "28116",
        "wave": 0
    },
    {
        "close": "4820.000",
        "ctm": "1727054760",
        "ctmfmt": "2024-09-23 09:26:00",
        "high": "4824.000",
        "low": "4812.000",
        "open": "4824.000",
        "volume": "61042",
        "wave": 0
    },
    {
        "close": "4818.000",
        "ctm": "1727054820",
        "ctmfmt": "2024-09-23 09:27:00",
        "high": "4822.000",
        "low": "4816.000",
        "open": "4822.000",
        "volume": "24502",
        "wave": 0
    },
    {
        "close": "4818.000",
        "ctm": "1727054880",
        "ctmfmt": "2024-09-23 09:28:00",
        "high": "4820.000",
        "low": "4816.000",
        "open": "4820.000",
        "volume": "25035",
        "wave": 0
    },
    {
        "close": "4818.000",
        "ctm": "1727054940",
        "ctmfmt": "2024-09-23 09:29:00",
        "high": "4820.000",
        "low": "4812.000",
        "open": "4820.000",
        "volume": "25620",
        "wave": 0
    },
    {
        "close": "4818.000",
        "ctm": "1727055000",
        "ctmfmt": "2024-09-23 09:30:00",
        "high": "4822.000",
        "low": "4816.000",
        "open": "4818.000",
        "volume": "29004",
        "wave": 0
    },
    {
        "close": "4812.000",
        "ctm": "1727055060",
        "ctmfmt": "2024-09-23 09:31:00",
        "high": "4818.000",
        "low": "4810.000",
        "open": "4818.000",
        "volume": "43255",
        "wave": 0
    },
    {
        "close": "4808.000",
        "ctm": "1727055120",
        "ctmfmt": "2024-09-23 09:32:00",
        "high": "4814.000",
        "low": "4808.000",
        "open": "4808.000",
        "volume": "52154",
        "wave": 0
    },
    {
        "close": "4814.000",
        "ctm": "1727055180",
        "ctmfmt": "2024-09-23 09:33:00",
        "high": "4816.000",
        "low": "4808.000",
        "open": "4814.000",
        "volume": "27716",
        "wave": 0
    },
    {
        "close": "4818.000",
        "ctm": "1727055240",
        "ctmfmt": "2024-09-23 09:34:00",
        "high": "4824.000",
        "low": "4814.000",
        "open": "4818.000",
        "volume": "58471",
        "wave": 0
    },
    {
        "close": "4826.000",
        "ctm": "1727055300",
        "ctmfmt": "2024-09-23 09:35:00",
        "high": "4828.000",
        "low": "4820.000",
        "open": "4822.000",
        "volume": "33460",
        "wave": 0
    },
    {
        "close": "4828.000",
        "ctm": "1727055360",
        "ctmfmt": "2024-09-23 09:36:00",
        "high": "4828.000",
        "low": "4822.000",
        "open": "4824.000",
        "volume": "37366",
        "wave": 0
    },
    {
        "close": "4840.000",
        "ctm": "1727055420",
        "ctmfmt": "2024-09-23 09:37:00",
        "high": "4840.000",
        "low": "4826.000",
        "open": "4828.000",
        "volume": "131096",
        "wave": 0
    },
    {
        "close": "4832.000",
        "ctm": "1727055480",
        "ctmfmt": "2024-09-23 09:38:00",
        "high": "4838.000",
        "low": "4830.000",
        "open": "4838.000",
        "volume": "86573",
        "wave": 0
    },
    {
        "close": "4832.000",
        "ctm": "1727055540",
        "ctmfmt": "2024-09-23 09:39:00",
        "high": "4834.000",
        "low": "4828.000",
        "open": "4834.000",
        "volume": "3615",
        "wave": 0
    },
    {
        "close": "4834.000",
        "ctm": "1727055600",
        "ctmfmt": "2024-09-23 09:40:00",
        "high": "4836.000",
        "low": "4830.000",
        "open": "4830.000",
        "volume": "55819",
        "wave": 0
    },
    {
        "close": "4830.000",
        "ctm": "1727055660",
        "ctmfmt": "2024-09-23 09:41:00",
        "high": "4834.000",
        "low": "4830.000",
        "open": "4834.000",
        "volume": "15132",
        "wave": 0
    },
    {
        "close": "4842.000",
        "ctm": "1727055720",
        "ctmfmt": "2024-09-23 09:42:00",
        "high": "4842.000",
        "low": "4832.000",
        "open": "4842.000",
        "volume": "85395",
        "wave": 0
    },
    {
        "close": "4842.000",
        "ctm": "1727055780",
        "ctmfmt": "2024-09-23 09:43:00",
        "high": "4846.000",
        "low": "4840.000",
        "open": "4842.000",
        "volume": "85250",
        "wave": 0
    },
    {
        "close": "4836.000",
        "ctm": "1727055840",
        "ctmfmt": "2024-09-23 09:44:00",
        "high": "4842.000",
        "low": "4836.000",
        "open": "4842.000",
        "volume": "41957",
        "wave": 0
    },
    {
        "close": "4842.000",
        "ctm": "1727055900",
        "ctmfmt": "2024-09-23 09:45:00",
        "high": "4842.000",
        "low": "4834.000",
        "open": "4836.000",
        "volume": "43656",
        "wave": 0
    },
    {
        "close": "4838.000",
        "ctm": "1727055960",
        "ctmfmt": "2024-09-23 09:46:00",
        "high": "4842.000",
        "low": "4834.000",
        "open": "4840.000",
        "volume": "29496",
        "wave": 0
    },
    {
        "close": "4840.000",
        "ctm": "1727056020",
        "ctmfmt": "2024-09-23 09:47:00",
        "high": "4842.000",
        "low": "4838.000",
        "open": "4840.000",
        "volume": "42012",
        "wave": 0
    },
    {
        "close": "4846.000",
        "ctm": "1727056080",
        "ctmfmt": "2024-09-23 09:48:00",
        "high": "4846.000",
        "low": "4838.000",
        "open": "4840.000",
        "volume": "30319",
        "wave": 0
    },
    {
        "close": "4844.000",
        "ctm": "1727056140",
        "ctmfmt": "2024-09-23 09:49:00",
        "high": "4848.000",
        "low": "4844.000",
        "open": "4846.000",
        "volume": "48732",
        "wave": 0
    },
    {
        "close": "4848.000",
        "ctm": "1727056200",
        "ctmfmt": "2024-09-23 09:50:00",
        "high": "4850.000",
        "low": "4846.000",
        "open": "4848.000",
        "volume": "94632",
        "wave": 0
    },
    {
        "close": "4842.000",
        "ctm": "1727056260",
        "ctmfmt": "2024-09-23 09:51:00",
        "high": "4848.000",
        "low": "4842.000",
        "open": "4848.000",
        "volume": "25992",
        "wave": 0
    },
    {
        "close": "4844.000",
        "ctm": "1727056320",
        "ctmfmt": "2024-09-23 09:52:00",
        "high": "4844.000",
        "low": "4840.000",
        "open": "4844.000",
        "volume": "28528",
        "wave": 0
    },
    {
        "close": "4842.000",
        "ctm": "1727056380",
        "ctmfmt": "2024-09-23 09:53:00",
        "high": "4844.000",
        "low": "4840.000",
        "open": "4842.000",
        "volume": "29592",
        "wave": 0
    },
    {
        "close": "4842.000",
        "ctm": "1727056440",
        "ctmfmt": "2024-09-23 09:54:00",
        "high": "4842.000",
        "low": "4838.000",
        "open": "4840.000",
        "volume": "16342",
        "wave": 0
    },
    {
        "close": "4842.000",
        "ctm": "1727056500",
        "ctmfmt": "2024-09-23 09:55:00",
        "high": "4846.000",
        "low": "4840.000",
        "open": "4842.000",
        "volume": "25961",
        "wave": 0
    },
    {
        "close": "4846.000",
        "ctm": "1727056560",
        "ctmfmt": "2024-09-23 09:56:00",
        "high": "4846.000",
        "low": "4842.000",
        "open": "4842.000",
        "volume": "18447",
        "wave": 0
    },
    {
        "close": "4844.000",
        "ctm": "1727056620",
        "ctmfmt": "2024-09-23 09:57:00",
        "high": "4846.000",
        "low": "4840.000",
        "open": "4846.000",
        "volume": "20515",
        "wave": 0
    },
    {
        "close": "4852.000",
        "ctm": "1727056680",
        "ctmfmt": "2024-09-23 09:58:00",
        "high": "4854.000",
        "low": "4846.000",
        "open": "4846.000",
        "volume": "64394",
        "wave": 0
    },
    {
        "close": "4850.000",
        "ctm": "1727056740",
        "ctmfmt": "2024-09-23 09:59:00",
        "high": "4854.000",
        "low": "4850.000",
        "open": "4850.000",
        "volume": "5390",
        "wave": 0
    },
    {
        "close": "4856.000",
        "ctm": "1727056800",
        "ctmfmt": "2024-09-23 10:00:00",
        "high": "4856.000",
        "low": "4850.000",
        "open": "4852.000",
        "volume": "54896",
        "wave": 0
    },
    {
        "close": "4846.000",
        "ctm": "1727056860",
        "ctmfmt": "2024-09-23 10:01:00",
        "high": "4854.000",
        "low": "4846.000",
        "open": "4848.000",
        "volume": "41984",
        "wave": 0
    },
    {
        "close": "4842.000",
        "ctm": "1727056920",
        "ctmfmt": "2024-09-23 10:02:00",
        "high": "4844.000",
        "low": "4842.000",
        "open": "4842.000",
        "volume": "1221",
        "wave": 0
    },
    {
        "close": "4834.000",
        "ctm": "1727056980",
        "ctmfmt": "2024-09-23 10:03:00",
        "high": "4842.000",
        "low": "4834.000",
        "open": "4834.000",
        "volume": "32604",
        "wave": 0
    },
    {
        "close": "4832.000",
        "ctm": "1727057040",
        "ctmfmt": "2024-09-23 10:04:00",
        "high": "4836.000",
        "low": "4830.000",
        "open": "4834.000",
        "volume": "40473",
        "wave": 0
    },
    {
        "close": "4830.000",
        "ctm": "1727057100",
        "ctmfmt": "2024-09-23 10:05:00",
        "high": "4830.000",
        "low": "4824.000",
        "open": "4828.000",
        "volume": "47716",
        "wave": 0
    },
    {
        "close": "4826.000",
        "ctm": "1727057160",
        "ctmfmt": "2024-09-23 10:06:00",
        "high": "4830.000",
        "low": "4824.000",
        "open": "4826.000",
        "volume": "23600",
        "wave": 0
    },
    {
        "close": "4826.000",
        "ctm": "1727057220",
        "ctmfmt": "2024-09-23 10:07:00",
        "high": "4828.000",
        "low": "4822.000",
        "open": "4826.000",
        "volume": "23610",
        "wave": 0
    },
    {
        "close": "4828.000",
        "ctm": "1727057280",
        "ctmfmt": "2024-09-23 10:08:00",
        "high": "4832.000",
        "low": "4826.000",
        "open": "4826.000",
        "volume": "27760",
        "wave": 0
    },
    {
        "close": "4830.000",
        "ctm": "1727057340",
        "ctmfmt": "2024-09-23 10:09:00",
        "high": "4830.000",
        "low": "4826.000",
        "open": "4828.000",
        "volume": "22160",
        "wave": 0
    },
    {
        "close": "4828.000",
        "ctm": "1727057400",
        "ctmfmt": "2024-09-23 10:10:00",
        "high": "4830.000",
        "low": "4828.000",
        "open": "4830.000",
        "volume": "7510",
        "wave": 0
    },
    {
        "close": "4832.000",
        "ctm": "1727057460",
        "ctmfmt": "2024-09-23 10:11:00",
        "high": "4836.000",
        "low": "4830.000",
        "open": "4830.000",
        "volume": "20740",
        "wave": 0
    },
    {
        "close": "4830.000",
        "ctm": "1727057520",
        "ctmfmt": "2024-09-23 10:12:00",
        "high": "4834.000",
        "low": "4830.000",
        "open": "4832.000",
        "volume": "10450",
        "wave": 0
    },
    {
        "close": "4830.000",
        "ctm": "1727057580",
        "ctmfmt": "2024-09-23 10:13:00",
        "high": "4832.000",
        "low": "4828.000",
        "open": "4832.000",
        "volume": "686",
        "wave": 0
    },
    {
        "close": "4824.000",
        "ctm": "1727057640",
        "ctmfmt": "2024-09-23 10:14:00",
        "high": "4830.000",
        "low": "4824.000",
        "open": "4826.000",
        "volume": "12545",
        "wave": 0
    },
    {
        "close": "4830.000",
        "ctm": "1727057700",
        "ctmfmt": "2024-09-23 10:15:00",
        "high": "4830.000",
        "low": "4824.000",
        "open": "4824.000",
        "volume": "14377",
        "wave": 0
    },
    {
        "close": "4834.000",
        "ctm": "1727058660",
        "ctmfmt": "2024-09-23 10:31:00",
        "high": "4834.000",
        "low": "4826.000",
        "open": "4830.000",
        "volume": "15605",
        "wave": 0
    },
    {
        "close": "4832.000",
        "ctm": "1727058720",
        "ctmfmt": "2024-09-23 10:32:00",
        "high": "4834.000",
        "low": "4830.000",
        "open": "4834.000",
        "volume": "12240",
        "wave": 0
    },
    {
        "close": "4838.000",
        "ctm": "1727058780",
        "ctmfmt": "2024-09-23 10:33:00",
        "high": "4840.000",
        "low": "4830.000",
        "open": "4830.000",
        "volume": "18144",
        "wave": 0
    },
    {
        "close": "4832.000",
        "ctm": "1727058840",
        "ctmfmt": "2024-09-23 10:34:00",
        "high": "4838.000",
        "low": "4832.000",
        "open": "4838.000",
        "volume": "7488",
        "wave": 0
    },
    {
        "close": "4834.000",
        "ctm": "1727058900",
        "ctmfmt": "2024-09-23 10:35:00",
        "high": "4836.000",
        "low": "4830.000",
        "open": "4832.000",
        "volume": "9819",
        "wave": 0
    },
    {
        "close": "4838.000",
        "ctm": "1727058960",
        "ctmfmt": "2024-09-23 10:36:00",
        "high": "4842.000",
        "low": "4836.000",
        "open": "4836.000",
        "volume": "22950",
        "wave": 0
    },
    {
        "close": "4830.000",
        "ctm": "1727059020",
        "ctmfmt": "2024-09-23 10:37:00",
        "high": "4840.000",
        "low": "4828.000",
        "open": "4838.000",
        "volume": "37117",
        "wave": 0
    },
    {
        "close": "4830.000",
        "ctm": "1727059080",
        "ctmfmt": "2024-09-23 10:38:00",
        "high": "4832.000",
        "low": "4828.000",
        "open": "4830.000",
        "volume": "10403",
        "wave": 0
    },
    {
        "close": "4828.000",
        "ctm": "1727059140",
        "ctmfmt": "2024-09-23 10:39:00",
        "high": "4832.000",
        "low": "4826.000",
        "open": "4828.000",
        "volume": "16688",
        "wave": 0
    },
    {
        "close": "4834.000",
        "ctm": "1727059200",
        "ctmfmt": "2024-09-23 10:40:00",
        "high": "4834.000",
        "low": "4828.000",
        "open": "4830.000",
        "volume": "6640",
        "wave": 0
    },
    {
        "close": "4838.000",
        "ctm": "1727059260",
        "ctmfmt": "2024-09-23 10:41:00",
        "high": "4840.000",
        "low": "4832.000",
        "open": "4834.000",
        "volume": "12824",
        "wave": 0
    },
    {
        "close": "4838.000",
        "ctm": "1727059320",
        "ctmfmt": "2024-09-23 10:42:00",
        "high": "4842.000",
        "low": "4838.000",
        "open": "4838.000",
        "volume": "7984",
        "wave": 0
    },
    {
        "close": "4838.000",
        "ctm": "1727059380",
        "ctmfmt": "2024-09-23 10:43:00",
        "high": "4840.000",
        "low": "4836.000",
        "open": "4838.000",
        "volume": "8136",
        "wave": 0
    },
    {
        "close": "4840.000",
        "ctm": "1727059440",
        "ctmfmt": "2024-09-23 10:44:00",
        "high": "4844.000",
        "low": "4838.000",
        "open": "4838.000",
        "volume": "18434",
        "wave": 0
    },
    {
        "close": "4838.000",
        "ctm": "1727059500",
        "ctmfmt": "2024-09-23 10:45:00",
        "high": "4842.000",
        "low": "4838.000",
        "open": "4838.000",
        "volume": "6822",
        "wave": 0
    },
    {
        "close": "4838.000",
        "ctm": "1727059560",
        "ctmfmt": "2024-09-23 10:46:00",
        "high": "4840.000",
        "low": "4838.000",
        "open": "4838.000",
        "volume": "5723",
        "wave": 0
    },
    {
        "close": "4836.000",
        "ctm": "1727059620",
        "ctmfmt": "2024-09-23 10:47:00",
        "high": "4838.000",
        "low": "4834.000",
        "open": "4836.000",
        "volume": "6565",
        "wave": 0
    },
    {
        "close": "4846.000",
        "ctm": "1727059680",
        "ctmfmt": "2024-09-23 10:48:00",
        "high": "4846.000",
        "low": "4836.000",
        "open": "4838.000",
        "volume": "18579",
        "wave": 0
    },
    {
        "close": "4846.000",
        "ctm": "1727059740",
        "ctmfmt": "2024-09-23 10:49:00",
        "high": "4846.000",
        "low": "4844.000",
        "open": "4846.000",
        "volume": "8995",
        "wave": 0
    },
    {
        "close": "4838.000",
        "ctm": "1727059800",
        "ctmfmt": "2024-09-23 10:50:00",
        "high": "4846.000",
        "low": "4838.000",
        "open": "4840.000",
        "volume": "10307",
        "wave": 0
    },
    {
        "close": "4840.000",
        "ctm": "1727059860",
        "ctmfmt": "2024-09-23 10:51:00",
        "high": "4842.000",
        "low": "4838.000",
        "open": "4840.000",
        "volume": "9436",
        "wave": 0
    },
    {
        "close": "4836.000",
        "ctm": "1727059920",
        "ctmfmt": "2024-09-23 10:52:00",
        "high": "4840.000",
        "low": "4834.000",
        "open": "4840.000",
        "volume": "9840",
        "wave": 0
    },
    {
        "close": "4828.000",
        "ctm": "1727059980",
        "ctmfmt": "2024-09-23 10:53:00",
        "high": "4836.000",
        "low": "4828.000",
        "open": "4834.000",
        "volume": "15680",
        "wave": 0
    },
    {
        "close": "4830.000",
        "ctm": "1727060040",
        "ctmfmt": "2024-09-23 10:54:00",
        "high": "4834.000",
        "low": "4830.000",
        "open": "4830.000",
        "volume": "10248",
        "wave": 0
    },
    {
        "close": "4830.000",
        "ctm": "1727060100",
        "ctmfmt": "2024-09-23 10:55:00",
        "high": "4832.000",
        "low": "4830.000",
        "open": "4830.000",
        "volume": "994",
        "wave": 0
    },
    {
        "close": "4838.000",
        "ctm": "1727060160",
        "ctmfmt": "2024-09-23 10:56:00",
        "high": "4840.000",
        "low": "4830.000",
        "open": "4832.000",
        "volume": "19663",
        "wave": 0
    },
    {
        "close": "4836.000",
        "ctm": "1727060220",
        "ctmfmt": "2024-09-23 10:57:00",
        "high": "4840.000",
        "low": "4836.000",
        "open": "4838.000",
        "volume": "4823",
        "wave": 0
    },
    {
        "close": "4838.000",
        "ctm": "1727060280",
        "ctmfmt": "2024-09-23 10:58:00",
        "high": "4838.000",
        "low": "4836.000",
        "open": "4836.000",
        "volume": "782",
        "wave": 0
    },
    {
        "close": "4834.000",
        "ctm": "1727060340",
        "ctmfmt": "2024-09-23 10:59:00",
        "high": "4838.000",
        "low": "4832.000",
        "open": "4832.000",
        "volume": "4339",
        "wave": 0
    },
    {
        "close": "4834.000",
        "ctm": "1727060400",
        "ctmfmt": "2024-09-23 11:00:00",
        "high": "4834.000",
        "low": "4832.000",
        "open": "4834.000",
        "volume": "4411",
        "wave": 0
    },
    {
        "close": "4836.000",
        "ctm": "1727060460",
        "ctmfmt": "2024-09-23 11:01:00",
        "high": "4836.000",
        "low": "4832.000",
        "open": "4834.000",
        "volume": "3233",
        "wave": 0
    },
    {
        "close": "4836.000",
        "ctm": "1727060520",
        "ctmfmt": "2024-09-23 11:02:00",
        "high": "4838.000",
        "low": "4836.000",
        "open": "4836.000",
        "volume": "4026",
        "wave": 0
    },
    {
        "close": "4840.000",
        "ctm": "1727060580",
        "ctmfmt": "2024-09-23 11:03:00",
        "high": "4844.000",
        "low": "4836.000",
        "open": "4844.000",
        "volume": "11327",
        "wave": 0
    },
    {
        "close": "4836.000",
        "ctm": "1727060640",
        "ctmfmt": "2024-09-23 11:04:00",
        "high": "4842.000",
        "low": "4836.000",
        "open": "4838.000",
        "volume": "6865",
        "wave": 0
    },
    {
        "close": "4840.000",
        "ctm": "1727060700",
        "ctmfmt": "2024-09-23 11:05:00",
        "high": "4842.000",
        "low": "4836.000",
        "open": "4838.000",
        "volume": "4189",
        "wave": 0
    },
    {
        "close": "4840.000",
        "ctm": "1727060760",
        "ctmfmt": "2024-09-23 11:06:00",
        "high": "4840.000",
        "low": "4838.000",
        "open": "4840.000",
        "volume": "1572",
        "wave": 0
    },
    {
        "close": "4838.000",
        "ctm": "1727060820",
        "ctmfmt": "2024-09-23 11:07:00",
        "high": "4840.000",
        "low": "4836.000",
        "open": "4838.000",
        "volume": "6129",
        "wave": 0
    },
    {
        "close": "4828.000",
        "ctm": "1727060880",
        "ctmfmt": "2024-09-23 11:08:00",
        "high": "4838.000",
        "low": "4828.000",
        "open": "4830.000",
        "volume": "10711",
        "wave": 0
    },
    {
        "close": "4830.000",
        "ctm": "1727060940",
        "ctmfmt": "2024-09-23 11:09:00",
        "high": "4832.000",
        "low": "4828.000",
        "open": "4828.000",
        "volume": "9247",
        "wave": 0
    },
    {
        "close": "4828.000",
        "ctm": "1727061000",
        "ctmfmt": "2024-09-23 11:10:00",
        "high": "4832.000",
        "low": "4826.000",
        "open": "4830.000",
        "volume": "10958",
        "wave": 0
    },
    {
        "close": "4828.000",
        "ctm": "1727061060",
        "ctmfmt": "2024-09-23 11:11:00",
        "high": "4832.000",
        "low": "4828.000",
        "open": "4830.000",
        "volume": "863",
        "wave": 0
    },
    {
        "close": "4828.000",
        "ctm": "1727061120",
        "ctmfmt": "2024-09-23 11:12:00",
        "high": "4830.000",
        "low": "4828.000",
        "open": "4828.000",
        "volume": "3974",
        "wave": 0
    },
    {
        "close": "4826.000",
        "ctm": "1727061180",
        "ctmfmt": "2024-09-23 11:13:00",
        "high": "4828.000",
        "low": "4824.000",
        "open": "4828.000",
        "volume": "11186",
        "wave": 0
    },
    {
        "close": "4828.000",
        "ctm": "1727061240",
        "ctmfmt": "2024-09-23 11:14:00",
        "high": "4830.000",
        "low": "4824.000",
        "open": "4826.000",
        "volume": "8862",
        "wave": 0
    },
    {
        "close": "4826.000",
        "ctm": "1727061300",
        "ctmfmt": "2024-09-23 11:15:00",
        "high": "4830.000",
        "low": "4826.000",
        "open": "4826.000",
        "volume": "4763",
        "wave": 0
    },
    {
        "close": "4826.000",
        "ctm": "1727061360",
        "ctmfmt": "2024-09-23 11:16:00",
        "high": "4828.000",
        "low": "4826.000",
        "open": "4828.000",
        "volume": "5264",
        "wave": 0
    },
    {
        "close": "4826.000",
        "ctm": "1727061420",
        "ctmfmt": "2024-09-23 11:17:00",
        "high": "4826.000",
        "low": "4818.000",
        "open": "4824.000",
        "volume": "27500",
        "wave": 0
    },
    {
        "close": "4834.000",
        "ctm": "1727061480",
        "ctmfmt": "2024-09-23 11:18:00",
        "high": "4834.000",
        "low": "4826.000",
        "open": "4826.000",
        "volume": "10059",
        "wave": 0
    },
    {
        "close": "4832.000",
        "ctm": "1727061540",
        "ctmfmt": "2024-09-23 11:19:00",
        "high": "4840.000",
        "low": "4832.000",
        "open": "4836.000",
        "volume": "21917",
        "wave": 0
    },
    {
        "close": "4832.000",
        "ctm": "1727061600",
        "ctmfmt": "2024-09-23 11:20:00",
        "high": "4834.000",
        "low": "4826.000",
        "open": "4834.000",
        "volume": "1734",
        "wave": 0
    },
    {
        "close": "4828.000",
        "ctm": "1727061660",
        "ctmfmt": "2024-09-23 11:21:00",
        "high": "4832.000",
        "low": "4828.000",
        "open": "4830.000",
        "volume": "10515",
        "wave": 0
    },
    {
        "close": "4828.000",
        "ctm": "1727061720",
        "ctmfmt": "2024-09-23 11:22:00",
        "high": "4830.000",
        "low": "4826.000",
        "open": "4826.000",
        "volume": "3816",
        "wave": 0
    },
    {
        "close": "4830.000",
        "ctm": "1727061780",
        "ctmfmt": "2024-09-23 11:23:00",
        "high": "4832.000",
        "low": "4826.000",
        "open": "4830.000",
        "volume": "6328",
        "wave": 0
    },
    {
        "close": "4828.000",
        "ctm": "1727061840",
        "ctmfmt": "2024-09-23 11:24:00",
        "high": "4830.000",
        "low": "4826.000",
        "open": "4828.000",
        "volume": "5881",
        "wave": 0
    },
    {
        "close": "4832.000",
        "ctm": "1727061900",
        "ctmfmt": "2024-09-23 11:25:00",
        "high": "4832.000",
        "low": "4828.000",
        "open": "4830.000",
        "volume": "2579",
        "wave": 0
    },
    {
        "close": "4828.000",
        "ctm": "1727061960",
        "ctmfmt": "2024-09-23 11:26:00",
        "high": "4832.000",
        "low": "4826.000",
        "open": "4830.000",
        "volume": "3063",
        "wave": 0
    },
    {
        "close": "4830.000",
        "ctm": "1727062020",
        "ctmfmt": "2024-09-23 11:27:00",
        "high": "4832.000",
        "low": "4828.000",
        "open": "4830.000",
        "volume": "3806",
        "wave": 0
    },
    {
        "close": "4832.000",
        "ctm": "1727062080",
        "ctmfmt": "2024-09-23 11:28:00",
        "high": "4832.000",
        "low": "4830.000",
        "open": "4832.000",
        "volume": "3745",
        "wave": 0
    },
    {
        "close": "4832.000",
        "ctm": "1727062140",
        "ctmfmt": "2024-09-23 11:29:00",
        "high": "4832.000",
        "low": "4830.000",
        "open": "4830.000",
        "volume": "1534",
        "wave": 0
    },
    {
        "close": "4828.000",
        "ctm": "1727062200",
        "ctmfmt": "2024-09-23 11:30:00",
        "high": "4832.000",
        "low": "4826.000",
        "open": "4830.000",
        "volume": "10274",
        "wave": 0
    },
    {
        "close": "4832.000",
        "ctm": "1727069460",
        "ctmfmt": "2024-09-23 13:31:00",
        "high": "4834.000",
        "low": "4828.000",
        "open": "4828.000",
        "volume": "17189",
        "wave": 0
    },
    {
        "close": "4832.000",
        "ctm": "1727069520",
        "ctmfmt": "2024-09-23 13:32:00",
        "high": "4834.000",
        "low": "4830.000",
        "open": "4832.000",
        "volume": "10331",
        "wave": 0
    },
    {
        "close": "4830.000",
        "ctm": "1727069580",
        "ctmfmt": "2024-09-23 13:33:00",
        "high": "4834.000",
        "low": "4828.000",
        "open": "4834.000",
        "volume": "9442",
        "wave": 0
    },
    {
        "close": "4828.000",
        "ctm": "1727069640",
        "ctmfmt": "2024-09-23 13:34:00",
        "high": "4830.000",
        "low": "4828.000",
        "open": "4830.000",
        "volume": "2070",
        "wave": 0
    },
    {
        "close": "4830.000",
        "ctm": "1727069700",
        "ctmfmt": "2024-09-23 13:35:00",
        "high": "4832.000",
        "low": "4828.000",
        "open": "4828.000",
        "volume": "5850",
        "wave": 0
    },
    {
        "close": "4830.000",
        "ctm": "1727069760",
        "ctmfmt": "2024-09-23 13:36:00",
        "high": "4832.000",
        "low": "4828.000",
        "open": "4828.000",
        "volume": "4914",
        "wave": 0
    },
    {
        "close": "4834.000",
        "ctm": "1727069820",
        "ctmfmt": "2024-09-23 13:37:00",
        "high": "4834.000",
        "low": "4830.000",
        "open": "4830.000",
        "volume": "3132",
        "wave": 0
    },
    {
        "close": "4838.000",
        "ctm": "1727069880",
        "ctmfmt": "2024-09-23 13:38:00",
        "high": "4838.000",
        "low": "4832.000",
        "open": "4832.000",
        "volume": "11040",
        "wave": 0
    },
    {
        "close": "4836.000",
        "ctm": "1727069940",
        "ctmfmt": "2024-09-23 13:39:00",
        "high": "4840.000",
        "low": "4836.000",
        "open": "4840.000",
        "volume": "9462",
        "wave": 0
    },
    {
        "close": "4836.000",
        "ctm": "1727070000",
        "ctmfmt": "2024-09-23 13:40:00",
        "high": "4838.000",
        "low": "4832.000",
        "open": "4838.000",
        "volume": "6164",
        "wave": 0
    },
    {
        "close": "4832.000",
        "ctm": "1727070060",
        "ctmfmt": "2024-09-23 13:41:00",
        "high": "4836.000",
        "low": "4830.000",
        "open": "4836.000",
        "volume": "4432",
        "wave": 0
    },
    {
        "close": "4824.000",
        "ctm": "1727070120",
        "ctmfmt": "2024-09-23 13:42:00",
        "high": "4832.000",
        "low": "4822.000",
        "open": "4830.000",
        "volume": "23603",
        "wave": 0
    },
    {
        "close": "4822.000",
        "ctm": "1727070180",
        "ctmfmt": "2024-09-23 13:43:00",
        "high": "4824.000",
        "low": "4822.000",
        "open": "4824.000",
        "volume": "6699",
        "wave": 0
    },
    {
        "close": "4824.000",
        "ctm": "1727070240",
        "ctmfmt": "2024-09-23 13:44:00",
        "high": "4826.000",
        "low": "4822.000",
        "open": "4822.000",
        "volume": "3945",
        "wave": 0
    },
    {
        "close": "4826.000",
        "ctm": "1727070300",
        "ctmfmt": "2024-09-23 13:45:00",
        "high": "4826.000",
        "low": "4826.000",
        "open": "4826.000",
        "volume": "10",
        "wave": 0
    },
    {
        "close": "4826.000",
        "ctm": "1727070360",
        "ctmfmt": "2024-09-23 13:46:00",
        "high": "4830.000",
        "low": "4824.000",
        "open": "4826.000",
        "volume": "11235",
        "wave": 0
    },
    {
        "close": "4828.000",
        "ctm": "1727070420",
        "ctmfmt": "2024-09-23 13:47:00",
        "high": "4830.000",
        "low": "4826.000",
        "open": "4826.000",
        "volume": "4695",
        "wave": 0
    },
    {
        "close": "4828.000",
        "ctm": "1727070480",
        "ctmfmt": "2024-09-23 13:48:00",
        "high": "4832.000",
        "low": "4826.000",
        "open": "4828.000",
        "volume": "5104",
        "wave": 0
    },
    {
        "close": "4826.000",
        "ctm": "1727070540",
        "ctmfmt": "2024-09-23 13:49:00",
        "high": "4828.000",
        "low": "4824.000",
        "open": "4828.000",
        "volume": "4940",
        "wave": 0
    },
    {
        "close": "4820.000",
        "ctm": "1727070600",
        "ctmfmt": "2024-09-23 13:50:00",
        "high": "4824.000",
        "low": "4820.000",
        "open": "4824.000",
        "volume": "29125",
        "wave": 0
    },
    {
        "close": "4818.000",
        "ctm": "1727070660",
        "ctmfmt": "2024-09-23 13:51:00",
        "high": "4822.000",
        "low": "4818.000",
        "open": "4820.000",
        "volume": "8382",
        "wave": 0
    },
    {
        "close": "4818.000",
        "ctm": "1727070720",
        "ctmfmt": "2024-09-23 13:52:00",
        "high": "4822.000",
        "low": "4816.000",
        "open": "4818.000",
        "volume": "16952",
        "wave": 0
    },
    {
        "close": "4824.000",
        "ctm": "1727070780",
        "ctmfmt": "2024-09-23 13:53:00",
        "high": "4824.000",
        "low": "4818.000",
        "open": "4818.000",
        "volume": "8816",
        "wave": 0
    },
    {
        "close": "4826.000",
        "ctm": "1727070840",
        "ctmfmt": "2024-09-23 13:54:00",
        "high": "4828.000",
        "low": "4822.000",
        "open": "4822.000",
        "volume": "8616",
        "wave": 0
    },
    {
        "close": "4822.000",
        "ctm": "1727070900",
        "ctmfmt": "2024-09-23 13:55:00",
        "high": "4826.000",
        "low": "4822.000",
        "open": "4826.000",
        "volume": "2412",
        "wave": 0
    },
    {
        "close": "4822.000",
        "ctm": "1727070960",
        "ctmfmt": "2024-09-23 13:56:00",
        "high": "4826.000",
        "low": "4822.000",
        "open": "4824.000",
        "volume": "11124",
        "wave": 0
    },
    {
        "close": "4820.000",
        "ctm": "1727071020",
        "ctmfmt": "2024-09-23 13:57:00",
        "high": "4824.000",
        "low": "4820.000",
        "open": "4824.000",
        "volume": "18948",
        "wave": 0
    },
    {
        "close": "4822.000",
        "ctm": "1727071080",
        "ctmfmt": "2024-09-23 13:58:00",
        "high": "4824.000",
        "low": "4820.000",
        "open": "4820.000",
        "volume": "4551",
        "wave": 0
    },
    {
        "close": "4824.000",
        "ctm": "1727071140",
        "ctmfmt": "2024-09-23 13:59:00",
        "high": "4826.000",
        "low": "4822.000",
        "open": "4822.000",
        "volume": "4416",
        "wave": 0
    },
    {
        "close": "4824.000",
        "ctm": "1727071200",
        "ctmfmt": "2024-09-23 14:00:00",
        "high": "4828.000",
        "low": "4824.000",
        "open": "4826.000",
        "volume": "3351",
        "wave": 0
    },
    {
        "close": "4826.000",
        "ctm": "1727071260",
        "ctmfmt": "2024-09-23 14:01:00",
        "high": "4826.000",
        "low": "4826.000",
        "open": "4826.000",
        "volume": "597",
        "wave": 0
    },
    {
        "close": "4828.000",
        "ctm": "1727071320",
        "ctmfmt": "2024-09-23 14:02:00",
        "high": "4828.000",
        "low": "4826.000",
        "open": "4826.000",
        "volume": "3102",
        "wave": 0
    },
    {
        "close": "4828.000",
        "ctm": "1727071380",
        "ctmfmt": "2024-09-23 14:03:00",
        "high": "4830.000",
        "low": "4826.000",
        "open": "4828.000",
        "volume": "2610",
        "wave": 0
    },
    {
        "close": "4832.000",
        "ctm": "1727071440",
        "ctmfmt": "2024-09-23 14:04:00",
        "high": "4834.000",
        "low": "4828.000",
        "open": "4830.000",
        "volume": "9552",
        "wave": 0
    },
    {
        "close": "4824.000",
        "ctm": "1727071500",
        "ctmfmt": "2024-09-23 14:05:00",
        "high": "4832.000",
        "low": "4824.000",
        "open": "4832.000",
        "volume": "4497",
        "wave": 0
    },
    {
        "close": "4826.000",
        "ctm": "1727071560",
        "ctmfmt": "2024-09-23 14:06:00",
        "high": "4826.000",
        "low": "4824.000",
        "open": "4826.000",
        "volume": "1876",
        "wave": 0
    },
    {
        "close": "4822.000",
        "ctm": "1727071620",
        "ctmfmt": "2024-09-23 14:07:00",
        "high": "4826.000",
        "low": "4822.000",
        "open": "4826.000",
        "volume": "1734",
        "wave": 0
    },
    {
        "close": "4826.000",
        "ctm": "1727071680",
        "ctmfmt": "2024-09-23 14:08:00",
        "high": "4828.000",
        "low": "4822.000",
        "open": "4824.000",
        "volume": "1870",
        "wave": 0
    },
    {
        "close": "4826.000",
        "ctm": "1727071740",
        "ctmfmt": "2024-09-23 14:09:00",
        "high": "4828.000",
        "low": "4824.000",
        "open": "4828.000",
        "volume": "1784",
        "wave": 0
    },
    {
        "close": "4826.000",
        "ctm": "1727071800",
        "ctmfmt": "2024-09-23 14:10:00",
        "high": "4828.000",
        "low": "4824.000",
        "open": "4828.000",
        "volume": "1218",
        "wave": 0
    },
    {
        "close": "4826.000",
        "ctm": "1727071860",
        "ctmfmt": "2024-09-23 14:11:00",
        "high": "4826.000",
        "low": "4824.000",
        "open": "4826.000",
        "volume": "1922",
        "wave": 0
    },
    {
        "close": "4826.000",
        "ctm": "1727071920",
        "ctmfmt": "2024-09-23 14:12:00",
        "high": "4826.000",
        "low": "4824.000",
        "open": "4826.000",
        "volume": "1560",
        "wave": 0
    },
    {
        "close": "4828.000",
        "ctm": "1727071980",
        "ctmfmt": "2024-09-23 14:13:00",
        "high": "4830.000",
        "low": "4824.000",
        "open": "4826.000",
        "volume": "2336",
        "wave": 0
    },
    {
        "close": "4830.000",
        "ctm": "1727072040",
        "ctmfmt": "2024-09-23 14:14:00",
        "high": "4830.000",
        "low": "4826.000",
        "open": "4830.000",
        "volume": "2086",
        "wave": 0
    },
    {
        "close": "4836.000",
        "ctm": "1727072100",
        "ctmfmt": "2024-09-23 14:15:00",
        "high": "4838.000",
        "low": "4830.000",
        "open": "4830.000",
        "volume": "7843",
        "wave": 0
    },
    {
        "close": "4842.000",
        "ctm": "1727072160",
        "ctmfmt": "2024-09-23 14:16:00",
        "high": "4844.000",
        "low": "4834.000",
        "open": "4834.000",
        "volume": "8244",
        "wave": 0
    },
    {
        "close": "4842.000",
        "ctm": "1727072220",
        "ctmfmt": "2024-09-23 14:17:00",
        "high": "4848.000",
        "low": "4840.000",
        "open": "4844.000",
        "volume": "6593",
        "wave": 0
    },
    {
        "close": "4832.000",
        "ctm": "1727072280",
        "ctmfmt": "2024-09-23 14:18:00",
        "high": "4842.000",
        "low": "4832.000",
        "open": "4842.000",
        "volume": "2657",
        "wave": 0
    },
    {
        "close": "4828.000",
        "ctm": "1727072340",
        "ctmfmt": "2024-09-23 14:19:00",
        "high": "4834.000",
        "low": "4828.000",
        "open": "4832.000",
        "volume": "2159",
        "wave": 0
    },
    {
        "close": "4822.000",
        "ctm": "1727072400",
        "ctmfmt": "2024-09-23 14:20:00",
        "high": "4830.000",
        "low": "4822.000",
        "open": "4828.000",
        "volume": "3705",
        "wave": 0
    },
    {
        "close": "4826.000",
        "ctm": "1727072460",
        "ctmfmt": "2024-09-23 14:21:00",
        "high": "4826.000",
        "low": "4822.000",
        "open": "4824.000",
        "volume": "1935",
        "wave": 0
    },
    {
        "close": "4826.000",
        "ctm": "1727072520",
        "ctmfmt": "2024-09-23 14:22:00",
        "high": "4828.000",
        "low": "4824.000",
        "open": "4826.000",
        "volume": "1103",
        "wave": 0
    },
    {
        "close": "4826.000",
        "ctm": "1727072580",
        "ctmfmt": "2024-09-23 14:23:00",
        "high": "4828.000",
        "low": "4826.000",
        "open": "4826.000",
        "volume": "764",
        "wave": 0
    },
    {
        "close": "4828.000",
        "ctm": "1727072640",
        "ctmfmt": "2024-09-23 14:24:00",
        "high": "4830.000",
        "low": "4826.000",
        "open": "4828.000",
        "volume": "723",
        "wave": 0
    },
    {
        "close": "4824.000",
        "ctm": "1727072700",
        "ctmfmt": "2024-09-23 14:25:00",
        "high": "4830.000",
        "low": "4824.000",
        "open": "4830.000",
        "volume": "1003",
        "wave": 0
    },
    {
        "close": "4824.000",
        "ctm": "1727072760",
        "ctmfmt": "2024-09-23 14:26:00",
        "high": "4826.000",
        "low": "4824.000",
        "open": "4824.000",
        "volume": "1031",
        "wave": 0
    }
]

    all_futures = get_all_futures()
    for future_code in all_futures:
        ks.save_klines(klines=value, prex='tf_futures_trade', cycle=1, code=future_code["symbol"])
        time.sleep(0.2)


if __name__ == '__main__':
    ks = KlineService()
    # print(get_all_ticket())
    try:
        while True:
            save_kline_data_by_redis(prex='tf_futures_trade', ks=ks)
            fetch_all_ticket_data(ks)
            time.sleep(1)
            print("正在更新数据...", time.time())
            # 设置更新间隔，这里是1秒
        # write_ready_data(ks)
        # print("初始数据写入完成")
    except KeyboardInterrupt:
        print("程序终止")
#----------------------------------------------------------
#     ready_data_5m = [
#         {
#         "close": "5398.000",
#         "ctm": "1724911500",
#         "ctmfmt": "2024-08-29 14:05:00",
#         "high": "5400.000",
#         "low": "5392.000",
#         "open": "5394.000",
#         "volume": "4897",
#         "wave": 0
#     },
#     {
#         "close": "5400.000",
#         "ctm": "1724911800",
#         "ctmfmt": "2024-08-29 14:10:00",
#         "high": "5404.000",
#         "low": "5396.000",
#         "open": "5398.000",
#         "volume": "5982",
#         "wave": 0
#     },
#     {
#         "close": "5398.000",
#         "ctm": "1724912100",
#         "ctmfmt": "2024-08-29 14:15:00",
#         "high": "5402.000",
#         "low": "5394.000",
#         "open": "5400.000",
#         "volume": "4141",
#         "wave": 0
#     },
#     {
#         "close": "5406.000",
#         "ctm": "1724912400",
#         "ctmfmt": "2024-08-29 14:20:00",
#         "high": "5406.000",
#         "low": "5396.000",
#         "open": "5398.000",
#         "volume": "4140",
#         "wave": 0
#     },
#     {
#         "close": "5404.000",
#         "ctm": "1724912700",
#         "ctmfmt": "2024-08-29 14:25:00",
#         "high": "5410.000",
#         "low": "5400.000",
#         "open": "5406.000",
#         "volume": "6317",
#         "wave": 0
#     },
#     {
#         "close": "5406.000",
#         "ctm": "1724913000",
#         "ctmfmt": "2024-08-29 14:30:00",
#         "high": "5408.000",
#         "low": "5402.000",
#         "open": "5402.000",
#         "volume": "3000",
#         "wave": 0
#     },
#     {
#         "close": "5400.000",
#         "ctm": "1724913300",
#         "ctmfmt": "2024-08-29 14:35:00",
#         "high": "5406.000",
#         "low": "5398.000",
#         "open": "5406.000",
#         "volume": "5476",
#         "wave": 0
#     },
#     {
#         "close": "5404.000",
#         "ctm": "1724913600",
#         "ctmfmt": "2024-08-29 14:40:00",
#         "high": "5404.000",
#         "low": "5398.000",
#         "open": "5398.000",
#         "volume": "4544",
#         "wave": 0
#     },
#     {
#         "close": "5402.000",
#         "ctm": "1724913900",
#         "ctmfmt": "2024-08-29 14:45:00",
#         "high": "5406.000",
#         "low": "5398.000",
#         "open": "5404.000",
#         "volume": "5887",
#         "wave": 0
#     },
#     {
#         "close": "5398.000",
#         "ctm": "1724914200",
#         "ctmfmt": "2024-08-29 14:50:00",
#         "high": "5404.000",
#         "low": "5396.000",
#         "open": "5400.000",
#         "volume": "6256",
#         "wave": 0
#     },
#     {
#         "close": "5396.000",
#         "ctm": "1724914500",
#         "ctmfmt": "2024-08-29 14:55:00",
#         "high": "5400.000",
#         "low": "5394.000",
#         "open": "5398.000",
#         "volume": "8129",
#         "wave": 0
#     },
#     {
#         "close": "5406.000",
#         "ctm": "1724914800",
#         "ctmfmt": "2024-08-29 15:00:00",
#         "high": "5406.000",
#         "low": "5394.000",
#         "open": "5396.000",
#         "volume": "24438",
#         "wave": 0
#     },
#     {
#         "close": "5414.000",
#         "ctm": "1724936700",
#         "ctmfmt": "2024-08-29 21:05:00",
#         "high": "5424.000",
#         "low": "5410.000",
#         "open": "5410.000",
#         "volume": "49501",
#         "wave": 0
#     },
#     {
#         "close": "5414.000",
#         "ctm": "1724937000",
#         "ctmfmt": "2024-08-29 21:10:00",
#         "high": "5420.000",
#         "low": "5408.000",
#         "open": "5416.000",
#         "volume": "12025",
#         "wave": 0
#     },
#     {
#         "close": "5420.000",
#         "ctm": "1724937300",
#         "ctmfmt": "2024-08-29 21:15:00",
#         "high": "5420.000",
#         "low": "5410.000",
#         "open": "5412.000",
#         "volume": "8842",
#         "wave": 0
#     },
#     {
#         "close": "5428.000",
#         "ctm": "1724937600",
#         "ctmfmt": "2024-08-29 21:20:00",
#         "high": "5428.000",
#         "low": "5416.000",
#         "open": "5420.000",
#         "volume": "13097",
#         "wave": 0
#     },
#     {
#         "close": "5428.000",
#         "ctm": "1724937900",
#         "ctmfmt": "2024-08-29 21:25:00",
#         "high": "5436.000",
#         "low": "5426.000",
#         "open": "5428.000",
#         "volume": "21516",
#         "wave": 0
#     },
#     {
#         "close": "5438.000",
#         "ctm": "1724938200",
#         "ctmfmt": "2024-08-29 21:30:00",
#         "high": "5438.000",
#         "low": "5426.000",
#         "open": "5428.000",
#         "volume": "12684",
#         "wave": 0
#     },
#     {
#         "close": "5434.000",
#         "ctm": "1724938500",
#         "ctmfmt": "2024-08-29 21:35:00",
#         "high": "5442.000",
#         "low": "5432.000",
#         "open": "5436.000",
#         "volume": "15689",
#         "wave": 0
#     },
#     {
#         "close": "5436.000",
#         "ctm": "1724938800",
#         "ctmfmt": "2024-08-29 21:40:00",
#         "high": "5440.000",
#         "low": "5430.000",
#         "open": "5436.000",
#         "volume": "6430",
#         "wave": 0
#     },
#     {
#         "close": "5434.000",
#         "ctm": "1724939100",
#         "ctmfmt": "2024-08-29 21:45:00",
#         "high": "5440.000",
#         "low": "5432.000",
#         "open": "5438.000",
#         "volume": "6591",
#         "wave": 0
#     },
#     {
#         "close": "5438.000",
#         "ctm": "1724939400",
#         "ctmfmt": "2024-08-29 21:50:00",
#         "high": "5440.000",
#         "low": "5432.000",
#         "open": "5432.000",
#         "volume": "6223",
#         "wave": 0
#     },
#     {
#         "close": "5442.000",
#         "ctm": "1724939700",
#         "ctmfmt": "2024-08-29 21:55:00",
#         "high": "5444.000",
#         "low": "5436.000",
#         "open": "5438.000",
#         "volume": "10892",
#         "wave": 0
#     },
#     {
#         "close": "5444.000",
#         "ctm": "1724940000",
#         "ctmfmt": "2024-08-29 22:00:00",
#         "high": "5444.000",
#         "low": "5438.000",
#         "open": "5442.000",
#         "volume": "4514",
#         "wave": 0
#     },
#     {
#         "close": "5442.000",
#         "ctm": "1724940300",
#         "ctmfmt": "2024-08-29 22:05:00",
#         "high": "5446.000",
#         "low": "5438.000",
#         "open": "5446.000",
#         "volume": "9208",
#         "wave": 0
#     },
#     {
#         "close": "5436.000",
#         "ctm": "1724940600",
#         "ctmfmt": "2024-08-29 22:10:00",
#         "high": "5444.000",
#         "low": "5434.000",
#         "open": "5444.000",
#         "volume": "8040",
#         "wave": 0
#     },
#     {
#         "close": "5428.000",
#         "ctm": "1724940900",
#         "ctmfmt": "2024-08-29 22:15:00",
#         "high": "5438.000",
#         "low": "5424.000",
#         "open": "5438.000",
#         "volume": "11563",
#         "wave": 0
#     },
#     {
#         "close": "5430.000",
#         "ctm": "1724941200",
#         "ctmfmt": "2024-08-29 22:20:00",
#         "high": "5432.000",
#         "low": "5424.000",
#         "open": "5428.000",
#         "volume": "6826",
#         "wave": 0
#     },
#     {
#         "close": "5430.000",
#         "ctm": "1724941500",
#         "ctmfmt": "2024-08-29 22:25:00",
#         "high": "5434.000",
#         "low": "5428.000",
#         "open": "5430.000",
#         "volume": "3253",
#         "wave": 0
#     },
#     {
#         "close": "5426.000",
#         "ctm": "1724941800",
#         "ctmfmt": "2024-08-29 22:30:00",
#         "high": "5432.000",
#         "low": "5424.000",
#         "open": "5430.000",
#         "volume": "3785",
#         "wave": 0
#     },
#     {
#         "close": "5422.000",
#         "ctm": "1724942100",
#         "ctmfmt": "2024-08-29 22:35:00",
#         "high": "5426.000",
#         "low": "5420.000",
#         "open": "5424.000",
#         "volume": "8265",
#         "wave": 0
#     },
#     {
#         "close": "5424.000",
#         "ctm": "1724942400",
#         "ctmfmt": "2024-08-29 22:40:00",
#         "high": "5426.000",
#         "low": "5422.000",
#         "open": "5424.000",
#         "volume": "2751",
#         "wave": 0
#     },
#     {
#         "close": "5428.000",
#         "ctm": "1724942700",
#         "ctmfmt": "2024-08-29 22:45:00",
#         "high": "5428.000",
#         "low": "5422.000",
#         "open": "5424.000",
#         "volume": "3848",
#         "wave": 0
#     },
#     {
#         "close": "5424.000",
#         "ctm": "1724943000",
#         "ctmfmt": "2024-08-29 22:50:00",
#         "high": "5428.000",
#         "low": "5422.000",
#         "open": "5426.000",
#         "volume": "2590",
#         "wave": 0
#     },
#     {
#         "close": "5420.000",
#         "ctm": "1724943300",
#         "ctmfmt": "2024-08-29 22:55:00",
#         "high": "5422.000",
#         "low": "5418.000",
#         "open": "5422.000",
#         "volume": "7738",
#         "wave": 0
#     },
#     {
#         "close": "5424.000",
#         "ctm": "1724943600",
#         "ctmfmt": "2024-08-29 23:00:00",
#         "high": "5426.000",
#         "low": "5420.000",
#         "open": "5420.000",
#         "volume": "7524",
#         "wave": 0
#     },
#     {
#         "close": "5406.000",
#         "ctm": "1724979900",
#         "ctmfmt": "2024-08-30 09:05:00",
#         "high": "5418.000",
#         "low": "5400.000",
#         "open": "5416.000",
#         "volume": "34092",
#         "wave": 0
#     },
#     {
#         "close": "5400.000",
#         "ctm": "1724980200",
#         "ctmfmt": "2024-08-30 09:10:00",
#         "high": "5408.000",
#         "low": "5394.000",
#         "open": "5404.000",
#         "volume": "23275",
#         "wave": 0
#     },
#     {
#         "close": "5398.000",
#         "ctm": "1724980500",
#         "ctmfmt": "2024-08-30 09:15:00",
#         "high": "5406.000",
#         "low": "5396.000",
#         "open": "5400.000",
#         "volume": "10055",
#         "wave": 0
#     },
#     {
#         "close": "5404.000",
#         "ctm": "1724980800",
#         "ctmfmt": "2024-08-30 09:20:00",
#         "high": "5406.000",
#         "low": "5396.000",
#         "open": "5398.000",
#         "volume": "10503",
#         "wave": 0
#     },
#     {
#         "close": "5400.000",
#         "ctm": "1724981100",
#         "ctmfmt": "2024-08-30 09:25:00",
#         "high": "5412.000",
#         "low": "5398.000",
#         "open": "5404.000",
#         "volume": "10760",
#         "wave": 0
#     },
#     {
#         "close": "5402.000",
#         "ctm": "1724981400",
#         "ctmfmt": "2024-08-30 09:30:00",
#         "high": "5406.000",
#         "low": "5398.000",
#         "open": "5400.000",
#         "volume": "7032",
#         "wave": 0
#     },
#     {
#         "close": "5406.000",
#         "ctm": "1724981700",
#         "ctmfmt": "2024-08-30 09:35:00",
#         "high": "5406.000",
#         "low": "5400.000",
#         "open": "5402.000",
#         "volume": "6179",
#         "wave": 0
#     },
#     {
#         "close": "5404.000",
#         "ctm": "1724982000",
#         "ctmfmt": "2024-08-30 09:40:00",
#         "high": "5406.000",
#         "low": "5400.000",
#         "open": "5406.000",
#         "volume": "6114",
#         "wave": 0
#     },
#     {
#         "close": "5402.000",
#         "ctm": "1724982300",
#         "ctmfmt": "2024-08-30 09:45:00",
#         "high": "5404.000",
#         "low": "5400.000",
#         "open": "5404.000",
#         "volume": "2204",
#         "wave": 0
#     },
#     {
#         "close": "5400.000",
#         "ctm": "1724982600",
#         "ctmfmt": "2024-08-30 09:50:00",
#         "high": "5404.000",
#         "low": "5396.000",
#         "open": "5402.000",
#         "volume": "7835",
#         "wave": 0
#     },
#     {
#         "close": "5392.000",
#         "ctm": "1724982900",
#         "ctmfmt": "2024-08-30 09:55:00",
#         "high": "5400.000",
#         "low": "5390.000",
#         "open": "5400.000",
#         "volume": "12913",
#         "wave": 0
#     },
#     {
#         "close": "5398.000",
#         "ctm": "1724983200",
#         "ctmfmt": "2024-08-30 10:00:00",
#         "high": "5400.000",
#         "low": "5390.000",
#         "open": "5394.000",
#         "volume": "15854",
#         "wave": 0
#     },
#     {
#         "close": "5404.000",
#         "ctm": "1724983500",
#         "ctmfmt": "2024-08-30 10:05:00",
#         "high": "5406.000",
#         "low": "5396.000",
#         "open": "5398.000",
#         "volume": "10313",
#         "wave": 0
#     },
#     {
#         "close": "5400.000",
#         "ctm": "1724983800",
#         "ctmfmt": "2024-08-30 10:10:00",
#         "high": "5406.000",
#         "low": "5396.000",
#         "open": "5404.000",
#         "volume": "6180",
#         "wave": 0
#     },
#     {
#         "close": "5398.000",
#         "ctm": "1724984100",
#         "ctmfmt": "2024-08-30 10:15:00",
#         "high": "5400.000",
#         "low": "5396.000",
#         "open": "5400.000",
#         "volume": "5552",
#         "wave": 0
#     },
#     {
#         "close": "5412.000",
#         "ctm": "1724985300",
#         "ctmfmt": "2024-08-30 10:35:00",
#         "high": "5412.000",
#         "low": "5398.000",
#         "open": "5398.000",
#         "volume": "11176",
#         "wave": 0
#     },
#     {
#         "close": "5408.000",
#         "ctm": "1724985600",
#         "ctmfmt": "2024-08-30 10:40:00",
#         "high": "5412.000",
#         "low": "5406.000",
#         "open": "5412.000",
#         "volume": "3252",
#         "wave": 0
#     },
#     {
#         "close": "5410.000",
#         "ctm": "1724985900",
#         "ctmfmt": "2024-08-30 10:45:00",
#         "high": "5410.000",
#         "low": "5404.000",
#         "open": "5408.000",
#         "volume": "4549",
#         "wave": 0
#     }]
#     ready_data_1m = [
#     {
#         "close": "4804.000",
#         "ctm": "1726641540",
#         "ctmfmt": "2024-09-18 14:39:00",
#         "high": "4804.000",
#         "low": "4804.000",
#         "open": "4804.000",
#         "volume": "104",
#         "wave": 0
#     },
#     {
#         "close": "4804.000",
#         "ctm": "1726641600",
#         "ctmfmt": "2024-09-18 14:40:00",
#         "high": "4806.000",
#         "low": "4802.000",
#         "open": "4806.000",
#         "volume": "780",
#         "wave": 0
#     },
#     {
#         "close": "4802.000",
#         "ctm": "1726641660",
#         "ctmfmt": "2024-09-18 14:41:00",
#         "high": "4804.000",
#         "low": "4802.000",
#         "open": "4804.000",
#         "volume": "236",
#         "wave": 0
#     },
#     {
#         "close": "4810.000",
#         "ctm": "1726641720",
#         "ctmfmt": "2024-09-18 14:42:00",
#         "high": "4810.000",
#         "low": "4804.000",
#         "open": "4804.000",
#         "volume": "2223",
#         "wave": 0
#     },
#     {
#         "close": "4802.000",
#         "ctm": "1726641780",
#         "ctmfmt": "2024-09-18 14:43:00",
#         "high": "4804.000",
#         "low": "4800.000",
#         "open": "4802.000",
#         "volume": "476",
#         "wave": 0
#     },
#     {
#         "close": "4804.000",
#         "ctm": "1726641840",
#         "ctmfmt": "2024-09-18 14:44:00",
#         "high": "4806.000",
#         "low": "4802.000",
#         "open": "4802.000",
#         "volume": "1376",
#         "wave": 0
#     },
#     {
#         "close": "4796.000",
#         "ctm": "1726641900",
#         "ctmfmt": "2024-09-18 14:45:00",
#         "high": "4800.000",
#         "low": "4796.000",
#         "open": "4800.000",
#         "volume": "1330",
#         "wave": 0
#     },
#     {
#         "close": "4794.000",
#         "ctm": "1726641960",
#         "ctmfmt": "2024-09-18 14:46:00",
#         "high": "4798.000",
#         "low": "4794.000",
#         "open": "4798.000",
#         "volume": "2691",
#         "wave": 0
#     },
#     {
#         "close": "4794.000",
#         "ctm": "1726642020",
#         "ctmfmt": "2024-09-18 14:47:00",
#         "high": "4794.000",
#         "low": "4794.000",
#         "open": "4794.000",
#         "volume": "3",
#         "wave": 0
#     },
#     {
#         "close": "4790.000",
#         "ctm": "1726642080",
#         "ctmfmt": "2024-09-18 14:48:00",
#         "high": "4794.000",
#         "low": "4790.000",
#         "open": "4794.000",
#         "volume": "1198",
#         "wave": 0
#     },
#     {
#         "close": "4788.000",
#         "ctm": "1726642140",
#         "ctmfmt": "2024-09-18 14:49:00",
#         "high": "4790.000",
#         "low": "4788.000",
#         "open": "4788.000",
#         "volume": "538",
#         "wave": 0
#     },
#     {
#         "close": "4788.000",
#         "ctm": "1726642200",
#         "ctmfmt": "2024-09-18 14:50:00",
#         "high": "4788.000",
#         "low": "4788.000",
#         "open": "4788.000",
#         "volume": "6",
#         "wave": 0
#     },
#     {
#         "close": "4784.000",
#         "ctm": "1726642260",
#         "ctmfmt": "2024-09-18 14:51:00",
#         "high": "4788.000",
#         "low": "4784.000",
#         "open": "4788.000",
#         "volume": "1265",
#         "wave": 0
#     },
#     {
#         "close": "4776.000",
#         "ctm": "1726642320",
#         "ctmfmt": "2024-09-18 14:52:00",
#         "high": "4782.000",
#         "low": "4776.000",
#         "open": "4782.000",
#         "volume": "4313",
#         "wave": 0
#     },
#     {
#         "close": "4762.000",
#         "ctm": "1726642380",
#         "ctmfmt": "2024-09-18 14:53:00",
#         "high": "4764.000",
#         "low": "4762.000",
#         "open": "4764.000",
#         "volume": "4317",
#         "wave": 0
#     },
#     {
#         "close": "4756.000",
#         "ctm": "1726642440",
#         "ctmfmt": "2024-09-18 14:54:00",
#         "high": "4760.000",
#         "low": "4756.000",
#         "open": "4760.000",
#         "volume": "2012",
#         "wave": 0
#     },
#     {
#         "close": "4760.000",
#         "ctm": "1726642500",
#         "ctmfmt": "2024-09-18 14:55:00",
#         "high": "4764.000",
#         "low": "4754.000",
#         "open": "4756.000",
#         "volume": "5550",
#         "wave": 0
#     },
#     {
#         "close": "4766.000",
#         "ctm": "1726642560",
#         "ctmfmt": "2024-09-18 14:56:00",
#         "high": "4766.000",
#         "low": "4764.000",
#         "open": "4766.000",
#         "volume": "437",
#         "wave": 0
#     },
#     {
#         "close": "4766.000",
#         "ctm": "1726642620",
#         "ctmfmt": "2024-09-18 14:57:00",
#         "high": "4770.000",
#         "low": "4764.000",
#         "open": "4766.000",
#         "volume": "5888",
#         "wave": 0
#     },
#     {
#         "close": "4768.000",
#         "ctm": "1726642680",
#         "ctmfmt": "2024-09-18 14:58:00",
#         "high": "4768.000",
#         "low": "4764.000",
#         "open": "4764.000",
#         "volume": "3479",
#         "wave": 0
#     },
#     {
#         "close": "4768.000",
#         "ctm": "1726642740",
#         "ctmfmt": "2024-09-18 14:59:00",
#         "high": "4770.000",
#         "low": "4764.000",
#         "open": "4770.000",
#         "volume": "9752",
#         "wave": 0
#     },
#     {
#         "close": "4766.000",
#         "ctm": "1726642800",
#         "ctmfmt": "2024-09-18 15:00:00",
#         "high": "4768.000",
#         "low": "4754.000",
#         "open": "4766.000",
#         "volume": "12258",
#         "wave": 0
#     },
#     {
#         "close": "4786.000",
#         "ctm": "1726664460",
#         "ctmfmt": "2024-09-18 21:01:00",
#         "high": "4788.000",
#         "low": "4774.000",
#         "open": "4774.000",
#         "volume": "26237",
#         "wave": 0
#     },
#     {
#         "close": "4784.000",
#         "ctm": "1726664520",
#         "ctmfmt": "2024-09-18 21:02:00",
#         "high": "4792.000",
#         "low": "4784.000",
#         "open": "4786.000",
#         "volume": "11067",
#         "wave": 0
#     },
#     {
#         "close": "4774.000",
#         "ctm": "1726664580",
#         "ctmfmt": "2024-09-18 21:03:00",
#         "high": "4786.000",
#         "low": "4772.000",
#         "open": "4784.000",
#         "volume": "8400",
#         "wave": 0
#     },
#     {
#         "close": "4774.000",
#         "ctm": "1726664640",
#         "ctmfmt": "2024-09-18 21:04:00",
#         "high": "4778.000",
#         "low": "4772.000",
#         "open": "4772.000",
#         "volume": "3913",
#         "wave": 0
#     },
#     {
#         "close": "4774.000",
#         "ctm": "1726664700",
#         "ctmfmt": "2024-09-18 21:05:00",
#         "high": "4780.000",
#         "low": "4772.000",
#         "open": "4776.000",
#         "volume": "4801",
#         "wave": 0
#     },
#     {
#         "close": "4774.000",
#         "ctm": "1726664760",
#         "ctmfmt": "2024-09-18 21:06:00",
#         "high": "4782.000",
#         "low": "4772.000",
#         "open": "4772.000",
#         "volume": "5627",
#         "wave": 0
#     },
#     {
#         "close": "4770.000",
#         "ctm": "1726664820",
#         "ctmfmt": "2024-09-18 21:07:00",
#         "high": "4776.000",
#         "low": "4768.000",
#         "open": "4774.000",
#         "volume": "6813",
#         "wave": 0
#     },
#     {
#         "close": "4772.000",
#         "ctm": "1726664880",
#         "ctmfmt": "2024-09-18 21:08:00",
#         "high": "4774.000",
#         "low": "4770.000",
#         "open": "4770.000",
#         "volume": "2975",
#         "wave": 0
#     },
#     {
#         "close": "4766.000",
#         "ctm": "1726664940",
#         "ctmfmt": "2024-09-18 21:09:00",
#         "high": "4772.000",
#         "low": "4766.000",
#         "open": "4772.000",
#         "volume": "6129",
#         "wave": 0
#     },
#     {
#         "close": "4766.000",
#         "ctm": "1726665000",
#         "ctmfmt": "2024-09-18 21:10:00",
#         "high": "4768.000",
#         "low": "4762.000",
#         "open": "4766.000",
#         "volume": "4708",
#         "wave": 0
#     },
#     {
#         "close": "4760.000",
#         "ctm": "1726665060",
#         "ctmfmt": "2024-09-18 21:11:00",
#         "high": "4768.000",
#         "low": "4760.000",
#         "open": "4766.000",
#         "volume": "5522",
#         "wave": 0
#     },
#     {
#         "close": "4762.000",
#         "ctm": "1726665120",
#         "ctmfmt": "2024-09-18 21:12:00",
#         "high": "4766.000",
#         "low": "4758.000",
#         "open": "4760.000",
#         "volume": "6419",
#         "wave": 0
#     },
#     {
#         "close": "4762.000",
#         "ctm": "1726665180",
#         "ctmfmt": "2024-09-18 21:13:00",
#         "high": "4762.000",
#         "low": "4758.000",
#         "open": "4762.000",
#         "volume": "4876",
#         "wave": 0
#     },
#     {
#         "close": "4766.000",
#         "ctm": "1726665240",
#         "ctmfmt": "2024-09-18 21:14:00",
#         "high": "4770.000",
#         "low": "4762.000",
#         "open": "4762.000",
#         "volume": "4594",
#         "wave": 0
#     },
#     {
#         "close": "4760.000",
#         "ctm": "1726665300",
#         "ctmfmt": "2024-09-18 21:15:00",
#         "high": "4766.000",
#         "low": "4758.000",
#         "open": "4766.000",
#         "volume": "4409",
#         "wave": 0
#     },
#     {
#         "close": "4760.000",
#         "ctm": "1726665360",
#         "ctmfmt": "2024-09-18 21:16:00",
#         "high": "4764.000",
#         "low": "4756.000",
#         "open": "4760.000",
#         "volume": "4599",
#         "wave": 0
#     },
#     {
#         "close": "4768.000",
#         "ctm": "1726665420",
#         "ctmfmt": "2024-09-18 21:17:00",
#         "high": "4768.000",
#         "low": "4760.000",
#         "open": "4760.000",
#         "volume": "5053",
#         "wave": 0
#     },
#     {
#         "close": "4780.000",
#         "ctm": "1726665480",
#         "ctmfmt": "2024-09-18 21:18:00",
#         "high": "4782.000",
#         "low": "4768.000",
#         "open": "4768.000",
#         "volume": "7048",
#         "wave": 0
#     },
#     {
#         "close": "4778.000",
#         "ctm": "1726665540",
#         "ctmfmt": "2024-09-18 21:19:00",
#         "high": "4780.000",
#         "low": "4774.000",
#         "open": "4778.000",
#         "volume": "4627",
#         "wave": 0
#     },
#     {
#         "close": "4768.000",
#         "ctm": "1726665600",
#         "ctmfmt": "2024-09-18 21:20:00",
#         "high": "4778.000",
#         "low": "4768.000",
#         "open": "4776.000",
#         "volume": "4387",
#         "wave": 0
#     },
#     {
#         "close": "4766.000",
#         "ctm": "1726665660",
#         "ctmfmt": "2024-09-18 21:21:00",
#         "high": "4770.000",
#         "low": "4766.000",
#         "open": "4768.000",
#         "volume": "2983",
#         "wave": 0
#     },
#     {
#         "close": "4762.000",
#         "ctm": "1726665720",
#         "ctmfmt": "2024-09-18 21:22:00",
#         "high": "4766.000",
#         "low": "4760.000",
#         "open": "4766.000",
#         "volume": "4378",
#         "wave": 0
#     },
#     {
#         "close": "4762.000",
#         "ctm": "1726665780",
#         "ctmfmt": "2024-09-18 21:23:00",
#         "high": "4764.000",
#         "low": "4758.000",
#         "open": "4762.000",
#         "volume": "4105",
#         "wave": 0
#     },
#     {
#         "close": "4756.000",
#         "ctm": "1726665840",
#         "ctmfmt": "2024-09-18 21:24:00",
#         "high": "4762.000",
#         "low": "4756.000",
#         "open": "4762.000",
#         "volume": "155882",
#         "wave": 0
#     },
#     {
#         "close": "4756.000",
#         "ctm": "1726665900",
#         "ctmfmt": "2024-09-18 21:25:00",
#         "high": "4760.000",
#         "low": "4750.000",
#         "open": "4756.000",
#         "volume": "8957",
#         "wave": 0
#     },
#     {
#         "close": "4742.000",
#         "ctm": "1726665960",
#         "ctmfmt": "2024-09-18 21:26:00",
#         "high": "4754.000",
#         "low": "4742.000",
#         "open": "4754.000",
#         "volume": "12123",
#         "wave": 0
#     },
#     {
#         "close": "4746.000",
#         "ctm": "1726666020",
#         "ctmfmt": "2024-09-18 21:27:00",
#         "high": "4748.000",
#         "low": "4742.000",
#         "open": "4742.000",
#         "volume": "7861",
#         "wave": 0
#     },
#     {
#         "close": "4734.000",
#         "ctm": "1726666080",
#         "ctmfmt": "2024-09-18 21:28:00",
#         "high": "4746.000",
#         "low": "4734.000",
#         "open": "4746.000",
#         "volume": "8913",
#         "wave": 0
#     },
#     {
#         "close": "4734.000",
#         "ctm": "1726666140",
#         "ctmfmt": "2024-09-18 21:29:00",
#         "high": "4736.000",
#         "low": "4732.000",
#         "open": "4736.000",
#         "volume": "5799",
#         "wave": 0
#     },
#     {
#         "close": "4732.000",
#         "ctm": "1726666200",
#         "ctmfmt": "2024-09-18 21:30:00",
#         "high": "4736.000",
#         "low": "4728.000",
#         "open": "4732.000",
#         "volume": "8629",
#         "wave": 0
#     },
#     {
#         "close": "4734.000",
#         "ctm": "1726666260",
#         "ctmfmt": "2024-09-18 21:31:00",
#         "high": "4738.000",
#         "low": "4730.000",
#         "open": "4732.000",
#         "volume": "5960",
#         "wave": 0
#     },
#     {
#         "close": "4726.000",
#         "ctm": "1726666320",
#         "ctmfmt": "2024-09-18 21:32:00",
#         "high": "4734.000",
#         "low": "4722.000",
#         "open": "4734.000",
#         "volume": "5743",
#         "wave": 0
#     },
#     {
#         "close": "4722.000",
#         "ctm": "1726666380",
#         "ctmfmt": "2024-09-18 21:33:00",
#         "high": "4730.000",
#         "low": "4722.000",
#         "open": "4726.000",
#         "volume": "6944",
#         "wave": 0
#     },
#     {
#         "close": "4724.000",
#         "ctm": "1726666440",
#         "ctmfmt": "2024-09-18 21:34:00",
#         "high": "4726.000",
#         "low": "4718.000",
#         "open": "4722.000",
#         "volume": "13031",
#         "wave": 0
#     },
#     {
#         "close": "4722.000",
#         "ctm": "1726666500",
#         "ctmfmt": "2024-09-18 21:35:00",
#         "high": "4728.000",
#         "low": "4722.000",
#         "open": "4722.000",
#         "volume": "6173",
#         "wave": 0
#     },
#     {
#         "close": "4720.000",
#         "ctm": "1726666560",
#         "ctmfmt": "2024-09-18 21:36:00",
#         "high": "4724.000",
#         "low": "4716.000",
#         "open": "4722.000",
#         "volume": "6965",
#         "wave": 0
#     },
#     {
#         "close": "4718.000",
#         "ctm": "1726666620",
#         "ctmfmt": "2024-09-18 21:37:00",
#         "high": "4722.000",
#         "low": "4716.000",
#         "open": "4722.000",
#         "volume": "2740",
#         "wave": 0
#     },
#     {
#         "close": "4728.000",
#         "ctm": "1726666680",
#         "ctmfmt": "2024-09-18 21:38:00",
#         "high": "4730.000",
#         "low": "4720.000",
#         "open": "4720.000",
#         "volume": "6944",
#         "wave": 0
#     },
#     {
#         "close": "4726.000",
#         "ctm": "1726666740",
#         "ctmfmt": "2024-09-18 21:39:00",
#         "high": "4730.000",
#         "low": "4722.000",
#         "open": "4728.000",
#         "volume": "3438",
#         "wave": 0
#     },
#     {
#         "close": "4724.000",
#         "ctm": "1726666800",
#         "ctmfmt": "2024-09-18 21:40:00",
#         "high": "4728.000",
#         "low": "4722.000",
#         "open": "4724.000",
#         "volume": "2172",
#         "wave": 0
#     },
#     {
#         "close": "4720.000",
#         "ctm": "1726666860",
#         "ctmfmt": "2024-09-18 21:41:00",
#         "high": "4730.000",
#         "low": "4720.000",
#         "open": "4724.000",
#         "volume": "3693",
#         "wave": 0
#     },
#     {
#         "close": "4720.000",
#         "ctm": "1726666920",
#         "ctmfmt": "2024-09-18 21:42:00",
#         "high": "4724.000",
#         "low": "4718.000",
#         "open": "4720.000",
#         "volume": "4113",
#         "wave": 0
#     },
#     {
#         "close": "4728.000",
#         "ctm": "1726666980",
#         "ctmfmt": "2024-09-18 21:43:00",
#         "high": "4728.000",
#         "low": "4720.000",
#         "open": "4720.000",
#         "volume": "1451",
#         "wave": 0
#     },
#     {
#         "close": "4724.000",
#         "ctm": "1726667040",
#         "ctmfmt": "2024-09-18 21:44:00",
#         "high": "4728.000",
#         "low": "4720.000",
#         "open": "4726.000",
#         "volume": "2427",
#         "wave": 0
#     },
#     {
#         "close": "4728.000",
#         "ctm": "1726667100",
#         "ctmfmt": "2024-09-18 21:45:00",
#         "high": "4728.000",
#         "low": "4720.000",
#         "open": "4724.000",
#         "volume": "3967",
#         "wave": 0
#     },
#     {
#         "close": "4726.000",
#         "ctm": "1726667160",
#         "ctmfmt": "2024-09-18 21:46:00",
#         "high": "4728.000",
#         "low": "4722.000",
#         "open": "4726.000",
#         "volume": "2979",
#         "wave": 0
#     },
#     {
#         "close": "4730.000",
#         "ctm": "1726667220",
#         "ctmfmt": "2024-09-18 21:47:00",
#         "high": "4730.000",
#         "low": "4722.000",
#         "open": "4726.000",
#         "volume": "2660",
#         "wave": 0
#     },
#     {
#         "close": "4734.000",
#         "ctm": "1726667280",
#         "ctmfmt": "2024-09-18 21:48:00",
#         "high": "4738.000",
#         "low": "4728.000",
#         "open": "4728.000",
#         "volume": "7816",
#         "wave": 0
#     },
#     {
#         "close": "4728.000",
#         "ctm": "1726667340",
#         "ctmfmt": "2024-09-18 21:49:00",
#         "high": "4736.000",
#         "low": "4728.000",
#         "open": "4732.000",
#         "volume": "5555",
#         "wave": 0
#     },
#     {
#         "close": "4732.000",
#         "ctm": "1726667400",
#         "ctmfmt": "2024-09-18 21:50:00",
#         "high": "4732.000",
#         "low": "4726.000",
#         "open": "4730.000",
#         "volume": "3460",
#         "wave": 0
#     },
#     {
#         "close": "4730.000",
#         "ctm": "1726667460",
#         "ctmfmt": "2024-09-18 21:51:00",
#         "high": "4730.000",
#         "low": "4724.000",
#         "open": "4730.000",
#         "volume": "4127",
#         "wave": 0
#     },
#     {
#         "close": "4730.000",
#         "ctm": "1726667520",
#         "ctmfmt": "2024-09-18 21:52:00",
#         "high": "4732.000",
#         "low": "4730.000",
#         "open": "4732.000",
#         "volume": "1281",
#         "wave": 0
#     },
#     {
#         "close": "4722.000",
#         "ctm": "1726667580",
#         "ctmfmt": "2024-09-18 21:53:00",
#         "high": "4728.000",
#         "low": "4720.000",
#         "open": "4728.000",
#         "volume": "3682",
#         "wave": 0
#     },
#     {
#         "close": "4716.000",
#         "ctm": "1726667640",
#         "ctmfmt": "2024-09-18 21:54:00",
#         "high": "4724.000",
#         "low": "4716.000",
#         "open": "4720.000",
#         "volume": "5162",
#         "wave": 0
#     },
#     {
#         "close": "4722.000",
#         "ctm": "1726667700",
#         "ctmfmt": "2024-09-18 21:55:00",
#         "high": "4722.000",
#         "low": "4716.000",
#         "open": "4718.000",
#         "volume": "3596",
#         "wave": 0
#     },
#     {
#         "close": "4716.000",
#         "ctm": "1726667760",
#         "ctmfmt": "2024-09-18 21:56:00",
#         "high": "4720.000",
#         "low": "4714.000",
#         "open": "4720.000",
#         "volume": "6484",
#         "wave": 0
#     },
#     {
#         "close": "4718.000",
#         "ctm": "1726667820",
#         "ctmfmt": "2024-09-18 21:57:00",
#         "high": "4718.000",
#         "low": "4712.000",
#         "open": "4716.000",
#         "volume": "2856",
#         "wave": 0
#     },
#     {
#         "close": "4720.000",
#         "ctm": "1726667880",
#         "ctmfmt": "2024-09-18 21:58:00",
#         "high": "4722.000",
#         "low": "4716.000",
#         "open": "4718.000",
#         "volume": "3042",
#         "wave": 0
#     },
#     {
#         "close": "4718.000",
#         "ctm": "1726667940",
#         "ctmfmt": "2024-09-18 21:59:00",
#         "high": "4726.000",
#         "low": "4714.000",
#         "open": "4722.000",
#         "volume": "4876",
#         "wave": 0
#     },
#     {
#         "close": "4716.000",
#         "ctm": "1726668000",
#         "ctmfmt": "2024-09-18 22:00:00",
#         "high": "4718.000",
#         "low": "4714.000",
#         "open": "4716.000",
#         "volume": "5721",
#         "wave": 0
#     },
#     {
#         "close": "4712.000",
#         "ctm": "1726668060",
#         "ctmfmt": "2024-09-18 22:01:00",
#         "high": "4718.000",
#         "low": "4712.000",
#         "open": "4716.000",
#         "volume": "7053",
#         "wave": 0
#     },
#     {
#         "close": "4716.000",
#         "ctm": "1726668120",
#         "ctmfmt": "2024-09-18 22:02:00",
#         "high": "4718.000",
#         "low": "4708.000",
#         "open": "4712.000",
#         "volume": "13257",
#         "wave": 0
#     },
#     {
#         "close": "4720.000",
#         "ctm": "1726668180",
#         "ctmfmt": "2024-09-18 22:03:00",
#         "high": "4724.000",
#         "low": "4716.000",
#         "open": "4718.000",
#         "volume": "6514",
#         "wave": 0
#     },
#     {
#         "close": "4720.000",
#         "ctm": "1726668240",
#         "ctmfmt": "2024-09-18 22:04:00",
#         "high": "4720.000",
#         "low": "4716.000",
#         "open": "4720.000",
#         "volume": "1885",
#         "wave": 0
#     },
#     {
#         "close": "4722.000",
#         "ctm": "1726668300",
#         "ctmfmt": "2024-09-18 22:05:00",
#         "high": "4722.000",
#         "low": "4718.000",
#         "open": "4718.000",
#         "volume": "1240",
#         "wave": 0
#     },
#     {
#         "close": "4720.000",
#         "ctm": "1726668360",
#         "ctmfmt": "2024-09-18 22:06:00",
#         "high": "4724.000",
#         "low": "4718.000",
#         "open": "4720.000",
#         "volume": "1669",
#         "wave": 0
#     },
#     {
#         "close": "4718.000",
#         "ctm": "1726668420",
#         "ctmfmt": "2024-09-18 22:07:00",
#         "high": "4722.000",
#         "low": "4716.000",
#         "open": "4720.000",
#         "volume": "1967",
#         "wave": 0
#     },
#     {
#         "close": "4716.000",
#         "ctm": "1726668480",
#         "ctmfmt": "2024-09-18 22:08:00",
#         "high": "4720.000",
#         "low": "4714.000",
#         "open": "4718.000",
#         "volume": "1953",
#         "wave": 0
#     },
#     {
#         "close": "4726.000",
#         "ctm": "1726668540",
#         "ctmfmt": "2024-09-18 22:09:00",
#         "high": "4726.000",
#         "low": "4716.000",
#         "open": "4716.000",
#         "volume": "3081",
#         "wave": 0
#     },
#     {
#         "close": "4732.000",
#         "ctm": "1726668600",
#         "ctmfmt": "2024-09-18 22:10:00",
#         "high": "4732.000",
#         "low": "4726.000",
#         "open": "4726.000",
#         "volume": "6140",
#         "wave": 0
#     },
#     {
#         "close": "4742.000",
#         "ctm": "1726668660",
#         "ctmfmt": "2024-09-18 22:11:00",
#         "high": "4742.000",
#         "low": "4732.000",
#         "open": "4732.000",
#         "volume": "10459",
#         "wave": 0
#     },
#     {
#         "close": "4748.000",
#         "ctm": "1726668720",
#         "ctmfmt": "2024-09-18 22:12:00",
#         "high": "4752.000",
#         "low": "4740.000",
#         "open": "4742.000",
#         "volume": "9713",
#         "wave": 0
#     },
#     {
#         "close": "4752.000",
#         "ctm": "1726668780",
#         "ctmfmt": "2024-09-18 22:13:00",
#         "high": "4754.000",
#         "low": "4748.000",
#         "open": "4748.000",
#         "volume": "7159",
#         "wave": 0
#     },
#     {
#         "close": "4748.000",
#         "ctm": "1726668840",
#         "ctmfmt": "2024-09-18 22:14:00",
#         "high": "4752.000",
#         "low": "4746.000",
#         "open": "4750.000",
#         "volume": "6364",
#         "wave": 0
#     },
#     {
#         "close": "4752.000",
#         "ctm": "1726668900",
#         "ctmfmt": "2024-09-18 22:15:00",
#         "high": "4752.000",
#         "low": "4746.000",
#         "open": "4748.000",
#         "volume": "3675",
#         "wave": 0
#     },
#     {
#         "close": "4754.000",
#         "ctm": "1726668960",
#         "ctmfmt": "2024-09-18 22:16:00",
#         "high": "4756.000",
#         "low": "4748.000",
#         "open": "4750.000",
#         "volume": "10148",
#         "wave": 0
#     },
#     {
#         "close": "4750.000",
#         "ctm": "1726669020",
#         "ctmfmt": "2024-09-18 22:17:00",
#         "high": "4758.000",
#         "low": "4750.000",
#         "open": "4754.000",
#         "volume": "5529",
#         "wave": 0
#     },
#     {
#         "close": "4756.000",
#         "ctm": "1726669080",
#         "ctmfmt": "2024-09-18 22:18:00",
#         "high": "4758.000",
#         "low": "4750.000",
#         "open": "4750.000",
#         "volume": "4477",
#         "wave": 0
#     },
#     {
#         "close": "4758.000",
#         "ctm": "1726669140",
#         "ctmfmt": "2024-09-18 22:19:00",
#         "high": "4758.000",
#         "low": "4754.000",
#         "open": "4756.000",
#         "volume": "3394",
#         "wave": 0
#     },
#     {
#         "close": "4752.000",
#         "ctm": "1726669200",
#         "ctmfmt": "2024-09-18 22:20:00",
#         "high": "4758.000",
#         "low": "4750.000",
#         "open": "4756.000",
#         "volume": "2170",
#         "wave": 0
#     },
#     {
#         "close": "4742.000",
#         "ctm": "1726669260",
#         "ctmfmt": "2024-09-18 22:21:00",
#         "high": "4752.000",
#         "low": "4742.000",
#         "open": "4752.000",
#         "volume": "5972",
#         "wave": 0
#     },
#     {
#         "close": "4740.000",
#         "ctm": "1726669320",
#         "ctmfmt": "2024-09-18 22:22:00",
#         "high": "4744.000",
#         "low": "4738.000",
#         "open": "4742.000",
#         "volume": "4524",
#         "wave": 0
#     },
#     {
#         "close": "4738.000",
#         "ctm": "1726669380",
#         "ctmfmt": "2024-09-18 22:23:00",
#         "high": "4742.000",
#         "low": "4736.000",
#         "open": "4742.000",
#         "volume": "1502",
#         "wave": 0
#     },
#     {
#         "close": "4738.000",
#         "ctm": "1726669440",
#         "ctmfmt": "2024-09-18 22:24:00",
#         "high": "4742.000",
#         "low": "4734.000",
#         "open": "4736.000",
#         "volume": "3538",
#         "wave": 0
#     },
#     {
#         "close": "4738.000",
#         "ctm": "1726669500",
#         "ctmfmt": "2024-09-18 22:25:00",
#         "high": "4740.000",
#         "low": "4736.000",
#         "open": "4738.000",
#         "volume": "1422",
#         "wave": 0
#     },
#     {
#         "close": "4746.000",
#         "ctm": "1726669560",
#         "ctmfmt": "2024-09-18 22:26:00",
#         "high": "4748.000",
#         "low": "4736.000",
#         "open": "4738.000",
#         "volume": "7165",
#         "wave": 0
#     },
#     {
#         "close": "4746.000",
#         "ctm": "1726669620",
#         "ctmfmt": "2024-09-18 22:27:00",
#         "high": "4746.000",
#         "low": "4742.000",
#         "open": "4746.000",
#         "volume": "1992",
#         "wave": 0
#     },
#     {
#         "close": "4746.000",
#         "ctm": "1726669680",
#         "ctmfmt": "2024-09-18 22:28:00",
#         "high": "4748.000",
#         "low": "4744.000",
#         "open": "4746.000",
#         "volume": "1502",
#         "wave": 0
#     },
#     {
#         "close": "4746.000",
#         "ctm": "1726669740",
#         "ctmfmt": "2024-09-18 22:29:00",
#         "high": "4752.000",
#         "low": "4744.000",
#         "open": "4746.000",
#         "volume": "2136",
#         "wave": 0
#     },
#     {
#         "close": "4746.000",
#         "ctm": "1726669800",
#         "ctmfmt": "2024-09-18 22:30:00",
#         "high": "4746.000",
#         "low": "4742.000",
#         "open": "4746.000",
#         "volume": "1097",
#         "wave": 0
#     },
#     {
#         "close": "4760.000",
#         "ctm": "1726669860",
#         "ctmfmt": "2024-09-18 22:31:00",
#         "high": "4764.000",
#         "low": "4750.000",
#         "open": "4750.000",
#         "volume": "8418",
#         "wave": 0
#     },
#     {
#         "close": "4766.000",
#         "ctm": "1726669920",
#         "ctmfmt": "2024-09-18 22:32:00",
#         "high": "4766.000",
#         "low": "4758.000",
#         "open": "4758.000",
#         "volume": "1331",
#         "wave": 0
#     },
#     {
#         "close": "4762.000",
#         "ctm": "1726669980",
#         "ctmfmt": "2024-09-18 22:33:00",
#         "high": "4766.000",
#         "low": "4760.000",
#         "open": "4764.000",
#         "volume": "3751",
#         "wave": 0
#     },
#     {
#         "close": "4762.000",
#         "ctm": "1726670040",
#         "ctmfmt": "2024-09-18 22:34:00",
#         "high": "4768.000",
#         "low": "4762.000",
#         "open": "4764.000",
#         "volume": "5657",
#         "wave": 0
#     },
#     {
#         "close": "4768.000",
#         "ctm": "1726670100",
#         "ctmfmt": "2024-09-18 22:35:00",
#         "high": "4770.000",
#         "low": "4762.000",
#         "open": "4762.000",
#         "volume": "3844",
#         "wave": 0
#     },
#     {
#         "close": "4764.000",
#         "ctm": "1726670160",
#         "ctmfmt": "2024-09-18 22:36:00",
#         "high": "4770.000",
#         "low": "4762.000",
#         "open": "4768.000",
#         "volume": "5968",
#         "wave": 0
#     },
#     {
#         "close": "4762.000",
#         "ctm": "1726670220",
#         "ctmfmt": "2024-09-18 22:37:00",
#         "high": "4766.000",
#         "low": "4760.000",
#         "open": "4766.000",
#         "volume": "3417",
#         "wave": 0
#     },
#     {
#         "close": "4768.000",
#         "ctm": "1726670280",
#         "ctmfmt": "2024-09-18 22:38:00",
#         "high": "4770.000",
#         "low": "4760.000",
#         "open": "4762.000",
#         "volume": "3275",
#         "wave": 0
#     },
#     {
#         "close": "4766.000",
#         "ctm": "1726670340",
#         "ctmfmt": "2024-09-18 22:39:00",
#         "high": "4770.000",
#         "low": "4762.000",
#         "open": "4768.000",
#         "volume": "1715",
#         "wave": 0
#     },
#     {
#         "close": "4766.000",
#         "ctm": "1726670400",
#         "ctmfmt": "2024-09-18 22:40:00",
#         "high": "4768.000",
#         "low": "4764.000",
#         "open": "4766.000",
#         "volume": "554241",
#         "wave": 0
#     },
#     {
#         "close": "4766.000",
#         "ctm": "1726670460",
#         "ctmfmt": "2024-09-18 22:41:00",
#         "high": "4766.000",
#         "low": "4764.000",
#         "open": "4766.000",
#         "volume": "477",
#         "wave": 0
#     },
#     {
#         "close": "4770.000",
#         "ctm": "1726670520",
#         "ctmfmt": "2024-09-18 22:42:00",
#         "high": "4774.000",
#         "low": "4764.000",
#         "open": "4764.000",
#         "volume": "5689",
#         "wave": 0
#     },
#     {
#         "close": "4768.000",
#         "ctm": "1726670580",
#         "ctmfmt": "2024-09-18 22:43:00",
#         "high": "4772.000",
#         "low": "4768.000",
#         "open": "4770.000",
#         "volume": "1763",
#         "wave": 0
#     },
#     {
#         "close": "4756.000",
#         "ctm": "1726670640",
#         "ctmfmt": "2024-09-18 22:44:00",
#         "high": "4770.000",
#         "low": "4756.000",
#         "open": "4770.000",
#         "volume": "4909",
#         "wave": 0
#     },
#     {
#         "close": "4758.000",
#         "ctm": "1726670700",
#         "ctmfmt": "2024-09-18 22:45:00",
#         "high": "4760.000",
#         "low": "4756.000",
#         "open": "4756.000",
#         "volume": "2568",
#         "wave": 0
#     },
#     {
#         "close": "4758.000",
#         "ctm": "1726670760",
#         "ctmfmt": "2024-09-18 22:46:00",
#         "high": "4760.000",
#         "low": "4756.000",
#         "open": "4758.000",
#         "volume": "1653",
#         "wave": 0
#     },
#     {
#         "close": "4762.000",
#         "ctm": "1726670820",
#         "ctmfmt": "2024-09-18 22:47:00",
#         "high": "4764.000",
#         "low": "4756.000",
#         "open": "4758.000",
#         "volume": "2180",
#         "wave": 0
#     },
#     {
#         "close": "4760.000",
#         "ctm": "1726670880",
#         "ctmfmt": "2024-09-18 22:48:00",
#         "high": "4762.000",
#         "low": "4758.000",
#         "open": "4762.000",
#         "volume": "761",
#         "wave": 0
#     },
#     {
#         "close": "4758.000",
#         "ctm": "1726670940",
#         "ctmfmt": "2024-09-18 22:49:00",
#         "high": "4762.000",
#         "low": "4756.000",
#         "open": "4762.000",
#         "volume": "1223",
#         "wave": 0
#     },
#     {
#         "close": "4756.000",
#         "ctm": "1726671000",
#         "ctmfmt": "2024-09-18 22:50:00",
#         "high": "4758.000",
#         "low": "4754.000",
#         "open": "4758.000",
#         "volume": "2180",
#         "wave": 0
#     },
#     {
#         "close": "4746.000",
#         "ctm": "1726671060",
#         "ctmfmt": "2024-09-18 22:51:00",
#         "high": "4758.000",
#         "low": "4746.000",
#         "open": "4756.000",
#         "volume": "4011",
#         "wave": 0
#     },
#     {
#         "close": "4744.000",
#         "ctm": "1726671120",
#         "ctmfmt": "2024-09-18 22:52:00",
#         "high": "4750.000",
#         "low": "4742.000",
#         "open": "4748.000",
#         "volume": "3725",
#         "wave": 0
#     },
#     {
#         "close": "4748.000",
#         "ctm": "1726671180",
#         "ctmfmt": "2024-09-18 22:53:00",
#         "high": "4750.000",
#         "low": "4744.000",
#         "open": "4746.000",
#         "volume": "1534",
#         "wave": 0
#     },
#     {
#         "close": "4746.000",
#         "ctm": "1726671240",
#         "ctmfmt": "2024-09-18 22:54:00",
#         "high": "4750.000",
#         "low": "4746.000",
#         "open": "4748.000",
#         "volume": "1457",
#         "wave": 0
#     },
#     {
#         "close": "4744.000",
#         "ctm": "1726671300",
#         "ctmfmt": "2024-09-18 22:55:00",
#         "high": "4746.000",
#         "low": "4742.000",
#         "open": "4746.000",
#         "volume": "2211",
#         "wave": 0
#     },
#     {
#         "close": "4740.000",
#         "ctm": "1726671360",
#         "ctmfmt": "2024-09-18 22:56:00",
#         "high": "4746.000",
#         "low": "4740.000",
#         "open": "4744.000",
#         "volume": "2085",
#         "wave": 0
#     },
#     {
#         "close": "4740.000",
#         "ctm": "1726671420",
#         "ctmfmt": "2024-09-18 22:57:00",
#         "high": "4742.000",
#         "low": "4738.000",
#         "open": "4742.000",
#         "volume": "2582",
#         "wave": 0
#     },
#     {
#         "close": "4744.000",
#         "ctm": "1726671480",
#         "ctmfmt": "2024-09-18 22:58:00",
#         "high": "4744.000",
#         "low": "4740.000",
#         "open": "4740.000",
#         "volume": "1913",
#         "wave": 0
#     },
#     {
#         "close": "4748.000",
#         "ctm": "1726671540",
#         "ctmfmt": "2024-09-18 22:59:00",
#         "high": "4750.000",
#         "low": "4742.000",
#         "open": "4742.000",
#         "volume": "3423",
#         "wave": 0
#     },
#     {
#         "close": "4758.000",
#         "ctm": "1726671600",
#         "ctmfmt": "2024-09-18 23:00:00",
#         "high": "4762.000",
#         "low": "4748.000",
#         "open": "4750.000",
#         "volume": "5660",
#         "wave": 0
#     },
#     {
#         "close": "4768.000",
#         "ctm": "1726707660",
#         "ctmfmt": "2024-09-19 09:01:00",
#         "high": "4782.000",
#         "low": "4750.000",
#         "open": "4750.000",
#         "volume": "19891",
#         "wave": 0
#     },
#     {
#         "close": "4762.000",
#         "ctm": "1726707720",
#         "ctmfmt": "2024-09-19 09:02:00",
#         "high": "4770.000",
#         "low": "4762.000",
#         "open": "4770.000",
#         "volume": "10264",
#         "wave": 0
#     },
#     {
#         "close": "4766.000",
#         "ctm": "1726707780",
#         "ctmfmt": "2024-09-19 09:03:00",
#         "high": "4766.000",
#         "low": "4758.000",
#         "open": "4760.000",
#         "volume": "5752",
#         "wave": 0
#     },
#     {
#         "close": "4760.000",
#         "ctm": "1726707840",
#         "ctmfmt": "2024-09-19 09:04:00",
#         "high": "4764.000",
#         "low": "4760.000",
#         "open": "4764.000",
#         "volume": "4826",
#         "wave": 0
#     },
#     {
#         "close": "4762.000",
#         "ctm": "1726707900",
#         "ctmfmt": "2024-09-19 09:05:00",
#         "high": "4766.000",
#         "low": "4760.000",
#         "open": "4760.000",
#         "volume": "4039",
#         "wave": 0
#     },
#     {
#         "close": "4762.000",
#         "ctm": "1726707960",
#         "ctmfmt": "2024-09-19 09:06:00",
#         "high": "4766.000",
#         "low": "4756.000",
#         "open": "4762.000",
#         "volume": "9651",
#         "wave": 0
#     },
#     {
#         "close": "4764.000",
#         "ctm": "1726708020",
#         "ctmfmt": "2024-09-19 09:07:00",
#         "high": "4766.000",
#         "low": "4760.000",
#         "open": "4762.000",
#         "volume": "3657",
#         "wave": 0
#     },
#     {
#         "close": "4762.000",
#         "ctm": "1726708080",
#         "ctmfmt": "2024-09-19 09:08:00",
#         "high": "4766.000",
#         "low": "4760.000",
#         "open": "4764.000",
#         "volume": "4363",
#         "wave": 0
#     },
#     {
#         "close": "4760.000",
#         "ctm": "1726708140",
#         "ctmfmt": "2024-09-19 09:09:00",
#         "high": "4764.000",
#         "low": "4756.000",
#         "open": "4760.000",
#         "volume": "3075",
#         "wave": 0
#     },
#     {
#         "close": "4760.000",
#         "ctm": "1726708200",
#         "ctmfmt": "2024-09-19 09:10:00",
#         "high": "4762.000",
#         "low": "4756.000",
#         "open": "4760.000",
#         "volume": "4667",
#         "wave": 0
#     },
#     {
#         "close": "4766.000",
#         "ctm": "1726708260",
#         "ctmfmt": "2024-09-19 09:11:00",
#         "high": "4766.000",
#         "low": "4756.000",
#         "open": "4762.000",
#         "volume": "6632",
#         "wave": 0
#     },
#     {
#         "close": "4768.000",
#         "ctm": "1726708320",
#         "ctmfmt": "2024-09-19 09:12:00",
#         "high": "4770.000",
#         "low": "4762.000",
#         "open": "4768.000",
#         "volume": "4091",
#         "wave": 0
#     },
#     {
#         "close": "4770.000",
#         "ctm": "1726708380",
#         "ctmfmt": "2024-09-19 09:13:00",
#         "high": "4772.000",
#         "low": "4768.000",
#         "open": "4772.000",
#         "volume": "1152",
#         "wave": 0
#     },
#     {
#         "close": "4766.000",
#         "ctm": "1726708440",
#         "ctmfmt": "2024-09-19 09:14:00",
#         "high": "4772.000",
#         "low": "4764.000",
#         "open": "4770.000",
#         "volume": "3147",
#         "wave": 0
#     },
#     {
#         "close": "4770.000",
#         "ctm": "1726708500",
#         "ctmfmt": "2024-09-19 09:15:00",
#         "high": "4770.000",
#         "low": "4766.000",
#         "open": "4766.000",
#         "volume": "1221",
#         "wave": 0
#     },
#     {
#         "close": "4766.000",
#         "ctm": "1726708560",
#         "ctmfmt": "2024-09-19 09:16:00",
#         "high": "4768.000",
#         "low": "4762.000",
#         "open": "4764.000",
#         "volume": "2958",
#         "wave": 0
#     },
#     {
#         "close": "4764.000",
#         "ctm": "1726708620",
#         "ctmfmt": "2024-09-19 09:17:00",
#         "high": "4764.000",
#         "low": "4762.000",
#         "open": "4762.000",
#         "volume": "498",
#         "wave": 0
#     },
#     {
#         "close": "4762.000",
#         "ctm": "1726708680",
#         "ctmfmt": "2024-09-19 09:18:00",
#         "high": "4768.000",
#         "low": "4762.000",
#         "open": "4766.000",
#         "volume": "2264",
#         "wave": 0
#     },
#     {
#         "close": "4762.000",
#         "ctm": "1726708740",
#         "ctmfmt": "2024-09-19 09:19:00",
#         "high": "4762.000",
#         "low": "4760.000",
#         "open": "4762.000",
#         "volume": "17",
#         "wave": 0
#     },
#     {
#         "close": "4758.000",
#         "ctm": "1726708800",
#         "ctmfmt": "2024-09-19 09:20:00",
#         "high": "4758.000",
#         "low": "4758.000",
#         "open": "4758.000",
#         "volume": "713048",
#         "wave": 0
#     },
#     {
#         "close": "4748.000",
#         "ctm": "1726708860",
#         "ctmfmt": "2024-09-19 09:21:00",
#         "high": "4754.000",
#         "low": "4746.000",
#         "open": "4754.000",
#         "volume": "6528",
#         "wave": 0
#     },
#     {
#         "close": "4748.000",
#         "ctm": "1726708920",
#         "ctmfmt": "2024-09-19 09:22:00",
#         "high": "4750.000",
#         "low": "4742.000",
#         "open": "4748.000",
#         "volume": "4990",
#         "wave": 0
#     },
#     {
#         "close": "4740.000",
#         "ctm": "1726708980",
#         "ctmfmt": "2024-09-19 09:23:00",
#         "high": "4748.000",
#         "low": "4740.000",
#         "open": "4746.000",
#         "volume": "4501",
#         "wave": 0
#     },
#     {
#         "close": "4732.000",
#         "ctm": "1726709040",
#         "ctmfmt": "2024-09-19 09:24:00",
#         "high": "4742.000",
#         "low": "4728.000",
#         "open": "4740.000",
#         "volume": "9426",
#         "wave": 0
#     },
#     {
#         "close": "4732.000",
#         "ctm": "1726709100",
#         "ctmfmt": "2024-09-19 09:25:00",
#         "high": "4738.000",
#         "low": "4732.000",
#         "open": "4734.000",
#         "volume": "3815",
#         "wave": 0
#     },
#     {
#         "close": "4726.000",
#         "ctm": "1726709160",
#         "ctmfmt": "2024-09-19 09:26:00",
#         "high": "4734.000",
#         "low": "4726.000",
#         "open": "4732.000",
#         "volume": "7778",
#         "wave": 0
#     },
#     {
#         "close": "4724.000",
#         "ctm": "1726709220",
#         "ctmfmt": "2024-09-19 09:27:00",
#         "high": "4728.000",
#         "low": "4724.000",
#         "open": "4726.000",
#         "volume": "1528",
#         "wave": 0
#     },
#     {
#         "close": "4718.000",
#         "ctm": "1726709280",
#         "ctmfmt": "2024-09-19 09:28:00",
#         "high": "4720.000",
#         "low": "4716.000",
#         "open": "4718.000",
#         "volume": "4255",
#         "wave": 0
#     },
#     {
#         "close": "4716.000",
#         "ctm": "1726709340",
#         "ctmfmt": "2024-09-19 09:29:00",
#         "high": "4720.000",
#         "low": "4714.000",
#         "open": "4716.000",
#         "volume": "5456",
#         "wave": 0
#     },
#     {
#         "close": "4714.000",
#         "ctm": "1726709400",
#         "ctmfmt": "2024-09-19 09:30:00",
#         "high": "4718.000",
#         "low": "4710.000",
#         "open": "4714.000",
#         "volume": "10274",
#         "wave": 0
#     },
#     {
#         "close": "4722.000",
#         "ctm": "1726709460",
#         "ctmfmt": "2024-09-19 09:31:00",
#         "high": "4724.000",
#         "low": "4716.000",
#         "open": "4716.000",
#         "volume": "7568",
#         "wave": 0
#     },
#     {
#         "close": "4722.000",
#         "ctm": "1726709520",
#         "ctmfmt": "2024-09-19 09:32:00",
#         "high": "4728.000",
#         "low": "4720.000",
#         "open": "4720.000",
#         "volume": "3613",
#         "wave": 0
#     },
#     {
#         "close": "4726.000",
#         "ctm": "1726709580",
#         "ctmfmt": "2024-09-19 09:33:00",
#         "high": "4726.000",
#         "low": "4722.000",
#         "open": "4722.000",
#         "volume": "1689",
#         "wave": 0
#     },
#     {
#         "close": "4714.000",
#         "ctm": "1726709640",
#         "ctmfmt": "2024-09-19 09:34:00",
#         "high": "4714.000",
#         "low": "4712.000",
#         "open": "4714.000",
#         "volume": "2058",
#         "wave": 0
#     },
#     {
#         "close": "4714.000",
#         "ctm": "1726709700",
#         "ctmfmt": "2024-09-19 09:35:00",
#         "high": "4716.000",
#         "low": "4710.000",
#         "open": "4714.000",
#         "volume": "9584",
#         "wave": 0
#     },
#     {
#         "close": "4714.000",
#         "ctm": "1726709760",
#         "ctmfmt": "2024-09-19 09:36:00",
#         "high": "4718.000",
#         "low": "4714.000",
#         "open": "4716.000",
#         "volume": "3585",
#         "wave": 0
#     },
#     {
#         "close": "4718.000",
#         "ctm": "1726709820",
#         "ctmfmt": "2024-09-19 09:37:00",
#         "high": "4718.000",
#         "low": "4716.000",
#         "open": "4718.000",
#         "volume": "747",
#         "wave": 0
#     },
#     {
#         "close": "4712.000",
#         "ctm": "1726709880",
#         "ctmfmt": "2024-09-19 09:38:00",
#         "high": "4718.000",
#         "low": "4710.000",
#         "open": "4718.000",
#         "volume": "3557",
#         "wave": 0
#     },
#     {
#         "close": "4716.000",
#         "ctm": "1726709940",
#         "ctmfmt": "2024-09-19 09:39:00",
#         "high": "4718.000",
#         "low": "4716.000",
#         "open": "4718.000",
#         "volume": "812",
#         "wave": 0
#     },
#     {
#         "close": "4714.000",
#         "ctm": "1726710000",
#         "ctmfmt": "2024-09-19 09:40:00",
#         "high": "4718.000",
#         "low": "4712.000",
#         "open": "4716.000",
#         "volume": "4393",
#         "wave": 0
#     },
#     {
#         "close": "4710.000",
#         "ctm": "1726710060",
#         "ctmfmt": "2024-09-19 09:41:00",
#         "high": "4716.000",
#         "low": "4710.000",
#         "open": "4712.000",
#         "volume": "4356",
#         "wave": 0
#     },
#     {
#         "close": "4710.000",
#         "ctm": "1726710120",
#         "ctmfmt": "2024-09-19 09:42:00",
#         "high": "4710.000",
#         "low": "4706.000",
#         "open": "4710.000",
#         "volume": "6915",
#         "wave": 0
#     },
#     {
#         "close": "4712.000",
#         "ctm": "1726710180",
#         "ctmfmt": "2024-09-19 09:43:00",
#         "high": "4714.000",
#         "low": "4708.000",
#         "open": "4710.000",
#         "volume": "4703",
#         "wave": 0
#     },
#     {
#         "close": "4712.000",
#         "ctm": "1726710240",
#         "ctmfmt": "2024-09-19 09:44:00",
#         "high": "4714.000",
#         "low": "4708.000",
#         "open": "4714.000",
#         "volume": "6606",
#         "wave": 0
#     },
#     {
#         "close": "4712.000",
#         "ctm": "1726710300",
#         "ctmfmt": "2024-09-19 09:45:00",
#         "high": "4714.000",
#         "low": "4708.000",
#         "open": "4710.000",
#         "volume": "2416",
#         "wave": 0
#     },
#     {
#         "close": "4718.000",
#         "ctm": "1726710360",
#         "ctmfmt": "2024-09-19 09:46:00",
#         "high": "4720.000",
#         "low": "4712.000",
#         "open": "4712.000",
#         "volume": "3453",
#         "wave": 0
#     },
#     {
#         "close": "4712.000",
#         "ctm": "1726710420",
#         "ctmfmt": "2024-09-19 09:47:00",
#         "high": "4720.000",
#         "low": "4710.000",
#         "open": "4718.000",
#         "volume": "4686",
#         "wave": 0
#     },
#     {
#         "close": "4710.000",
#         "ctm": "1726710480",
#         "ctmfmt": "2024-09-19 09:48:00",
#         "high": "4712.000",
#         "low": "4706.000",
#         "open": "4712.000",
#         "volume": "3024",
#         "wave": 0
#     },
#     {
#         "close": "4700.000",
#         "ctm": "1726710540",
#         "ctmfmt": "2024-09-19 09:49:00",
#         "high": "4708.000",
#         "low": "4700.000",
#         "open": "4708.000",
#         "volume": "7642",
#         "wave": 0
#     },
#     {
#         "close": "4700.000",
#         "ctm": "1726710600",
#         "ctmfmt": "2024-09-19 09:50:00",
#         "high": "4702.000",
#         "low": "4696.000",
#         "open": "4700.000",
#         "volume": "8377",
#         "wave": 0
#     },
#     {
#         "close": "4702.000",
#         "ctm": "1726710660",
#         "ctmfmt": "2024-09-19 09:51:00",
#         "high": "4704.000",
#         "low": "4698.000",
#         "open": "4698.000",
#         "volume": "4861",
#         "wave": 0
#     },
#     {
#         "close": "4708.000",
#         "ctm": "1726710720",
#         "ctmfmt": "2024-09-19 09:52:00",
#         "high": "4708.000",
#         "low": "4702.000",
#         "open": "4702.000",
#         "volume": "3420",
#         "wave": 0
#     },
#     {
#         "close": "4708.000",
#         "ctm": "1726710780",
#         "ctmfmt": "2024-09-19 09:53:00",
#         "high": "4710.000",
#         "low": "4704.000",
#         "open": "4706.000",
#         "volume": "2671",
#         "wave": 0
#     },
#     {
#         "close": "4722.000",
#         "ctm": "1726710840",
#         "ctmfmt": "2024-09-19 09:54:00",
#         "high": "4726.000",
#         "low": "4708.000",
#         "open": "4708.000",
#         "volume": "9361",
#         "wave": 0
#     },
#     {
#         "close": "4720.000",
#         "ctm": "1726710900",
#         "ctmfmt": "2024-09-19 09:55:00",
#         "high": "4728.000",
#         "low": "4720.000",
#         "open": "4724.000",
#         "volume": "5905",
#         "wave": 0
#     },
#     {
#         "close": "4722.000",
#         "ctm": "1726710960",
#         "ctmfmt": "2024-09-19 09:56:00",
#         "high": "4728.000",
#         "low": "4722.000",
#         "open": "4722.000",
#         "volume": "3419",
#         "wave": 0
#     },
#     {
#         "close": "4728.000",
#         "ctm": "1726711020",
#         "ctmfmt": "2024-09-19 09:57:00",
#         "high": "4728.000",
#         "low": "4722.000",
#         "open": "4722.000",
#         "volume": "2674",
#         "wave": 0
#     },
#     {
#         "close": "4736.000",
#         "ctm": "1726711080",
#         "ctmfmt": "2024-09-19 09:58:00",
#         "high": "4736.000",
#         "low": "4728.000",
#         "open": "4732.000",
#         "volume": "7250",
#         "wave": 0
#     },
#     {
#         "close": "4732.000",
#         "ctm": "1726711140",
#         "ctmfmt": "2024-09-19 09:59:00",
#         "high": "4740.000",
#         "low": "4732.000",
#         "open": "4738.000",
#         "volume": "4047",
#         "wave": 0
#     },
#     {
#         "close": "4744.000",
#         "ctm": "1726711200",
#         "ctmfmt": "2024-09-19 10:00:00",
#         "high": "4744.000",
#         "low": "4732.000",
#         "open": "4732.000",
#         "volume": "7115",
#         "wave": 0
#     },
#     {
#         "close": "4742.000",
#         "ctm": "1726711260",
#         "ctmfmt": "2024-09-19 10:01:00",
#         "high": "4744.000",
#         "low": "4738.000",
#         "open": "4744.000",
#         "volume": "5047",
#         "wave": 0
#     },
#     {
#         "close": "4756.000",
#         "ctm": "1726711320",
#         "ctmfmt": "2024-09-19 10:02:00",
#         "high": "4756.000",
#         "low": "4756.000",
#         "open": "4756.000",
#         "volume": "484",
#         "wave": 0
#     },
#     {
#         "close": "4752.000",
#         "ctm": "1726711380",
#         "ctmfmt": "2024-09-19 10:03:00",
#         "high": "4756.000",
#         "low": "4752.000",
#         "open": "4756.000",
#         "volume": "7461",
#         "wave": 0
#     },
#     {
#         "close": "4764.000",
#         "ctm": "1726711440",
#         "ctmfmt": "2024-09-19 10:04:00",
#         "high": "4766.000",
#         "low": "4752.000",
#         "open": "4752.000",
#         "volume": "7869",
#         "wave": 0
#     },
#     {
#         "close": "4770.000",
#         "ctm": "1726711500",
#         "ctmfmt": "2024-09-19 10:05:00",
#         "high": "4770.000",
#         "low": "4762.000",
#         "open": "4762.000",
#         "volume": "7712",
#         "wave": 0
#     },
#     {
#         "close": "4758.000",
#         "ctm": "1726711560",
#         "ctmfmt": "2024-09-19 10:06:00",
#         "high": "4766.000",
#         "low": "4756.000",
#         "open": "4766.000",
#         "volume": "7124",
#         "wave": 0
#     },
#     {
#         "close": "4758.000",
#         "ctm": "1726711620",
#         "ctmfmt": "2024-09-19 10:07:00",
#         "high": "4762.000",
#         "low": "4758.000",
#         "open": "4758.000",
#         "volume": "5882",
#         "wave": 0
#     },
#     {
#         "close": "4764.000",
#         "ctm": "1726711680",
#         "ctmfmt": "2024-09-19 10:08:00",
#         "high": "4768.000",
#         "low": "4756.000",
#         "open": "4758.000",
#         "volume": "8969",
#         "wave": 0
#     },
#     {
#         "close": "4768.000",
#         "ctm": "1726711740",
#         "ctmfmt": "2024-09-19 10:09:00",
#         "high": "4768.000",
#         "low": "4762.000",
#         "open": "4764.000",
#         "volume": "3885",
#         "wave": 0
#     },
#     {
#         "close": "4766.000",
#         "ctm": "1726711800",
#         "ctmfmt": "2024-09-19 10:10:00",
#         "high": "4770.000",
#         "low": "4766.000",
#         "open": "4768.000",
#         "volume": "2887",
#         "wave": 0
#     },
#     {
#         "close": "4766.000",
#         "ctm": "1726711860",
#         "ctmfmt": "2024-09-19 10:11:00",
#         "high": "4768.000",
#         "low": "4762.000",
#         "open": "4766.000",
#         "volume": "3581",
#         "wave": 0
#     },
#     {
#         "close": "4776.000",
#         "ctm": "1726711920",
#         "ctmfmt": "2024-09-19 10:12:00",
#         "high": "4778.000",
#         "low": "4766.000",
#         "open": "4766.000",
#         "volume": "8082",
#         "wave": 0
#     },
#     {
#         "close": "4764.000",
#         "ctm": "1726711980",
#         "ctmfmt": "2024-09-19 10:13:00",
#         "high": "4772.000",
#         "low": "4764.000",
#         "open": "4772.000",
#         "volume": "5316",
#         "wave": 0
#     },
#     {
#         "close": "4766.000",
#         "ctm": "1726712040",
#         "ctmfmt": "2024-09-19 10:14:00",
#         "high": "4768.000",
#         "low": "4762.000",
#         "open": "4762.000",
#         "volume": "2040",
#         "wave": 0
#     },
#     {
#         "close": "4770.000",
#         "ctm": "1726712100",
#         "ctmfmt": "2024-09-19 10:15:00",
#         "high": "4770.000",
#         "low": "4764.000",
#         "open": "4766.000",
#         "volume": "2925",
#         "wave": 0
#     },
#     {
#         "close": "4812.000",
#         "ctm": "1726713060",
#         "ctmfmt": "2024-09-19 10:31:00",
#         "high": "4814.000",
#         "low": "4774.000",
#         "open": "4774.000",
#         "volume": "46342",
#         "wave": 0
#     },
#     {
#         "close": "4820.000",
#         "ctm": "1726713120",
#         "ctmfmt": "2024-09-19 10:32:00",
#         "high": "4826.000",
#         "low": "4806.000",
#         "open": "4814.000",
#         "volume": "32670",
#         "wave": 0
#     },
#     {
#         "close": "4814.000",
#         "ctm": "1726713180",
#         "ctmfmt": "2024-09-19 10:33:00",
#         "high": "4818.000",
#         "low": "4810.000",
#         "open": "4816.000",
#         "volume": "14269",
#         "wave": 0
#     },
#     {
#         "close": "4802.000",
#         "ctm": "1726713240",
#         "ctmfmt": "2024-09-19 10:34:00",
#         "high": "4812.000",
#         "low": "4800.000",
#         "open": "4810.000",
#         "volume": "9303",
#         "wave": 0
#     },
#     {
#         "close": "4808.000",
#         "ctm": "1726713300",
#         "ctmfmt": "2024-09-19 10:35:00",
#         "high": "4812.000",
#         "low": "4802.000",
#         "open": "4802.000",
#         "volume": "8758",
#         "wave": 0
#     },
#     {
#         "close": "4814.000",
#         "ctm": "1726713360",
#         "ctmfmt": "2024-09-19 10:36:00",
#         "high": "4816.000",
#         "low": "4804.000",
#         "open": "4804.000",
#         "volume": "8612",
#         "wave": 0
#     },
#     {
#         "close": "4824.000",
#         "ctm": "1726713420",
#         "ctmfmt": "2024-09-19 10:37:00",
#         "high": "4824.000",
#         "low": "4812.000",
#         "open": "4812.000",
#         "volume": "12306",
#         "wave": 0
#     },
#     {
#         "close": "4818.000",
#         "ctm": "1726713480",
#         "ctmfmt": "2024-09-19 10:38:00",
#         "high": "4826.000",
#         "low": "4816.000",
#         "open": "4822.000",
#         "volume": "13348",
#         "wave": 0
#     },
#     {
#         "close": "4822.000",
#         "ctm": "1726713540",
#         "ctmfmt": "2024-09-19 10:39:00",
#         "high": "4830.000",
#         "low": "4818.000",
#         "open": "4818.000",
#         "volume": "19081",
#         "wave": 0
#     },
#     {
#         "close": "4828.000",
#         "ctm": "1726713600",
#         "ctmfmt": "2024-09-19 10:40:00",
#         "high": "4828.000",
#         "low": "4818.000",
#         "open": "4822.000",
#         "volume": "5759",
#         "wave": 0
#     },
#     {
#         "close": "4834.000",
#         "ctm": "1726713660",
#         "ctmfmt": "2024-09-19 10:41:00",
#         "high": "4840.000",
#         "low": "4828.000",
#         "open": "4828.000",
#         "volume": "15341",
#         "wave": 0
#     },
#     {
#         "close": "4840.000",
#         "ctm": "1726713720",
#         "ctmfmt": "2024-09-19 10:42:00",
#         "high": "4842.000",
#         "low": "4834.000",
#         "open": "4838.000",
#         "volume": "9237",
#         "wave": 0
#     },
#     {
#         "close": "4828.000",
#         "ctm": "1726713780",
#         "ctmfmt": "2024-09-19 10:43:00",
#         "high": "4840.000",
#         "low": "4828.000",
#         "open": "4838.000",
#         "volume": "8117",
#         "wave": 0
#     },
#     {
#         "close": "4832.000",
#         "ctm": "1726713840",
#         "ctmfmt": "2024-09-19 10:44:00",
#         "high": "4832.000",
#         "low": "4828.000",
#         "open": "4830.000",
#         "volume": "2224",
#         "wave": 0
#     },
#     {
#         "close": "4832.000",
#         "ctm": "1726713900",
#         "ctmfmt": "2024-09-19 10:45:00",
#         "high": "4838.000",
#         "low": "4832.000",
#         "open": "4832.000",
#         "volume": "4940",
#         "wave": 0
#     },
#     {
#         "close": "4836.000",
#         "ctm": "1726713960",
#         "ctmfmt": "2024-09-19 10:46:00",
#         "high": "4836.000",
#         "low": "4830.000",
#         "open": "4834.000",
#         "volume": "8468",
#         "wave": 0
#     },
#     {
#         "close": "4838.000",
#         "ctm": "1726714020",
#         "ctmfmt": "2024-09-19 10:47:00",
#         "high": "4840.000",
#         "low": "4834.000",
#         "open": "4836.000",
#         "volume": "4387",
#         "wave": 0
#     },
#     {
#         "close": "4852.000",
#         "ctm": "1726714080",
#         "ctmfmt": "2024-09-19 10:48:00",
#         "high": "4852.000",
#         "low": "4840.000",
#         "open": "4840.000",
#         "volume": "11359",
#         "wave": 0
#     },
#     {
#         "close": "4842.000",
#         "ctm": "1726714140",
#         "ctmfmt": "2024-09-19 10:49:00",
#         "high": "4842.000",
#         "low": "4842.000",
#         "open": "4842.000",
#         "volume": "12",
#         "wave": 0
#     },
#     {
#         "close": "4840.000",
#         "ctm": "1726714200",
#         "ctmfmt": "2024-09-19 10:50:00",
#         "high": "4848.000",
#         "low": "4840.000",
#         "open": "4844.000",
#         "volume": "7617",
#         "wave": 0
#     },
#     {
#         "close": "4844.000",
#         "ctm": "1726714260",
#         "ctmfmt": "2024-09-19 10:51:00",
#         "high": "4846.000",
#         "low": "4838.000",
#         "open": "4840.000",
#         "volume": "3657",
#         "wave": 0
#     },
#     {
#         "close": "4842.000",
#         "ctm": "1726714320",
#         "ctmfmt": "2024-09-19 10:52:00",
#         "high": "4846.000",
#         "low": "4840.000",
#         "open": "4842.000",
#         "volume": "3445",
#         "wave": 0
#     },
#     {
#         "close": "4828.000",
#         "ctm": "1726714380",
#         "ctmfmt": "2024-09-19 10:53:00",
#         "high": "4844.000",
#         "low": "4824.000",
#         "open": "4844.000",
#         "volume": "10758",
#         "wave": 0
#     },
#     {
#         "close": "4820.000",
#         "ctm": "1726714440",
#         "ctmfmt": "2024-09-19 10:54:00",
#         "high": "4830.000",
#         "low": "4818.000",
#         "open": "4828.000",
#         "volume": "11871",
#         "wave": 0
#     },
#     {
#         "close": "4828.000",
#         "ctm": "1726714500",
#         "ctmfmt": "2024-09-19 10:55:00",
#         "high": "4828.000",
#         "low": "4818.000",
#         "open": "4820.000",
#         "volume": "7812",
#         "wave": 0
#     },
#     {
#         "close": "4836.000",
#         "ctm": "1726714560",
#         "ctmfmt": "2024-09-19 10:56:00",
#         "high": "4836.000",
#         "low": "4828.000",
#         "open": "4828.000",
#         "volume": "5379",
#         "wave": 0
#     },
#     {
#         "close": "4838.000",
#         "ctm": "1726714620",
#         "ctmfmt": "2024-09-19 10:57:00",
#         "high": "4842.000",
#         "low": "4834.000",
#         "open": "4834.000",
#         "volume": "5523",
#         "wave": 0
#     },
#     {
#         "close": "4832.000",
#         "ctm": "1726714680",
#         "ctmfmt": "2024-09-19 10:58:00",
#         "high": "4838.000",
#         "low": "4832.000",
#         "open": "4838.000",
#         "volume": "3539",
#         "wave": 0
#     },
#     {
#         "close": "4832.000",
#         "ctm": "1726714740",
#         "ctmfmt": "2024-09-19 10:59:00",
#         "high": "4838.000",
#         "low": "4828.000",
#         "open": "4834.000",
#         "volume": "2416",
#         "wave": 0
#     },
#     {
#         "close": "4834.000",
#         "ctm": "1726714800",
#         "ctmfmt": "2024-09-19 11:00:00",
#         "high": "4834.000",
#         "low": "4830.000",
#         "open": "4830.000",
#         "volume": "2583",
#         "wave": 0
#     },
#     {
#         "close": "4826.000",
#         "ctm": "1726714860",
#         "ctmfmt": "2024-09-19 11:01:00",
#         "high": "4836.000",
#         "low": "4824.000",
#         "open": "4836.000",
#         "volume": "3698",
#         "wave": 0
#     },
#     {
#         "close": "4826.000",
#         "ctm": "1726714920",
#         "ctmfmt": "2024-09-19 11:02:00",
#         "high": "4830.000",
#         "low": "4824.000",
#         "open": "4826.000",
#         "volume": "2335",
#         "wave": 0
#     },
#     {
#         "close": "4818.000",
#         "ctm": "1726714980",
#         "ctmfmt": "2024-09-19 11:03:00",
#         "high": "4824.000",
#         "low": "4818.000",
#         "open": "4824.000",
#         "volume": "3475",
#         "wave": 0
#     },
#     {
#         "close": "4816.000",
#         "ctm": "1726715040",
#         "ctmfmt": "2024-09-19 11:04:00",
#         "high": "4820.000",
#         "low": "4812.000",
#         "open": "4818.000",
#         "volume": "4873",
#         "wave": 0
#     },
#     {
#         "close": "4818.000",
#         "ctm": "1726715100",
#         "ctmfmt": "2024-09-19 11:05:00",
#         "high": "4820.000",
#         "low": "4814.000",
#         "open": "4814.000",
#         "volume": "6500",
#         "wave": 0
#     },
#     {
#         "close": "4814.000",
#         "ctm": "1726715160",
#         "ctmfmt": "2024-09-19 11:06:00",
#         "high": "4818.000",
#         "low": "4814.000",
#         "open": "4816.000",
#         "volume": "1710",
#         "wave": 0
#     },
#     {
#         "close": "4820.000",
#         "ctm": "1726715220",
#         "ctmfmt": "2024-09-19 11:07:00",
#         "high": "4820.000",
#         "low": "4814.000",
#         "open": "4814.000",
#         "volume": "2810",
#         "wave": 0
#     },
#     {
#         "close": "4826.000",
#         "ctm": "1726715280",
#         "ctmfmt": "2024-09-19 11:08:00",
#         "high": "4826.000",
#         "low": "4818.000",
#         "open": "4818.000",
#         "volume": "2118",
#         "wave": 0
#     },
#     {
#         "close": "4822.000",
#         "ctm": "1726715340",
#         "ctmfmt": "2024-09-19 11:09:00",
#         "high": "4826.000",
#         "low": "4820.000",
#         "open": "4826.000",
#         "volume": "1897",
#         "wave": 0
#     },
#     {
#         "close": "4814.000",
#         "ctm": "1726715400",
#         "ctmfmt": "2024-09-19 11:10:00",
#         "high": "4822.000",
#         "low": "4814.000",
#         "open": "4822.000",
#         "volume": "2047",
#         "wave": 0
#     },
#     {
#         "close": "4818.000",
#         "ctm": "1726715460",
#         "ctmfmt": "2024-09-19 11:11:00",
#         "high": "4820.000",
#         "low": "4814.000",
#         "open": "4816.000",
#         "volume": "1593",
#         "wave": 0
#     },
#     {
#         "close": "4822.000",
#         "ctm": "1726715520",
#         "ctmfmt": "2024-09-19 11:12:00",
#         "high": "4822.000",
#         "low": "4818.000",
#         "open": "4818.000",
#         "volume": "2317",
#         "wave": 0
#     },
#     {
#         "close": "4818.000",
#         "ctm": "1726715580",
#         "ctmfmt": "2024-09-19 11:13:00",
#         "high": "4822.000",
#         "low": "4818.000",
#         "open": "4820.000",
#         "volume": "1424",
#         "wave": 0
#     },
#     {
#         "close": "4818.000",
#         "ctm": "1726715640",
#         "ctmfmt": "2024-09-19 11:14:00",
#         "high": "4822.000",
#         "low": "4816.000",
#         "open": "4818.000",
#         "volume": "2822",
#         "wave": 0
#     },
#     {
#         "close": "4822.000",
#         "ctm": "1726715700",
#         "ctmfmt": "2024-09-19 11:15:00",
#         "high": "4822.000",
#         "low": "4818.000",
#         "open": "4818.000",
#         "volume": "1707",
#         "wave": 0
#     },
#     {
#         "close": "4824.000",
#         "ctm": "1726715760",
#         "ctmfmt": "2024-09-19 11:16:00",
#         "high": "4824.000",
#         "low": "4818.000",
#         "open": "4822.000",
#         "volume": "1440",
#         "wave": 0
#     },
#     {
#         "close": "4830.000",
#         "ctm": "1726715820",
#         "ctmfmt": "2024-09-19 11:17:00",
#         "high": "4832.000",
#         "low": "4822.000",
#         "open": "4824.000",
#         "volume": "3572",
#         "wave": 0
#     },
#     {
#         "close": "4826.000",
#         "ctm": "1726715880",
#         "ctmfmt": "2024-09-19 11:18:00",
#         "high": "4832.000",
#         "low": "4824.000",
#         "open": "4832.000",
#         "volume": "3037",
#         "wave": 0
#     },
#     {
#         "close": "4832.000",
#         "ctm": "1726715940",
#         "ctmfmt": "2024-09-19 11:19:00",
#         "high": "4832.000",
#         "low": "4824.000",
#         "open": "4826.000",
#         "volume": "2172",
#         "wave": 0
#     },
#     {
#         "close": "4832.000",
#         "ctm": "1726716000",
#         "ctmfmt": "2024-09-19 11:20:00",
#         "high": "4834.000",
#         "low": "4830.000",
#         "open": "4830.000",
#         "volume": "2595",
#         "wave": 0
#     },
#     {
#         "close": "4838.000",
#         "ctm": "1726716060",
#         "ctmfmt": "2024-09-19 11:21:00",
#         "high": "4842.000",
#         "low": "4832.000",
#         "open": "4834.000",
#         "volume": "5296",
#         "wave": 0
#     },
#     {
#         "close": "4842.000",
#         "ctm": "1726716120",
#         "ctmfmt": "2024-09-19 11:22:00",
#         "high": "4842.000",
#         "low": "4836.000",
#         "open": "4838.000",
#         "volume": "2316",
#         "wave": 0
#     },
#     {
#         "close": "4836.000",
#         "ctm": "1726716180",
#         "ctmfmt": "2024-09-19 11:23:00",
#         "high": "4842.000",
#         "low": "4834.000",
#         "open": "4842.000",
#         "volume": "2518",
#         "wave": 0
#     },
#     {
#         "close": "4838.000",
#         "ctm": "1726716240",
#         "ctmfmt": "2024-09-19 11:24:00",
#         "high": "4838.000",
#         "low": "4834.000",
#         "open": "4834.000",
#         "volume": "1433",
#         "wave": 0
#     },
#     {
#         "close": "4838.000",
#         "ctm": "1726716300",
#         "ctmfmt": "2024-09-19 11:25:00",
#         "high": "4838.000",
#         "low": "4834.000",
#         "open": "4838.000",
#         "volume": "1118",
#         "wave": 0
#     },
#     {
#         "close": "4836.000",
#         "ctm": "1726716360",
#         "ctmfmt": "2024-09-19 11:26:00",
#         "high": "4842.000",
#         "low": "4834.000",
#         "open": "4838.000",
#         "volume": "3281",
#         "wave": 0
#     },
#     {
#         "close": "4840.000",
#         "ctm": "1726716420",
#         "ctmfmt": "2024-09-19 11:27:00",
#         "high": "4842.000",
#         "low": "4834.000",
#         "open": "4834.000",
#         "volume": "3393",
#         "wave": 0
#     },
#     {
#         "close": "4836.000",
#         "ctm": "1726716480",
#         "ctmfmt": "2024-09-19 11:28:00",
#         "high": "4840.000",
#         "low": "4836.000",
#         "open": "4838.000",
#         "volume": "1581",
#         "wave": 0
#     },
#     {
#         "close": "4836.000",
#         "ctm": "1726716540",
#         "ctmfmt": "2024-09-19 11:29:00",
#         "high": "4836.000",
#         "low": "4836.000",
#         "open": "4836.000",
#         "volume": "534",
#         "wave": 0
#     },
#     {
#         "close": "4842.000",
#         "ctm": "1726716600",
#         "ctmfmt": "2024-09-19 11:30:00",
#         "high": "4846.000",
#         "low": "4836.000",
#         "open": "4836.000",
#         "volume": "3848",
#         "wave": 0
#     },
#     {
#         "close": "4848.000",
#         "ctm": "1726723860",
#         "ctmfmt": "2024-09-19 13:31:00",
#         "high": "4856.000",
#         "low": "4844.000",
#         "open": "4852.000",
#         "volume": "12299",
#         "wave": 0
#     },
#     {
#         "close": "4846.000",
#         "ctm": "1726723920",
#         "ctmfmt": "2024-09-19 13:32:00",
#         "high": "4850.000",
#         "low": "4844.000",
#         "open": "4848.000",
#         "volume": "3268",
#         "wave": 0
#     },
#     {
#         "close": "4848.000",
#         "ctm": "1726723980",
#         "ctmfmt": "2024-09-19 13:33:00",
#         "high": "4850.000",
#         "low": "4846.000",
#         "open": "4848.000",
#         "volume": "1885",
#         "wave": 0
#     },
#     {
#         "close": "4852.000",
#         "ctm": "1726724040",
#         "ctmfmt": "2024-09-19 13:34:00",
#         "high": "4852.000",
#         "low": "4846.000",
#         "open": "4848.000",
#         "volume": "3275",
#         "wave": 0
#     },
#     {
#         "close": "4850.000",
#         "ctm": "1726724100",
#         "ctmfmt": "2024-09-19 13:35:00",
#         "high": "4856.000",
#         "low": "4848.000",
#         "open": "4852.000",
#         "volume": "5255",
#         "wave": 0
#     },
#     {
#         "close": "4860.000",
#         "ctm": "1726724160",
#         "ctmfmt": "2024-09-19 13:36:00",
#         "high": "4860.000",
#         "low": "4850.000",
#         "open": "4850.000",
#         "volume": "8188",
#         "wave": 0
#     },
#     {
#         "close": "4862.000",
#         "ctm": "1726724220",
#         "ctmfmt": "2024-09-19 13:37:00",
#         "high": "4864.000",
#         "low": "4860.000",
#         "open": "4860.000",
#         "volume": "1816",
#         "wave": 0
#     },
#     {
#         "close": "4854.000",
#         "ctm": "1726724280",
#         "ctmfmt": "2024-09-19 13:38:00",
#         "high": "4862.000",
#         "low": "4854.000",
#         "open": "4862.000",
#         "volume": "505",
#         "wave": 0
#     },
#     {
#         "close": "4854.000",
#         "ctm": "1726724340",
#         "ctmfmt": "2024-09-19 13:39:00",
#         "high": "4856.000",
#         "low": "4852.000",
#         "open": "4854.000",
#         "volume": "2448",
#         "wave": 0
#     },
#     {
#         "close": "4850.000",
#         "ctm": "1726724400",
#         "ctmfmt": "2024-09-19 13:40:00",
#         "high": "4854.000",
#         "low": "4850.000",
#         "open": "4854.000",
#         "volume": "2644",
#         "wave": 0
#     },
#     {
#         "close": "4856.000",
#         "ctm": "1726724460",
#         "ctmfmt": "2024-09-19 13:41:00",
#         "high": "4856.000",
#         "low": "4850.000",
#         "open": "4850.000",
#         "volume": "2015",
#         "wave": 0
#     },
#     {
#         "close": "4860.000",
#         "ctm": "1726724520",
#         "ctmfmt": "2024-09-19 13:42:00",
#         "high": "4862.000",
#         "low": "4856.000",
#         "open": "4856.000",
#         "volume": "7389",
#         "wave": 0
#     },
#     {
#         "close": "4870.000",
#         "ctm": "1726724580",
#         "ctmfmt": "2024-09-19 13:43:00",
#         "high": "4870.000",
#         "low": "4858.000",
#         "open": "4858.000",
#         "volume": "10015",
#         "wave": 0
#     },
#     {
#         "close": "4866.000",
#         "ctm": "1726724640",
#         "ctmfmt": "2024-09-19 13:44:00",
#         "high": "4872.000",
#         "low": "4864.000",
#         "open": "4870.000",
#         "volume": "6060",
#         "wave": 0
#     },
#     {
#         "close": "4866.000",
#         "ctm": "1726724700",
#         "ctmfmt": "2024-09-19 13:45:00",
#         "high": "4870.000",
#         "low": "4864.000",
#         "open": "4864.000",
#         "volume": "3368",
#         "wave": 0
#     },
#     {
#         "close": "4864.000",
#         "ctm": "1726724760",
#         "ctmfmt": "2024-09-19 13:46:00",
#         "high": "4868.000",
#         "low": "4860.000",
#         "open": "4864.000",
#         "volume": "5458",
#         "wave": 0
#     },
#     {
#         "close": "4858.000",
#         "ctm": "1726724820",
#         "ctmfmt": "2024-09-19 13:47:00",
#         "high": "4864.000",
#         "low": "4858.000",
#         "open": "4864.000",
#         "volume": "4905",
#         "wave": 0
#     },
#     {
#         "close": "4858.000",
#         "ctm": "1726724880",
#         "ctmfmt": "2024-09-19 13:48:00",
#         "high": "4862.000",
#         "low": "4858.000",
#         "open": "4858.000",
#         "volume": "2678",
#         "wave": 0
#     },
#     {
#         "close": "4854.000",
#         "ctm": "1726724940",
#         "ctmfmt": "2024-09-19 13:49:00",
#         "high": "4856.000",
#         "low": "4854.000",
#         "open": "4854.000",
#         "volume": "867",
#         "wave": 0
#     },
#     {
#         "close": "4856.000",
#         "ctm": "1726725000",
#         "ctmfmt": "2024-09-19 13:50:00",
#         "high": "4858.000",
#         "low": "4854.000",
#         "open": "4854.000",
#         "volume": "2270",
#         "wave": 0
#     },
#     {
#         "close": "4862.000",
#         "ctm": "1726725060",
#         "ctmfmt": "2024-09-19 13:51:00",
#         "high": "4862.000",
#         "low": "4856.000",
#         "open": "4856.000",
#         "volume": "1341",
#         "wave": 0
#     },
#     {
#         "close": "4854.000",
#         "ctm": "1726725120",
#         "ctmfmt": "2024-09-19 13:52:00",
#         "high": "4856.000",
#         "low": "4854.000",
#         "open": "4854.000",
#         "volume": "1320",
#         "wave": 0
#     },
#     {
#         "close": "4852.000",
#         "ctm": "1726725180",
#         "ctmfmt": "2024-09-19 13:53:00",
#         "high": "4854.000",
#         "low": "4852.000",
#         "open": "4854.000",
#         "volume": "153",
#         "wave": 0
#     },
#     {
#         "close": "4856.000",
#         "ctm": "1726725240",
#         "ctmfmt": "2024-09-19 13:54:00",
#         "high": "4856.000",
#         "low": "4854.000",
#         "open": "4854.000",
#         "volume": "49",
#         "wave": 0
#     },
#     {
#         "close": "4854.000",
#         "ctm": "1726725300",
#         "ctmfmt": "2024-09-19 13:55:00",
#         "high": "4858.000",
#         "low": "4854.000",
#         "open": "4856.000",
#         "volume": "1465",
#         "wave": 0
#     },
#     {
#         "close": "4856.000",
#         "ctm": "1726725360",
#         "ctmfmt": "2024-09-19 13:56:00",
#         "high": "4858.000",
#         "low": "4856.000",
#         "open": "4856.000",
#         "volume": "690",
#         "wave": 0
#     },
#     {
#         "close": "4858.000",
#         "ctm": "1726725420",
#         "ctmfmt": "2024-09-19 13:57:00",
#         "high": "4860.000",
#         "low": "4856.000",
#         "open": "4858.000",
#         "volume": "1097",
#         "wave": 0
#     },
#     {
#         "close": "4860.000",
#         "ctm": "1726725480",
#         "ctmfmt": "2024-09-19 13:58:00",
#         "high": "4860.000",
#         "low": "4858.000",
#         "open": "4860.000",
#         "volume": "404",
#         "wave": 0
#     },
#     {
#         "close": "4862.000",
#         "ctm": "1726725540",
#         "ctmfmt": "2024-09-19 13:59:00",
#         "high": "4862.000",
#         "low": "4858.000",
#         "open": "4860.000",
#         "volume": "1163",
#         "wave": 0
#     },
#     {
#         "close": "4860.000",
#         "ctm": "1726725600",
#         "ctmfmt": "2024-09-19 14:00:00",
#         "high": "4862.000",
#         "low": "4858.000",
#         "open": "4862.000",
#         "volume": "817",
#         "wave": 0
#     },
#     {
#         "close": "4864.000",
#         "ctm": "1726725660",
#         "ctmfmt": "2024-09-19 14:01:00",
#         "high": "4864.000",
#         "low": "4860.000",
#         "open": "4862.000",
#         "volume": "1997",
#         "wave": 0
#     },
#     {
#         "close": "4868.000",
#         "ctm": "1726725720",
#         "ctmfmt": "2024-09-19 14:02:00",
#         "high": "4868.000",
#         "low": "4864.000",
#         "open": "4864.000",
#         "volume": "1636",
#         "wave": 0
#     },
#     {
#         "close": "4862.000",
#         "ctm": "1726725780",
#         "ctmfmt": "2024-09-19 14:03:00",
#         "high": "4866.000",
#         "low": "4862.000",
#         "open": "4866.000",
#         "volume": "573",
#         "wave": 0
#     },
#     {
#         "close": "4864.000",
#         "ctm": "1726725840",
#         "ctmfmt": "2024-09-19 14:04:00",
#         "high": "4864.000",
#         "low": "4860.000",
#         "open": "4862.000",
#         "volume": "1125",
#         "wave": 0
#     },
#     {
#         "close": "4862.000",
#         "ctm": "1726725900",
#         "ctmfmt": "2024-09-19 14:05:00",
#         "high": "4864.000",
#         "low": "4860.000",
#         "open": "4864.000",
#         "volume": "482",
#         "wave": 0
#     },
#     {
#         "close": "4864.000",
#         "ctm": "1726725960",
#         "ctmfmt": "2024-09-19 14:06:00",
#         "high": "4864.000",
#         "low": "4862.000",
#         "open": "4864.000",
#         "volume": "327",
#         "wave": 0
#     },
#     {
#         "close": "4870.000",
#         "ctm": "1726726020",
#         "ctmfmt": "2024-09-19 14:07:00",
#         "high": "4870.000",
#         "low": "4866.000",
#         "open": "4866.000",
#         "volume": "437",
#         "wave": 0
#     },
#     {
#         "close": "4874.000",
#         "ctm": "1726726080",
#         "ctmfmt": "2024-09-19 14:08:00",
#         "high": "4874.000",
#         "low": "4868.000",
#         "open": "4870.000",
#         "volume": "6523",
#         "wave": 0
#     },
#     {
#         "close": "4872.000",
#         "ctm": "1726726140",
#         "ctmfmt": "2024-09-19 14:09:00",
#         "high": "4874.000",
#         "low": "4870.000",
#         "open": "4872.000",
#         "volume": "3096",
#         "wave": 0
#     },
#     {
#         "close": "4868.000",
#         "ctm": "1726726200",
#         "ctmfmt": "2024-09-19 14:10:00",
#         "high": "4868.000",
#         "low": "4868.000",
#         "open": "4868.000",
#         "volume": "10",
#         "wave": 0
#     },
#     {
#         "close": "4864.000",
#         "ctm": "1726726260",
#         "ctmfmt": "2024-09-19 14:11:00",
#         "high": "4866.000",
#         "low": "4864.000",
#         "open": "4866.000",
#         "volume": "1812",
#         "wave": 0
#     },
#     {
#         "close": "4862.000",
#         "ctm": "1726726320",
#         "ctmfmt": "2024-09-19 14:12:00",
#         "high": "4866.000",
#         "low": "4862.000",
#         "open": "4866.000",
#         "volume": "2250",
#         "wave": 0
#     },
#     {
#         "close": "4866.000",
#         "ctm": "1726726380",
#         "ctmfmt": "2024-09-19 14:13:00",
#         "high": "4866.000",
#         "low": "4864.000",
#         "open": "4866.000",
#         "volume": "1261",
#         "wave": 0
#     },
#     {
#         "close": "4868.000",
#         "ctm": "1726726440",
#         "ctmfmt": "2024-09-19 14:14:00",
#         "high": "4870.000",
#         "low": "4868.000",
#         "open": "4870.000",
#         "volume": "1143",
#         "wave": 0
#     },
#     {
#         "close": "4872.000",
#         "ctm": "1726726500",
#         "ctmfmt": "2024-09-19 14:15:00",
#         "high": "4872.000",
#         "low": "4870.000",
#         "open": "4872.000",
#         "volume": "477",
#         "wave": 0
#     },
#     {
#         "close": "4878.000",
#         "ctm": "1726726560",
#         "ctmfmt": "2024-09-19 14:16:00",
#         "high": "4878.000",
#         "low": "4876.000",
#         "open": "4876.000",
#         "volume": "1488",
#         "wave": 0
#     },
#     {
#         "close": "4870.000",
#         "ctm": "1726726620",
#         "ctmfmt": "2024-09-19 14:17:00",
#         "high": "4872.000",
#         "low": "4870.000",
#         "open": "4870.000",
#         "volume": "122",
#         "wave": 0
#     },
#     {
#         "close": "4868.000",
#         "ctm": "1726726680",
#         "ctmfmt": "2024-09-19 14:18:00",
#         "high": "4870.000",
#         "low": "4866.000",
#         "open": "4870.000",
#         "volume": "1332",
#         "wave": 0
#     },
#     {
#         "close": "4868.000",
#         "ctm": "1726726740",
#         "ctmfmt": "2024-09-19 14:19:00",
#         "high": "4868.000",
#         "low": "4868.000",
#         "open": "4868.000",
#         "volume": "6",
#         "wave": 0
#     },
#     {
#         "close": "4870.000",
#         "ctm": "1726726800",
#         "ctmfmt": "2024-09-19 14:20:00",
#         "high": "4870.000",
#         "low": "4868.000",
#         "open": "4868.000",
#         "volume": "332",
#         "wave": 0
#     },
#     {
#         "close": "4876.000",
#         "ctm": "1726726860",
#         "ctmfmt": "2024-09-19 14:21:00",
#         "high": "4876.000",
#         "low": "4868.000",
#         "open": "4870.000",
#         "volume": "2872",
#         "wave": 0
#     },
#     {
#         "close": "4872.000",
#         "ctm": "1726726920",
#         "ctmfmt": "2024-09-19 14:22:00",
#         "high": "4874.000",
#         "low": "4872.000",
#         "open": "4874.000",
#         "volume": "2505",
#         "wave": 0
#     },
#     {
#         "close": "4872.000",
#         "ctm": "1726726980",
#         "ctmfmt": "2024-09-19 14:23:00",
#         "high": "4878.000",
#         "low": "4872.000",
#         "open": "4872.000",
#         "volume": "2110",
#         "wave": 0
#     },
#     {
#         "close": "4870.000",
#         "ctm": "1726727040",
#         "ctmfmt": "2024-09-19 14:24:00",
#         "high": "4874.000",
#         "low": "4870.000",
#         "open": "4874.000",
#         "volume": "3433",
#         "wave": 0
#     },
#     {
#         "close": "4876.000",
#         "ctm": "1726727100",
#         "ctmfmt": "2024-09-19 14:25:00",
#         "high": "4876.000",
#         "low": "4870.000",
#         "open": "4870.000",
#         "volume": "1646",
#         "wave": 0
#     },
#     {
#         "close": "4878.000",
#         "ctm": "1726727160",
#         "ctmfmt": "2024-09-19 14:26:00",
#         "high": "4878.000",
#         "low": "4874.000",
#         "open": "4876.000",
#         "volume": "889",
#         "wave": 0
#     },
#     {
#         "close": "4874.000",
#         "ctm": "1726727220",
#         "ctmfmt": "2024-09-19 14:27:00",
#         "high": "4880.000",
#         "low": "4874.000",
#         "open": "4878.000",
#         "volume": "3579",
#         "wave": 0
#     },
#     {
#         "close": "4874.000",
#         "ctm": "1726727280",
#         "ctmfmt": "2024-09-19 14:28:00",
#         "high": "4874.000",
#         "low": "4872.000",
#         "open": "4872.000",
#         "volume": "377",
#         "wave": 0
#     },
#     {
#         "close": "4878.000",
#         "ctm": "1726727340",
#         "ctmfmt": "2024-09-19 14:29:00",
#         "high": "4878.000",
#         "low": "4876.000",
#         "open": "4876.000",
#         "volume": "243",
#         "wave": 0
#     },
#     {
#         "close": "4878.000",
#         "ctm": "1726727400",
#         "ctmfmt": "2024-09-19 14:30:00",
#         "high": "4878.000",
#         "low": "4878.000",
#         "open": "4878.000",
#         "volume": "97",
#         "wave": 0
#     },
#     {
#         "close": "4878.000",
#         "ctm": "1726727460",
#         "ctmfmt": "2024-09-19 14:31:00",
#         "high": "4880.000",
#         "low": "4878.000",
#         "open": "4878.000",
#         "volume": "349",
#         "wave": 0
#     },
#     {
#         "close": "4874.000",
#         "ctm": "1726727520",
#         "ctmfmt": "2024-09-19 14:32:00",
#         "high": "4876.000",
#         "low": "4874.000",
#         "open": "4876.000",
#         "volume": "857",
#         "wave": 0
#     },
#     {
#         "close": "4876.000",
#         "ctm": "1726727580",
#         "ctmfmt": "2024-09-19 14:33:00",
#         "high": "4876.000",
#         "low": "4876.000",
#         "open": "4876.000",
#         "volume": "69",
#         "wave": 0
#     },
#     {
#         "close": "4878.000",
#         "ctm": "1726727640",
#         "ctmfmt": "2024-09-19 14:34:00",
#         "high": "4880.000",
#         "low": "4876.000",
#         "open": "4876.000",
#         "volume": "1641",
#         "wave": 0
#     },
#     {
#         "close": "4884.000",
#         "ctm": "1726727700",
#         "ctmfmt": "2024-09-19 14:35:00",
#         "high": "4886.000",
#         "low": "4878.000",
#         "open": "4878.000",
#         "volume": "5609",
#         "wave": 0
#     },
#     {
#         "close": "4882.000",
#         "ctm": "1726727760",
#         "ctmfmt": "2024-09-19 14:36:00",
#         "high": "4886.000",
#         "low": "4880.000",
#         "open": "4884.000",
#         "volume": "3488",
#         "wave": 0
#     },
#     {
#         "close": "4880.000",
#         "ctm": "1726727820",
#         "ctmfmt": "2024-09-19 14:37:00",
#         "high": "4882.000",
#         "low": "4878.000",
#         "open": "4880.000",
#         "volume": "408",
#         "wave": 0
#     },
#     {
#         "close": "4878.000",
#         "ctm": "1726727880",
#         "ctmfmt": "2024-09-19 14:38:00",
#         "high": "4882.000",
#         "low": "4876.000",
#         "open": "4882.000",
#         "volume": "2048",
#         "wave": 0
#     },
#     {
#         "close": "4872.000",
#         "ctm": "1726727940",
#         "ctmfmt": "2024-09-19 14:39:00",
#         "high": "4878.000",
#         "low": "4870.000",
#         "open": "4876.000",
#         "volume": "2548",
#         "wave": 0
#     },
#     {
#         "close": "4876.000",
#         "ctm": "1726728000",
#         "ctmfmt": "2024-09-19 14:40:00",
#         "high": "4878.000",
#         "low": "4872.000",
#         "open": "4872.000",
#         "volume": "2329",
#         "wave": 0
#     },
#     {
#         "close": "4876.000",
#         "ctm": "1726728060",
#         "ctmfmt": "2024-09-19 14:41:00",
#         "high": "4878.000",
#         "low": "4876.000",
#         "open": "4878.000",
#         "volume": "669",
#         "wave": 0
#     },
#     {
#         "close": "4874.000",
#         "ctm": "1726728120",
#         "ctmfmt": "2024-09-19 14:42:00",
#         "high": "4876.000",
#         "low": "4874.000",
#         "open": "4874.000",
#         "volume": "62",
#         "wave": 0
#     },
#     {
#         "close": "4872.000",
#         "ctm": "1726728180",
#         "ctmfmt": "2024-09-19 14:43:00",
#         "high": "4876.000",
#         "low": "4872.000",
#         "open": "4876.000",
#         "volume": "493",
#         "wave": 0
#     },
#     {
#         "close": "4870.000",
#         "ctm": "1726728240",
#         "ctmfmt": "2024-09-19 14:44:00",
#         "high": "4872.000",
#         "low": "4868.000",
#         "open": "4872.000",
#         "volume": "3099",
#         "wave": 0
#     },
#     {
#         "close": "4874.000",
#         "ctm": "1726728300",
#         "ctmfmt": "2024-09-19 14:45:00",
#         "high": "4874.000",
#         "low": "4872.000",
#         "open": "4872.000",
#         "volume": "123",
#         "wave": 0
#     },
#     {
#         "close": "4872.000",
#         "ctm": "1726728360",
#         "ctmfmt": "2024-09-19 14:46:00",
#         "high": "4876.000",
#         "low": "4872.000",
#         "open": "4874.000",
#         "volume": "1299",
#         "wave": 0
#     },
#     {
#         "close": "4872.000",
#         "ctm": "1726728420",
#         "ctmfmt": "2024-09-19 14:47:00",
#         "high": "4874.000",
#         "low": "4870.000",
#         "open": "4874.000",
#         "volume": "1498",
#         "wave": 0
#     },
#     {
#         "close": "4874.000",
#         "ctm": "1726728480",
#         "ctmfmt": "2024-09-19 14:48:00",
#         "high": "4874.000",
#         "low": "4870.000",
#         "open": "4870.000",
#         "volume": "1399",
#         "wave": 0
#     },
#     {
#         "close": "4880.000",
#         "ctm": "1726728540",
#         "ctmfmt": "2024-09-19 14:49:00",
#         "high": "4882.000",
#         "low": "4872.000",
#         "open": "4874.000",
#         "volume": "2987",
#         "wave": 0
#     },
#     {
#         "close": "4882.000",
#         "ctm": "1726728600",
#         "ctmfmt": "2024-09-19 14:50:00",
#         "high": "4884.000",
#         "low": "4880.000",
#         "open": "4880.000",
#         "volume": "1988",
#         "wave": 0
#     },
#     {
#         "close": "4886.000",
#         "ctm": "1726728660",
#         "ctmfmt": "2024-09-19 14:51:00",
#         "high": "4888.000",
#         "low": "4882.000",
#         "open": "4882.000",
#         "volume": "6205",
#         "wave": 0
#     },
#     {
#         "close": "4886.000",
#         "ctm": "1726728720",
#         "ctmfmt": "2024-09-19 14:52:00",
#         "high": "4888.000",
#         "low": "4884.000",
#         "open": "4886.000",
#         "volume": "2434",
#         "wave": 0
#     },
#     {
#         "close": "4884.000",
#         "ctm": "1726728780",
#         "ctmfmt": "2024-09-19 14:53:00",
#         "high": "4886.000",
#         "low": "4884.000",
#         "open": "4886.000",
#         "volume": "174",
#         "wave": 0
#     },
#     {
#         "close": "4882.000",
#         "ctm": "1726728840",
#         "ctmfmt": "2024-09-19 14:54:00",
#         "high": "4882.000",
#         "low": "4882.000",
#         "open": "4882.000",
#         "volume": "586",
#         "wave": 0
#     },
#     {
#         "close": "4886.000",
#         "ctm": "1726728900",
#         "ctmfmt": "2024-09-19 14:55:00",
#         "high": "4886.000",
#         "low": "4882.000",
#         "open": "4884.000",
#         "volume": "1912",
#         "wave": 0
#     },
#     {
#         "close": "4880.000",
#         "ctm": "1726728960",
#         "ctmfmt": "2024-09-19 14:56:00",
#         "high": "4882.000",
#         "low": "4880.000",
#         "open": "4882.000",
#         "volume": "88",
#         "wave": 0
#     },
#     {
#         "close": "4884.000",
#         "ctm": "1726729020",
#         "ctmfmt": "2024-09-19 14:57:00",
#         "high": "4886.000",
#         "low": "4882.000",
#         "open": "4884.000",
#         "volume": "799",
#         "wave": 0
#     },
#     {
#         "close": "4886.000",
#         "ctm": "1726729080",
#         "ctmfmt": "2024-09-19 14:58:00",
#         "high": "4886.000",
#         "low": "4882.000",
#         "open": "4886.000",
#         "volume": "2926",
#         "wave": 0
#     },
#     {
#         "close": "4882.000",
#         "ctm": "1726729140",
#         "ctmfmt": "2024-09-19 14:59:00",
#         "high": "4888.000",
#         "low": "4882.000",
#         "open": "4884.000",
#         "volume": "3988",
#         "wave": 0
#     },
#     {
#         "close": "4882.000",
#         "ctm": "1726729200",
#         "ctmfmt": "2024-09-19 15:00:00",
#         "high": "4884.000",
#         "low": "4878.000",
#         "open": "4884.000",
#         "volume": "7788",
#         "wave": 0
#     },
#     {
#         "close": "4886.000",
#         "ctm": "1726750860",
#         "ctmfmt": "2024-09-19 21:01:00",
#         "high": "4890.000",
#         "low": "4874.000",
#         "open": "4890.000",
#         "volume": "948750",
#         "wave": 0
#     },
#     {
#         "close": "4878.000",
#         "ctm": "1726750920",
#         "ctmfmt": "2024-09-19 21:02:00",
#         "high": "4888.000",
#         "low": "4876.000",
#         "open": "4888.000",
#         "volume": "527482",
#         "wave": 0
#     },
#     {
#         "close": "4872.000",
#         "ctm": "1726750980",
#         "ctmfmt": "2024-09-19 21:03:00",
#         "high": "4878.000",
#         "low": "4870.000",
#         "open": "4876.000",
#         "volume": "431658",
#         "wave": 0
#     },
#     {
#         "close": "4878.000",
#         "ctm": "1726751040",
#         "ctmfmt": "2024-09-19 21:04:00",
#         "high": "4878.000",
#         "low": "4872.000",
#         "open": "4874.000",
#         "volume": "320032",
#         "wave": 0
#     },
#     {
#         "close": "4876.000",
#         "ctm": "1726751100",
#         "ctmfmt": "2024-09-19 21:05:00",
#         "high": "4878.000",
#         "low": "4872.000",
#         "open": "4878.000",
#         "volume": "236610",
#         "wave": 0
#     },
#     {
#         "close": "4874.000",
#         "ctm": "1726751160",
#         "ctmfmt": "2024-09-19 21:06:00",
#         "high": "4878.000",
#         "low": "4872.000",
#         "open": "4874.000",
#         "volume": "186728",
#         "wave": 0
#     },
#     {
#         "close": "4870.000",
#         "ctm": "1726751220",
#         "ctmfmt": "2024-09-19 21:07:00",
#         "high": "4876.000",
#         "low": "4866.000",
#         "open": "4876.000",
#         "volume": "288160",
#         "wave": 0
#     },
#     {
#         "close": "4872.000",
#         "ctm": "1726751280",
#         "ctmfmt": "2024-09-19 21:08:00",
#         "high": "4876.000",
#         "low": "4870.000",
#         "open": "4870.000",
#         "volume": "129224",
#         "wave": 0
#     },
#     {
#         "close": "4874.000",
#         "ctm": "1726751340",
#         "ctmfmt": "2024-09-19 21:09:00",
#         "high": "4878.000",
#         "low": "4872.000",
#         "open": "4874.000",
#         "volume": "176683",
#         "wave": 0
#     },
#     {
#         "close": "4870.000",
#         "ctm": "1726751400",
#         "ctmfmt": "2024-09-19 21:10:00",
#         "high": "4876.000",
#         "low": "4870.000",
#         "open": "4874.000",
#         "volume": "131053",
#         "wave": 0
#     },
#     {
#         "close": "4868.000",
#         "ctm": "1726751460",
#         "ctmfmt": "2024-09-19 21:11:00",
#         "high": "4874.000",
#         "low": "4866.000",
#         "open": "4870.000",
#         "volume": "188125",
#         "wave": 0
#     },
#     {
#         "close": "4866.000",
#         "ctm": "1726751520",
#         "ctmfmt": "2024-09-19 21:12:00",
#         "high": "4868.000",
#         "low": "4864.000",
#         "open": "4868.000",
#         "volume": "284246",
#         "wave": 0
#     },
#     {
#         "close": "4870.000",
#         "ctm": "1726751580",
#         "ctmfmt": "2024-09-19 21:13:00",
#         "high": "4870.000",
#         "low": "4866.000",
#         "open": "4866.000",
#         "volume": "123698",
#         "wave": 0
#     },
#     {
#         "close": "4868.000",
#         "ctm": "1726751640",
#         "ctmfmt": "2024-09-19 21:14:00",
#         "high": "4870.000",
#         "low": "4866.000",
#         "open": "4868.000",
#         "volume": "126791",
#         "wave": 0
#     },
#     {
#         "close": "4868.000",
#         "ctm": "1726751700",
#         "ctmfmt": "2024-09-19 21:15:00",
#         "high": "4870.000",
#         "low": "4864.000",
#         "open": "4870.000",
#         "volume": "93553",
#         "wave": 0
#     },
#     {
#         "close": "4856.000",
#         "ctm": "1726751760",
#         "ctmfmt": "2024-09-19 21:16:00",
#         "high": "4868.000",
#         "low": "4856.000",
#         "open": "4866.000",
#         "volume": "421291",
#         "wave": 0
#     },
#     {
#         "close": "4860.000",
#         "ctm": "1726751820",
#         "ctmfmt": "2024-09-19 21:17:00",
#         "high": "4862.000",
#         "low": "4858.000",
#         "open": "4858.000",
#         "volume": "5404",
#         "wave": 0
#     },
#     {
#         "close": "4856.000",
#         "ctm": "1726751880",
#         "ctmfmt": "2024-09-19 21:18:00",
#         "high": "4860.000",
#         "low": "4854.000",
#         "open": "4860.000",
#         "volume": "195447",
#         "wave": 0
#     },
#     {
#         "close": "4854.000",
#         "ctm": "1726751940",
#         "ctmfmt": "2024-09-19 21:19:00",
#         "high": "4858.000",
#         "low": "4854.000",
#         "open": "4856.000",
#         "volume": "138471",
#         "wave": 0
#     },
#     {
#         "close": "4864.000",
#         "ctm": "1726752000",
#         "ctmfmt": "2024-09-19 21:20:00",
#         "high": "4866.000",
#         "low": "4854.000",
#         "open": "4854.000",
#         "volume": "223464",
#         "wave": 0
#     },
#     {
#         "close": "4866.000",
#         "ctm": "1726752060",
#         "ctmfmt": "2024-09-19 21:21:00",
#         "high": "4870.000",
#         "low": "4862.000",
#         "open": "4864.000",
#         "volume": "302796",
#         "wave": 0
#     },
#     {
#         "close": "4864.000",
#         "ctm": "1726752120",
#         "ctmfmt": "2024-09-19 21:22:00",
#         "high": "4866.000",
#         "low": "4860.000",
#         "open": "4864.000",
#         "volume": "96918",
#         "wave": 0
#     },
#     {
#         "close": "4858.000",
#         "ctm": "1726752180",
#         "ctmfmt": "2024-09-19 21:23:00",
#         "high": "4868.000",
#         "low": "4856.000",
#         "open": "4864.000",
#         "volume": "201706",
#         "wave": 0
#     },
#     {
#         "close": "4852.000",
#         "ctm": "1726752240",
#         "ctmfmt": "2024-09-19 21:24:00",
#         "high": "4858.000",
#         "low": "4852.000",
#         "open": "4858.000",
#         "volume": "326003",
#         "wave": 0
#     },
#     {
#         "close": "4860.000",
#         "ctm": "1726752300",
#         "ctmfmt": "2024-09-19 21:25:00",
#         "high": "4860.000",
#         "low": "4854.000",
#         "open": "4856.000",
#         "volume": "138358",
#         "wave": 0
#     },
#     {
#         "close": "4856.000",
#         "ctm": "1726752360",
#         "ctmfmt": "2024-09-19 21:26:00",
#         "high": "4862.000",
#         "low": "4856.000",
#         "open": "4858.000",
#         "volume": "106336",
#         "wave": 0
#     },
#     {
#         "close": "4854.000",
#         "ctm": "1726752420",
#         "ctmfmt": "2024-09-19 21:27:00",
#         "high": "4860.000",
#         "low": "4854.000",
#         "open": "4856.000",
#         "volume": "160286",
#         "wave": 0
#     },
#     {
#         "close": "4856.000",
#         "ctm": "1726752480",
#         "ctmfmt": "2024-09-19 21:28:00",
#         "high": "4858.000",
#         "low": "4852.000",
#         "open": "4854.000",
#         "volume": "164249",
#         "wave": 0
#     },
#     {
#         "close": "4858.000",
#         "ctm": "1726752540",
#         "ctmfmt": "2024-09-19 21:29:00",
#         "high": "4860.000",
#         "low": "4854.000",
#         "open": "4858.000",
#         "volume": "109721",
#         "wave": 0
#     },
#     {
#         "close": "4858.000",
#         "ctm": "1726752600",
#         "ctmfmt": "2024-09-19 21:30:00",
#         "high": "4862.000",
#         "low": "4856.000",
#         "open": "4858.000",
#         "volume": "107834",
#         "wave": 0
#     },
#     {
#         "close": "4858.000",
#         "ctm": "1726752660",
#         "ctmfmt": "2024-09-19 21:31:00",
#         "high": "4860.000",
#         "low": "4856.000",
#         "open": "4860.000",
#         "volume": "49946",
#         "wave": 0
#     },
#     {
#         "close": "4858.000",
#         "ctm": "1726752720",
#         "ctmfmt": "2024-09-19 21:32:00",
#         "high": "4862.000",
#         "low": "4856.000",
#         "open": "4856.000",
#         "volume": "83726",
#         "wave": 0
#     },
#     {
#         "close": "4858.000",
#         "ctm": "1726752780",
#         "ctmfmt": "2024-09-19 21:33:00",
#         "high": "4862.000",
#         "low": "4856.000",
#         "open": "4858.000",
#         "volume": "47354",
#         "wave": 0
#     },
#     {
#         "close": "4856.000",
#         "ctm": "1726752840",
#         "ctmfmt": "2024-09-19 21:34:00",
#         "high": "4858.000",
#         "low": "4852.000",
#         "open": "4858.000",
#         "volume": "125615",
#         "wave": 0
#     },
#     {
#         "close": "4854.000",
#         "ctm": "1726752900",
#         "ctmfmt": "2024-09-19 21:35:00",
#         "high": "4856.000",
#         "low": "4854.000",
#         "open": "4856.000",
#         "volume": "33428",
#         "wave": 0
#     },
#     {
#         "close": "4856.000",
#         "ctm": "1726752960",
#         "ctmfmt": "2024-09-19 21:36:00",
#         "high": "4858.000",
#         "low": "4852.000",
#         "open": "4856.000",
#         "volume": "59552",
#         "wave": 0
#     },
#     {
#         "close": "4860.000",
#         "ctm": "1726753020",
#         "ctmfmt": "2024-09-19 21:37:00",
#         "high": "4862.000",
#         "low": "4856.000",
#         "open": "4858.000",
#         "volume": "86313",
#         "wave": 0
#     },
#     {
#         "close": "4872.000",
#         "ctm": "1726753080",
#         "ctmfmt": "2024-09-19 21:38:00",
#         "high": "4872.000",
#         "low": "4858.000",
#         "open": "4860.000",
#         "volume": "254417",
#         "wave": 0
#     },
#     {
#         "close": "4870.000",
#         "ctm": "1726753140",
#         "ctmfmt": "2024-09-19 21:39:00",
#         "high": "4870.000",
#         "low": "4866.000",
#         "open": "4870.000",
#         "volume": "161457",
#         "wave": 0
#     },
#     {
#         "close": "4874.000",
#         "ctm": "1726753200",
#         "ctmfmt": "2024-09-19 21:40:00",
#         "high": "4874.000",
#         "low": "4868.000",
#         "open": "4870.000",
#         "volume": "304575",
#         "wave": 0
#     },
#     {
#         "close": "4886.000",
#         "ctm": "1726753260",
#         "ctmfmt": "2024-09-19 21:41:00",
#         "high": "4886.000",
#         "low": "4872.000",
#         "open": "4874.000",
#         "volume": "673966",
#         "wave": 0
#     },
#     {
#         "close": "4878.000",
#         "ctm": "1726753320",
#         "ctmfmt": "2024-09-19 21:42:00",
#         "high": "4886.000",
#         "low": "4878.000",
#         "open": "4886.000",
#         "volume": "138774",
#         "wave": 0
#     },
#     {
#         "close": "4876.000",
#         "ctm": "1726753380",
#         "ctmfmt": "2024-09-19 21:43:00",
#         "high": "4880.000",
#         "low": "4874.000",
#         "open": "4878.000",
#         "volume": "138811",
#         "wave": 0
#     },
#     {
#         "close": "4870.000",
#         "ctm": "1726753440",
#         "ctmfmt": "2024-09-19 21:44:00",
#         "high": "4876.000",
#         "low": "4870.000",
#         "open": "4876.000",
#         "volume": "87720",
#         "wave": 0
#     },
#     {
#         "close": "4868.000",
#         "ctm": "1726753500",
#         "ctmfmt": "2024-09-19 21:45:00",
#         "high": "4870.000",
#         "low": "4866.000",
#         "open": "4868.000",
#         "volume": "144010",
#         "wave": 0
#     },
#     {
#         "close": "4868.000",
#         "ctm": "1726753560",
#         "ctmfmt": "2024-09-19 21:46:00",
#         "high": "4870.000",
#         "low": "4868.000",
#         "open": "4868.000",
#         "volume": "78106",
#         "wave": 0
#     },
#     {
#         "close": "4874.000",
#         "ctm": "1726753620",
#         "ctmfmt": "2024-09-19 21:47:00",
#         "high": "4874.000",
#         "low": "4868.000",
#         "open": "4868.000",
#         "volume": "55547",
#         "wave": 0
#     },
#     {
#         "close": "4878.000",
#         "ctm": "1726753680",
#         "ctmfmt": "2024-09-19 21:48:00",
#         "high": "4878.000",
#         "low": "4872.000",
#         "open": "4874.000",
#         "volume": "81060",
#         "wave": 0
#     },
#     {
#         "close": "4872.000",
#         "ctm": "1726753740",
#         "ctmfmt": "2024-09-19 21:49:00",
#         "high": "4878.000",
#         "low": "4872.000",
#         "open": "4878.000",
#         "volume": "109680",
#         "wave": 0
#     },
#     {
#         "close": "4866.000",
#         "ctm": "1726753800",
#         "ctmfmt": "2024-09-19 21:50:00",
#         "high": "4874.000",
#         "low": "4864.000",
#         "open": "4872.000",
#         "volume": "167096",
#         "wave": 0
#     },
#     {
#         "close": "4864.000",
#         "ctm": "1726753860",
#         "ctmfmt": "2024-09-19 21:51:00",
#         "high": "4868.000",
#         "low": "4862.000",
#         "open": "4866.000",
#         "volume": "103184",
#         "wave": 0
#     },
#     {
#         "close": "4860.000",
#         "ctm": "1726753920",
#         "ctmfmt": "2024-09-19 21:52:00",
#         "high": "4864.000",
#         "low": "4858.000",
#         "open": "4862.000",
#         "volume": "183198",
#         "wave": 0
#     },
#     {
#         "close": "4866.000",
#         "ctm": "1726753980",
#         "ctmfmt": "2024-09-19 21:53:00",
#         "high": "4868.000",
#         "low": "4862.000",
#         "open": "4862.000",
#         "volume": "133419",
#         "wave": 0
#     },
#     {
#         "close": "4868.000",
#         "ctm": "1726754040",
#         "ctmfmt": "2024-09-19 21:54:00",
#         "high": "4870.000",
#         "low": "4864.000",
#         "open": "4866.000",
#         "volume": "110640",
#         "wave": 0
#     },
#     {
#         "close": "4868.000",
#         "ctm": "1726754100",
#         "ctmfmt": "2024-09-19 21:55:00",
#         "high": "4872.000",
#         "low": "4866.000",
#         "open": "4868.000",
#         "volume": "87881",
#         "wave": 0
#     },
#     {
#         "close": "4870.000",
#         "ctm": "1726754160",
#         "ctmfmt": "2024-09-19 21:56:00",
#         "high": "4870.000",
#         "low": "4866.000",
#         "open": "4868.000",
#         "volume": "99778",
#         "wave": 0
#     },
#     {
#         "close": "4874.000",
#         "ctm": "1726754220",
#         "ctmfmt": "2024-09-19 21:57:00",
#         "high": "4876.000",
#         "low": "4870.000",
#         "open": "4870.000",
#         "volume": "113783",
#         "wave": 0
#     },
#     {
#         "close": "4870.000",
#         "ctm": "1726754280",
#         "ctmfmt": "2024-09-19 21:58:00",
#         "high": "4874.000",
#         "low": "4868.000",
#         "open": "4874.000",
#         "volume": "75170",
#         "wave": 0
#     },
#     {
#         "close": "4868.000",
#         "ctm": "1726754340",
#         "ctmfmt": "2024-09-19 21:59:00",
#         "high": "4872.000",
#         "low": "4868.000",
#         "open": "4870.000",
#         "volume": "57974",
#         "wave": 0
#     },
#     {
#         "close": "4868.000",
#         "ctm": "1726754400",
#         "ctmfmt": "2024-09-19 22:00:00",
#         "high": "4870.000",
#         "low": "4866.000",
#         "open": "4868.000",
#         "volume": "67260",
#         "wave": 0
#     },
#     {
#         "close": "4870.000",
#         "ctm": "1726754460",
#         "ctmfmt": "2024-09-19 22:01:00",
#         "high": "4872.000",
#         "low": "4866.000",
#         "open": "4866.000",
#         "volume": "106849",
#         "wave": 0
#     },
#     {
#         "close": "4870.000",
#         "ctm": "1726754520",
#         "ctmfmt": "2024-09-19 22:02:00",
#         "high": "4872.000",
#         "low": "4866.000",
#         "open": "4870.000",
#         "volume": "73328",
#         "wave": 0
#     },
#     {
#         "close": "4866.000",
#         "ctm": "1726754580",
#         "ctmfmt": "2024-09-19 22:03:00",
#         "high": "4870.000",
#         "low": "4864.000",
#         "open": "4870.000",
#         "volume": "108087",
#         "wave": 0
#     },
#     {
#         "close": "4872.000",
#         "ctm": "1726754640",
#         "ctmfmt": "2024-09-19 22:04:00",
#         "high": "4872.000",
#         "low": "4866.000",
#         "open": "4866.000",
#         "volume": "60464",
#         "wave": 0
#     },
#     {
#         "close": "4878.000",
#         "ctm": "1726754700",
#         "ctmfmt": "2024-09-19 22:05:00",
#         "high": "4878.000",
#         "low": "4872.000",
#         "open": "4872.000",
#         "volume": "115465",
#         "wave": 0
#     },
#     {
#         "close": "4872.000",
#         "ctm": "1726754760",
#         "ctmfmt": "2024-09-19 22:06:00",
#         "high": "4878.000",
#         "low": "4872.000",
#         "open": "4878.000",
#         "volume": "148866",
#         "wave": 0
#     },
#     {
#         "close": "4872.000",
#         "ctm": "1726754820",
#         "ctmfmt": "2024-09-19 22:07:00",
#         "high": "4874.000",
#         "low": "4870.000",
#         "open": "4872.000",
#         "volume": "33395",
#         "wave": 0
#     },
#     {
#         "close": "4874.000",
#         "ctm": "1726754880",
#         "ctmfmt": "2024-09-19 22:08:00",
#         "high": "4878.000",
#         "low": "4872.000",
#         "open": "4872.000",
#         "volume": "63969",
#         "wave": 0
#     },
#     {
#         "close": "4876.000",
#         "ctm": "1726754940",
#         "ctmfmt": "2024-09-19 22:09:00",
#         "high": "4878.000",
#         "low": "4872.000",
#         "open": "4872.000",
#         "volume": "79504",
#         "wave": 0
#     },
#     {
#         "close": "4876.000",
#         "ctm": "1726755000",
#         "ctmfmt": "2024-09-19 22:10:00",
#         "high": "4878.000",
#         "low": "4874.000",
#         "open": "4874.000",
#         "volume": "50984",
#         "wave": 0
#     },
#     {
#         "close": "4872.000",
#         "ctm": "1726755060",
#         "ctmfmt": "2024-09-19 22:11:00",
#         "high": "4876.000",
#         "low": "4872.000",
#         "open": "4874.000",
#         "volume": "68034",
#         "wave": 0
#     },
#     {
#         "close": "4874.000",
#         "ctm": "1726755120",
#         "ctmfmt": "2024-09-19 22:12:00",
#         "high": "4876.000",
#         "low": "4872.000",
#         "open": "4872.000",
#         "volume": "27441",
#         "wave": 0
#     },
#     {
#         "close": "4876.000",
#         "ctm": "1726755180",
#         "ctmfmt": "2024-09-19 22:13:00",
#         "high": "4878.000",
#         "low": "4872.000",
#         "open": "4872.000",
#         "volume": "26378",
#         "wave": 0
#     },
#     {
#         "close": "4874.000",
#         "ctm": "1726755240",
#         "ctmfmt": "2024-09-19 22:14:00",
#         "high": "4876.000",
#         "low": "4872.000",
#         "open": "4876.000",
#         "volume": "25641",
#         "wave": 0
#     },
#     {
#         "close": "4874.000",
#         "ctm": "1726755300",
#         "ctmfmt": "2024-09-19 22:15:00",
#         "high": "4876.000",
#         "low": "4872.000",
#         "open": "4874.000",
#         "volume": "46512",
#         "wave": 0
#     },
#     {
#         "close": "4878.000",
#         "ctm": "1726755360",
#         "ctmfmt": "2024-09-19 22:16:00",
#         "high": "4878.000",
#         "low": "4872.000",
#         "open": "4874.000",
#         "volume": "54483",
#         "wave": 0
#     },
#     {
#         "close": "4870.000",
#         "ctm": "1726755420",
#         "ctmfmt": "2024-09-19 22:17:00",
#         "high": "4878.000",
#         "low": "4870.000",
#         "open": "4878.000",
#         "volume": "113078",
#         "wave": 0
#     },
#     {
#         "close": "4876.000",
#         "ctm": "1726755480",
#         "ctmfmt": "2024-09-19 22:18:00",
#         "high": "4876.000",
#         "low": "4870.000",
#         "open": "4870.000",
#         "volume": "76257",
#         "wave": 0
#     },
#     {
#         "close": "4878.000",
#         "ctm": "1726755540",
#         "ctmfmt": "2024-09-19 22:19:00",
#         "high": "4878.000",
#         "low": "4874.000",
#         "open": "4876.000",
#         "volume": "48063",
#         "wave": 0
#     },
#     {
#         "close": "4884.000",
#         "ctm": "1726755600",
#         "ctmfmt": "2024-09-19 22:20:00",
#         "high": "4886.000",
#         "low": "4876.000",
#         "open": "4878.000",
#         "volume": "169006",
#         "wave": 0
#     },
#     {
#         "close": "4882.000",
#         "ctm": "1726755660",
#         "ctmfmt": "2024-09-19 22:21:00",
#         "high": "4886.000",
#         "low": "4880.000",
#         "open": "4884.000",
#         "volume": "131328",
#         "wave": 0
#     },
#     {
#         "close": "4880.000",
#         "ctm": "1726755720",
#         "ctmfmt": "2024-09-19 22:22:00",
#         "high": "4884.000",
#         "low": "4878.000",
#         "open": "4882.000",
#         "volume": "74612",
#         "wave": 0
#     },
#     {
#         "close": "4878.000",
#         "ctm": "1726755780",
#         "ctmfmt": "2024-09-19 22:23:00",
#         "high": "4882.000",
#         "low": "4878.000",
#         "open": "4880.000",
#         "volume": "26808",
#         "wave": 0
#     },
#     {
#         "close": "4878.000",
#         "ctm": "1726755840",
#         "ctmfmt": "2024-09-19 22:24:00",
#         "high": "4878.000",
#         "low": "4876.000",
#         "open": "4878.000",
#         "volume": "26867",
#         "wave": 0
#     },
#     {
#         "close": "4878.000",
#         "ctm": "1726755900",
#         "ctmfmt": "2024-09-19 22:25:00",
#         "high": "4878.000",
#         "low": "4872.000",
#         "open": "4878.000",
#         "volume": "55471",
#         "wave": 0
#     },
#     {
#         "close": "4882.000",
#         "ctm": "1726755960",
#         "ctmfmt": "2024-09-19 22:26:00",
#         "high": "4884.000",
#         "low": "4878.000",
#         "open": "4878.000",
#         "volume": "65959",
#         "wave": 0
#     },
#     {
#         "close": "4882.000",
#         "ctm": "1726756020",
#         "ctmfmt": "2024-09-19 22:27:00",
#         "high": "4882.000",
#         "low": "4878.000",
#         "open": "4882.000",
#         "volume": "64941",
#         "wave": 0
#     },
#     {
#         "close": "4882.000",
#         "ctm": "1726756080",
#         "ctmfmt": "2024-09-19 22:28:00",
#         "high": "4884.000",
#         "low": "4880.000",
#         "open": "4882.000",
#         "volume": "46489",
#         "wave": 0
#     },
#     {
#         "close": "4876.000",
#         "ctm": "1726756140",
#         "ctmfmt": "2024-09-19 22:29:00",
#         "high": "4882.000",
#         "low": "4876.000",
#         "open": "4882.000",
#         "volume": "50650",
#         "wave": 0
#     },
#     {
#         "close": "4878.000",
#         "ctm": "1726756200",
#         "ctmfmt": "2024-09-19 22:30:00",
#         "high": "4880.000",
#         "low": "4876.000",
#         "open": "4876.000",
#         "volume": "28443",
#         "wave": 0
#     },
#     {
#         "close": "4886.000",
#         "ctm": "1726756260",
#         "ctmfmt": "2024-09-19 22:31:00",
#         "high": "4886.000",
#         "low": "4876.000",
#         "open": "4878.000",
#         "volume": "68180",
#         "wave": 0
#     },
#     {
#         "close": "4882.000",
#         "ctm": "1726756320",
#         "ctmfmt": "2024-09-19 22:32:00",
#         "high": "4886.000",
#         "low": "4880.000",
#         "open": "4886.000",
#         "volume": "43695",
#         "wave": 0
#     },
#     {
#         "close": "4882.000",
#         "ctm": "1726756380",
#         "ctmfmt": "2024-09-19 22:33:00",
#         "high": "4882.000",
#         "low": "4878.000",
#         "open": "4882.000",
#         "volume": "40210",
#         "wave": 0
#     },
#     {
#         "close": "4882.000",
#         "ctm": "1726756440",
#         "ctmfmt": "2024-09-19 22:34:00",
#         "high": "4882.000",
#         "low": "4878.000",
#         "open": "4880.000",
#         "volume": "37699",
#         "wave": 0
#     },
#     {
#         "close": "4880.000",
#         "ctm": "1726756500",
#         "ctmfmt": "2024-09-19 22:35:00",
#         "high": "4884.000",
#         "low": "4878.000",
#         "open": "4884.000",
#         "volume": "38425",
#         "wave": 0
#     },
#     {
#         "close": "4882.000",
#         "ctm": "1726756560",
#         "ctmfmt": "2024-09-19 22:36:00",
#         "high": "4884.000",
#         "low": "4878.000",
#         "open": "4880.000",
#         "volume": "35478",
#         "wave": 0
#     },
#     {
#         "close": "4876.000",
#         "ctm": "1726756620",
#         "ctmfmt": "2024-09-19 22:37:00",
#         "high": "4882.000",
#         "low": "4874.000",
#         "open": "4882.000",
#         "volume": "55718",
#         "wave": 0
#     },
#     {
#         "close": "4878.000",
#         "ctm": "1726756680",
#         "ctmfmt": "2024-09-19 22:38:00",
#         "high": "4882.000",
#         "low": "4874.000",
#         "open": "4876.000",
#         "volume": "51441",
#         "wave": 0
#     },
#     {
#         "close": "4876.000",
#         "ctm": "1726756740",
#         "ctmfmt": "2024-09-19 22:39:00",
#         "high": "4880.000",
#         "low": "4876.000",
#         "open": "4878.000",
#         "volume": "21071",
#         "wave": 0
#     },
#     {
#         "close": "4876.000",
#         "ctm": "1726756800",
#         "ctmfmt": "2024-09-19 22:40:00",
#         "high": "4882.000",
#         "low": "4876.000",
#         "open": "4876.000",
#         "volume": "42026",
#         "wave": 0
#     },
#     {
#         "close": "4876.000",
#         "ctm": "1726756860",
#         "ctmfmt": "2024-09-19 22:41:00",
#         "high": "4882.000",
#         "low": "4876.000",
#         "open": "4878.000",
#         "volume": "28593",
#         "wave": 0
#     },
#     {
#         "close": "4880.000",
#         "ctm": "1726756920",
#         "ctmfmt": "2024-09-19 22:42:00",
#         "high": "4880.000",
#         "low": "4876.000",
#         "open": "4876.000",
#         "volume": "33007",
#         "wave": 0
#     },
#     {
#         "close": "4874.000",
#         "ctm": "1726756980",
#         "ctmfmt": "2024-09-19 22:43:00",
#         "high": "4880.000",
#         "low": "4872.000",
#         "open": "4880.000",
#         "volume": "63376",
#         "wave": 0
#     },
#     {
#         "close": "4876.000",
#         "ctm": "1726757040",
#         "ctmfmt": "2024-09-19 22:44:00",
#         "high": "4876.000",
#         "low": "4872.000",
#         "open": "4874.000",
#         "volume": "45794",
#         "wave": 0
#     },
#     {
#         "close": "4878.000",
#         "ctm": "1726757100",
#         "ctmfmt": "2024-09-19 22:45:00",
#         "high": "4878.000",
#         "low": "4874.000",
#         "open": "4876.000",
#         "volume": "38352",
#         "wave": 0
#     },
#     {
#         "close": "4872.000",
#         "ctm": "1726757160",
#         "ctmfmt": "2024-09-19 22:46:00",
#         "high": "4878.000",
#         "low": "4870.000",
#         "open": "4876.000",
#         "volume": "90334",
#         "wave": 0
#     },
#     {
#         "close": "4868.000",
#         "ctm": "1726757220",
#         "ctmfmt": "2024-09-19 22:47:00",
#         "high": "4872.000",
#         "low": "4868.000",
#         "open": "4872.000",
#         "volume": "95629",
#         "wave": 0
#     },
#     {
#         "close": "4870.000",
#         "ctm": "1726757280",
#         "ctmfmt": "2024-09-19 22:48:00",
#         "high": "4874.000",
#         "low": "4868.000",
#         "open": "4870.000",
#         "volume": "58136",
#         "wave": 0
#     },
#     {
#         "close": "4874.000",
#         "ctm": "1726757340",
#         "ctmfmt": "2024-09-19 22:49:00",
#         "high": "4874.000",
#         "low": "4870.000",
#         "open": "4870.000",
#         "volume": "34699",
#         "wave": 0
#     },
#     {
#         "close": "4874.000",
#         "ctm": "1726757400",
#         "ctmfmt": "2024-09-19 22:50:00",
#         "high": "4876.000",
#         "low": "4872.000",
#         "open": "4874.000",
#         "volume": "54760",
#         "wave": 0
#     },
#     {
#         "close": "4878.000",
#         "ctm": "1726757460",
#         "ctmfmt": "2024-09-19 22:51:00",
#         "high": "4880.000",
#         "low": "4874.000",
#         "open": "4874.000",
#         "volume": "50387",
#         "wave": 0
#     },
#     {
#         "close": "4878.000",
#         "ctm": "1726757520",
#         "ctmfmt": "2024-09-19 22:52:00",
#         "high": "4880.000",
#         "low": "4876.000",
#         "open": "4876.000",
#         "volume": "22063",
#         "wave": 0
#     },
#     {
#         "close": "4876.000",
#         "ctm": "1726757580",
#         "ctmfmt": "2024-09-19 22:53:00",
#         "high": "4882.000",
#         "low": "4876.000",
#         "open": "4878.000",
#         "volume": "74382",
#         "wave": 0
#     },
#     {
#         "close": "4878.000",
#         "ctm": "1726757640",
#         "ctmfmt": "2024-09-19 22:54:00",
#         "high": "4880.000",
#         "low": "4876.000",
#         "open": "4876.000",
#         "volume": "36398",
#         "wave": 0
#     },
#     {
#         "close": "4878.000",
#         "ctm": "1726757700",
#         "ctmfmt": "2024-09-19 22:55:00",
#         "high": "4878.000",
#         "low": "4876.000",
#         "open": "4878.000",
#         "volume": "15977",
#         "wave": 0
#     },
#     {
#         "close": "4878.000",
#         "ctm": "1726757760",
#         "ctmfmt": "2024-09-19 22:56:00",
#         "high": "4880.000",
#         "low": "4874.000",
#         "open": "4876.000",
#         "volume": "71776",
#         "wave": 0
#     },
#     {
#         "close": "4878.000",
#         "ctm": "1726757820",
#         "ctmfmt": "2024-09-19 22:57:00",
#         "high": "4880.000",
#         "low": "4876.000",
#         "open": "4878.000",
#         "volume": "38723",
#         "wave": 0
#     },
#     {
#         "close": "4878.000",
#         "ctm": "1726757880",
#         "ctmfmt": "2024-09-19 22:58:00",
#         "high": "4880.000",
#         "low": "4876.000",
#         "open": "4878.000",
#         "volume": "42048",
#         "wave": 0
#     },
#     {
#         "close": "4882.000",
#         "ctm": "1726757940",
#         "ctmfmt": "2024-09-19 22:59:00",
#         "high": "4882.000",
#         "low": "4876.000",
#         "open": "4876.000",
#         "volume": "56690",
#         "wave": 0
#     },
#     {
#         "close": "4886.000",
#         "ctm": "1726758000",
#         "ctmfmt": "2024-09-19 23:00:00",
#         "high": "4886.000",
#         "low": "4878.000",
#         "open": "4882.000",
#         "volume": "100820",
#         "wave": 0
#     },
#     {
#         "close": "4872.000",
#         "ctm": "1726794060",
#         "ctmfmt": "2024-09-20 09:01:00",
#         "high": "4886.000",
#         "low": "4870.000",
#         "open": "4886.000",
#         "volume": "352424",
#         "wave": 0
#     },
#     {
#         "close": "4860.000",
#         "ctm": "1726794120",
#         "ctmfmt": "2024-09-20 09:02:00",
#         "high": "4872.000",
#         "low": "4858.000",
#         "open": "4872.000",
#         "volume": "322351",
#         "wave": 0
#     },
#     {
#         "close": "4856.000",
#         "ctm": "1726794180",
#         "ctmfmt": "2024-09-20 09:03:00",
#         "high": "4864.000",
#         "low": "4854.000",
#         "open": "4860.000",
#         "volume": "233475",
#         "wave": 0
#     },
#     {
#         "close": "4848.000",
#         "ctm": "1726794240",
#         "ctmfmt": "2024-09-20 09:04:00",
#         "high": "4856.000",
#         "low": "4846.000",
#         "open": "4854.000",
#         "volume": "359010",
#         "wave": 0
#     },
#     {
#         "close": "4844.000",
#         "ctm": "1726794300",
#         "ctmfmt": "2024-09-20 09:05:00",
#         "high": "4848.000",
#         "low": "4844.000",
#         "open": "4848.000",
#         "volume": "196230",
#         "wave": 0
#     },
#     {
#         "close": "4846.000",
#         "ctm": "1726794360",
#         "ctmfmt": "2024-09-20 09:06:00",
#         "high": "4852.000",
#         "low": "4844.000",
#         "open": "4844.000",
#         "volume": "164070",
#         "wave": 0
#     },
#     {
#         "close": "4840.000",
#         "ctm": "1726794420",
#         "ctmfmt": "2024-09-20 09:07:00",
#         "high": "4846.000",
#         "low": "4838.000",
#         "open": "4846.000",
#         "volume": "419672",
#         "wave": 0
#     },
#     {
#         "close": "4840.000",
#         "ctm": "1726794480",
#         "ctmfmt": "2024-09-20 09:08:00",
#         "high": "4842.000",
#         "low": "4836.000",
#         "open": "4838.000",
#         "volume": "259521",
#         "wave": 0
#     },
#     {
#         "close": "4838.000",
#         "ctm": "1726794540",
#         "ctmfmt": "2024-09-20 09:09:00",
#         "high": "4844.000",
#         "low": "4836.000",
#         "open": "4842.000",
#         "volume": "150162",
#         "wave": 0
#     },
#     {
#         "close": "4836.000",
#         "ctm": "1726794600",
#         "ctmfmt": "2024-09-20 09:10:00",
#         "high": "4838.000",
#         "low": "4832.000",
#         "open": "4836.000",
#         "volume": "375782",
#         "wave": 0
#     },
#     {
#         "close": "4832.000",
#         "ctm": "1726794660",
#         "ctmfmt": "2024-09-20 09:11:00",
#         "high": "4838.000",
#         "low": "4826.000",
#         "open": "4836.000",
#         "volume": "289853",
#         "wave": 0
#     },
#     {
#         "close": "4826.000",
#         "ctm": "1726794720",
#         "ctmfmt": "2024-09-20 09:12:00",
#         "high": "4830.000",
#         "low": "4824.000",
#         "open": "4830.000",
#         "volume": "274874",
#         "wave": 0
#     },
#     {
#         "close": "4832.000",
#         "ctm": "1726794780",
#         "ctmfmt": "2024-09-20 09:13:00",
#         "high": "4834.000",
#         "low": "4828.000",
#         "open": "4828.000",
#         "volume": "258496",
#         "wave": 0
#     },
#     {
#         "close": "4834.000",
#         "ctm": "1726794840",
#         "ctmfmt": "2024-09-20 09:14:00",
#         "high": "4838.000",
#         "low": "4830.000",
#         "open": "4832.000",
#         "volume": "175511",
#         "wave": 0
#     },
#     {
#         "close": "4838.000",
#         "ctm": "1726794900",
#         "ctmfmt": "2024-09-20 09:15:00",
#         "high": "4840.000",
#         "low": "4834.000",
#         "open": "4836.000",
#         "volume": "142552",
#         "wave": 0
#     },
#     {
#         "close": "4840.000",
#         "ctm": "1726794960",
#         "ctmfmt": "2024-09-20 09:16:00",
#         "high": "4842.000",
#         "low": "4836.000",
#         "open": "4838.000",
#         "volume": "329856",
#         "wave": 0
#     },
#     {
#         "close": "4850.000",
#         "ctm": "1726795020",
#         "ctmfmt": "2024-09-20 09:17:00",
#         "high": "4850.000",
#         "low": "4840.000",
#         "open": "4840.000",
#         "volume": "6627",
#         "wave": 0
#     },
#     {
#         "close": "4842.000",
#         "ctm": "1726795080",
#         "ctmfmt": "2024-09-20 09:18:00",
#         "high": "4852.000",
#         "low": "4842.000",
#         "open": "4850.000",
#         "volume": "11896",
#         "wave": 0
#     },
#     {
#         "close": "4846.000",
#         "ctm": "1726795140",
#         "ctmfmt": "2024-09-20 09:19:00",
#         "high": "4850.000",
#         "low": "4842.000",
#         "open": "4842.000",
#         "volume": "95283",
#         "wave": 0
#     },
#     {
#         "close": "4838.000",
#         "ctm": "1726795200",
#         "ctmfmt": "2024-09-20 09:20:00",
#         "high": "4846.000",
#         "low": "4838.000",
#         "open": "4846.000",
#         "volume": "168345",
#         "wave": 0
#     },
#     {
#         "close": "4834.000",
#         "ctm": "1726795260",
#         "ctmfmt": "2024-09-20 09:21:00",
#         "high": "4842.000",
#         "low": "4834.000",
#         "open": "4838.000",
#         "volume": "99413",
#         "wave": 0
#     },
#     {
#         "close": "4836.000",
#         "ctm": "1726795320",
#         "ctmfmt": "2024-09-20 09:22:00",
#         "high": "4836.000",
#         "low": "4830.000",
#         "open": "4834.000",
#         "volume": "117599",
#         "wave": 0
#     },
#     {
#         "close": "4846.000",
#         "ctm": "1726795380",
#         "ctmfmt": "2024-09-20 09:23:00",
#         "high": "4846.000",
#         "low": "4836.000",
#         "open": "4836.000",
#         "volume": "131838",
#         "wave": 0
#     },
#     {
#         "close": "4842.000",
#         "ctm": "1726795440",
#         "ctmfmt": "2024-09-20 09:24:00",
#         "high": "4848.000",
#         "low": "4842.000",
#         "open": "4846.000",
#         "volume": "75651",
#         "wave": 0
#     },
#     {
#         "close": "4844.000",
#         "ctm": "1726795500",
#         "ctmfmt": "2024-09-20 09:25:00",
#         "high": "4846.000",
#         "low": "4842.000",
#         "open": "4842.000",
#         "volume": "78871",
#         "wave": 0
#     },
#     {
#         "close": "4846.000",
#         "ctm": "1726795560",
#         "ctmfmt": "2024-09-20 09:26:00",
#         "high": "4848.000",
#         "low": "4844.000",
#         "open": "4846.000",
#         "volume": "50960",
#         "wave": 0
#     },
#     {
#         "close": "4848.000",
#         "ctm": "1726795620",
#         "ctmfmt": "2024-09-20 09:27:00",
#         "high": "4850.000",
#         "low": "4846.000",
#         "open": "4848.000",
#         "volume": "66800",
#         "wave": 0
#     },
#     {
#         "close": "4850.000",
#         "ctm": "1726795680",
#         "ctmfmt": "2024-09-20 09:28:00",
#         "high": "4850.000",
#         "low": "4846.000",
#         "open": "4848.000",
#         "volume": "65000",
#         "wave": 0
#     },
#     {
#         "close": "4854.000",
#         "ctm": "1726795740",
#         "ctmfmt": "2024-09-20 09:29:00",
#         "high": "4858.000",
#         "low": "4850.000",
#         "open": "4850.000",
#         "volume": "164079",
#         "wave": 0
#     },
#     {
#         "close": "4850.000",
#         "ctm": "1726795800",
#         "ctmfmt": "2024-09-20 09:30:00",
#         "high": "4854.000",
#         "low": "4848.000",
#         "open": "4854.000",
#         "volume": "82170",
#         "wave": 0
#     },
#     {
#         "close": "4844.000",
#         "ctm": "1726795860",
#         "ctmfmt": "2024-09-20 09:31:00",
#         "high": "4852.000",
#         "low": "4844.000",
#         "open": "4850.000",
#         "volume": "61675",
#         "wave": 0
#     },
#     {
#         "close": "4840.000",
#         "ctm": "1726795920",
#         "ctmfmt": "2024-09-20 09:32:00",
#         "high": "4844.000",
#         "low": "4838.000",
#         "open": "4840.000",
#         "volume": "110450",
#         "wave": 0
#     },
#     {
#         "close": "4838.000",
#         "ctm": "1726795980",
#         "ctmfmt": "2024-09-20 09:33:00",
#         "high": "4840.000",
#         "low": "4836.000",
#         "open": "4840.000",
#         "volume": "81702",
#         "wave": 0
#     },
#     {
#         "close": "4844.000",
#         "ctm": "1726796040",
#         "ctmfmt": "2024-09-20 09:34:00",
#         "high": "4846.000",
#         "low": "4838.000",
#         "open": "4838.000",
#         "volume": "53304",
#         "wave": 0
#     },
#     {
#         "close": "4840.000",
#         "ctm": "1726796100",
#         "ctmfmt": "2024-09-20 09:35:00",
#         "high": "4846.000",
#         "low": "4840.000",
#         "open": "4844.000",
#         "volume": "42720",
#         "wave": 0
#     },
#     {
#         "close": "4842.000",
#         "ctm": "1726796160",
#         "ctmfmt": "2024-09-20 09:36:00",
#         "high": "4844.000",
#         "low": "4840.000",
#         "open": "4842.000",
#         "volume": "57522",
#         "wave": 0
#     },
#     {
#         "close": "4852.000",
#         "ctm": "1726796220",
#         "ctmfmt": "2024-09-20 09:37:00",
#         "high": "4852.000",
#         "low": "4840.000",
#         "open": "4842.000",
#         "volume": "49646",
#         "wave": 0
#     },
#     {
#         "close": "4844.000",
#         "ctm": "1726796280",
#         "ctmfmt": "2024-09-20 09:38:00",
#         "high": "4854.000",
#         "low": "4844.000",
#         "open": "4852.000",
#         "volume": "44574",
#         "wave": 0
#     },
#     {
#         "close": "4844.000",
#         "ctm": "1726796340",
#         "ctmfmt": "2024-09-20 09:39:00",
#         "high": "4846.000",
#         "low": "4842.000",
#         "open": "4842.000",
#         "volume": "33968",
#         "wave": 0
#     },
#     {
#         "close": "4840.000",
#         "ctm": "1726796400",
#         "ctmfmt": "2024-09-20 09:40:00",
#         "high": "4844.000",
#         "low": "4838.000",
#         "open": "4844.000",
#         "volume": "57592",
#         "wave": 0
#     },
#     {
#         "close": "4846.000",
#         "ctm": "1726796460",
#         "ctmfmt": "2024-09-20 09:41:00",
#         "high": "4846.000",
#         "low": "4840.000",
#         "open": "4840.000",
#         "volume": "46368",
#         "wave": 0
#     },
#     {
#         "close": "4844.000",
#         "ctm": "1726796520",
#         "ctmfmt": "2024-09-20 09:42:00",
#         "high": "4848.000",
#         "low": "4844.000",
#         "open": "4844.000",
#         "volume": "40636",
#         "wave": 0
#     },
#     {
#         "close": "4842.000",
#         "ctm": "1726796580",
#         "ctmfmt": "2024-09-20 09:43:00",
#         "high": "4842.000",
#         "low": "4842.000",
#         "open": "4842.000",
#         "volume": "44",
#         "wave": 0
#     },
#     {
#         "close": "4840.000",
#         "ctm": "1726796640",
#         "ctmfmt": "2024-09-20 09:44:00",
#         "high": "4842.000",
#         "low": "4840.000",
#         "open": "4842.000",
#         "volume": "23499",
#         "wave": 0
#     },
#     {
#         "close": "4840.000",
#         "ctm": "1726796700",
#         "ctmfmt": "2024-09-20 09:45:00",
#         "high": "4842.000",
#         "low": "4840.000",
#         "open": "4842.000",
#         "volume": "25894",
#         "wave": 0
#     },
#     {
#         "close": "4846.000",
#         "ctm": "1726796760",
#         "ctmfmt": "2024-09-20 09:46:00",
#         "high": "4848.000",
#         "low": "4840.000",
#         "open": "4840.000",
#         "volume": "40348",
#         "wave": 0
#     },
#     {
#         "close": "4850.000",
#         "ctm": "1726796820",
#         "ctmfmt": "2024-09-20 09:47:00",
#         "high": "4852.000",
#         "low": "4848.000",
#         "open": "4848.000",
#         "volume": "65143",
#         "wave": 0
#     },
#     {
#         "close": "4846.000",
#         "ctm": "1726796880",
#         "ctmfmt": "2024-09-20 09:48:00",
#         "high": "4850.000",
#         "low": "4846.000",
#         "open": "4848.000",
#         "volume": "14417",
#         "wave": 0
#     },
#     {
#         "close": "4850.000",
#         "ctm": "1726796940",
#         "ctmfmt": "2024-09-20 09:49:00",
#         "high": "4850.000",
#         "low": "4846.000",
#         "open": "4848.000",
#         "volume": "46746",
#         "wave": 0
#     },
#     {
#         "close": "4840.000",
#         "ctm": "1726797000",
#         "ctmfmt": "2024-09-20 09:50:00",
#         "high": "4854.000",
#         "low": "4840.000",
#         "open": "4852.000",
#         "volume": "138759",
#         "wave": 0
#     },
#     {
#         "close": "4842.000",
#         "ctm": "1726797060",
#         "ctmfmt": "2024-09-20 09:51:00",
#         "high": "4844.000",
#         "low": "4840.000",
#         "open": "4842.000",
#         "volume": "25924",
#         "wave": 0
#     },
#     {
#         "close": "4840.000",
#         "ctm": "1726797120",
#         "ctmfmt": "2024-09-20 09:52:00",
#         "high": "4842.000",
#         "low": "4838.000",
#         "open": "4842.000",
#         "volume": "53558",
#         "wave": 0
#     },
#     {
#         "close": "4832.000",
#         "ctm": "1726797180",
#         "ctmfmt": "2024-09-20 09:53:00",
#         "high": "4838.000",
#         "low": "4832.000",
#         "open": "4838.000",
#         "volume": "93109",
#         "wave": 0
#     },
#     {
#         "close": "4834.000",
#         "ctm": "1726797240",
#         "ctmfmt": "2024-09-20 09:54:00",
#         "high": "4836.000",
#         "low": "4832.000",
#         "open": "4832.000",
#         "volume": "67883",
#         "wave": 0
#     },
#     {
#         "close": "4834.000",
#         "ctm": "1726797300",
#         "ctmfmt": "2024-09-20 09:55:00",
#         "high": "4838.000",
#         "low": "4832.000",
#         "open": "4836.000",
#         "volume": "27560",
#         "wave": 0
#     },
#     {
#         "close": "4834.000",
#         "ctm": "1726797360",
#         "ctmfmt": "2024-09-20 09:56:00",
#         "high": "4838.000",
#         "low": "4832.000",
#         "open": "4834.000",
#         "volume": "51668",
#         "wave": 0
#     },
#     {
#         "close": "4836.000",
#         "ctm": "1726797420",
#         "ctmfmt": "2024-09-20 09:57:00",
#         "high": "4836.000",
#         "low": "4832.000",
#         "open": "4834.000",
#         "volume": "26280",
#         "wave": 0
#     },
#     {
#         "close": "4836.000",
#         "ctm": "1726797480",
#         "ctmfmt": "2024-09-20 09:58:00",
#         "high": "4840.000",
#         "low": "4834.000",
#         "open": "4836.000",
#         "volume": "34140",
#         "wave": 0
#     },
#     {
#         "close": "4838.000",
#         "ctm": "1726797540",
#         "ctmfmt": "2024-09-20 09:59:00",
#         "high": "4838.000",
#         "low": "4834.000",
#         "open": "4836.000",
#         "volume": "13440",
#         "wave": 0
#     },
#     {
#         "close": "4830.000",
#         "ctm": "1726797600",
#         "ctmfmt": "2024-09-20 10:00:00",
#         "high": "4836.000",
#         "low": "4830.000",
#         "open": "4836.000",
#         "volume": "53979",
#         "wave": 0
#     },
#     {
#         "close": "4832.000",
#         "ctm": "1726797660",
#         "ctmfmt": "2024-09-20 10:01:00",
#         "high": "4834.000",
#         "low": "4830.000",
#         "open": "4830.000",
#         "volume": "62100",
#         "wave": 0
#     },
#     {
#         "close": "4826.000",
#         "ctm": "1726797720",
#         "ctmfmt": "2024-09-20 10:02:00",
#         "high": "4834.000",
#         "low": "4824.000",
#         "open": "4832.000",
#         "volume": "92122",
#         "wave": 0
#     },
#     {
#         "close": "4824.000",
#         "ctm": "1726797780",
#         "ctmfmt": "2024-09-20 10:03:00",
#         "high": "4826.000",
#         "low": "4820.000",
#         "open": "4824.000",
#         "volume": "124585",
#         "wave": 0
#     },
#     {
#         "close": "4824.000",
#         "ctm": "1726797840",
#         "ctmfmt": "2024-09-20 10:04:00",
#         "high": "4826.000",
#         "low": "4822.000",
#         "open": "4822.000",
#         "volume": "42845",
#         "wave": 0
#     },
#     {
#         "close": "4824.000",
#         "ctm": "1726797900",
#         "ctmfmt": "2024-09-20 10:05:00",
#         "high": "4826.000",
#         "low": "4820.000",
#         "open": "4822.000",
#         "volume": "47715",
#         "wave": 0
#     },
#     {
#         "close": "4828.000",
#         "ctm": "1726797960",
#         "ctmfmt": "2024-09-20 10:06:00",
#         "high": "4830.000",
#         "low": "4824.000",
#         "open": "4826.000",
#         "volume": "46987",
#         "wave": 0
#     },
#     {
#         "close": "4828.000",
#         "ctm": "1726798020",
#         "ctmfmt": "2024-09-20 10:07:00",
#         "high": "4828.000",
#         "low": "4826.000",
#         "open": "4826.000",
#         "volume": "42921",
#         "wave": 0
#     },
#     {
#         "close": "4828.000",
#         "ctm": "1726798080",
#         "ctmfmt": "2024-09-20 10:08:00",
#         "high": "4832.000",
#         "low": "4826.000",
#         "open": "4826.000",
#         "volume": "34105",
#         "wave": 0
#     },
#     {
#         "close": "4838.000",
#         "ctm": "1726798140",
#         "ctmfmt": "2024-09-20 10:09:00",
#         "high": "4838.000",
#         "low": "4828.000",
#         "open": "4830.000",
#         "volume": "42544",
#         "wave": 0
#     },
#     {
#         "close": "4838.000",
#         "ctm": "1726798200",
#         "ctmfmt": "2024-09-20 10:10:00",
#         "high": "4846.000",
#         "low": "4838.000",
#         "open": "4838.000",
#         "volume": "81738",
#         "wave": 0
#     },
#     {
#         "close": "4842.000",
#         "ctm": "1726798260",
#         "ctmfmt": "2024-09-20 10:11:00",
#         "high": "4844.000",
#         "low": "4836.000",
#         "open": "4840.000",
#         "volume": "28494",
#         "wave": 0
#     },
#     {
#         "close": "4848.000",
#         "ctm": "1726798320",
#         "ctmfmt": "2024-09-20 10:12:00",
#         "high": "4850.000",
#         "low": "4840.000",
#         "open": "4842.000",
#         "volume": "61848",
#         "wave": 0
#     },
#     {
#         "close": "4848.000",
#         "ctm": "1726798380",
#         "ctmfmt": "2024-09-20 10:13:00",
#         "high": "4850.000",
#         "low": "4846.000",
#         "open": "4846.000",
#         "volume": "4413",
#         "wave": 0
#     },
#     {
#         "close": "4856.000",
#         "ctm": "1726798440",
#         "ctmfmt": "2024-09-20 10:14:00",
#         "high": "4856.000",
#         "low": "4848.000",
#         "open": "4848.000",
#         "volume": "66168",
#         "wave": 0
#     },
#     {
#         "close": "4854.000",
#         "ctm": "1726798500",
#         "ctmfmt": "2024-09-20 10:15:00",
#         "high": "4856.000",
#         "low": "4852.000",
#         "open": "4856.000",
#         "volume": "49100",
#         "wave": 0
#     },
#     {
#         "close": "4866.000",
#         "ctm": "1726799460",
#         "ctmfmt": "2024-09-20 10:31:00",
#         "high": "4876.000",
#         "low": "4854.000",
#         "open": "4854.000",
#         "volume": "341281",
#         "wave": 0
#     },
#     {
#         "close": "4856.000",
#         "ctm": "1726799520",
#         "ctmfmt": "2024-09-20 10:32:00",
#         "high": "4868.000",
#         "low": "4856.000",
#         "open": "4866.000",
#         "volume": "101535",
#         "wave": 0
#     },
#     {
#         "close": "4858.000",
#         "ctm": "1726799580",
#         "ctmfmt": "2024-09-20 10:33:00",
#         "high": "4858.000",
#         "low": "4850.000",
#         "open": "4854.000",
#         "volume": "67904",
#         "wave": 0
#     },
#     {
#         "close": "4860.000",
#         "ctm": "1726799640",
#         "ctmfmt": "2024-09-20 10:34:00",
#         "high": "4860.000",
#         "low": "4856.000",
#         "open": "4858.000",
#         "volume": "23808",
#         "wave": 0
#     },
#     {
#         "close": "4862.000",
#         "ctm": "1726799700",
#         "ctmfmt": "2024-09-20 10:35:00",
#         "high": "4864.000",
#         "low": "4858.000",
#         "open": "4860.000",
#         "volume": "32400",
#         "wave": 0
#     },
#     {
#         "close": "4864.000",
#         "ctm": "1726799760",
#         "ctmfmt": "2024-09-20 10:36:00",
#         "high": "4866.000",
#         "low": "4862.000",
#         "open": "4862.000",
#         "volume": "62761",
#         "wave": 0
#     },
#     {
#         "close": "4862.000",
#         "ctm": "1726799820",
#         "ctmfmt": "2024-09-20 10:37:00",
#         "high": "4866.000",
#         "low": "4860.000",
#         "open": "4864.000",
#         "volume": "24379",
#         "wave": 0
#     },
#     {
#         "close": "4866.000",
#         "ctm": "1726799880",
#         "ctmfmt": "2024-09-20 10:38:00",
#         "high": "4866.000",
#         "low": "4858.000",
#         "open": "4860.000",
#         "volume": "34833",
#         "wave": 0
#     },
#     {
#         "close": "4860.000",
#         "ctm": "1726799940",
#         "ctmfmt": "2024-09-20 10:39:00",
#         "high": "4866.000",
#         "low": "4858.000",
#         "open": "4866.000",
#         "volume": "19178",
#         "wave": 0
#     },
#     {
#         "close": "4858.000",
#         "ctm": "1726800000",
#         "ctmfmt": "2024-09-20 10:40:00",
#         "high": "4864.000",
#         "low": "4858.000",
#         "open": "4858.000",
#         "volume": "769078",
#         "wave": 0
#     },
#     {
#         "close": "4856.000",
#         "ctm": "1726800060",
#         "ctmfmt": "2024-09-20 10:41:00",
#         "high": "4860.000",
#         "low": "4854.000",
#         "open": "4860.000",
#         "volume": "19470",
#         "wave": 0
#     },
#     {
#         "close": "4856.000",
#         "ctm": "1726800120",
#         "ctmfmt": "2024-09-20 10:42:00",
#         "high": "4860.000",
#         "low": "4854.000",
#         "open": "4856.000",
#         "volume": "28365",
#         "wave": 0
#     },
#     {
#         "close": "4856.000",
#         "ctm": "1726800180",
#         "ctmfmt": "2024-09-20 10:43:00",
#         "high": "4858.000",
#         "low": "4852.000",
#         "open": "4856.000",
#         "volume": "30090",
#         "wave": 0
#     },
#     {
#         "close": "4862.000",
#         "ctm": "1726800240",
#         "ctmfmt": "2024-09-20 10:44:00",
#         "high": "4862.000",
#         "low": "4856.000",
#         "open": "4858.000",
#         "volume": "22353",
#         "wave": 0
#     },
#     {
#         "close": "4862.000",
#         "ctm": "1726800300",
#         "ctmfmt": "2024-09-20 10:45:00",
#         "high": "4864.000",
#         "low": "4860.000",
#         "open": "4862.000",
#         "volume": "18354",
#         "wave": 0
#     },
#     {
#         "close": "4854.000",
#         "ctm": "1726800360",
#         "ctmfmt": "2024-09-20 10:46:00",
#         "high": "4862.000",
#         "low": "4852.000",
#         "open": "4860.000",
#         "volume": "36736",
#         "wave": 0
#     },
#     {
#         "close": "4854.000",
#         "ctm": "1726800420",
#         "ctmfmt": "2024-09-20 10:47:00",
#         "high": "4854.000",
#         "low": "4852.000",
#         "open": "4854.000",
#         "volume": "19544",
#         "wave": 0
#     },
#     {
#         "close": "4856.000",
#         "ctm": "1726800480",
#         "ctmfmt": "2024-09-20 10:48:00",
#         "high": "4858.000",
#         "low": "4854.000",
#         "open": "4854.000",
#         "volume": "6930",
#         "wave": 0
#     },
#     {
#         "close": "4852.000",
#         "ctm": "1726800540",
#         "ctmfmt": "2024-09-20 10:49:00",
#         "high": "4856.000",
#         "low": "4850.000",
#         "open": "4856.000",
#         "volume": "25998",
#         "wave": 0
#     },
#     {
#         "close": "4854.000",
#         "ctm": "1726800600",
#         "ctmfmt": "2024-09-20 10:50:00",
#         "high": "4856.000",
#         "low": "4852.000",
#         "open": "4854.000",
#         "volume": "23798",
#         "wave": 0
#     },
#     {
#         "close": "4854.000",
#         "ctm": "1726800660",
#         "ctmfmt": "2024-09-20 10:51:00",
#         "high": "4854.000",
#         "low": "4852.000",
#         "open": "4854.000",
#         "volume": "1365",
#         "wave": 0
#     },
#     {
#         "close": "4848.000",
#         "ctm": "1726800720",
#         "ctmfmt": "2024-09-20 10:52:00",
#         "high": "4854.000",
#         "low": "4846.000",
#         "open": "4854.000",
#         "volume": "30766",
#         "wave": 0
#     },
#     {
#         "close": "4854.000",
#         "ctm": "1726800780",
#         "ctmfmt": "2024-09-20 10:53:00",
#         "high": "4854.000",
#         "low": "4846.000",
#         "open": "4846.000",
#         "volume": "22256",
#         "wave": 0
#     },
#     {
#         "close": "4854.000",
#         "ctm": "1726800840",
#         "ctmfmt": "2024-09-20 10:54:00",
#         "high": "4860.000",
#         "low": "4852.000",
#         "open": "4854.000",
#         "volume": "21918",
#         "wave": 0
#     },
#     {
#         "close": "4852.000",
#         "ctm": "1726800900",
#         "ctmfmt": "2024-09-20 10:55:00",
#         "high": "4856.000",
#         "low": "4852.000",
#         "open": "4854.000",
#         "volume": "13065",
#         "wave": 0
#     },
#     {
#         "close": "4848.000",
#         "ctm": "1726800960",
#         "ctmfmt": "2024-09-20 10:56:00",
#         "high": "4852.000",
#         "low": "4848.000",
#         "open": "4850.000",
#         "volume": "19838",
#         "wave": 0
#     },
#     {
#         "close": "4848.000",
#         "ctm": "1726801020",
#         "ctmfmt": "2024-09-20 10:57:00",
#         "high": "4850.000",
#         "low": "4848.000",
#         "open": "4848.000",
#         "volume": "9542",
#         "wave": 0
#     },
#     {
#         "close": "4852.000",
#         "ctm": "1726801080",
#         "ctmfmt": "2024-09-20 10:58:00",
#         "high": "4852.000",
#         "low": "4846.000",
#         "open": "4848.000",
#         "volume": "25558",
#         "wave": 0
#     },
#     {
#         "close": "4850.000",
#         "ctm": "1726801140",
#         "ctmfmt": "2024-09-20 10:59:00",
#         "high": "4852.000",
#         "low": "4848.000",
#         "open": "4852.000",
#         "volume": "18135",
#         "wave": 0
#     },
#     {
#         "close": "4854.000",
#         "ctm": "1726801200",
#         "ctmfmt": "2024-09-20 11:00:00",
#         "high": "4856.000",
#         "low": "4850.000",
#         "open": "4852.000",
#         "volume": "17147",
#         "wave": 0
#     },
#     {
#         "close": "4866.000",
#         "ctm": "1726801260",
#         "ctmfmt": "2024-09-20 11:01:00",
#         "high": "4866.000",
#         "low": "4856.000",
#         "open": "4856.000",
#         "volume": "46137",
#         "wave": 0
#     },
#     {
#         "close": "4866.000",
#         "ctm": "1726801320",
#         "ctmfmt": "2024-09-20 11:02:00",
#         "high": "4870.000",
#         "low": "4862.000",
#         "open": "4864.000",
#         "volume": "77736",
#         "wave": 0
#     },
#     {
#         "close": "4864.000",
#         "ctm": "1726801380",
#         "ctmfmt": "2024-09-20 11:03:00",
#         "high": "4866.000",
#         "low": "4862.000",
#         "open": "4864.000",
#         "volume": "27913",
#         "wave": 0
#     },
#     {
#         "close": "4870.000",
#         "ctm": "1726801440",
#         "ctmfmt": "2024-09-20 11:04:00",
#         "high": "4870.000",
#         "low": "4864.000",
#         "open": "4866.000",
#         "volume": "120132",
#         "wave": 0
#     },
#     {
#         "close": "4872.000",
#         "ctm": "1726801500",
#         "ctmfmt": "2024-09-20 11:05:00",
#         "high": "4874.000",
#         "low": "4864.000",
#         "open": "4870.000",
#         "volume": "51307",
#         "wave": 0
#     },
#     {
#         "close": "4870.000",
#         "ctm": "1726801560",
#         "ctmfmt": "2024-09-20 11:06:00",
#         "high": "4876.000",
#         "low": "4868.000",
#         "open": "4872.000",
#         "volume": "118260",
#         "wave": 0
#     },
#     {
#         "close": "4866.000",
#         "ctm": "1726801620",
#         "ctmfmt": "2024-09-20 11:07:00",
#         "high": "4870.000",
#         "low": "4864.000",
#         "open": "4868.000",
#         "volume": "12756",
#         "wave": 0
#     },
#     {
#         "close": "4866.000",
#         "ctm": "1726801680",
#         "ctmfmt": "2024-09-20 11:08:00",
#         "high": "4868.000",
#         "low": "4860.000",
#         "open": "4864.000",
#         "volume": "53820",
#         "wave": 0
#     },
#     {
#         "close": "4868.000",
#         "ctm": "1726801740",
#         "ctmfmt": "2024-09-20 11:09:00",
#         "high": "4870.000",
#         "low": "4864.000",
#         "open": "4868.000",
#         "volume": "16668",
#         "wave": 0
#     },
#     {
#         "close": "4870.000",
#         "ctm": "1726801800",
#         "ctmfmt": "2024-09-20 11:10:00",
#         "high": "4872.000",
#         "low": "4868.000",
#         "open": "4870.000",
#         "volume": "14916",
#         "wave": 0
#     },
#     {
#         "close": "4874.000",
#         "ctm": "1726801860",
#         "ctmfmt": "2024-09-20 11:11:00",
#         "high": "4876.000",
#         "low": "4868.000",
#         "open": "4868.000",
#         "volume": "21285",
#         "wave": 0
#     },
#     {
#         "close": "4880.000",
#         "ctm": "1726801920",
#         "ctmfmt": "2024-09-20 11:12:00",
#         "high": "4884.000",
#         "low": "4872.000",
#         "open": "4874.000",
#         "volume": "129327",
#         "wave": 0
#     },
#     {
#         "close": "4878.000",
#         "ctm": "1726801980",
#         "ctmfmt": "2024-09-20 11:13:00",
#         "high": "4880.000",
#         "low": "4876.000",
#         "open": "4880.000",
#         "volume": "27038",
#         "wave": 0
#     },
#     {
#         "close": "4876.000",
#         "ctm": "1726802040",
#         "ctmfmt": "2024-09-20 11:14:00",
#         "high": "4878.000",
#         "low": "4874.000",
#         "open": "4876.000",
#         "volume": "25430",
#         "wave": 0
#     },
#     {
#         "close": "4874.000",
#         "ctm": "1726802100",
#         "ctmfmt": "2024-09-20 11:15:00",
#         "high": "4874.000",
#         "low": "4872.000",
#         "open": "4874.000",
#         "volume": "880",
#         "wave": 0
#     },
#     {
#         "close": "4872.000",
#         "ctm": "1726802160",
#         "ctmfmt": "2024-09-20 11:16:00",
#         "high": "4878.000",
#         "low": "4872.000",
#         "open": "4876.000",
#         "volume": "16489",
#         "wave": 0
#     },
#     {
#         "close": "4876.000",
#         "ctm": "1726802220",
#         "ctmfmt": "2024-09-20 11:17:00",
#         "high": "4876.000",
#         "low": "4872.000",
#         "open": "4874.000",
#         "volume": "5685",
#         "wave": 0
#     },
#     {
#         "close": "4888.000",
#         "ctm": "1726802280",
#         "ctmfmt": "2024-09-20 11:18:00",
#         "high": "4888.000",
#         "low": "4876.000",
#         "open": "4876.000",
#         "volume": "82900",
#         "wave": 0
#     },
#     {
#         "close": "4884.000",
#         "ctm": "1726802340",
#         "ctmfmt": "2024-09-20 11:19:00",
#         "high": "4886.000",
#         "low": "4882.000",
#         "open": "4884.000",
#         "volume": "3506",
#         "wave": 0
#     },
#     {
#         "close": "4882.000",
#         "ctm": "1726802400",
#         "ctmfmt": "2024-09-20 11:20:00",
#         "high": "4884.000",
#         "low": "4878.000",
#         "open": "4882.000",
#         "volume": "22437",
#         "wave": 0
#     },
#     {
#         "close": "4880.000",
#         "ctm": "1726802460",
#         "ctmfmt": "2024-09-20 11:21:00",
#         "high": "4882.000",
#         "low": "4878.000",
#         "open": "4880.000",
#         "volume": "12080",
#         "wave": 0
#     },
#     {
#         "close": "4882.000",
#         "ctm": "1726802520",
#         "ctmfmt": "2024-09-20 11:22:00",
#         "high": "4882.000",
#         "low": "4878.000",
#         "open": "4880.000",
#         "volume": "12830",
#         "wave": 0
#     },
#     {
#         "close": "4880.000",
#         "ctm": "1726802580",
#         "ctmfmt": "2024-09-20 11:23:00",
#         "high": "4880.000",
#         "low": "4876.000",
#         "open": "4880.000",
#         "volume": "18770",
#         "wave": 0
#     },
#     {
#         "close": "4878.000",
#         "ctm": "1726802640",
#         "ctmfmt": "2024-09-20 11:24:00",
#         "high": "4882.000",
#         "low": "4878.000",
#         "open": "4880.000",
#         "volume": "9970",
#         "wave": 0
#     },
#     {
#         "close": "4876.000",
#         "ctm": "1726802700",
#         "ctmfmt": "2024-09-20 11:25:00",
#         "high": "4880.000",
#         "low": "4874.000",
#         "open": "4880.000",
#         "volume": "10110",
#         "wave": 0
#     },
#     {
#         "close": "4874.000",
#         "ctm": "1726802760",
#         "ctmfmt": "2024-09-20 11:26:00",
#         "high": "4878.000",
#         "low": "4874.000",
#         "open": "4876.000",
#         "volume": "11192",
#         "wave": 0
#     },
#     {
#         "close": "4876.000",
#         "ctm": "1726802820",
#         "ctmfmt": "2024-09-20 11:27:00",
#         "high": "4878.000",
#         "low": "4874.000",
#         "open": "4874.000",
#         "volume": "9361",
#         "wave": 0
#     },
#     {
#         "close": "4874.000",
#         "ctm": "1726802880",
#         "ctmfmt": "2024-09-20 11:28:00",
#         "high": "4878.000",
#         "low": "4872.000",
#         "open": "4878.000",
#         "volume": "17739",
#         "wave": 0
#     },
#     {
#         "close": "4870.000",
#         "ctm": "1726802940",
#         "ctmfmt": "2024-09-20 11:29:00",
#         "high": "4876.000",
#         "low": "4870.000",
#         "open": "4874.000",
#         "volume": "31689",
#         "wave": 0
#     },
#     {
#         "close": "4870.000",
#         "ctm": "1726803000",
#         "ctmfmt": "2024-09-20 11:30:00",
#         "high": "4876.000",
#         "low": "4870.000",
#         "open": "4870.000",
#         "volume": "47415",
#         "wave": 0
#     },
#     {
#         "close": "4854.000",
#         "ctm": "1726810260",
#         "ctmfmt": "2024-09-20 13:31:00",
#         "high": "4870.000",
#         "low": "4854.000",
#         "open": "4870.000",
#         "volume": "92949",
#         "wave": 0
#     },
#     {
#         "close": "4854.000",
#         "ctm": "1726810320",
#         "ctmfmt": "2024-09-20 13:32:00",
#         "high": "4856.000",
#         "low": "4850.000",
#         "open": "4856.000",
#         "volume": "42781",
#         "wave": 0
#     },
#     {
#         "close": "4852.000",
#         "ctm": "1726810380",
#         "ctmfmt": "2024-09-20 13:33:00",
#         "high": "4856.000",
#         "low": "4850.000",
#         "open": "4854.000",
#         "volume": "25774",
#         "wave": 0
#     },
#     {
#         "close": "4854.000",
#         "ctm": "1726810440",
#         "ctmfmt": "2024-09-20 13:34:00",
#         "high": "4854.000",
#         "low": "4848.000",
#         "open": "4850.000",
#         "volume": "36531",
#         "wave": 0
#     },
#     {
#         "close": "4858.000",
#         "ctm": "1726810500",
#         "ctmfmt": "2024-09-20 13:35:00",
#         "high": "4858.000",
#         "low": "4854.000",
#         "open": "4856.000",
#         "volume": "31697",
#         "wave": 0
#     },
#     {
#         "close": "4862.000",
#         "ctm": "1726810560",
#         "ctmfmt": "2024-09-20 13:36:00",
#         "high": "4864.000",
#         "low": "4858.000",
#         "open": "4858.000",
#         "volume": "26945",
#         "wave": 0
#     },
#     {
#         "close": "4860.000",
#         "ctm": "1726810620",
#         "ctmfmt": "2024-09-20 13:37:00",
#         "high": "4864.000",
#         "low": "4860.000",
#         "open": "4862.000",
#         "volume": "16409",
#         "wave": 0
#     },
#     {
#         "close": "4858.000",
#         "ctm": "1726810680",
#         "ctmfmt": "2024-09-20 13:38:00",
#         "high": "4862.000",
#         "low": "4856.000",
#         "open": "4860.000",
#         "volume": "20608",
#         "wave": 0
#     },
#     {
#         "close": "4856.000",
#         "ctm": "1726810740",
#         "ctmfmt": "2024-09-20 13:39:00",
#         "high": "4858.000",
#         "low": "4854.000",
#         "open": "4856.000",
#         "volume": "22160",
#         "wave": 0
#     },
#     {
#         "close": "4854.000",
#         "ctm": "1726810800",
#         "ctmfmt": "2024-09-20 13:40:00",
#         "high": "4860.000",
#         "low": "4852.000",
#         "open": "4858.000",
#         "volume": "42272",
#         "wave": 0
#     },
#     {
#         "close": "4852.000",
#         "ctm": "1726810860",
#         "ctmfmt": "2024-09-20 13:41:00",
#         "high": "4856.000",
#         "low": "4850.000",
#         "open": "4854.000",
#         "volume": "30942",
#         "wave": 0
#     },
#     {
#         "close": "4848.000",
#         "ctm": "1726810920",
#         "ctmfmt": "2024-09-20 13:42:00",
#         "high": "4852.000",
#         "low": "4848.000",
#         "open": "4852.000",
#         "volume": "28377",
#         "wave": 0
#     },
#     {
#         "close": "4848.000",
#         "ctm": "1726810980",
#         "ctmfmt": "2024-09-20 13:43:00",
#         "high": "4850.000",
#         "low": "4846.000",
#         "open": "4848.000",
#         "volume": "27720",
#         "wave": 0
#     },
#     {
#         "close": "4852.000",
#         "ctm": "1726811040",
#         "ctmfmt": "2024-09-20 13:44:00",
#         "high": "4854.000",
#         "low": "4848.000",
#         "open": "4850.000",
#         "volume": "18417",
#         "wave": 0
#     },
#     {
#         "close": "4854.000",
#         "ctm": "1726811100",
#         "ctmfmt": "2024-09-20 13:45:00",
#         "high": "4856.000",
#         "low": "4852.000",
#         "open": "4852.000",
#         "volume": "12859",
#         "wave": 0
#     },
#     {
#         "close": "4852.000",
#         "ctm": "1726811160",
#         "ctmfmt": "2024-09-20 13:46:00",
#         "high": "4856.000",
#         "low": "4852.000",
#         "open": "4856.000",
#         "volume": "13488",
#         "wave": 0
#     },
#     {
#         "close": "4852.000",
#         "ctm": "1726811220",
#         "ctmfmt": "2024-09-20 13:47:00",
#         "high": "4856.000",
#         "low": "4850.000",
#         "open": "4852.000",
#         "volume": "16348",
#         "wave": 0
#     },
#     {
#         "close": "4850.000",
#         "ctm": "1726811280",
#         "ctmfmt": "2024-09-20 13:48:00",
#         "high": "4852.000",
#         "low": "4850.000",
#         "open": "4852.000",
#         "volume": "4273",
#         "wave": 0
#     },
#     {
#         "close": "4850.000",
#         "ctm": "1726811340",
#         "ctmfmt": "2024-09-20 13:49:00",
#         "high": "4852.000",
#         "low": "4848.000",
#         "open": "4850.000",
#         "volume": "10509",
#         "wave": 0
#     },
#     {
#         "close": "4846.000",
#         "ctm": "1726811400",
#         "ctmfmt": "2024-09-20 13:50:00",
#         "high": "4850.000",
#         "low": "4844.000",
#         "open": "4850.000",
#         "volume": "27480",
#         "wave": 0
#     },
#     {
#         "close": "4846.000",
#         "ctm": "1726811460",
#         "ctmfmt": "2024-09-20 13:51:00",
#         "high": "4850.000",
#         "low": "4846.000",
#         "open": "4846.000",
#         "volume": "15224",
#         "wave": 0
#     },
#     {
#         "close": "4852.000",
#         "ctm": "1726811520",
#         "ctmfmt": "2024-09-20 13:52:00",
#         "high": "4852.000",
#         "low": "4846.000",
#         "open": "4846.000",
#         "volume": "10760",
#         "wave": 0
#     },
#     {
#         "close": "4856.000",
#         "ctm": "1726811580",
#         "ctmfmt": "2024-09-20 13:53:00",
#         "high": "4860.000",
#         "low": "4850.000",
#         "open": "4850.000",
#         "volume": "38456",
#         "wave": 0
#     },
#     {
#         "close": "4852.000",
#         "ctm": "1726811640",
#         "ctmfmt": "2024-09-20 13:54:00",
#         "high": "4854.000",
#         "low": "4852.000",
#         "open": "4854.000",
#         "volume": "9560",
#         "wave": 0
#     },
#     {
#         "close": "4858.000",
#         "ctm": "1726811700",
#         "ctmfmt": "2024-09-20 13:55:00",
#         "high": "4860.000",
#         "low": "4852.000",
#         "open": "4852.000",
#         "volume": "12144",
#         "wave": 0
#     },
#     {
#         "close": "4858.000",
#         "ctm": "1726811760",
#         "ctmfmt": "2024-09-20 13:56:00",
#         "high": "4860.000",
#         "low": "4856.000",
#         "open": "4860.000",
#         "volume": "6936",
#         "wave": 0
#     },
#     {
#         "close": "4868.000",
#         "ctm": "1726811820",
#         "ctmfmt": "2024-09-20 13:57:00",
#         "high": "4870.000",
#         "low": "4858.000",
#         "open": "4858.000",
#         "volume": "51062",
#         "wave": 0
#     },
#     {
#         "close": "4860.000",
#         "ctm": "1726811880",
#         "ctmfmt": "2024-09-20 13:58:00",
#         "high": "4868.000",
#         "low": "4858.000",
#         "open": "4868.000",
#         "volume": "20216",
#         "wave": 0
#     },
#     {
#         "close": "4860.000",
#         "ctm": "1726811940",
#         "ctmfmt": "2024-09-20 13:59:00",
#         "high": "4862.000",
#         "low": "4858.000",
#         "open": "4860.000",
#         "volume": "11046",
#         "wave": 0
#     },
#     {
#         "close": "4862.000",
#         "ctm": "1726812000",
#         "ctmfmt": "2024-09-20 14:00:00",
#         "high": "4862.000",
#         "low": "4856.000",
#         "open": "4858.000",
#         "volume": "9387",
#         "wave": 0
#     },
#     {
#         "close": "4860.000",
#         "ctm": "1726812060",
#         "ctmfmt": "2024-09-20 14:01:00",
#         "high": "4862.000",
#         "low": "4858.000",
#         "open": "4860.000",
#         "volume": "8526",
#         "wave": 0
#     },
#     {
#         "close": "4864.000",
#         "ctm": "1726812120",
#         "ctmfmt": "2024-09-20 14:02:00",
#         "high": "4866.000",
#         "low": "4858.000",
#         "open": "4860.000",
#         "volume": "13202",
#         "wave": 0
#     },
#     {
#         "close": "4866.000",
#         "ctm": "1726812180",
#         "ctmfmt": "2024-09-20 14:03:00",
#         "high": "4870.000",
#         "low": "4864.000",
#         "open": "4866.000",
#         "volume": "22946",
#         "wave": 0
#     },
#     {
#         "close": "4864.000",
#         "ctm": "1726812240",
#         "ctmfmt": "2024-09-20 14:04:00",
#         "high": "4866.000",
#         "low": "4860.000",
#         "open": "4864.000",
#         "volume": "10661",
#         "wave": 0
#     },
#     {
#         "close": "4866.000",
#         "ctm": "1726812300",
#         "ctmfmt": "2024-09-20 14:05:00",
#         "high": "4866.000",
#         "low": "4860.000",
#         "open": "4864.000",
#         "volume": "9463",
#         "wave": 0
#     },
#     {
#         "close": "4868.000",
#         "ctm": "1726812360",
#         "ctmfmt": "2024-09-20 14:06:00",
#         "high": "4870.000",
#         "low": "4864.000",
#         "open": "4868.000",
#         "volume": "11946",
#         "wave": 0
#     },
#     {
#         "close": "4868.000",
#         "ctm": "1726812420",
#         "ctmfmt": "2024-09-20 14:07:00",
#         "high": "4872.000",
#         "low": "4866.000",
#         "open": "4866.000",
#         "volume": "12432",
#         "wave": 0
#     },
#     {
#         "close": "4870.000",
#         "ctm": "1726812480",
#         "ctmfmt": "2024-09-20 14:08:00",
#         "high": "4872.000",
#         "low": "4868.000",
#         "open": "4870.000",
#         "volume": "9548",
#         "wave": 0
#     },
#     {
#         "close": "4870.000",
#         "ctm": "1726812540",
#         "ctmfmt": "2024-09-20 14:09:00",
#         "high": "4872.000",
#         "low": "4868.000",
#         "open": "4868.000",
#         "volume": "988744",
#         "wave": 0
#     },
#     {
#         "close": "4868.000",
#         "ctm": "1726812600",
#         "ctmfmt": "2024-09-20 14:10:00",
#         "high": "4872.000",
#         "low": "4868.000",
#         "open": "4872.000",
#         "volume": "6990",
#         "wave": 0
#     },
#     {
#         "close": "4866.000",
#         "ctm": "1726812660",
#         "ctmfmt": "2024-09-20 14:11:00",
#         "high": "4870.000",
#         "low": "4866.000",
#         "open": "4868.000",
#         "volume": "8100",
#         "wave": 0
#     },
#     {
#         "close": "4862.000",
#         "ctm": "1726812720",
#         "ctmfmt": "2024-09-20 14:12:00",
#         "high": "4866.000",
#         "low": "4862.000",
#         "open": "4866.000",
#         "volume": "8151",
#         "wave": 0
#     },
#     {
#         "close": "4862.000",
#         "ctm": "1726812780",
#         "ctmfmt": "2024-09-20 14:13:00",
#         "high": "4866.000",
#         "low": "4862.000",
#         "open": "4862.000",
#         "volume": "11678",
#         "wave": 0
#     },
#     {
#         "close": "4858.000",
#         "ctm": "1726812840",
#         "ctmfmt": "2024-09-20 14:14:00",
#         "high": "4864.000",
#         "low": "4858.000",
#         "open": "4862.000",
#         "volume": "21507",
#         "wave": 0
#     },
#     {
#         "close": "4862.000",
#         "ctm": "1726812900",
#         "ctmfmt": "2024-09-20 14:15:00",
#         "high": "4864.000",
#         "low": "4858.000",
#         "open": "4858.000",
#         "volume": "10478",
#         "wave": 0
#     },
#     {
#         "close": "4854.000",
#         "ctm": "1726812960",
#         "ctmfmt": "2024-09-20 14:16:00",
#         "high": "4856.000",
#         "low": "4852.000",
#         "open": "4854.000",
#         "volume": "27800",
#         "wave": 0
#     },
#     {
#         "close": "4850.000",
#         "ctm": "1726813020",
#         "ctmfmt": "2024-09-20 14:17:00",
#         "high": "4854.000",
#         "low": "4850.000",
#         "open": "4854.000",
#         "volume": "20253",
#         "wave": 0
#     },
#     {
#         "close": "4852.000",
#         "ctm": "1726813080",
#         "ctmfmt": "2024-09-20 14:18:00",
#         "high": "4856.000",
#         "low": "4850.000",
#         "open": "4850.000",
#         "volume": "2001",
#         "wave": 0
#     },
#     {
#         "close": "4856.000",
#         "ctm": "1726813140",
#         "ctmfmt": "2024-09-20 14:19:00",
#         "high": "4856.000",
#         "low": "4850.000",
#         "open": "4856.000",
#         "volume": "8037",
#         "wave": 0
#     },
#     {
#         "close": "4860.000",
#         "ctm": "1726813200",
#         "ctmfmt": "2024-09-20 14:20:00",
#         "high": "4860.000",
#         "low": "4854.000",
#         "open": "4856.000",
#         "volume": "7461",
#         "wave": 0
#     },
#     {
#         "close": "4862.000",
#         "ctm": "1726813260",
#         "ctmfmt": "2024-09-20 14:21:00",
#         "high": "4864.000",
#         "low": "4858.000",
#         "open": "4860.000",
#         "volume": "12110",
#         "wave": 0
#     },
#     {
#         "close": "4866.000",
#         "ctm": "1726813320",
#         "ctmfmt": "2024-09-20 14:22:00",
#         "high": "4866.000",
#         "low": "4862.000",
#         "open": "4864.000",
#         "volume": "10460",
#         "wave": 0
#     },
#     {
#         "close": "4866.000",
#         "ctm": "1726813380",
#         "ctmfmt": "2024-09-20 14:23:00",
#         "high": "4870.000",
#         "low": "4862.000",
#         "open": "4866.000",
#         "volume": "11977",
#         "wave": 0
#     },
#     {
#         "close": "4872.000",
#         "ctm": "1726813440",
#         "ctmfmt": "2024-09-20 14:24:00",
#         "high": "4872.000",
#         "low": "4866.000",
#         "open": "4868.000",
#         "volume": "13565",
#         "wave": 0
#     },
#     {
#         "close": "4876.000",
#         "ctm": "1726813500",
#         "ctmfmt": "2024-09-20 14:25:00",
#         "high": "4876.000",
#         "low": "4870.000",
#         "open": "4870.000",
#         "volume": "32335",
#         "wave": 0
#     },
#     {
#         "close": "4876.000",
#         "ctm": "1726813560",
#         "ctmfmt": "2024-09-20 14:26:00",
#         "high": "4880.000",
#         "low": "4874.000",
#         "open": "4874.000",
#         "volume": "35130",
#         "wave": 0
#     },
#     {
#         "close": "4872.000",
#         "ctm": "1726813620",
#         "ctmfmt": "2024-09-20 14:27:00",
#         "high": "4874.000",
#         "low": "4872.000",
#         "open": "4872.000",
#         "volume": "490",
#         "wave": 0
#     },
#     {
#         "close": "4872.000",
#         "ctm": "1726813680",
#         "ctmfmt": "2024-09-20 14:28:00",
#         "high": "4876.000",
#         "low": "4870.000",
#         "open": "4872.000",
#         "volume": "5593",
#         "wave": 0
#     },
#     {
#         "close": "4872.000",
#         "ctm": "1726813740",
#         "ctmfmt": "2024-09-20 14:29:00",
#         "high": "4876.000",
#         "low": "4872.000",
#         "open": "4874.000",
#         "volume": "5698",
#         "wave": 0
#     },
#     {
#         "close": "4872.000",
#         "ctm": "1726813800",
#         "ctmfmt": "2024-09-20 14:30:00",
#         "high": "4876.000",
#         "low": "4872.000",
#         "open": "4872.000",
#         "volume": "6913",
#         "wave": 0
#     },
#     {
#         "close": "4874.000",
#         "ctm": "1726813860",
#         "ctmfmt": "2024-09-20 14:31:00",
#         "high": "4876.000",
#         "low": "4872.000",
#         "open": "4876.000",
#         "volume": "3734",
#         "wave": 0
#     },
#     {
#         "close": "4876.000",
#         "ctm": "1726813920",
#         "ctmfmt": "2024-09-20 14:32:00",
#         "high": "4878.000",
#         "low": "4874.000",
#         "open": "4874.000",
#         "volume": "6224",
#         "wave": 0
#     },
#     {
#         "close": "4872.000",
#         "ctm": "1726813980",
#         "ctmfmt": "2024-09-20 14:33:00",
#         "high": "4878.000",
#         "low": "4872.000",
#         "open": "4876.000",
#         "volume": "4064",
#         "wave": 0
#     },
#     {
#         "close": "4868.000",
#         "ctm": "1726814040",
#         "ctmfmt": "2024-09-20 14:34:00",
#         "high": "4874.000",
#         "low": "4868.000",
#         "open": "4872.000",
#         "volume": "9232",
#         "wave": 0
#     },
#     {
#         "close": "4874.000",
#         "ctm": "1726814100",
#         "ctmfmt": "2024-09-20 14:35:00",
#         "high": "4874.000",
#         "low": "4868.000",
#         "open": "4868.000",
#         "volume": "7876",
#         "wave": 0
#     },
#     {
#         "close": "4866.000",
#         "ctm": "1726814160",
#         "ctmfmt": "2024-09-20 14:36:00",
#         "high": "4872.000",
#         "low": "4866.000",
#         "open": "4872.000",
#         "volume": "9984",
#         "wave": 0
#     },
#     {
#         "close": "4868.000",
#         "ctm": "1726814220",
#         "ctmfmt": "2024-09-20 14:37:00",
#         "high": "4870.000",
#         "low": "4864.000",
#         "open": "4864.000",
#         "volume": "5531",
#         "wave": 0
#     },
#     {
#         "close": "4862.000",
#         "ctm": "1726814280",
#         "ctmfmt": "2024-09-20 14:38:00",
#         "high": "4870.000",
#         "low": "4862.000",
#         "open": "4870.000",
#         "volume": "8648",
#         "wave": 0
#     },
#     {
#         "close": "4862.000",
#         "ctm": "1726814340",
#         "ctmfmt": "2024-09-20 14:39:00",
#         "high": "4864.000",
#         "low": "4860.000",
#         "open": "4864.000",
#         "volume": "6405",
#         "wave": 0
#     },
#     {
#         "close": "4868.000",
#         "ctm": "1726814400",
#         "ctmfmt": "2024-09-20 14:40:00",
#         "high": "4868.000",
#         "low": "4862.000",
#         "open": "4864.000",
#         "volume": "3894",
#         "wave": 0
#     },
#     {
#         "close": "4868.000",
#         "ctm": "1726814460",
#         "ctmfmt": "2024-09-20 14:41:00",
#         "high": "4868.000",
#         "low": "4864.000",
#         "open": "4868.000",
#         "volume": "4176",
#         "wave": 0
#     },
#     {
#         "close": "4868.000",
#         "ctm": "1726814520",
#         "ctmfmt": "2024-09-20 14:42:00",
#         "high": "4870.000",
#         "low": "4868.000",
#         "open": "4868.000",
#         "volume": "2112",
#         "wave": 0
#     },
#     {
#         "close": "4870.000",
#         "ctm": "1726814580",
#         "ctmfmt": "2024-09-20 14:43:00",
#         "high": "4870.000",
#         "low": "4866.000",
#         "open": "4870.000",
#         "volume": "3735",
#         "wave": 0
#     },
#     {
#         "close": "4872.000",
#         "ctm": "1726814640",
#         "ctmfmt": "2024-09-20 14:44:00",
#         "high": "4872.000",
#         "low": "4868.000",
#         "open": "4870.000",
#         "volume": "9900",
#         "wave": 0
#     },
#     {
#         "close": "4872.000",
#         "ctm": "1726814700",
#         "ctmfmt": "2024-09-20 14:45:00",
#         "high": "4872.000",
#         "low": "4868.000",
#         "open": "4870.000",
#         "volume": "4611",
#         "wave": 0
#     },
#     {
#         "close": "4874.000",
#         "ctm": "1726814760",
#         "ctmfmt": "2024-09-20 14:46:00",
#         "high": "4876.000",
#         "low": "4870.000",
#         "open": "4872.000",
#         "volume": "9174",
#         "wave": 0
#     },
#     {
#         "close": "4872.000",
#         "ctm": "1726814820",
#         "ctmfmt": "2024-09-20 14:47:00",
#         "high": "4876.000",
#         "low": "4870.000",
#         "open": "4874.000",
#         "volume": "4875",
#         "wave": 0
#     },
#     {
#         "close": "4872.000",
#         "ctm": "1726814880",
#         "ctmfmt": "2024-09-20 14:48:00",
#         "high": "4876.000",
#         "low": "4870.000",
#         "open": "4870.000",
#         "volume": "8403",
#         "wave": 0
#     },
#     {
#         "close": "4876.000",
#         "ctm": "1726814940",
#         "ctmfmt": "2024-09-20 14:49:00",
#         "high": "4876.000",
#         "low": "4870.000",
#         "open": "4874.000",
#         "volume": "5265",
#         "wave": 0
#     },
#     {
#         "close": "4876.000",
#         "ctm": "1726815000",
#         "ctmfmt": "2024-09-20 14:50:00",
#         "high": "4878.000",
#         "low": "4874.000",
#         "open": "4874.000",
#         "volume": "4593",
#         "wave": 0
#     },
#     {
#         "close": "4878.000",
#         "ctm": "1726815060",
#         "ctmfmt": "2024-09-20 14:51:00",
#         "high": "4880.000",
#         "low": "4874.000",
#         "open": "4876.000",
#         "volume": "3424",
#         "wave": 0
#     },
#     {
#         "close": "4880.000",
#         "ctm": "1726815120",
#         "ctmfmt": "2024-09-20 14:52:00",
#         "high": "4880.000",
#         "low": "4876.000",
#         "open": "4876.000",
#         "volume": "1980",
#         "wave": 0
#     },
#     {
#         "close": "4876.000",
#         "ctm": "1726815180",
#         "ctmfmt": "2024-09-20 14:53:00",
#         "high": "4880.000",
#         "low": "4874.000",
#         "open": "4880.000",
#         "volume": "2240",
#         "wave": 0
#     },
#     {
#         "close": "4878.000",
#         "ctm": "1726815240",
#         "ctmfmt": "2024-09-20 14:54:00",
#         "high": "4878.000",
#         "low": "4874.000",
#         "open": "4874.000",
#         "volume": "1260",
#         "wave": 0
#     },
#     {
#         "close": "4876.000",
#         "ctm": "1726815300",
#         "ctmfmt": "2024-09-20 14:55:00",
#         "high": "4878.000",
#         "low": "4874.000",
#         "open": "4876.000",
#         "volume": "4008",
#         "wave": 0
#     },
#     {
#         "close": "4876.000",
#         "ctm": "1726815360",
#         "ctmfmt": "2024-09-20 14:56:00",
#         "high": "4878.000",
#         "low": "4874.000",
#         "open": "4876.000",
#         "volume": "1506",
#         "wave": 0
#     },
#     {
#         "close": "4874.000",
#         "ctm": "1726815420",
#         "ctmfmt": "2024-09-20 14:57:00",
#         "high": "4876.000",
#         "low": "4874.000",
#         "open": "4876.000",
#         "volume": "1863",
#         "wave": 0
#     },
#     {
#         "close": "4868.000",
#         "ctm": "1726815480",
#         "ctmfmt": "2024-09-20 14:58:00",
#         "high": "4874.000",
#         "low": "4868.000",
#         "open": "4874.000",
#         "volume": "6622",
#         "wave": 0
#     },
#     {
#         "close": "4870.000",
#         "ctm": "1726815540",
#         "ctmfmt": "2024-09-20 14:59:00",
#         "high": "4872.000",
#         "low": "4868.000",
#         "open": "4870.000",
#         "volume": "4825",
#         "wave": 0
#     },
#     {
#         "close": "4866.000",
#         "ctm": "1726815600",
#         "ctmfmt": "2024-09-20 15:00:00",
#         "high": "4872.000",
#         "low": "4866.000",
#         "open": "4870.000",
#         "volume": "8715",
#         "wave": 0
#     },
#     {
#         "close": "4852.000",
#         "ctm": "1726837260",
#         "ctmfmt": "2024-09-20 21:01:00",
#         "high": "4868.000",
#         "low": "4848.000",
#         "open": "4856.000",
#         "volume": "961703",
#         "wave": 0
#     },
#     {
#         "close": "4838.000",
#         "ctm": "1726837320",
#         "ctmfmt": "2024-09-20 21:02:00",
#         "high": "4852.000",
#         "low": "4838.000",
#         "open": "4852.000",
#         "volume": "499144",
#         "wave": 0
#     },
#     {
#         "close": "4842.000",
#         "ctm": "1726837380",
#         "ctmfmt": "2024-09-20 21:03:00",
#         "high": "4842.000",
#         "low": "4830.000",
#         "open": "4836.000",
#         "volume": "443287",
#         "wave": 0
#     },
#     {
#         "close": "4838.000",
#         "ctm": "1726837440",
#         "ctmfmt": "2024-09-20 21:04:00",
#         "high": "4846.000",
#         "low": "4836.000",
#         "open": "4842.000",
#         "volume": "403144",
#         "wave": 0
#     },
#     {
#         "close": "4844.000",
#         "ctm": "1726837500",
#         "ctmfmt": "2024-09-20 21:05:00",
#         "high": "4846.000",
#         "low": "4840.000",
#         "open": "4840.000",
#         "volume": "233177",
#         "wave": 0
#     },
#     {
#         "close": "4856.000",
#         "ctm": "1726837560",
#         "ctmfmt": "2024-09-20 21:06:00",
#         "high": "4856.000",
#         "low": "4844.000",
#         "open": "4844.000",
#         "volume": "196082",
#         "wave": 0
#     },
#     {
#         "close": "4854.000",
#         "ctm": "1726837620",
#         "ctmfmt": "2024-09-20 21:07:00",
#         "high": "4858.000",
#         "low": "4852.000",
#         "open": "4856.000",
#         "volume": "195284",
#         "wave": 0
#     },
#     {
#         "close": "4852.000",
#         "ctm": "1726837680",
#         "ctmfmt": "2024-09-20 21:08:00",
#         "high": "4858.000",
#         "low": "4852.000",
#         "open": "4856.000",
#         "volume": "148606",
#         "wave": 0
#     },
#     {
#         "close": "4856.000",
#         "ctm": "1726837740",
#         "ctmfmt": "2024-09-20 21:09:00",
#         "high": "4856.000",
#         "low": "4848.000",
#         "open": "4852.000",
#         "volume": "122232",
#         "wave": 0
#     },
#     {
#         "close": "4854.000",
#         "ctm": "1726837800",
#         "ctmfmt": "2024-09-20 21:10:00",
#         "high": "4858.000",
#         "low": "4852.000",
#         "open": "4854.000",
#         "volume": "141448",
#         "wave": 0
#     },
#     {
#         "close": "4848.000",
#         "ctm": "1726837860",
#         "ctmfmt": "2024-09-20 21:11:00",
#         "high": "4856.000",
#         "low": "4848.000",
#         "open": "4856.000",
#         "volume": "160167",
#         "wave": 0
#     },
#     {
#         "close": "4852.000",
#         "ctm": "1726837920",
#         "ctmfmt": "2024-09-20 21:12:00",
#         "high": "4854.000",
#         "low": "4848.000",
#         "open": "4848.000",
#         "volume": "122743",
#         "wave": 0
#     },
#     {
#         "close": "4848.000",
#         "ctm": "1726837980",
#         "ctmfmt": "2024-09-20 21:13:00",
#         "high": "4854.000",
#         "low": "4848.000",
#         "open": "4852.000",
#         "volume": "94578",
#         "wave": 0
#     },
#     {
#         "close": "4854.000",
#         "ctm": "1726838040",
#         "ctmfmt": "2024-09-20 21:14:00",
#         "high": "4854.000",
#         "low": "4848.000",
#         "open": "4848.000",
#         "volume": "117158",
#         "wave": 0
#     },
#     {
#         "close": "4850.000",
#         "ctm": "1726838100",
#         "ctmfmt": "2024-09-20 21:15:00",
#         "high": "4854.000",
#         "low": "4850.000",
#         "open": "4854.000",
#         "volume": "200448",
#         "wave": 0
#     },
#     {
#         "close": "4848.000",
#         "ctm": "1726838160",
#         "ctmfmt": "2024-09-20 21:16:00",
#         "high": "4854.000",
#         "low": "4848.000",
#         "open": "4850.000",
#         "volume": "94961",
#         "wave": 0
#     },
#     {
#         "close": "4840.000",
#         "ctm": "1726838220",
#         "ctmfmt": "2024-09-20 21:17:00",
#         "high": "4850.000",
#         "low": "4840.000",
#         "open": "4848.000",
#         "volume": "185636",
#         "wave": 0
#     },
#     {
#         "close": "4834.000",
#         "ctm": "1726838280",
#         "ctmfmt": "2024-09-20 21:18:00",
#         "high": "4842.000",
#         "low": "4834.000",
#         "open": "4840.000",
#         "volume": "210401",
#         "wave": 0
#     },
#     {
#         "close": "4836.000",
#         "ctm": "1726838340",
#         "ctmfmt": "2024-09-20 21:19:00",
#         "high": "4838.000",
#         "low": "4832.000",
#         "open": "4836.000",
#         "volume": "163091",
#         "wave": 0
#     },
#     {
#         "close": "4836.000",
#         "ctm": "1726838400",
#         "ctmfmt": "2024-09-20 21:20:00",
#         "high": "4838.000",
#         "low": "4832.000",
#         "open": "4836.000",
#         "volume": "135860",
#         "wave": 0
#     },
#     {
#         "close": "4834.000",
#         "ctm": "1726838460",
#         "ctmfmt": "2024-09-20 21:21:00",
#         "high": "4838.000",
#         "low": "4832.000",
#         "open": "4836.000",
#         "volume": "90995",
#         "wave": 0
#     },
#     {
#         "close": "4842.000",
#         "ctm": "1726838520",
#         "ctmfmt": "2024-09-20 21:22:00",
#         "high": "4842.000",
#         "low": "4832.000",
#         "open": "4834.000",
#         "volume": "127919",
#         "wave": 0
#     },
#     {
#         "close": "4844.000",
#         "ctm": "1726838580",
#         "ctmfmt": "2024-09-20 21:23:00",
#         "high": "4848.000",
#         "low": "4842.000",
#         "open": "4842.000",
#         "volume": "161336",
#         "wave": 0
#     },
#     {
#         "close": "4836.000",
#         "ctm": "1726838640",
#         "ctmfmt": "2024-09-20 21:24:00",
#         "high": "4844.000",
#         "low": "4832.000",
#         "open": "4842.000",
#         "volume": "101539",
#         "wave": 0
#     },
#     {
#         "close": "4834.000",
#         "ctm": "1726838700",
#         "ctmfmt": "2024-09-20 21:25:00",
#         "high": "4836.000",
#         "low": "4832.000",
#         "open": "4836.000",
#         "volume": "84439",
#         "wave": 0
#     },
#     {
#         "close": "4836.000",
#         "ctm": "1726838760",
#         "ctmfmt": "2024-09-20 21:26:00",
#         "high": "4838.000",
#         "low": "4832.000",
#         "open": "4834.000",
#         "volume": "87220",
#         "wave": 0
#     },
#     {
#         "close": "4832.000",
#         "ctm": "1726838820",
#         "ctmfmt": "2024-09-20 21:27:00",
#         "high": "4836.000",
#         "low": "4832.000",
#         "open": "4836.000",
#         "volume": "101289",
#         "wave": 0
#     },
#     {
#         "close": "4834.000",
#         "ctm": "1726838880",
#         "ctmfmt": "2024-09-20 21:28:00",
#         "high": "4834.000",
#         "low": "4832.000",
#         "open": "4834.000",
#         "volume": "125187",
#         "wave": 0
#     },
#     {
#         "close": "4832.000",
#         "ctm": "1726838940",
#         "ctmfmt": "2024-09-20 21:29:00",
#         "high": "4834.000",
#         "low": "4832.000",
#         "open": "4834.000",
#         "volume": "60584",
#         "wave": 0
#     },
#     {
#         "close": "4834.000",
#         "ctm": "1726839000",
#         "ctmfmt": "2024-09-20 21:30:00",
#         "high": "4836.000",
#         "low": "4832.000",
#         "open": "4832.000",
#         "volume": "64339",
#         "wave": 0
#     },
#     {
#         "close": "4834.000",
#         "ctm": "1726839060",
#         "ctmfmt": "2024-09-20 21:31:00",
#         "high": "4836.000",
#         "low": "4832.000",
#         "open": "4834.000",
#         "volume": "82218",
#         "wave": 0
#     },
#     {
#         "close": "4832.000",
#         "ctm": "1726839120",
#         "ctmfmt": "2024-09-20 21:32:00",
#         "high": "4834.000",
#         "low": "4828.000",
#         "open": "4832.000",
#         "volume": "11312",
#         "wave": 0
#     },
#     {
#         "close": "4832.000",
#         "ctm": "1726839180",
#         "ctmfmt": "2024-09-20 21:33:00",
#         "high": "4836.000",
#         "low": "4832.000",
#         "open": "4834.000",
#         "volume": "92753",
#         "wave": 0
#     },
#     {
#         "close": "4838.000",
#         "ctm": "1726839240",
#         "ctmfmt": "2024-09-20 21:34:00",
#         "high": "4838.000",
#         "low": "4834.000",
#         "open": "4834.000",
#         "volume": "47440",
#         "wave": 0
#     },
#     {
#         "close": "4828.000",
#         "ctm": "1726839300",
#         "ctmfmt": "2024-09-20 21:35:00",
#         "high": "4836.000",
#         "low": "4828.000",
#         "open": "4836.000",
#         "volume": "90538",
#         "wave": 0
#     },
#     {
#         "close": "4830.000",
#         "ctm": "1726839360",
#         "ctmfmt": "2024-09-20 21:36:00",
#         "high": "4832.000",
#         "low": "4828.000",
#         "open": "4830.000",
#         "volume": "122146",
#         "wave": 0
#     },
#     {
#         "close": "4832.000",
#         "ctm": "1726839420",
#         "ctmfmt": "2024-09-20 21:37:00",
#         "high": "4834.000",
#         "low": "4830.000",
#         "open": "4830.000",
#         "volume": "48664",
#         "wave": 0
#     },
#     {
#         "close": "4830.000",
#         "ctm": "1726839480",
#         "ctmfmt": "2024-09-20 21:38:00",
#         "high": "4832.000",
#         "low": "4828.000",
#         "open": "4832.000",
#         "volume": "41078",
#         "wave": 0
#     },
#     {
#         "close": "4828.000",
#         "ctm": "1726839540",
#         "ctmfmt": "2024-09-20 21:39:00",
#         "high": "4830.000",
#         "low": "4826.000",
#         "open": "4830.000",
#         "volume": "96251",
#         "wave": 0
#     },
#     {
#         "close": "4828.000",
#         "ctm": "1726839600",
#         "ctmfmt": "2024-09-20 21:40:00",
#         "high": "4830.000",
#         "low": "4826.000",
#         "open": "4828.000",
#         "volume": "75911",
#         "wave": 0
#     },
#     {
#         "close": "4832.000",
#         "ctm": "1726839660",
#         "ctmfmt": "2024-09-20 21:41:00",
#         "high": "4832.000",
#         "low": "4826.000",
#         "open": "4828.000",
#         "volume": "116764",
#         "wave": 0
#     },
#     {
#         "close": "4830.000",
#         "ctm": "1726839720",
#         "ctmfmt": "2024-09-20 21:42:00",
#         "high": "4832.000",
#         "low": "4828.000",
#         "open": "4830.000",
#         "volume": "71231",
#         "wave": 0
#     },
#     {
#         "close": "4830.000",
#         "ctm": "1726839780",
#         "ctmfmt": "2024-09-20 21:43:00",
#         "high": "4832.000",
#         "low": "4828.000",
#         "open": "4830.000",
#         "volume": "36611",
#         "wave": 0
#     },
#     {
#         "close": "4824.000",
#         "ctm": "1726839840",
#         "ctmfmt": "2024-09-20 21:44:00",
#         "high": "4830.000",
#         "low": "4824.000",
#         "open": "4830.000",
#         "volume": "140581",
#         "wave": 0
#     },
#     {
#         "close": "4816.000",
#         "ctm": "1726839900",
#         "ctmfmt": "2024-09-20 21:45:00",
#         "high": "4822.000",
#         "low": "4816.000",
#         "open": "4822.000",
#         "volume": "399329",
#         "wave": 0
#     },
#     {
#         "close": "4816.000",
#         "ctm": "1726839960",
#         "ctmfmt": "2024-09-20 21:46:00",
#         "high": "4818.000",
#         "low": "4814.000",
#         "open": "4816.000",
#         "volume": "147872",
#         "wave": 0
#     },
#     {
#         "close": "4804.000",
#         "ctm": "1726840020",
#         "ctmfmt": "2024-09-20 21:47:00",
#         "high": "4816.000",
#         "low": "4804.000",
#         "open": "4816.000",
#         "volume": "342799",
#         "wave": 0
#     },
#     {
#         "close": "4804.000",
#         "ctm": "1726840080",
#         "ctmfmt": "2024-09-20 21:48:00",
#         "high": "4808.000",
#         "low": "4802.000",
#         "open": "4804.000",
#         "volume": "221255",
#         "wave": 0
#     },
#     {
#         "close": "4796.000",
#         "ctm": "1726840140",
#         "ctmfmt": "2024-09-20 21:49:00",
#         "high": "4806.000",
#         "low": "4794.000",
#         "open": "4804.000",
#         "volume": "405440",
#         "wave": 0
#     },
#     {
#         "close": "4802.000",
#         "ctm": "1726840200",
#         "ctmfmt": "2024-09-20 21:50:00",
#         "high": "4804.000",
#         "low": "4796.000",
#         "open": "4796.000",
#         "volume": "209042",
#         "wave": 0
#     },
#     {
#         "close": "4804.000",
#         "ctm": "1726840260",
#         "ctmfmt": "2024-09-20 21:51:00",
#         "high": "4806.000",
#         "low": "4798.000",
#         "open": "4804.000",
#         "volume": "118930",
#         "wave": 0
#     },
#     {
#         "close": "4804.000",
#         "ctm": "1726840320",
#         "ctmfmt": "2024-09-20 21:52:00",
#         "high": "4806.000",
#         "low": "4800.000",
#         "open": "4804.000",
#         "volume": "99782",
#         "wave": 0
#     },
#     {
#         "close": "4800.000",
#         "ctm": "1726840380",
#         "ctmfmt": "2024-09-20 21:53:00",
#         "high": "4804.000",
#         "low": "4798.000",
#         "open": "4802.000",
#         "volume": "130061",
#         "wave": 0
#     },
#     {
#         "close": "4792.000",
#         "ctm": "1726840440",
#         "ctmfmt": "2024-09-20 21:54:00",
#         "high": "4800.000",
#         "low": "4792.000",
#         "open": "4798.000",
#         "volume": "141942",
#         "wave": 0
#     },
#     {
#         "close": "4798.000",
#         "ctm": "1726840500",
#         "ctmfmt": "2024-09-20 21:55:00",
#         "high": "4800.000",
#         "low": "4792.000",
#         "open": "4792.000",
#         "volume": "86326",
#         "wave": 0
#     },
#     {
#         "close": "4796.000",
#         "ctm": "1726840560",
#         "ctmfmt": "2024-09-20 21:56:00",
#         "high": "4800.000",
#         "low": "4796.000",
#         "open": "4798.000",
#         "volume": "56137",
#         "wave": 0
#     },
#     {
#         "close": "4792.000",
#         "ctm": "1726840620",
#         "ctmfmt": "2024-09-20 21:57:00",
#         "high": "4798.000",
#         "low": "4792.000",
#         "open": "4796.000",
#         "volume": "117311",
#         "wave": 0
#     },
#     {
#         "close": "4790.000",
#         "ctm": "1726840680",
#         "ctmfmt": "2024-09-20 21:58:00",
#         "high": "4794.000",
#         "low": "4790.000",
#         "open": "4792.000",
#         "volume": "93077",
#         "wave": 0
#     },
#     {
#         "close": "4794.000",
#         "ctm": "1726840740",
#         "ctmfmt": "2024-09-20 21:59:00",
#         "high": "4796.000",
#         "low": "4790.000",
#         "open": "4790.000",
#         "volume": "91638",
#         "wave": 0
#     },
#     {
#         "close": "4788.000",
#         "ctm": "1726840800",
#         "ctmfmt": "2024-09-20 22:00:00",
#         "high": "4796.000",
#         "low": "4788.000",
#         "open": "4794.000",
#         "volume": "125460",
#         "wave": 0
#     },
#     {
#         "close": "4788.000",
#         "ctm": "1726840860",
#         "ctmfmt": "2024-09-20 22:01:00",
#         "high": "4792.000",
#         "low": "4788.000",
#         "open": "4790.000",
#         "volume": "122603",
#         "wave": 0
#     },
#     {
#         "close": "4788.000",
#         "ctm": "1726840920",
#         "ctmfmt": "2024-09-20 22:02:00",
#         "high": "4790.000",
#         "low": "4784.000",
#         "open": "4788.000",
#         "volume": "161717",
#         "wave": 0
#     },
#     {
#         "close": "4796.000",
#         "ctm": "1726840980",
#         "ctmfmt": "2024-09-20 22:03:00",
#         "high": "4798.000",
#         "low": "4788.000",
#         "open": "4790.000",
#         "volume": "185687",
#         "wave": 0
#     },
#     {
#         "close": "4780.000",
#         "ctm": "1726841040",
#         "ctmfmt": "2024-09-20 22:04:00",
#         "high": "4796.000",
#         "low": "4780.000",
#         "open": "4796.000",
#         "volume": "285593",
#         "wave": 0
#     },
#     {
#         "close": "4784.000",
#         "ctm": "1726841100",
#         "ctmfmt": "2024-09-20 22:05:00",
#         "high": "4788.000",
#         "low": "4780.000",
#         "open": "4780.000",
#         "volume": "155786",
#         "wave": 0
#     },
#     {
#         "close": "4786.000",
#         "ctm": "1726841160",
#         "ctmfmt": "2024-09-20 22:06:00",
#         "high": "4788.000",
#         "low": "4784.000",
#         "open": "4786.000",
#         "volume": "43259",
#         "wave": 0
#     },
#     {
#         "close": "4792.000",
#         "ctm": "1726841220",
#         "ctmfmt": "2024-09-20 22:07:00",
#         "high": "4794.000",
#         "low": "4784.000",
#         "open": "4786.000",
#         "volume": "114255",
#         "wave": 0
#     },
#     {
#         "close": "4792.000",
#         "ctm": "1726841280",
#         "ctmfmt": "2024-09-20 22:08:00",
#         "high": "4794.000",
#         "low": "4792.000",
#         "open": "4794.000",
#         "volume": "60255",
#         "wave": 0
#     },
#     {
#         "close": "4804.000",
#         "ctm": "1726841340",
#         "ctmfmt": "2024-09-20 22:09:00",
#         "high": "4804.000",
#         "low": "4792.000",
#         "open": "4794.000",
#         "volume": "148174",
#         "wave": 0
#     },
#     {
#         "close": "4794.000",
#         "ctm": "1726841400",
#         "ctmfmt": "2024-09-20 22:10:00",
#         "high": "4802.000",
#         "low": "4794.000",
#         "open": "4800.000",
#         "volume": "413657",
#         "wave": 0
#     },
#     {
#         "close": "4796.000",
#         "ctm": "1726841460",
#         "ctmfmt": "2024-09-20 22:11:00",
#         "high": "4802.000",
#         "low": "4794.000",
#         "open": "4794.000",
#         "volume": "81248",
#         "wave": 0
#     },
#     {
#         "close": "4798.000",
#         "ctm": "1726841520",
#         "ctmfmt": "2024-09-20 22:12:00",
#         "high": "4798.000",
#         "low": "4794.000",
#         "open": "4798.000",
#         "volume": "54735",
#         "wave": 0
#     },
#     {
#         "close": "4794.000",
#         "ctm": "1726841580",
#         "ctmfmt": "2024-09-20 22:13:00",
#         "high": "4796.000",
#         "low": "4790.000",
#         "open": "4796.000",
#         "volume": "39823",
#         "wave": 0
#     },
#     {
#         "close": "4796.000",
#         "ctm": "1726841640",
#         "ctmfmt": "2024-09-20 22:14:00",
#         "high": "4796.000",
#         "low": "4792.000",
#         "open": "4794.000",
#         "volume": "73519",
#         "wave": 0
#     },
#     {
#         "close": "4798.000",
#         "ctm": "1726841700",
#         "ctmfmt": "2024-09-20 22:15:00",
#         "high": "4800.000",
#         "low": "4796.000",
#         "open": "4796.000",
#         "volume": "33612",
#         "wave": 0
#     },
#     {
#         "close": "4798.000",
#         "ctm": "1726841760",
#         "ctmfmt": "2024-09-20 22:16:00",
#         "high": "4802.000",
#         "low": "4796.000",
#         "open": "4798.000",
#         "volume": "56144",
#         "wave": 0
#     },
#     {
#         "close": "4802.000",
#         "ctm": "1726841820",
#         "ctmfmt": "2024-09-20 22:17:00",
#         "high": "4806.000",
#         "low": "4800.000",
#         "open": "4800.000",
#         "volume": "86375",
#         "wave": 0
#     },
#     {
#         "close": "4806.000",
#         "ctm": "1726841880",
#         "ctmfmt": "2024-09-20 22:18:00",
#         "high": "4808.000",
#         "low": "4802.000",
#         "open": "4802.000",
#         "volume": "129425",
#         "wave": 0
#     },
#     {
#         "close": "4802.000",
#         "ctm": "1726841940",
#         "ctmfmt": "2024-09-20 22:19:00",
#         "high": "4806.000",
#         "low": "4802.000",
#         "open": "4806.000",
#         "volume": "98422",
#         "wave": 0
#     },
#     {
#         "close": "4800.000",
#         "ctm": "1726842000",
#         "ctmfmt": "2024-09-20 22:20:00",
#         "high": "4802.000",
#         "low": "4800.000",
#         "open": "4802.000",
#         "volume": "50084",
#         "wave": 0
#     },
#     {
#         "close": "4806.000",
#         "ctm": "1726842060",
#         "ctmfmt": "2024-09-20 22:21:00",
#         "high": "4808.000",
#         "low": "4800.000",
#         "open": "4800.000",
#         "volume": "70200",
#         "wave": 0
#     },
#     {
#         "close": "4808.000",
#         "ctm": "1726842120",
#         "ctmfmt": "2024-09-20 22:22:00",
#         "high": "4808.000",
#         "low": "4804.000",
#         "open": "4806.000",
#         "volume": "49567",
#         "wave": 0
#     },
#     {
#         "close": "4808.000",
#         "ctm": "1726842180",
#         "ctmfmt": "2024-09-20 22:23:00",
#         "high": "4812.000",
#         "low": "4806.000",
#         "open": "4808.000",
#         "volume": "108592",
#         "wave": 0
#     },
#     {
#         "close": "4806.000",
#         "ctm": "1726842240",
#         "ctmfmt": "2024-09-20 22:24:00",
#         "high": "4810.000",
#         "low": "4804.000",
#         "open": "4810.000",
#         "volume": "30744",
#         "wave": 0
#     },
#     {
#         "close": "4802.000",
#         "ctm": "1726842300",
#         "ctmfmt": "2024-09-20 22:25:00",
#         "high": "4806.000",
#         "low": "4800.000",
#         "open": "4806.000",
#         "volume": "41370",
#         "wave": 0
#     },
#     {
#         "close": "4802.000",
#         "ctm": "1726842360",
#         "ctmfmt": "2024-09-20 22:26:00",
#         "high": "4802.000",
#         "low": "4800.000",
#         "open": "4800.000",
#         "volume": "77148",
#         "wave": 0
#     },
#     {
#         "close": "4796.000",
#         "ctm": "1726842420",
#         "ctmfmt": "2024-09-20 22:27:00",
#         "high": "4802.000",
#         "low": "4796.000",
#         "open": "4802.000",
#         "volume": "3113",
#         "wave": 0
#     },
#     {
#         "close": "4802.000",
#         "ctm": "1726842480",
#         "ctmfmt": "2024-09-20 22:28:00",
#         "high": "4802.000",
#         "low": "4796.000",
#         "open": "4798.000",
#         "volume": "56828",
#         "wave": 0
#     },
#     {
#         "close": "4798.000",
#         "ctm": "1726842540",
#         "ctmfmt": "2024-09-20 22:29:00",
#         "high": "4806.000",
#         "low": "4798.000",
#         "open": "4802.000",
#         "volume": "46409",
#         "wave": 0
#     },
#     {
#         "close": "4796.000",
#         "ctm": "1726842600",
#         "ctmfmt": "2024-09-20 22:30:00",
#         "high": "4800.000",
#         "low": "4794.000",
#         "open": "4798.000",
#         "volume": "73690",
#         "wave": 0
#     },
#     {
#         "close": "4800.000",
#         "ctm": "1726842660",
#         "ctmfmt": "2024-09-20 22:31:00",
#         "high": "4802.000",
#         "low": "4796.000",
#         "open": "4796.000",
#         "volume": "56559",
#         "wave": 0
#     },
#     {
#         "close": "4806.000",
#         "ctm": "1726842720",
#         "ctmfmt": "2024-09-20 22:32:00",
#         "high": "4806.000",
#         "low": "4800.000",
#         "open": "4800.000",
#         "volume": "35178",
#         "wave": 0
#     },
#     {
#         "close": "4804.000",
#         "ctm": "1726842780",
#         "ctmfmt": "2024-09-20 22:33:00",
#         "high": "4810.000",
#         "low": "4804.000",
#         "open": "4804.000",
#         "volume": "51752",
#         "wave": 0
#     },
#     {
#         "close": "4806.000",
#         "ctm": "1726842840",
#         "ctmfmt": "2024-09-20 22:34:00",
#         "high": "4806.000",
#         "low": "4804.000",
#         "open": "4804.000",
#         "volume": "35223",
#         "wave": 0
#     },
#     {
#         "close": "4802.000",
#         "ctm": "1726842900",
#         "ctmfmt": "2024-09-20 22:35:00",
#         "high": "4806.000",
#         "low": "4802.000",
#         "open": "4804.000",
#         "volume": "16214",
#         "wave": 0
#     },
#     {
#         "close": "4796.000",
#         "ctm": "1726842960",
#         "ctmfmt": "2024-09-20 22:36:00",
#         "high": "4802.000",
#         "low": "4796.000",
#         "open": "4800.000",
#         "volume": "60709",
#         "wave": 0
#     },
#     {
#         "close": "4796.000",
#         "ctm": "1726843020",
#         "ctmfmt": "2024-09-20 22:37:00",
#         "high": "4800.000",
#         "low": "4796.000",
#         "open": "4800.000",
#         "volume": "14876",
#         "wave": 0
#     },
#     {
#         "close": "4796.000",
#         "ctm": "1726843080",
#         "ctmfmt": "2024-09-20 22:38:00",
#         "high": "4798.000",
#         "low": "4794.000",
#         "open": "4796.000",
#         "volume": "40793",
#         "wave": 0
#     },
#     {
#         "close": "4796.000",
#         "ctm": "1726843140",
#         "ctmfmt": "2024-09-20 22:39:00",
#         "high": "4798.000",
#         "low": "4794.000",
#         "open": "4794.000",
#         "volume": "46117",
#         "wave": 0
#     },
#     {
#         "close": "4794.000",
#         "ctm": "1726843200",
#         "ctmfmt": "2024-09-20 22:40:00",
#         "high": "4798.000",
#         "low": "4794.000",
#         "open": "4796.000",
#         "volume": "37610",
#         "wave": 0
#     },
#     {
#         "close": "4796.000",
#         "ctm": "1726843260",
#         "ctmfmt": "2024-09-20 22:41:00",
#         "high": "4798.000",
#         "low": "4794.000",
#         "open": "4794.000",
#         "volume": "36496",
#         "wave": 0
#     },
#     {
#         "close": "4800.000",
#         "ctm": "1726843320",
#         "ctmfmt": "2024-09-20 22:42:00",
#         "high": "4800.000",
#         "low": "4796.000",
#         "open": "4796.000",
#         "volume": "23278",
#         "wave": 0
#     },
#     {
#         "close": "4802.000",
#         "ctm": "1726843380",
#         "ctmfmt": "2024-09-20 22:43:00",
#         "high": "4804.000",
#         "low": "4798.000",
#         "open": "4800.000",
#         "volume": "50765",
#         "wave": 0
#     },
#     {
#         "close": "4800.000",
#         "ctm": "1726843440",
#         "ctmfmt": "2024-09-20 22:44:00",
#         "high": "4804.000",
#         "low": "4798.000",
#         "open": "4800.000",
#         "volume": "36508",
#         "wave": 0
#     },
#     {
#         "close": "4802.000",
#         "ctm": "1726843500",
#         "ctmfmt": "2024-09-20 22:45:00",
#         "high": "4806.000",
#         "low": "4798.000",
#         "open": "4802.000",
#         "volume": "50663",
#         "wave": 0
#     },
#     {
#         "close": "4802.000",
#         "ctm": "1726843560",
#         "ctmfmt": "2024-09-20 22:46:00",
#         "high": "4802.000",
#         "low": "4798.000",
#         "open": "4802.000",
#         "volume": "45862",
#         "wave": 0
#     },
#     {
#         "close": "4798.000",
#         "ctm": "1726843620",
#         "ctmfmt": "2024-09-20 22:47:00",
#         "high": "4806.000",
#         "low": "4798.000",
#         "open": "4802.000",
#         "volume": "44618",
#         "wave": 0
#     },
#     {
#         "close": "4800.000",
#         "ctm": "1726843680",
#         "ctmfmt": "2024-09-20 22:48:00",
#         "high": "4800.000",
#         "low": "4796.000",
#         "open": "4798.000",
#         "volume": "19997",
#         "wave": 0
#     },
#     {
#         "close": "4800.000",
#         "ctm": "1726843740",
#         "ctmfmt": "2024-09-20 22:49:00",
#         "high": "4802.000",
#         "low": "4796.000",
#         "open": "4800.000",
#         "volume": "27099",
#         "wave": 0
#     },
#     {
#         "close": "4800.000",
#         "ctm": "1726843800",
#         "ctmfmt": "2024-09-20 22:50:00",
#         "high": "4802.000",
#         "low": "4798.000",
#         "open": "4800.000",
#         "volume": "21758",
#         "wave": 0
#     },
#     {
#         "close": "4800.000",
#         "ctm": "1726843860",
#         "ctmfmt": "2024-09-20 22:51:00",
#         "high": "4802.000",
#         "low": "4798.000",
#         "open": "4798.000",
#         "volume": "20842",
#         "wave": 0
#     },
#     {
#         "close": "4796.000",
#         "ctm": "1726843920",
#         "ctmfmt": "2024-09-20 22:52:00",
#         "high": "4800.000",
#         "low": "4796.000",
#         "open": "4798.000",
#         "volume": "11242",
#         "wave": 0
#     },
#     {
#         "close": "4794.000",
#         "ctm": "1726843980",
#         "ctmfmt": "2024-09-20 22:53:00",
#         "high": "4798.000",
#         "low": "4792.000",
#         "open": "4796.000",
#         "volume": "74878",
#         "wave": 0
#     },
#     {
#         "close": "4796.000",
#         "ctm": "1726844040",
#         "ctmfmt": "2024-09-20 22:54:00",
#         "high": "4796.000",
#         "low": "4792.000",
#         "open": "4794.000",
#         "volume": "45789",
#         "wave": 0
#     },
#     {
#         "close": "4798.000",
#         "ctm": "1726844100",
#         "ctmfmt": "2024-09-20 22:55:00",
#         "high": "4798.000",
#         "low": "4796.000",
#         "open": "4796.000",
#         "volume": "19975",
#         "wave": 0
#     },
#     {
#         "close": "4798.000",
#         "ctm": "1726844160",
#         "ctmfmt": "2024-09-20 22:56:00",
#         "high": "4800.000",
#         "low": "4794.000",
#         "open": "4796.000",
#         "volume": "59647",
#         "wave": 0
#     },
#     {
#         "close": "4800.000",
#         "ctm": "1726844220",
#         "ctmfmt": "2024-09-20 22:57:00",
#         "high": "4800.000",
#         "low": "4796.000",
#         "open": "4798.000",
#         "volume": "44310",
#         "wave": 0
#     },
#     {
#         "close": "4800.000",
#         "ctm": "1726844280",
#         "ctmfmt": "2024-09-20 22:58:00",
#         "high": "4802.000",
#         "low": "4798.000",
#         "open": "4800.000",
#         "volume": "60450",
#         "wave": 0
#     },
#     {
#         "close": "4798.000",
#         "ctm": "1726844340",
#         "ctmfmt": "2024-09-20 22:59:00",
#         "high": "4802.000",
#         "low": "4796.000",
#         "open": "4802.000",
#         "volume": "62606",
#         "wave": 0
#     },
#     {
#         "close": "4792.000",
#         "ctm": "1726844400",
#         "ctmfmt": "2024-09-20 23:00:00",
#         "high": "4802.000",
#         "low": "4792.000",
#         "open": "4798.000",
#         "volume": "128663",
#         "wave": 0
#     },
#     {
#         "close": "4796.000",
#         "ctm": "1727053260",
#         "ctmfmt": "2024-09-23 09:01:00",
#         "high": "4800.000",
#         "low": "4784.000",
#         "open": "4792.000",
#         "volume": "401913",
#         "wave": 0
#     },
#     {
#         "close": "4798.000",
#         "ctm": "1727053320",
#         "ctmfmt": "2024-09-23 09:02:00",
#         "high": "4798.000",
#         "low": "4790.000",
#         "open": "4794.000",
#         "volume": "99282",
#         "wave": 0
#     },
#     {
#         "close": "4810.000",
#         "ctm": "1727053380",
#         "ctmfmt": "2024-09-23 09:03:00",
#         "high": "4810.000",
#         "low": "4798.000",
#         "open": "4798.000",
#         "volume": "183939",
#         "wave": 0
#     },
#     {
#         "close": "4820.000",
#         "ctm": "1727053440",
#         "ctmfmt": "2024-09-23 09:04:00",
#         "high": "4820.000",
#         "low": "4810.000",
#         "open": "4810.000",
#         "volume": "311068",
#         "wave": 0
#     },
#     {
#         "close": "4818.000",
#         "ctm": "1727053500",
#         "ctmfmt": "2024-09-23 09:05:00",
#         "high": "4820.000",
#         "low": "4812.000",
#         "open": "4820.000",
#         "volume": "177140",
#         "wave": 0
#     },
#     {
#         "close": "4826.000",
#         "ctm": "1727053560",
#         "ctmfmt": "2024-09-23 09:06:00",
#         "high": "4828.000",
#         "low": "4818.000",
#         "open": "4818.000",
#         "volume": "187132",
#         "wave": 0
#     },
#     {
#         "close": "4822.000",
#         "ctm": "1727053620",
#         "ctmfmt": "2024-09-23 09:07:00",
#         "high": "4828.000",
#         "low": "4820.000",
#         "open": "4826.000",
#         "volume": "95808",
#         "wave": 0
#     },
#     {
#         "close": "4820.000",
#         "ctm": "1727053680",
#         "ctmfmt": "2024-09-23 09:08:00",
#         "high": "4824.000",
#         "low": "4818.000",
#         "open": "4824.000",
#         "volume": "54682",
#         "wave": 0
#     },
#     {
#         "close": "4822.000",
#         "ctm": "1727053740",
#         "ctmfmt": "2024-09-23 09:09:00",
#         "high": "4822.000",
#         "low": "4818.000",
#         "open": "4820.000",
#         "volume": "65212",
#         "wave": 0
#     },
#     {
#         "close": "4820.000",
#         "ctm": "1727053800",
#         "ctmfmt": "2024-09-23 09:10:00",
#         "high": "4822.000",
#         "low": "4814.000",
#         "open": "4822.000",
#         "volume": "60467",
#         "wave": 0
#     },
#     {
#         "close": "4808.000",
#         "ctm": "1727053860",
#         "ctmfmt": "2024-09-23 09:11:00",
#         "high": "4820.000",
#         "low": "4808.000",
#         "open": "4820.000",
#         "volume": "78432",
#         "wave": 0
#     },
#     {
#         "close": "4808.000",
#         "ctm": "1727053920",
#         "ctmfmt": "2024-09-23 09:12:00",
#         "high": "4812.000",
#         "low": "4804.000",
#         "open": "4804.000",
#         "volume": "120005",
#         "wave": 0
#     },
#     {
#         "close": "4810.000",
#         "ctm": "1727053980",
#         "ctmfmt": "2024-09-23 09:13:00",
#         "high": "4810.000",
#         "low": "4804.000",
#         "open": "4810.000",
#         "volume": "58973",
#         "wave": 0
#     },
#     {
#         "close": "4820.000",
#         "ctm": "1727054040",
#         "ctmfmt": "2024-09-23 09:14:00",
#         "high": "4824.000",
#         "low": "4810.000",
#         "open": "4810.000",
#         "volume": "109854",
#         "wave": 0
#     },
#     {
#         "close": "4830.000",
#         "ctm": "1727054100",
#         "ctmfmt": "2024-09-23 09:15:00",
#         "high": "4830.000",
#         "low": "4820.000",
#         "open": "4820.000",
#         "volume": "95203",
#         "wave": 0
#     },
#     {
#         "close": "4824.000",
#         "ctm": "1727054160",
#         "ctmfmt": "2024-09-23 09:16:00",
#         "high": "4834.000",
#         "low": "4824.000",
#         "open": "4830.000",
#         "volume": "5255",
#         "wave": 0
#     },
#     {
#         "close": "4818.000",
#         "ctm": "1727054220",
#         "ctmfmt": "2024-09-23 09:17:00",
#         "high": "4818.000",
#         "low": "4818.000",
#         "open": "4818.000",
#         "volume": "192",
#         "wave": 0
#     },
#     {
#         "close": "4818.000",
#         "ctm": "1727054280",
#         "ctmfmt": "2024-09-23 09:18:00",
#         "high": "4820.000",
#         "low": "4816.000",
#         "open": "4818.000",
#         "volume": "38256",
#         "wave": 0
#     },
#     {
#         "close": "4814.000",
#         "ctm": "1727054340",
#         "ctmfmt": "2024-09-23 09:19:00",
#         "high": "4818.000",
#         "low": "4806.000",
#         "open": "4816.000",
#         "volume": "81468",
#         "wave": 0
#     },
#     {
#         "close": "4808.000",
#         "ctm": "1727054400",
#         "ctmfmt": "2024-09-23 09:20:00",
#         "high": "4814.000",
#         "low": "4808.000",
#         "open": "4814.000",
#         "volume": "51818",
#         "wave": 0
#     },
#     {
#         "close": "4812.000",
#         "ctm": "1727054460",
#         "ctmfmt": "2024-09-23 09:21:00",
#         "high": "4812.000",
#         "low": "4806.000",
#         "open": "4808.000",
#         "volume": "42799",
#         "wave": 0
#     },
#     {
#         "close": "4808.000",
#         "ctm": "1727054520",
#         "ctmfmt": "2024-09-23 09:22:00",
#         "high": "4812.000",
#         "low": "4806.000",
#         "open": "4808.000",
#         "volume": "59077",
#         "wave": 0
#     },
#     {
#         "close": "4812.000",
#         "ctm": "1727054580",
#         "ctmfmt": "2024-09-23 09:23:00",
#         "high": "4812.000",
#         "low": "4810.000",
#         "open": "4810.000",
#         "volume": "23925",
#         "wave": 0
#     },
#     {
#         "close": "4818.000",
#         "ctm": "1727054640",
#         "ctmfmt": "2024-09-23 09:24:00",
#         "high": "4820.000",
#         "low": "4812.000",
#         "open": "4812.000",
#         "volume": "41437",
#         "wave": 0
#     },
#     {
#         "close": "4818.000",
#         "ctm": "1727054700",
#         "ctmfmt": "2024-09-23 09:25:00",
#         "high": "4820.000",
#         "low": "4814.000",
#         "open": "4820.000",
#         "volume": "28116",
#         "wave": 0
#     },
#     {
#         "close": "4820.000",
#         "ctm": "1727054760",
#         "ctmfmt": "2024-09-23 09:26:00",
#         "high": "4824.000",
#         "low": "4812.000",
#         "open": "4824.000",
#         "volume": "61042",
#         "wave": 0
#     },
#     {
#         "close": "4818.000",
#         "ctm": "1727054820",
#         "ctmfmt": "2024-09-23 09:27:00",
#         "high": "4822.000",
#         "low": "4816.000",
#         "open": "4822.000",
#         "volume": "24502",
#         "wave": 0
#     },
#     {
#         "close": "4818.000",
#         "ctm": "1727054880",
#         "ctmfmt": "2024-09-23 09:28:00",
#         "high": "4820.000",
#         "low": "4816.000",
#         "open": "4820.000",
#         "volume": "25035",
#         "wave": 0
#     },
#     {
#         "close": "4818.000",
#         "ctm": "1727054940",
#         "ctmfmt": "2024-09-23 09:29:00",
#         "high": "4820.000",
#         "low": "4812.000",
#         "open": "4820.000",
#         "volume": "25620",
#         "wave": 0
#     },
#     {
#         "close": "4818.000",
#         "ctm": "1727055000",
#         "ctmfmt": "2024-09-23 09:30:00",
#         "high": "4822.000",
#         "low": "4816.000",
#         "open": "4818.000",
#         "volume": "29004",
#         "wave": 0
#     },
#     {
#         "close": "4812.000",
#         "ctm": "1727055060",
#         "ctmfmt": "2024-09-23 09:31:00",
#         "high": "4818.000",
#         "low": "4810.000",
#         "open": "4818.000",
#         "volume": "43255",
#         "wave": 0
#     },
#     {
#         "close": "4808.000",
#         "ctm": "1727055120",
#         "ctmfmt": "2024-09-23 09:32:00",
#         "high": "4814.000",
#         "low": "4808.000",
#         "open": "4808.000",
#         "volume": "52154",
#         "wave": 0
#     },
#     {
#         "close": "4814.000",
#         "ctm": "1727055180",
#         "ctmfmt": "2024-09-23 09:33:00",
#         "high": "4816.000",
#         "low": "4808.000",
#         "open": "4814.000",
#         "volume": "27716",
#         "wave": 0
#     },
#     {
#         "close": "4818.000",
#         "ctm": "1727055240",
#         "ctmfmt": "2024-09-23 09:34:00",
#         "high": "4824.000",
#         "low": "4814.000",
#         "open": "4818.000",
#         "volume": "58471",
#         "wave": 0
#     },
#     {
#         "close": "4826.000",
#         "ctm": "1727055300",
#         "ctmfmt": "2024-09-23 09:35:00",
#         "high": "4828.000",
#         "low": "4820.000",
#         "open": "4822.000",
#         "volume": "33460",
#         "wave": 0
#     },
#     {
#         "close": "4828.000",
#         "ctm": "1727055360",
#         "ctmfmt": "2024-09-23 09:36:00",
#         "high": "4828.000",
#         "low": "4822.000",
#         "open": "4824.000",
#         "volume": "37366",
#         "wave": 0
#     },
#     {
#         "close": "4840.000",
#         "ctm": "1727055420",
#         "ctmfmt": "2024-09-23 09:37:00",
#         "high": "4840.000",
#         "low": "4826.000",
#         "open": "4828.000",
#         "volume": "131096",
#         "wave": 0
#     },
#     {
#         "close": "4832.000",
#         "ctm": "1727055480",
#         "ctmfmt": "2024-09-23 09:38:00",
#         "high": "4838.000",
#         "low": "4830.000",
#         "open": "4838.000",
#         "volume": "86573",
#         "wave": 0
#     },
#     {
#         "close": "4832.000",
#         "ctm": "1727055540",
#         "ctmfmt": "2024-09-23 09:39:00",
#         "high": "4834.000",
#         "low": "4828.000",
#         "open": "4834.000",
#         "volume": "3615",
#         "wave": 0
#     },
#     {
#         "close": "4834.000",
#         "ctm": "1727055600",
#         "ctmfmt": "2024-09-23 09:40:00",
#         "high": "4836.000",
#         "low": "4830.000",
#         "open": "4830.000",
#         "volume": "55819",
#         "wave": 0
#     },
#     {
#         "close": "4830.000",
#         "ctm": "1727055660",
#         "ctmfmt": "2024-09-23 09:41:00",
#         "high": "4834.000",
#         "low": "4830.000",
#         "open": "4834.000",
#         "volume": "15132",
#         "wave": 0
#     },
#     {
#         "close": "4842.000",
#         "ctm": "1727055720",
#         "ctmfmt": "2024-09-23 09:42:00",
#         "high": "4842.000",
#         "low": "4832.000",
#         "open": "4842.000",
#         "volume": "85395",
#         "wave": 0
#     },
#     {
#         "close": "4842.000",
#         "ctm": "1727055780",
#         "ctmfmt": "2024-09-23 09:43:00",
#         "high": "4846.000",
#         "low": "4840.000",
#         "open": "4842.000",
#         "volume": "85250",
#         "wave": 0
#     },
#     {
#         "close": "4836.000",
#         "ctm": "1727055840",
#         "ctmfmt": "2024-09-23 09:44:00",
#         "high": "4842.000",
#         "low": "4836.000",
#         "open": "4842.000",
#         "volume": "41957",
#         "wave": 0
#     },
#     {
#         "close": "4842.000",
#         "ctm": "1727055900",
#         "ctmfmt": "2024-09-23 09:45:00",
#         "high": "4842.000",
#         "low": "4834.000",
#         "open": "4836.000",
#         "volume": "43656",
#         "wave": 0
#     },
#     {
#         "close": "4838.000",
#         "ctm": "1727055960",
#         "ctmfmt": "2024-09-23 09:46:00",
#         "high": "4842.000",
#         "low": "4834.000",
#         "open": "4840.000",
#         "volume": "29496",
#         "wave": 0
#     },
#     {
#         "close": "4840.000",
#         "ctm": "1727056020",
#         "ctmfmt": "2024-09-23 09:47:00",
#         "high": "4842.000",
#         "low": "4838.000",
#         "open": "4840.000",
#         "volume": "42012",
#         "wave": 0
#     },
#     {
#         "close": "4846.000",
#         "ctm": "1727056080",
#         "ctmfmt": "2024-09-23 09:48:00",
#         "high": "4846.000",
#         "low": "4838.000",
#         "open": "4840.000",
#         "volume": "30319",
#         "wave": 0
#     },
#     {
#         "close": "4844.000",
#         "ctm": "1727056140",
#         "ctmfmt": "2024-09-23 09:49:00",
#         "high": "4848.000",
#         "low": "4844.000",
#         "open": "4846.000",
#         "volume": "48732",
#         "wave": 0
#     },
#     {
#         "close": "4848.000",
#         "ctm": "1727056200",
#         "ctmfmt": "2024-09-23 09:50:00",
#         "high": "4850.000",
#         "low": "4846.000",
#         "open": "4848.000",
#         "volume": "94632",
#         "wave": 0
#     },
#     {
#         "close": "4842.000",
#         "ctm": "1727056260",
#         "ctmfmt": "2024-09-23 09:51:00",
#         "high": "4848.000",
#         "low": "4842.000",
#         "open": "4848.000",
#         "volume": "25992",
#         "wave": 0
#     },
#     {
#         "close": "4844.000",
#         "ctm": "1727056320",
#         "ctmfmt": "2024-09-23 09:52:00",
#         "high": "4844.000",
#         "low": "4840.000",
#         "open": "4844.000",
#         "volume": "28528",
#         "wave": 0
#     },
#     {
#         "close": "4842.000",
#         "ctm": "1727056380",
#         "ctmfmt": "2024-09-23 09:53:00",
#         "high": "4844.000",
#         "low": "4840.000",
#         "open": "4842.000",
#         "volume": "29592",
#         "wave": 0
#     },
#     {
#         "close": "4842.000",
#         "ctm": "1727056440",
#         "ctmfmt": "2024-09-23 09:54:00",
#         "high": "4842.000",
#         "low": "4838.000",
#         "open": "4840.000",
#         "volume": "16342",
#         "wave": 0
#     },
#     {
#         "close": "4842.000",
#         "ctm": "1727056500",
#         "ctmfmt": "2024-09-23 09:55:00",
#         "high": "4846.000",
#         "low": "4840.000",
#         "open": "4842.000",
#         "volume": "25961",
#         "wave": 0
#     },
#     {
#         "close": "4846.000",
#         "ctm": "1727056560",
#         "ctmfmt": "2024-09-23 09:56:00",
#         "high": "4846.000",
#         "low": "4842.000",
#         "open": "4842.000",
#         "volume": "18447",
#         "wave": 0
#     },
#     {
#         "close": "4844.000",
#         "ctm": "1727056620",
#         "ctmfmt": "2024-09-23 09:57:00",
#         "high": "4846.000",
#         "low": "4840.000",
#         "open": "4846.000",
#         "volume": "20515",
#         "wave": 0
#     },
#     {
#         "close": "4852.000",
#         "ctm": "1727056680",
#         "ctmfmt": "2024-09-23 09:58:00",
#         "high": "4854.000",
#         "low": "4846.000",
#         "open": "4846.000",
#         "volume": "64394",
#         "wave": 0
#     },
#     {
#         "close": "4850.000",
#         "ctm": "1727056740",
#         "ctmfmt": "2024-09-23 09:59:00",
#         "high": "4854.000",
#         "low": "4850.000",
#         "open": "4850.000",
#         "volume": "5390",
#         "wave": 0
#     },
#     {
#         "close": "4856.000",
#         "ctm": "1727056800",
#         "ctmfmt": "2024-09-23 10:00:00",
#         "high": "4856.000",
#         "low": "4850.000",
#         "open": "4852.000",
#         "volume": "54896",
#         "wave": 0
#     },
#     {
#         "close": "4846.000",
#         "ctm": "1727056860",
#         "ctmfmt": "2024-09-23 10:01:00",
#         "high": "4854.000",
#         "low": "4846.000",
#         "open": "4848.000",
#         "volume": "41984",
#         "wave": 0
#     },
#     {
#         "close": "4842.000",
#         "ctm": "1727056920",
#         "ctmfmt": "2024-09-23 10:02:00",
#         "high": "4844.000",
#         "low": "4842.000",
#         "open": "4842.000",
#         "volume": "1221",
#         "wave": 0
#     },
#     {
#         "close": "4834.000",
#         "ctm": "1727056980",
#         "ctmfmt": "2024-09-23 10:03:00",
#         "high": "4842.000",
#         "low": "4834.000",
#         "open": "4834.000",
#         "volume": "32604",
#         "wave": 0
#     },
#     {
#         "close": "4832.000",
#         "ctm": "1727057040",
#         "ctmfmt": "2024-09-23 10:04:00",
#         "high": "4836.000",
#         "low": "4830.000",
#         "open": "4834.000",
#         "volume": "40473",
#         "wave": 0
#     },
#     {
#         "close": "4830.000",
#         "ctm": "1727057100",
#         "ctmfmt": "2024-09-23 10:05:00",
#         "high": "4830.000",
#         "low": "4824.000",
#         "open": "4828.000",
#         "volume": "47716",
#         "wave": 0
#     },
#     {
#         "close": "4826.000",
#         "ctm": "1727057160",
#         "ctmfmt": "2024-09-23 10:06:00",
#         "high": "4830.000",
#         "low": "4824.000",
#         "open": "4826.000",
#         "volume": "23600",
#         "wave": 0
#     },
#     {
#         "close": "4826.000",
#         "ctm": "1727057220",
#         "ctmfmt": "2024-09-23 10:07:00",
#         "high": "4828.000",
#         "low": "4822.000",
#         "open": "4826.000",
#         "volume": "23610",
#         "wave": 0
#     },
#     {
#         "close": "4828.000",
#         "ctm": "1727057280",
#         "ctmfmt": "2024-09-23 10:08:00",
#         "high": "4832.000",
#         "low": "4826.000",
#         "open": "4826.000",
#         "volume": "27760",
#         "wave": 0
#     },
#     {
#         "close": "4830.000",
#         "ctm": "1727057340",
#         "ctmfmt": "2024-09-23 10:09:00",
#         "high": "4830.000",
#         "low": "4826.000",
#         "open": "4828.000",
#         "volume": "22160",
#         "wave": 0
#     },
#     {
#         "close": "4828.000",
#         "ctm": "1727057400",
#         "ctmfmt": "2024-09-23 10:10:00",
#         "high": "4830.000",
#         "low": "4828.000",
#         "open": "4830.000",
#         "volume": "7510",
#         "wave": 0
#     },
#     {
#         "close": "4832.000",
#         "ctm": "1727057460",
#         "ctmfmt": "2024-09-23 10:11:00",
#         "high": "4836.000",
#         "low": "4830.000",
#         "open": "4830.000",
#         "volume": "20740",
#         "wave": 0
#     },
#     {
#         "close": "4830.000",
#         "ctm": "1727057520",
#         "ctmfmt": "2024-09-23 10:12:00",
#         "high": "4834.000",
#         "low": "4830.000",
#         "open": "4832.000",
#         "volume": "10450",
#         "wave": 0
#     },
#     {
#         "close": "4830.000",
#         "ctm": "1727057580",
#         "ctmfmt": "2024-09-23 10:13:00",
#         "high": "4832.000",
#         "low": "4828.000",
#         "open": "4832.000",
#         "volume": "686",
#         "wave": 0
#     },
#     {
#         "close": "4824.000",
#         "ctm": "1727057640",
#         "ctmfmt": "2024-09-23 10:14:00",
#         "high": "4830.000",
#         "low": "4824.000",
#         "open": "4826.000",
#         "volume": "12545",
#         "wave": 0
#     },
#     {
#         "close": "4830.000",
#         "ctm": "1727057700",
#         "ctmfmt": "2024-09-23 10:15:00",
#         "high": "4830.000",
#         "low": "4824.000",
#         "open": "4824.000",
#         "volume": "14377",
#         "wave": 0
#     },
#     {
#         "close": "4834.000",
#         "ctm": "1727058660",
#         "ctmfmt": "2024-09-23 10:31:00",
#         "high": "4834.000",
#         "low": "4826.000",
#         "open": "4830.000",
#         "volume": "15605",
#         "wave": 0
#     },
#     {
#         "close": "4832.000",
#         "ctm": "1727058720",
#         "ctmfmt": "2024-09-23 10:32:00",
#         "high": "4834.000",
#         "low": "4830.000",
#         "open": "4834.000",
#         "volume": "12240",
#         "wave": 0
#     },
#     {
#         "close": "4838.000",
#         "ctm": "1727058780",
#         "ctmfmt": "2024-09-23 10:33:00",
#         "high": "4840.000",
#         "low": "4830.000",
#         "open": "4830.000",
#         "volume": "18144",
#         "wave": 0
#     },
#     {
#         "close": "4832.000",
#         "ctm": "1727058840",
#         "ctmfmt": "2024-09-23 10:34:00",
#         "high": "4838.000",
#         "low": "4832.000",
#         "open": "4838.000",
#         "volume": "7488",
#         "wave": 0
#     },
#     {
#         "close": "4834.000",
#         "ctm": "1727058900",
#         "ctmfmt": "2024-09-23 10:35:00",
#         "high": "4836.000",
#         "low": "4830.000",
#         "open": "4832.000",
#         "volume": "9819",
#         "wave": 0
#     },
#     {
#         "close": "4838.000",
#         "ctm": "1727058960",
#         "ctmfmt": "2024-09-23 10:36:00",
#         "high": "4842.000",
#         "low": "4836.000",
#         "open": "4836.000",
#         "volume": "22950",
#         "wave": 0
#     },
#     {
#         "close": "4830.000",
#         "ctm": "1727059020",
#         "ctmfmt": "2024-09-23 10:37:00",
#         "high": "4840.000",
#         "low": "4828.000",
#         "open": "4838.000",
#         "volume": "37117",
#         "wave": 0
#     },
#     {
#         "close": "4830.000",
#         "ctm": "1727059080",
#         "ctmfmt": "2024-09-23 10:38:00",
#         "high": "4832.000",
#         "low": "4828.000",
#         "open": "4830.000",
#         "volume": "10403",
#         "wave": 0
#     },
#     {
#         "close": "4828.000",
#         "ctm": "1727059140",
#         "ctmfmt": "2024-09-23 10:39:00",
#         "high": "4832.000",
#         "low": "4826.000",
#         "open": "4828.000",
#         "volume": "16688",
#         "wave": 0
#     },
#     {
#         "close": "4834.000",
#         "ctm": "1727059200",
#         "ctmfmt": "2024-09-23 10:40:00",
#         "high": "4834.000",
#         "low": "4828.000",
#         "open": "4830.000",
#         "volume": "6640",
#         "wave": 0
#     },
#     {
#         "close": "4838.000",
#         "ctm": "1727059260",
#         "ctmfmt": "2024-09-23 10:41:00",
#         "high": "4840.000",
#         "low": "4832.000",
#         "open": "4834.000",
#         "volume": "12824",
#         "wave": 0
#     },
#     {
#         "close": "4838.000",
#         "ctm": "1727059320",
#         "ctmfmt": "2024-09-23 10:42:00",
#         "high": "4842.000",
#         "low": "4838.000",
#         "open": "4838.000",
#         "volume": "7984",
#         "wave": 0
#     },
#     {
#         "close": "4838.000",
#         "ctm": "1727059380",
#         "ctmfmt": "2024-09-23 10:43:00",
#         "high": "4840.000",
#         "low": "4836.000",
#         "open": "4838.000",
#         "volume": "8136",
#         "wave": 0
#     },
#     {
#         "close": "4840.000",
#         "ctm": "1727059440",
#         "ctmfmt": "2024-09-23 10:44:00",
#         "high": "4844.000",
#         "low": "4838.000",
#         "open": "4838.000",
#         "volume": "18434",
#         "wave": 0
#     },
#     {
#         "close": "4838.000",
#         "ctm": "1727059500",
#         "ctmfmt": "2024-09-23 10:45:00",
#         "high": "4842.000",
#         "low": "4838.000",
#         "open": "4838.000",
#         "volume": "6822",
#         "wave": 0
#     },
#     {
#         "close": "4838.000",
#         "ctm": "1727059560",
#         "ctmfmt": "2024-09-23 10:46:00",
#         "high": "4840.000",
#         "low": "4838.000",
#         "open": "4838.000",
#         "volume": "5723",
#         "wave": 0
#     },
#     {
#         "close": "4836.000",
#         "ctm": "1727059620",
#         "ctmfmt": "2024-09-23 10:47:00",
#         "high": "4838.000",
#         "low": "4834.000",
#         "open": "4836.000",
#         "volume": "6565",
#         "wave": 0
#     },
#     {
#         "close": "4846.000",
#         "ctm": "1727059680",
#         "ctmfmt": "2024-09-23 10:48:00",
#         "high": "4846.000",
#         "low": "4836.000",
#         "open": "4838.000",
#         "volume": "18579",
#         "wave": 0
#     },
#     {
#         "close": "4846.000",
#         "ctm": "1727059740",
#         "ctmfmt": "2024-09-23 10:49:00",
#         "high": "4846.000",
#         "low": "4844.000",
#         "open": "4846.000",
#         "volume": "8995",
#         "wave": 0
#     },
#     {
#         "close": "4838.000",
#         "ctm": "1727059800",
#         "ctmfmt": "2024-09-23 10:50:00",
#         "high": "4846.000",
#         "low": "4838.000",
#         "open": "4840.000",
#         "volume": "10307",
#         "wave": 0
#     },
#     {
#         "close": "4840.000",
#         "ctm": "1727059860",
#         "ctmfmt": "2024-09-23 10:51:00",
#         "high": "4842.000",
#         "low": "4838.000",
#         "open": "4840.000",
#         "volume": "9436",
#         "wave": 0
#     },
#     {
#         "close": "4836.000",
#         "ctm": "1727059920",
#         "ctmfmt": "2024-09-23 10:52:00",
#         "high": "4840.000",
#         "low": "4834.000",
#         "open": "4840.000",
#         "volume": "9840",
#         "wave": 0
#     },
#     {
#         "close": "4828.000",
#         "ctm": "1727059980",
#         "ctmfmt": "2024-09-23 10:53:00",
#         "high": "4836.000",
#         "low": "4828.000",
#         "open": "4834.000",
#         "volume": "15680",
#         "wave": 0
#     },
#     {
#         "close": "4830.000",
#         "ctm": "1727060040",
#         "ctmfmt": "2024-09-23 10:54:00",
#         "high": "4834.000",
#         "low": "4830.000",
#         "open": "4830.000",
#         "volume": "10248",
#         "wave": 0
#     },
#     {
#         "close": "4830.000",
#         "ctm": "1727060100",
#         "ctmfmt": "2024-09-23 10:55:00",
#         "high": "4832.000",
#         "low": "4830.000",
#         "open": "4830.000",
#         "volume": "994",
#         "wave": 0
#     },
#     {
#         "close": "4838.000",
#         "ctm": "1727060160",
#         "ctmfmt": "2024-09-23 10:56:00",
#         "high": "4840.000",
#         "low": "4830.000",
#         "open": "4832.000",
#         "volume": "19663",
#         "wave": 0
#     },
#     {
#         "close": "4836.000",
#         "ctm": "1727060220",
#         "ctmfmt": "2024-09-23 10:57:00",
#         "high": "4840.000",
#         "low": "4836.000",
#         "open": "4838.000",
#         "volume": "4823",
#         "wave": 0
#     },
#     {
#         "close": "4838.000",
#         "ctm": "1727060280",
#         "ctmfmt": "2024-09-23 10:58:00",
#         "high": "4838.000",
#         "low": "4836.000",
#         "open": "4836.000",
#         "volume": "782",
#         "wave": 0
#     },
#     {
#         "close": "4834.000",
#         "ctm": "1727060340",
#         "ctmfmt": "2024-09-23 10:59:00",
#         "high": "4838.000",
#         "low": "4832.000",
#         "open": "4832.000",
#         "volume": "4339",
#         "wave": 0
#     },
#     {
#         "close": "4834.000",
#         "ctm": "1727060400",
#         "ctmfmt": "2024-09-23 11:00:00",
#         "high": "4834.000",
#         "low": "4832.000",
#         "open": "4834.000",
#         "volume": "4411",
#         "wave": 0
#     },
#     {
#         "close": "4836.000",
#         "ctm": "1727060460",
#         "ctmfmt": "2024-09-23 11:01:00",
#         "high": "4836.000",
#         "low": "4832.000",
#         "open": "4834.000",
#         "volume": "3233",
#         "wave": 0
#     },
#     {
#         "close": "4836.000",
#         "ctm": "1727060520",
#         "ctmfmt": "2024-09-23 11:02:00",
#         "high": "4838.000",
#         "low": "4836.000",
#         "open": "4836.000",
#         "volume": "4026",
#         "wave": 0
#     },
#     {
#         "close": "4840.000",
#         "ctm": "1727060580",
#         "ctmfmt": "2024-09-23 11:03:00",
#         "high": "4844.000",
#         "low": "4836.000",
#         "open": "4844.000",
#         "volume": "11327",
#         "wave": 0
#     },
#     {
#         "close": "4836.000",
#         "ctm": "1727060640",
#         "ctmfmt": "2024-09-23 11:04:00",
#         "high": "4842.000",
#         "low": "4836.000",
#         "open": "4838.000",
#         "volume": "6865",
#         "wave": 0
#     },
#     {
#         "close": "4840.000",
#         "ctm": "1727060700",
#         "ctmfmt": "2024-09-23 11:05:00",
#         "high": "4842.000",
#         "low": "4836.000",
#         "open": "4838.000",
#         "volume": "4189",
#         "wave": 0
#     },
#     {
#         "close": "4840.000",
#         "ctm": "1727060760",
#         "ctmfmt": "2024-09-23 11:06:00",
#         "high": "4840.000",
#         "low": "4838.000",
#         "open": "4840.000",
#         "volume": "1572",
#         "wave": 0
#     },
#     {
#         "close": "4838.000",
#         "ctm": "1727060820",
#         "ctmfmt": "2024-09-23 11:07:00",
#         "high": "4840.000",
#         "low": "4836.000",
#         "open": "4838.000",
#         "volume": "6129",
#         "wave": 0
#     },
#     {
#         "close": "4828.000",
#         "ctm": "1727060880",
#         "ctmfmt": "2024-09-23 11:08:00",
#         "high": "4838.000",
#         "low": "4828.000",
#         "open": "4830.000",
#         "volume": "10711",
#         "wave": 0
#     },
#     {
#         "close": "4830.000",
#         "ctm": "1727060940",
#         "ctmfmt": "2024-09-23 11:09:00",
#         "high": "4832.000",
#         "low": "4828.000",
#         "open": "4828.000",
#         "volume": "9247",
#         "wave": 0
#     },
#     {
#         "close": "4828.000",
#         "ctm": "1727061000",
#         "ctmfmt": "2024-09-23 11:10:00",
#         "high": "4832.000",
#         "low": "4826.000",
#         "open": "4830.000",
#         "volume": "10958",
#         "wave": 0
#     },
#     {
#         "close": "4828.000",
#         "ctm": "1727061060",
#         "ctmfmt": "2024-09-23 11:11:00",
#         "high": "4832.000",
#         "low": "4828.000",
#         "open": "4830.000",
#         "volume": "863",
#         "wave": 0
#     },
#     {
#         "close": "4828.000",
#         "ctm": "1727061120",
#         "ctmfmt": "2024-09-23 11:12:00",
#         "high": "4830.000",
#         "low": "4828.000",
#         "open": "4828.000",
#         "volume": "3974",
#         "wave": 0
#     },
#     {
#         "close": "4826.000",
#         "ctm": "1727061180",
#         "ctmfmt": "2024-09-23 11:13:00",
#         "high": "4828.000",
#         "low": "4824.000",
#         "open": "4828.000",
#         "volume": "11186",
#         "wave": 0
#     },
#     {
#         "close": "4828.000",
#         "ctm": "1727061240",
#         "ctmfmt": "2024-09-23 11:14:00",
#         "high": "4830.000",
#         "low": "4824.000",
#         "open": "4826.000",
#         "volume": "8862",
#         "wave": 0
#     },
#     {
#         "close": "4826.000",
#         "ctm": "1727061300",
#         "ctmfmt": "2024-09-23 11:15:00",
#         "high": "4830.000",
#         "low": "4826.000",
#         "open": "4826.000",
#         "volume": "4763",
#         "wave": 0
#     },
#     {
#         "close": "4826.000",
#         "ctm": "1727061360",
#         "ctmfmt": "2024-09-23 11:16:00",
#         "high": "4828.000",
#         "low": "4826.000",
#         "open": "4828.000",
#         "volume": "5264",
#         "wave": 0
#     },
#     {
#         "close": "4826.000",
#         "ctm": "1727061420",
#         "ctmfmt": "2024-09-23 11:17:00",
#         "high": "4826.000",
#         "low": "4818.000",
#         "open": "4824.000",
#         "volume": "27500",
#         "wave": 0
#     },
#     {
#         "close": "4834.000",
#         "ctm": "1727061480",
#         "ctmfmt": "2024-09-23 11:18:00",
#         "high": "4834.000",
#         "low": "4826.000",
#         "open": "4826.000",
#         "volume": "10059",
#         "wave": 0
#     },
#     {
#         "close": "4832.000",
#         "ctm": "1727061540",
#         "ctmfmt": "2024-09-23 11:19:00",
#         "high": "4840.000",
#         "low": "4832.000",
#         "open": "4836.000",
#         "volume": "21917",
#         "wave": 0
#     },
#     {
#         "close": "4832.000",
#         "ctm": "1727061600",
#         "ctmfmt": "2024-09-23 11:20:00",
#         "high": "4834.000",
#         "low": "4826.000",
#         "open": "4834.000",
#         "volume": "1734",
#         "wave": 0
#     },
#     {
#         "close": "4828.000",
#         "ctm": "1727061660",
#         "ctmfmt": "2024-09-23 11:21:00",
#         "high": "4832.000",
#         "low": "4828.000",
#         "open": "4830.000",
#         "volume": "10515",
#         "wave": 0
#     },
#     {
#         "close": "4828.000",
#         "ctm": "1727061720",
#         "ctmfmt": "2024-09-23 11:22:00",
#         "high": "4830.000",
#         "low": "4826.000",
#         "open": "4826.000",
#         "volume": "3816",
#         "wave": 0
#     },
#     {
#         "close": "4830.000",
#         "ctm": "1727061780",
#         "ctmfmt": "2024-09-23 11:23:00",
#         "high": "4832.000",
#         "low": "4826.000",
#         "open": "4830.000",
#         "volume": "6328",
#         "wave": 0
#     },
#     {
#         "close": "4828.000",
#         "ctm": "1727061840",
#         "ctmfmt": "2024-09-23 11:24:00",
#         "high": "4830.000",
#         "low": "4826.000",
#         "open": "4828.000",
#         "volume": "5881",
#         "wave": 0
#     },
#     {
#         "close": "4832.000",
#         "ctm": "1727061900",
#         "ctmfmt": "2024-09-23 11:25:00",
#         "high": "4832.000",
#         "low": "4828.000",
#         "open": "4830.000",
#         "volume": "2579",
#         "wave": 0
#     },
#     {
#         "close": "4828.000",
#         "ctm": "1727061960",
#         "ctmfmt": "2024-09-23 11:26:00",
#         "high": "4832.000",
#         "low": "4826.000",
#         "open": "4830.000",
#         "volume": "3063",
#         "wave": 0
#     },
#     {
#         "close": "4830.000",
#         "ctm": "1727062020",
#         "ctmfmt": "2024-09-23 11:27:00",
#         "high": "4832.000",
#         "low": "4828.000",
#         "open": "4830.000",
#         "volume": "3806",
#         "wave": 0
#     },
#     {
#         "close": "4832.000",
#         "ctm": "1727062080",
#         "ctmfmt": "2024-09-23 11:28:00",
#         "high": "4832.000",
#         "low": "4830.000",
#         "open": "4832.000",
#         "volume": "3745",
#         "wave": 0
#     },
#     {
#         "close": "4832.000",
#         "ctm": "1727062140",
#         "ctmfmt": "2024-09-23 11:29:00",
#         "high": "4832.000",
#         "low": "4830.000",
#         "open": "4830.000",
#         "volume": "1534",
#         "wave": 0
#     },
#     {
#         "close": "4828.000",
#         "ctm": "1727062200",
#         "ctmfmt": "2024-09-23 11:30:00",
#         "high": "4832.000",
#         "low": "4826.000",
#         "open": "4830.000",
#         "volume": "10274",
#         "wave": 0
#     },
#     {
#         "close": "4832.000",
#         "ctm": "1727069460",
#         "ctmfmt": "2024-09-23 13:31:00",
#         "high": "4834.000",
#         "low": "4828.000",
#         "open": "4828.000",
#         "volume": "17189",
#         "wave": 0
#     },
#     {
#         "close": "4832.000",
#         "ctm": "1727069520",
#         "ctmfmt": "2024-09-23 13:32:00",
#         "high": "4834.000",
#         "low": "4830.000",
#         "open": "4832.000",
#         "volume": "10331",
#         "wave": 0
#     },
#     {
#         "close": "4830.000",
#         "ctm": "1727069580",
#         "ctmfmt": "2024-09-23 13:33:00",
#         "high": "4834.000",
#         "low": "4828.000",
#         "open": "4834.000",
#         "volume": "9442",
#         "wave": 0
#     },
#     {
#         "close": "4828.000",
#         "ctm": "1727069640",
#         "ctmfmt": "2024-09-23 13:34:00",
#         "high": "4830.000",
#         "low": "4828.000",
#         "open": "4830.000",
#         "volume": "2070",
#         "wave": 0
#     },
#     {
#         "close": "4830.000",
#         "ctm": "1727069700",
#         "ctmfmt": "2024-09-23 13:35:00",
#         "high": "4832.000",
#         "low": "4828.000",
#         "open": "4828.000",
#         "volume": "5850",
#         "wave": 0
#     },
#     {
#         "close": "4830.000",
#         "ctm": "1727069760",
#         "ctmfmt": "2024-09-23 13:36:00",
#         "high": "4832.000",
#         "low": "4828.000",
#         "open": "4828.000",
#         "volume": "4914",
#         "wave": 0
#     },
#     {
#         "close": "4834.000",
#         "ctm": "1727069820",
#         "ctmfmt": "2024-09-23 13:37:00",
#         "high": "4834.000",
#         "low": "4830.000",
#         "open": "4830.000",
#         "volume": "3132",
#         "wave": 0
#     },
#     {
#         "close": "4838.000",
#         "ctm": "1727069880",
#         "ctmfmt": "2024-09-23 13:38:00",
#         "high": "4838.000",
#         "low": "4832.000",
#         "open": "4832.000",
#         "volume": "11040",
#         "wave": 0
#     },
#     {
#         "close": "4836.000",
#         "ctm": "1727069940",
#         "ctmfmt": "2024-09-23 13:39:00",
#         "high": "4840.000",
#         "low": "4836.000",
#         "open": "4840.000",
#         "volume": "9462",
#         "wave": 0
#     },
#     {
#         "close": "4836.000",
#         "ctm": "1727070000",
#         "ctmfmt": "2024-09-23 13:40:00",
#         "high": "4838.000",
#         "low": "4832.000",
#         "open": "4838.000",
#         "volume": "6164",
#         "wave": 0
#     },
#     {
#         "close": "4832.000",
#         "ctm": "1727070060",
#         "ctmfmt": "2024-09-23 13:41:00",
#         "high": "4836.000",
#         "low": "4830.000",
#         "open": "4836.000",
#         "volume": "4432",
#         "wave": 0
#     },
#     {
#         "close": "4824.000",
#         "ctm": "1727070120",
#         "ctmfmt": "2024-09-23 13:42:00",
#         "high": "4832.000",
#         "low": "4822.000",
#         "open": "4830.000",
#         "volume": "23603",
#         "wave": 0
#     },
#     {
#         "close": "4822.000",
#         "ctm": "1727070180",
#         "ctmfmt": "2024-09-23 13:43:00",
#         "high": "4824.000",
#         "low": "4822.000",
#         "open": "4824.000",
#         "volume": "6699",
#         "wave": 0
#     },
#     {
#         "close": "4824.000",
#         "ctm": "1727070240",
#         "ctmfmt": "2024-09-23 13:44:00",
#         "high": "4826.000",
#         "low": "4822.000",
#         "open": "4822.000",
#         "volume": "3945",
#         "wave": 0
#     },
#     {
#         "close": "4826.000",
#         "ctm": "1727070300",
#         "ctmfmt": "2024-09-23 13:45:00",
#         "high": "4826.000",
#         "low": "4826.000",
#         "open": "4826.000",
#         "volume": "10",
#         "wave": 0
#     },
#     {
#         "close": "4826.000",
#         "ctm": "1727070360",
#         "ctmfmt": "2024-09-23 13:46:00",
#         "high": "4830.000",
#         "low": "4824.000",
#         "open": "4826.000",
#         "volume": "11235",
#         "wave": 0
#     },
#     {
#         "close": "4828.000",
#         "ctm": "1727070420",
#         "ctmfmt": "2024-09-23 13:47:00",
#         "high": "4830.000",
#         "low": "4826.000",
#         "open": "4826.000",
#         "volume": "4695",
#         "wave": 0
#     },
#     {
#         "close": "4828.000",
#         "ctm": "1727070480",
#         "ctmfmt": "2024-09-23 13:48:00",
#         "high": "4832.000",
#         "low": "4826.000",
#         "open": "4828.000",
#         "volume": "5104",
#         "wave": 0
#     },
#     {
#         "close": "4826.000",
#         "ctm": "1727070540",
#         "ctmfmt": "2024-09-23 13:49:00",
#         "high": "4828.000",
#         "low": "4824.000",
#         "open": "4828.000",
#         "volume": "4940",
#         "wave": 0
#     },
#     {
#         "close": "4820.000",
#         "ctm": "1727070600",
#         "ctmfmt": "2024-09-23 13:50:00",
#         "high": "4824.000",
#         "low": "4820.000",
#         "open": "4824.000",
#         "volume": "29125",
#         "wave": 0
#     },
#     {
#         "close": "4818.000",
#         "ctm": "1727070660",
#         "ctmfmt": "2024-09-23 13:51:00",
#         "high": "4822.000",
#         "low": "4818.000",
#         "open": "4820.000",
#         "volume": "8382",
#         "wave": 0
#     },
#     {
#         "close": "4818.000",
#         "ctm": "1727070720",
#         "ctmfmt": "2024-09-23 13:52:00",
#         "high": "4822.000",
#         "low": "4816.000",
#         "open": "4818.000",
#         "volume": "16952",
#         "wave": 0
#     },
#     {
#         "close": "4824.000",
#         "ctm": "1727070780",
#         "ctmfmt": "2024-09-23 13:53:00",
#         "high": "4824.000",
#         "low": "4818.000",
#         "open": "4818.000",
#         "volume": "8816",
#         "wave": 0
#     },
#     {
#         "close": "4826.000",
#         "ctm": "1727070840",
#         "ctmfmt": "2024-09-23 13:54:00",
#         "high": "4828.000",
#         "low": "4822.000",
#         "open": "4822.000",
#         "volume": "8616",
#         "wave": 0
#     },
#     {
#         "close": "4822.000",
#         "ctm": "1727070900",
#         "ctmfmt": "2024-09-23 13:55:00",
#         "high": "4826.000",
#         "low": "4822.000",
#         "open": "4826.000",
#         "volume": "2412",
#         "wave": 0
#     },
#     {
#         "close": "4822.000",
#         "ctm": "1727070960",
#         "ctmfmt": "2024-09-23 13:56:00",
#         "high": "4826.000",
#         "low": "4822.000",
#         "open": "4824.000",
#         "volume": "11124",
#         "wave": 0
#     },
#     {
#         "close": "4820.000",
#         "ctm": "1727071020",
#         "ctmfmt": "2024-09-23 13:57:00",
#         "high": "4824.000",
#         "low": "4820.000",
#         "open": "4824.000",
#         "volume": "18948",
#         "wave": 0
#     },
#     {
#         "close": "4822.000",
#         "ctm": "1727071080",
#         "ctmfmt": "2024-09-23 13:58:00",
#         "high": "4824.000",
#         "low": "4820.000",
#         "open": "4820.000",
#         "volume": "4551",
#         "wave": 0
#     },
#     {
#         "close": "4824.000",
#         "ctm": "1727071140",
#         "ctmfmt": "2024-09-23 13:59:00",
#         "high": "4826.000",
#         "low": "4822.000",
#         "open": "4822.000",
#         "volume": "4416",
#         "wave": 0
#     },
#     {
#         "close": "4824.000",
#         "ctm": "1727071200",
#         "ctmfmt": "2024-09-23 14:00:00",
#         "high": "4828.000",
#         "low": "4824.000",
#         "open": "4826.000",
#         "volume": "3351",
#         "wave": 0
#     },
#     {
#         "close": "4826.000",
#         "ctm": "1727071260",
#         "ctmfmt": "2024-09-23 14:01:00",
#         "high": "4826.000",
#         "low": "4826.000",
#         "open": "4826.000",
#         "volume": "597",
#         "wave": 0
#     },
#     {
#         "close": "4828.000",
#         "ctm": "1727071320",
#         "ctmfmt": "2024-09-23 14:02:00",
#         "high": "4828.000",
#         "low": "4826.000",
#         "open": "4826.000",
#         "volume": "3102",
#         "wave": 0
#     },
#     {
#         "close": "4828.000",
#         "ctm": "1727071380",
#         "ctmfmt": "2024-09-23 14:03:00",
#         "high": "4830.000",
#         "low": "4826.000",
#         "open": "4828.000",
#         "volume": "2610",
#         "wave": 0
#     },
#     {
#         "close": "4832.000",
#         "ctm": "1727071440",
#         "ctmfmt": "2024-09-23 14:04:00",
#         "high": "4834.000",
#         "low": "4828.000",
#         "open": "4830.000",
#         "volume": "9552",
#         "wave": 0
#     },
#     {
#         "close": "4824.000",
#         "ctm": "1727071500",
#         "ctmfmt": "2024-09-23 14:05:00",
#         "high": "4832.000",
#         "low": "4824.000",
#         "open": "4832.000",
#         "volume": "4497",
#         "wave": 0
#     },
#     {
#         "close": "4826.000",
#         "ctm": "1727071560",
#         "ctmfmt": "2024-09-23 14:06:00",
#         "high": "4826.000",
#         "low": "4824.000",
#         "open": "4826.000",
#         "volume": "1876",
#         "wave": 0
#     },
#     {
#         "close": "4822.000",
#         "ctm": "1727071620",
#         "ctmfmt": "2024-09-23 14:07:00",
#         "high": "4826.000",
#         "low": "4822.000",
#         "open": "4826.000",
#         "volume": "1734",
#         "wave": 0
#     },
#     {
#         "close": "4826.000",
#         "ctm": "1727071680",
#         "ctmfmt": "2024-09-23 14:08:00",
#         "high": "4828.000",
#         "low": "4822.000",
#         "open": "4824.000",
#         "volume": "1870",
#         "wave": 0
#     },
#     {
#         "close": "4826.000",
#         "ctm": "1727071740",
#         "ctmfmt": "2024-09-23 14:09:00",
#         "high": "4828.000",
#         "low": "4824.000",
#         "open": "4828.000",
#         "volume": "1784",
#         "wave": 0
#     },
#     {
#         "close": "4826.000",
#         "ctm": "1727071800",
#         "ctmfmt": "2024-09-23 14:10:00",
#         "high": "4828.000",
#         "low": "4824.000",
#         "open": "4828.000",
#         "volume": "1218",
#         "wave": 0
#     },
#     {
#         "close": "4826.000",
#         "ctm": "1727071860",
#         "ctmfmt": "2024-09-23 14:11:00",
#         "high": "4826.000",
#         "low": "4824.000",
#         "open": "4826.000",
#         "volume": "1922",
#         "wave": 0
#     },
#     {
#         "close": "4826.000",
#         "ctm": "1727071920",
#         "ctmfmt": "2024-09-23 14:12:00",
#         "high": "4826.000",
#         "low": "4824.000",
#         "open": "4826.000",
#         "volume": "1560",
#         "wave": 0
#     },
#     {
#         "close": "4828.000",
#         "ctm": "1727071980",
#         "ctmfmt": "2024-09-23 14:13:00",
#         "high": "4830.000",
#         "low": "4824.000",
#         "open": "4826.000",
#         "volume": "2336",
#         "wave": 0
#     },
#     {
#         "close": "4830.000",
#         "ctm": "1727072040",
#         "ctmfmt": "2024-09-23 14:14:00",
#         "high": "4830.000",
#         "low": "4826.000",
#         "open": "4830.000",
#         "volume": "2086",
#         "wave": 0
#     },
#     {
#         "close": "4836.000",
#         "ctm": "1727072100",
#         "ctmfmt": "2024-09-23 14:15:00",
#         "high": "4838.000",
#         "low": "4830.000",
#         "open": "4830.000",
#         "volume": "7843",
#         "wave": 0
#     },
#     {
#         "close": "4842.000",
#         "ctm": "1727072160",
#         "ctmfmt": "2024-09-23 14:16:00",
#         "high": "4844.000",
#         "low": "4834.000",
#         "open": "4834.000",
#         "volume": "8244",
#         "wave": 0
#     },
#     {
#         "close": "4842.000",
#         "ctm": "1727072220",
#         "ctmfmt": "2024-09-23 14:17:00",
#         "high": "4848.000",
#         "low": "4840.000",
#         "open": "4844.000",
#         "volume": "6593",
#         "wave": 0
#     },
#     {
#         "close": "4832.000",
#         "ctm": "1727072280",
#         "ctmfmt": "2024-09-23 14:18:00",
#         "high": "4842.000",
#         "low": "4832.000",
#         "open": "4842.000",
#         "volume": "2657",
#         "wave": 0
#     },
#     {
#         "close": "4828.000",
#         "ctm": "1727072340",
#         "ctmfmt": "2024-09-23 14:19:00",
#         "high": "4834.000",
#         "low": "4828.000",
#         "open": "4832.000",
#         "volume": "2159",
#         "wave": 0
#     },
#     {
#         "close": "4822.000",
#         "ctm": "1727072400",
#         "ctmfmt": "2024-09-23 14:20:00",
#         "high": "4830.000",
#         "low": "4822.000",
#         "open": "4828.000",
#         "volume": "3705",
#         "wave": 0
#     },
#     {
#         "close": "4826.000",
#         "ctm": "1727072460",
#         "ctmfmt": "2024-09-23 14:21:00",
#         "high": "4826.000",
#         "low": "4822.000",
#         "open": "4824.000",
#         "volume": "1935",
#         "wave": 0
#     },
#     {
#         "close": "4826.000",
#         "ctm": "1727072520",
#         "ctmfmt": "2024-09-23 14:22:00",
#         "high": "4828.000",
#         "low": "4824.000",
#         "open": "4826.000",
#         "volume": "1103",
#         "wave": 0
#     },
#     {
#         "close": "4826.000",
#         "ctm": "1727072580",
#         "ctmfmt": "2024-09-23 14:23:00",
#         "high": "4828.000",
#         "low": "4826.000",
#         "open": "4826.000",
#         "volume": "764",
#         "wave": 0
#     },
#     {
#         "close": "4828.000",
#         "ctm": "1727072640",
#         "ctmfmt": "2024-09-23 14:24:00",
#         "high": "4830.000",
#         "low": "4826.000",
#         "open": "4828.000",
#         "volume": "723",
#         "wave": 0
#     },
#     {
#         "close": "4824.000",
#         "ctm": "1727072700",
#         "ctmfmt": "2024-09-23 14:25:00",
#         "high": "4830.000",
#         "low": "4824.000",
#         "open": "4830.000",
#         "volume": "1003",
#         "wave": 0
#     },
#     {
#         "close": "4824.000",
#         "ctm": "1727072760",
#         "ctmfmt": "2024-09-23 14:26:00",
#         "high": "4826.000",
#         "low": "4824.000",
#         "open": "4824.000",
#         "volume": "1031",
#         "wave": 0
#     }
# ]
#     ready_data_10m = [
#         {
#             "close": "5520.000",
#             "ctm": "1723167600",
#             "ctmfmt": "2024-08-09 09:40:00",
#             "high": "5522.000",
#             "low": "5488.000",
#             "open": "5490.000",
#             "volume": "26237",
#             "wave": 0
#         },
#         {
#             "close": "5516.000",
#             "ctm": "1723168200",
#             "ctmfmt": "2024-08-09 09:50:00",
#             "high": "5526.000",
#             "low": "5516.000",
#             "open": "5518.000",
#             "volume": "28022",
#             "wave": 0
#         },
#         {
#             "close": "5520.000",
#             "ctm": "1723168800",
#             "ctmfmt": "2024-08-09 10:00:00",
#             "high": "5534.000",
#             "low": "5516.000",
#             "open": "5518.000",
#             "volume": "15839",
#             "wave": 0
#         },
#         {
#             "close": "5508.000",
#             "ctm": "1723169400",
#             "ctmfmt": "2024-08-09 10:10:00",
#             "high": "5520.000",
#             "low": "5502.000",
#             "open": "5520.000",
#             "volume": "14193",
#             "wave": 0
#         },
#         {
#             "close": "5518.000",
#             "ctm": "1723170900",
#             "ctmfmt": "2024-08-09 10:35:00",
#             "high": "5520.000",
#             "low": "5506.000",
#             "open": "5508.000",
#             "volume": "8359",
#             "wave": 0
#         },
#         {
#             "close": "5532.000",
#             "ctm": "1723171500",
#             "ctmfmt": "2024-08-09 10:45:00",
#             "high": "5532.000",
#             "low": "5514.000",
#             "open": "5518.000",
#             "volume": "17458",
#             "wave": 0
#         },
#         {
#             "close": "5542.000",
#             "ctm": "1723172100",
#             "ctmfmt": "2024-08-09 10:55:00",
#             "high": "5544.000",
#             "low": "5526.000",
#             "open": "5532.000",
#             "volume": "18497",
#             "wave": 0
#         },
#         {
#             "close": "5554.000",
#             "ctm": "1723172700",
#             "ctmfmt": "2024-08-09 11:05:00",
#             "high": "5556.000",
#             "low": "5542.000",
#             "open": "5542.000",
#             "volume": "21458",
#             "wave": 0
#         },
#         {
#             "close": "5562.000",
#             "ctm": "1723173300",
#             "ctmfmt": "2024-08-09 11:15:00",
#             "high": "5562.000",
#             "low": "5550.000",
#             "open": "5554.000",
#             "volume": "16568",
#             "wave": 0
#         },
#         {
#             "close": "5554.000",
#             "ctm": "1723173900",
#             "ctmfmt": "2024-08-09 11:25:00",
#             "high": "5568.000",
#             "low": "5554.000",
#             "open": "5562.000",
#             "volume": "16453",
#             "wave": 0
#         },
#         {
#             "close": "5530.000",
#             "ctm": "1723181700",
#             "ctmfmt": "2024-08-09 13:35:00",
#             "high": "5558.000",
#             "low": "5526.000",
#             "open": "5554.000",
#             "volume": "22220",
#             "wave": 0
#         },
#         {
#             "close": "5530.000",
#             "ctm": "1723182300",
#             "ctmfmt": "2024-08-09 13:45:00",
#             "high": "5532.000",
#             "low": "5520.000",
#             "open": "5528.000",
#             "volume": "13607",
#             "wave": 0
#         },
#         {
#             "close": "5526.000",
#             "ctm": "1723182900",
#             "ctmfmt": "2024-08-09 13:55:00",
#             "high": "5530.000",
#             "low": "5518.000",
#             "open": "5530.000",
#             "volume": "8850",
#             "wave": 0
#         },
#         {
#             "close": "5536.000",
#             "ctm": "1723183500",
#             "ctmfmt": "2024-08-09 14:05:00",
#             "high": "5536.000",
#             "low": "5526.000",
#             "open": "5526.000",
#             "volume": "8367",
#             "wave": 0
#         },
#         {
#             "close": "5524.000",
#             "ctm": "1723184100",
#             "ctmfmt": "2024-08-09 14:15:00",
#             "high": "5540.000",
#             "low": "5522.000",
#             "open": "5536.000",
#             "volume": "7123",
#             "wave": 0
#         },
#         {
#             "close": "5532.000",
#             "ctm": "1723184700",
#             "ctmfmt": "2024-08-09 14:25:00",
#             "high": "5534.000",
#             "low": "5524.000",
#             "open": "5524.000",
#             "volume": "6259",
#             "wave": 0
#         },
#         {
#             "close": "5528.000",
#             "ctm": "1723185300",
#             "ctmfmt": "2024-08-09 14:35:00",
#             "high": "5534.000",
#             "low": "5528.000",
#             "open": "5532.000",
#             "volume": "5554",
#             "wave": 0
#         },
#         {
#             "close": "5530.000",
#             "ctm": "1723185900",
#             "ctmfmt": "2024-08-09 14:45:00",
#             "high": "5532.000",
#             "low": "5524.000",
#             "open": "5528.000",
#             "volume": "4548",
#             "wave": 0
#         },
#         {
#             "close": "5536.000",
#             "ctm": "1723186500",
#             "ctmfmt": "2024-08-09 14:55:00",
#             "high": "5538.000",
#             "low": "5530.000",
#             "open": "5532.000",
#             "volume": "10637",
#             "wave": 0
#         },
#         {
#             "close": "5532.000",
#             "ctm": "1723186800",
#             "ctmfmt": "2024-08-09 15:00:00",
#             "high": "5538.000",
#             "low": "5530.000",
#             "open": "5536.000",
#             "volume": "10413",
#             "wave": 0
#         },
#         {
#             "close": "5528.000",
#             "ctm": "1723209000",
#             "ctmfmt": "2024-08-09 21:10:00",
#             "high": "5552.000",
#             "low": "5526.000",
#             "open": "5538.000",
#             "volume": "160452",
#             "wave": 0
#         },
#         {
#             "close": "5530.000",
#             "ctm": "1723209600",
#             "ctmfmt": "2024-08-09 21:20:00",
#             "high": "5540.000",
#             "low": "5522.000",
#             "open": "5526.000",
#             "volume": "36727",
#             "wave": 0
#         },
#         {
#             "close": "5526.000",
#             "ctm": "1723210200",
#             "ctmfmt": "2024-08-09 21:30:00",
#             "high": "5542.000",
#             "low": "5526.000",
#             "open": "5530.000",
#             "volume": "26634",
#             "wave": 0
#         },
#         {
#             "close": "5520.000",
#             "ctm": "1723210800",
#             "ctmfmt": "2024-08-09 21:40:00",
#             "high": "5528.000",
#             "low": "5514.000",
#             "open": "5528.000",
#             "volume": "35637",
#             "wave": 0
#         },
#         {
#             "close": "5518.000",
#             "ctm": "1723211400",
#             "ctmfmt": "2024-08-09 21:50:00",
#             "high": "5522.000",
#             "low": "5512.000",
#             "open": "5520.000",
#             "volume": "16496",
#             "wave": 0
#         },
#         {
#             "close": "5522.000",
#             "ctm": "1723212000",
#             "ctmfmt": "2024-08-09 22:00:00",
#             "high": "5532.000",
#             "low": "5516.000",
#             "open": "5518.000",
#             "volume": "24323",
#             "wave": 0
#         },
#         {
#             "close": "5524.000",
#             "ctm": "1723212600",
#             "ctmfmt": "2024-08-09 22:10:00",
#             "high": "5534.000",
#             "low": "5520.000",
#             "open": "5524.000",
#             "volume": "16298",
#             "wave": 0
#         },
#         {
#             "close": "5530.000",
#             "ctm": "1723213200",
#             "ctmfmt": "2024-08-09 22:20:00",
#             "high": "5536.000",
#             "low": "5524.000",
#             "open": "5524.000",
#             "volume": "20511",
#             "wave": 0
#         },
#         {
#             "close": "5532.000",
#             "ctm": "1723213800",
#             "ctmfmt": "2024-08-09 22:30:00",
#             "high": "5538.000",
#             "low": "5532.000",
#             "open": "5532.000",
#             "volume": "14480",
#             "wave": 0
#         },
#         {
#             "close": "5534.000",
#             "ctm": "1723214400",
#             "ctmfmt": "2024-08-09 22:40:00",
#             "high": "5540.000",
#             "low": "5530.000",
#             "open": "5532.000",
#             "volume": "14896",
#             "wave": 0
#         },
#         {
#             "close": "5528.000",
#             "ctm": "1723215000",
#             "ctmfmt": "2024-08-09 22:50:00",
#             "high": "5536.000",
#             "low": "5526.000",
#             "open": "5534.000",
#             "volume": "16968",
#             "wave": 0
#         },
#         {
#             "close": "5544.000",
#             "ctm": "1723215600",
#             "ctmfmt": "2024-08-09 23:00:00",
#             "high": "5544.000",
#             "low": "5528.000",
#             "open": "5528.000",
#             "volume": "20801",
#             "wave": 0
#         },
#         {
#             "close": "5528.000",
#             "ctm": "1723425000",
#             "ctmfmt": "2024-08-12 09:10:00",
#             "high": "5552.000",
#             "low": "5524.000",
#             "open": "5544.000",
#             "volume": "52945",
#             "wave": 0
#         },
#         {
#             "close": "5512.000",
#             "ctm": "1723425600",
#             "ctmfmt": "2024-08-12 09:20:00",
#             "high": "5530.000",
#             "low": "5508.000",
#             "open": "5528.000",
#             "volume": "32103",
#             "wave": 0
#         },
#         {
#             "close": "5518.000",
#             "ctm": "1723426200",
#             "ctmfmt": "2024-08-12 09:30:00",
#             "high": "5520.000",
#             "low": "5504.000",
#             "open": "5512.000",
#             "volume": "31059",
#             "wave": 0
#         },
#         {
#             "close": "5514.000",
#             "ctm": "1723426800",
#             "ctmfmt": "2024-08-12 09:40:00",
#             "high": "5520.000",
#             "low": "5502.000",
#             "open": "5520.000",
#             "volume": "33322",
#             "wave": 0
#         },
#         {
#             "close": "5518.000",
#             "ctm": "1723427400",
#             "ctmfmt": "2024-08-12 09:50:00",
#             "high": "5538.000",
#             "low": "5512.000",
#             "open": "5514.000",
#             "volume": "32724",
#             "wave": 0
#         },
#         {
#             "close": "5526.000",
#             "ctm": "1723428000",
#             "ctmfmt": "2024-08-12 10:00:00",
#             "high": "5530.000",
#             "low": "5516.000",
#             "open": "5518.000",
#             "volume": "16892",
#             "wave": 0
#         },
#         {
#             "close": "5526.000",
#             "ctm": "1723428600",
#             "ctmfmt": "2024-08-12 10:10:00",
#             "high": "5528.000",
#             "low": "5520.000",
#             "open": "5526.000",
#             "volume": "10943",
#             "wave": 0
#         },
#         {
#             "close": "5538.000",
#             "ctm": "1723430100",
#             "ctmfmt": "2024-08-12 10:35:00",
#             "high": "5538.000",
#             "low": "5522.000",
#             "open": "5524.000",
#             "volume": "25563",
#             "wave": 0
#         },
#         {
#             "close": "5532.000",
#             "ctm": "1723430700",
#             "ctmfmt": "2024-08-12 10:45:00",
#             "high": "5538.000",
#             "low": "5530.000",
#             "open": "5538.000",
#             "volume": "9436",
#             "wave": 0
#         },
#         {
#             "close": "5542.000",
#             "ctm": "1723431300",
#             "ctmfmt": "2024-08-12 10:55:00",
#             "high": "5544.000",
#             "low": "5530.000",
#             "open": "5530.000",
#             "volume": "10310",
#             "wave": 0
#         },
#         {
#             "close": "5534.000",
#             "ctm": "1723431900",
#             "ctmfmt": "2024-08-12 11:05:00",
#             "high": "5544.000",
#             "low": "5530.000",
#             "open": "5542.000",
#             "volume": "6452",
#             "wave": 0
#         },
#         {
#             "close": "5534.000",
#             "ctm": "1723432500",
#             "ctmfmt": "2024-08-12 11:15:00",
#             "high": "5534.000",
#             "low": "5524.000",
#             "open": "5532.000",
#             "volume": "9173",
#             "wave": 0
#         },
#         {
#             "close": "5536.000",
#             "ctm": "1723433100",
#             "ctmfmt": "2024-08-12 11:25:00",
#             "high": "5538.000",
#             "low": "5532.000",
#             "open": "5532.000",
#             "volume": "6235",
#             "wave": 0
#         },
#         {
#             "close": "5558.000",
#             "ctm": "1723440900",
#             "ctmfmt": "2024-08-12 13:35:00",
#             "high": "5558.000",
#             "low": "5534.000",
#             "open": "5536.000",
#             "volume": "23540",
#             "wave": 0
#         },
#         {
#             "close": "5558.000",
#             "ctm": "1723441500",
#             "ctmfmt": "2024-08-12 13:45:00",
#             "high": "5562.000",
#             "low": "5550.000",
#             "open": "5558.000",
#             "volume": "12996",
#             "wave": 0
#         },
#         {
#             "close": "5554.000",
#             "ctm": "1723442100",
#             "ctmfmt": "2024-08-12 13:55:00",
#             "high": "5564.000",
#             "low": "5552.000",
#             "open": "5556.000",
#             "volume": "12741",
#             "wave": 0
#         },
#         {
#             "close": "5562.000",
#             "ctm": "1723442700",
#             "ctmfmt": "2024-08-12 14:05:00",
#             "high": "5566.000",
#             "low": "5552.000",
#             "open": "5554.000",
#             "volume": "12074",
#             "wave": 0
#         },
#         {
#             "close": "5562.000",
#             "ctm": "1723443300",
#             "ctmfmt": "2024-08-12 14:15:00",
#             "high": "5566.000",
#             "low": "5558.000",
#             "open": "5564.000",
#             "volume": "6808",
#             "wave": 0
#         },
#         {
#             "close": "5568.000",
#             "ctm": "1723443900",
#             "ctmfmt": "2024-08-12 14:25:00",
#             "high": "5568.000",
#             "low": "5560.000",
#             "open": "5562.000",
#             "volume": "6681",
#             "wave": 0
#         },
#         {
#             "close": "5558.000",
#             "ctm": "1723444500",
#             "ctmfmt": "2024-08-12 14:35:00",
#             "high": "5568.000",
#             "low": "5556.000",
#             "open": "5568.000",
#             "volume": "7809",
#             "wave": 0
#         },
#         {
#             "close": "5562.000",
#             "ctm": "1723445100",
#             "ctmfmt": "2024-08-12 14:45:00",
#             "high": "5564.000",
#             "low": "5554.000",
#             "open": "5558.000",
#             "volume": "6370",
#             "wave": 0
#         },
#         {
#             "close": "5568.000",
#             "ctm": "1723445700",
#             "ctmfmt": "2024-08-12 14:55:00",
#             "high": "5572.000",
#             "low": "5560.000",
#             "open": "5562.000",
#             "volume": "10187",
#             "wave": 0
#         },
#         {
#             "close": "5572.000",
#             "ctm": "1723446000",
#             "ctmfmt": "2024-08-12 15:00:00",
#             "high": "5574.000",
#             "low": "5568.000",
#             "open": "5570.000",
#             "volume": "11566",
#             "wave": 0
#         },
#         {
#             "close": "5576.000",
#             "ctm": "1723468200",
#             "ctmfmt": "2024-08-12 21:10:00",
#             "high": "5594.000",
#             "low": "5574.000",
#             "open": "5586.000",
#             "volume": "115612",
#             "wave": 0
#         },
#         {
#             "close": "5566.000",
#             "ctm": "1723468800",
#             "ctmfmt": "2024-08-12 21:20:00",
#             "high": "5578.000",
#             "low": "5566.000",
#             "open": "5574.000",
#             "volume": "45370",
#             "wave": 0
#         },
#         {
#             "close": "5572.000",
#             "ctm": "1723469400",
#             "ctmfmt": "2024-08-12 21:30:00",
#             "high": "5578.000",
#             "low": "5564.000",
#             "open": "5568.000",
#             "volume": "20345",
#             "wave": 0
#         },
#         {
#             "close": "5580.000",
#             "ctm": "1723470000",
#             "ctmfmt": "2024-08-12 21:40:00",
#             "high": "5584.000",
#             "low": "5568.000",
#             "open": "5572.000",
#             "volume": "27654",
#             "wave": 0
#         },
#         {
#             "close": "5574.000",
#             "ctm": "1723470600",
#             "ctmfmt": "2024-08-12 21:50:00",
#             "high": "5582.000",
#             "low": "5572.000",
#             "open": "5580.000",
#             "volume": "16344",
#             "wave": 0
#         },
#         {
#             "close": "5570.000",
#             "ctm": "1723471200",
#             "ctmfmt": "2024-08-12 22:00:00",
#             "high": "5580.000",
#             "low": "5570.000",
#             "open": "5572.000",
#             "volume": "12636",
#             "wave": 0
#         },
#         {
#             "close": "5574.000",
#             "ctm": "1723471800",
#             "ctmfmt": "2024-08-12 22:10:00",
#             "high": "5574.000",
#             "low": "5568.000",
#             "open": "5570.000",
#             "volume": "13980",
#             "wave": 0
#         },
#         {
#             "close": "5568.000",
#             "ctm": "1723472400",
#             "ctmfmt": "2024-08-12 22:20:00",
#             "high": "5576.000",
#             "low": "5568.000",
#             "open": "5572.000",
#             "volume": "9834",
#             "wave": 0
#         },
#         {
#             "close": "5570.000",
#             "ctm": "1723473000",
#             "ctmfmt": "2024-08-12 22:30:00",
#             "high": "5570.000",
#             "low": "5566.000",
#             "open": "5570.000",
#             "volume": "10367",
#             "wave": 0
#         },
#         {
#             "close": "5574.000",
#             "ctm": "1723473600",
#             "ctmfmt": "2024-08-12 22:40:00",
#             "high": "5578.000",
#             "low": "5568.000",
#             "open": "5570.000",
#             "volume": "12777",
#             "wave": 0
#         },
#         {
#             "close": "5578.000",
#             "ctm": "1723474200",
#             "ctmfmt": "2024-08-12 22:50:00",
#             "high": "5580.000",
#             "low": "5572.000",
#             "open": "5574.000",
#             "volume": "11890",
#             "wave": 0
#         },
#         {
#             "close": "5620.000",
#             "ctm": "1723474800",
#             "ctmfmt": "2024-08-12 23:00:00",
#             "high": "5620.000",
#             "low": "5578.000",
#             "open": "5578.000",
#             "volume": "46044",
#             "wave": 0
#         },
#         {
#             "close": "5612.000",
#             "ctm": "1723511400",
#             "ctmfmt": "2024-08-13 09:10:00",
#             "high": "5620.000",
#             "low": "5598.000",
#             "open": "5620.000",
#             "volume": "115948",
#             "wave": 0
#         },
#         {
#             "close": "5610.000",
#             "ctm": "1723512000",
#             "ctmfmt": "2024-08-13 09:20:00",
#             "high": "5620.000",
#             "low": "5608.000",
#             "open": "5612.000",
#             "volume": "59554",
#             "wave": 0
#         },
#         {
#             "close": "5614.000",
#             "ctm": "1723512600",
#             "ctmfmt": "2024-08-13 09:30:00",
#             "high": "5614.000",
#             "low": "5604.000",
#             "open": "5610.000",
#             "volume": "21914",
#             "wave": 0
#         },
#         {
#             "close": "5604.000",
#             "ctm": "1723513200",
#             "ctmfmt": "2024-08-13 09:40:00",
#             "high": "5614.000",
#             "low": "5602.000",
#             "open": "5614.000",
#             "volume": "16056",
#             "wave": 0
#         },
#         {
#             "close": "5602.000",
#             "ctm": "1723513800",
#             "ctmfmt": "2024-08-13 09:50:00",
#             "high": "5610.000",
#             "low": "5600.000",
#             "open": "5604.000",
#             "volume": "12632",
#             "wave": 0
#         },
#         {
#             "close": "5598.000",
#             "ctm": "1723514400",
#             "ctmfmt": "2024-08-13 10:00:00",
#             "high": "5602.000",
#             "low": "5596.000",
#             "open": "5600.000",
#             "volume": "9607",
#             "wave": 0
#         },
#         {
#             "close": "5602.000",
#             "ctm": "1723515000",
#             "ctmfmt": "2024-08-13 10:10:00",
#             "high": "5604.000",
#             "low": "5594.000",
#             "open": "5598.000",
#             "volume": "11771",
#             "wave": 0
#         },
#         {
#             "close": "5602.000",
#             "ctm": "1723516500",
#             "ctmfmt": "2024-08-13 10:35:00",
#             "high": "5608.000",
#             "low": "5598.000",
#             "open": "5602.000",
#             "volume": "19271",
#             "wave": 0
#         },
#         {
#             "close": "5598.000",
#             "ctm": "1723517100",
#             "ctmfmt": "2024-08-13 10:45:00",
#             "high": "5608.000",
#             "low": "5596.000",
#             "open": "5602.000",
#             "volume": "15334",
#             "wave": 0
#         },
#         {
#             "close": "5598.000",
#             "ctm": "1723517700",
#             "ctmfmt": "2024-08-13 10:55:00",
#             "high": "5602.000",
#             "low": "5596.000",
#             "open": "5598.000",
#             "volume": "9329",
#             "wave": 0
#         },
#         {
#             "close": "5590.000",
#             "ctm": "1723518300",
#             "ctmfmt": "2024-08-13 11:05:00",
#             "high": "5600.000",
#             "low": "5590.000",
#             "open": "5598.000",
#             "volume": "24059",
#             "wave": 0
#         },
#         {
#             "close": "5594.000",
#             "ctm": "1723518900",
#             "ctmfmt": "2024-08-13 11:15:00",
#             "high": "5596.000",
#             "low": "5590.000",
#             "open": "5590.000",
#             "volume": "10808",
#             "wave": 0
#         },
#         {
#             "close": "5594.000",
#             "ctm": "1723519500",
#             "ctmfmt": "2024-08-13 11:25:00",
#             "high": "5596.000",
#             "low": "5588.000",
#             "open": "5594.000",
#             "volume": "16179",
#             "wave": 0
#         },
#         {
#             "close": "5588.000",
#             "ctm": "1723527300",
#             "ctmfmt": "2024-08-13 13:35:00",
#             "high": "5594.000",
#             "low": "5586.000",
#             "open": "5592.000",
#             "volume": "23537",
#             "wave": 0
#         },
#         {
#             "close": "5586.000",
#             "ctm": "1723527900",
#             "ctmfmt": "2024-08-13 13:45:00",
#             "high": "5592.000",
#             "low": "5582.000",
#             "open": "5588.000",
#             "volume": "20433",
#             "wave": 0
#         },
#         {
#             "close": "5588.000",
#             "ctm": "1723528500",
#             "ctmfmt": "2024-08-13 13:55:00",
#             "high": "5590.000",
#             "low": "5584.000",
#             "open": "5586.000",
#             "volume": "9520",
#             "wave": 0
#         },
#         {
#             "close": "5594.000",
#             "ctm": "1723529100",
#             "ctmfmt": "2024-08-13 14:05:00",
#             "high": "5598.000",
#             "low": "5588.000",
#             "open": "5588.000",
#             "volume": "15098",
#             "wave": 0
#         },
#         {
#             "close": "5586.000",
#             "ctm": "1723529700",
#             "ctmfmt": "2024-08-13 14:15:00",
#             "high": "5596.000",
#             "low": "5584.000",
#             "open": "5596.000",
#             "volume": "11148",
#             "wave": 0
#         },
#         {
#             "close": "5594.000",
#             "ctm": "1723530300",
#             "ctmfmt": "2024-08-13 14:25:00",
#             "high": "5596.000",
#             "low": "5586.000",
#             "open": "5588.000",
#             "volume": "10305",
#             "wave": 0
#         },
#         {
#             "close": "5596.000",
#             "ctm": "1723530900",
#             "ctmfmt": "2024-08-13 14:35:00",
#             "high": "5600.000",
#             "low": "5594.000",
#             "open": "5596.000",
#             "volume": "13026",
#             "wave": 0
#         },
#         {
#             "close": "5598.000",
#             "ctm": "1723531500",
#             "ctmfmt": "2024-08-13 14:45:00",
#             "high": "5606.000",
#             "low": "5596.000",
#             "open": "5596.000",
#             "volume": "11762",
#             "wave": 0
#         },
#         {
#             "close": "5602.000",
#             "ctm": "1723532100",
#             "ctmfmt": "2024-08-13 14:55:00",
#             "high": "5606.000",
#             "low": "5594.000",
#             "open": "5598.000",
#             "volume": "12572",
#             "wave": 0
#         },
#         {
#             "close": "5600.000",
#             "ctm": "1723532400",
#             "ctmfmt": "2024-08-13 15:00:00",
#             "high": "5604.000",
#             "low": "5596.000",
#             "open": "5602.000",
#             "volume": "9427",
#             "wave": 0
#         },
#         {
#             "close": "5610.000",
#             "ctm": "1723554600",
#             "ctmfmt": "2024-08-13 21:10:00",
#             "high": "5636.000",
#             "low": "5604.000",
#             "open": "5626.000",
#             "volume": "148676",
#             "wave": 0
#         },
#         {
#             "close": "5606.000",
#             "ctm": "1723555200",
#             "ctmfmt": "2024-08-13 21:20:00",
#             "high": "5626.000",
#             "low": "5606.000",
#             "open": "5610.000",
#             "volume": "39364",
#             "wave": 0
#         },
#         {
#             "close": "5626.000",
#             "ctm": "1723555800",
#             "ctmfmt": "2024-08-13 21:30:00",
#             "high": "5632.000",
#             "low": "5602.000",
#             "open": "5606.000",
#             "volume": "80472",
#             "wave": 0
#         },
#         {
#             "close": "5620.000",
#             "ctm": "1723556400",
#             "ctmfmt": "2024-08-13 21:40:00",
#             "high": "5628.000",
#             "low": "5618.000",
#             "open": "5626.000",
#             "volume": "20708",
#             "wave": 0
#         },
#         {
#             "close": "5612.000",
#             "ctm": "1723557000",
#             "ctmfmt": "2024-08-13 21:50:00",
#             "high": "5622.000",
#             "low": "5612.000",
#             "open": "5618.000",
#             "volume": "18005",
#             "wave": 0
#         },
#         {
#             "close": "5614.000",
#             "ctm": "1723557600",
#             "ctmfmt": "2024-08-13 22:00:00",
#             "high": "5618.000",
#             "low": "5612.000",
#             "open": "5612.000",
#             "volume": "13214",
#             "wave": 0
#         },
#         {
#             "close": "5610.000",
#             "ctm": "1723558200",
#             "ctmfmt": "2024-08-13 22:10:00",
#             "high": "5622.000",
#             "low": "5610.000",
#             "open": "5614.000",
#             "volume": "14617",
#             "wave": 0
#         },
#         {
#             "close": "5610.000",
#             "ctm": "1723558800",
#             "ctmfmt": "2024-08-13 22:20:00",
#             "high": "5612.000",
#             "low": "5606.000",
#             "open": "5610.000",
#             "volume": "17876",
#             "wave": 0
#         },
#         {
#             "close": "5608.000",
#             "ctm": "1723559400",
#             "ctmfmt": "2024-08-13 22:30:00",
#             "high": "5614.000",
#             "low": "5606.000",
#             "open": "5610.000",
#             "volume": "16331",
#             "wave": 0
#         },
#         {
#             "close": "5612.000",
#             "ctm": "1723560000",
#             "ctmfmt": "2024-08-13 22:40:00",
#             "high": "5612.000",
#             "low": "5602.000",
#             "open": "5608.000",
#             "volume": "12531",
#             "wave": 0
#         },
#         {
#             "close": "5620.000",
#             "ctm": "1723560600",
#             "ctmfmt": "2024-08-13 22:50:00",
#             "high": "5622.000",
#             "low": "5612.000",
#             "open": "5612.000",
#             "volume": "13945",
#             "wave": 0
#         },
#         {
#             "close": "5616.000",
#             "ctm": "1723561200",
#             "ctmfmt": "2024-08-13 23:00:00",
#             "high": "5620.000",
#             "low": "5614.000",
#             "open": "5620.000",
#             "volume": "31642",
#             "wave": 0
#         },
#         {
#             "close": "5598.000",
#             "ctm": "1723597800",
#             "ctmfmt": "2024-08-14 09:10:00",
#             "high": "5616.000",
#             "low": "5594.000",
#             "open": "5616.000",
#             "volume": "53536",
#             "wave": 0
#         },
#         {
#             "close": "5596.000",
#             "ctm": "1723598400",
#             "ctmfmt": "2024-08-14 09:20:00",
#             "high": "5604.000",
#             "low": "5578.000",
#             "open": "5600.000",
#             "volume": "96850",
#             "wave": 0
#         },
#         {
#             "close": "5612.000",
#             "ctm": "1723599000",
#             "ctmfmt": "2024-08-14 09:30:00",
#             "high": "5614.000",
#             "low": "5596.000",
#             "open": "5598.000",
#             "volume": "38963",
#             "wave": 0
#         },
#         {
#             "close": "5606.000",
#             "ctm": "1723599600",
#             "ctmfmt": "2024-08-14 09:40:00",
#             "high": "5618.000",
#             "low": "5602.000",
#             "open": "5612.000",
#             "volume": "22501",
#             "wave": 0
#         },
#         {
#             "close": "5618.000",
#             "ctm": "1723600200",
#             "ctmfmt": "2024-08-14 09:50:00",
#             "high": "5620.000",
#             "low": "5606.000",
#             "open": "5606.000",
#             "volume": "24379",
#             "wave": 0
#         },
#         {
#             "close": "5602.000",
#             "ctm": "1723600800",
#             "ctmfmt": "2024-08-14 10:00:00",
#             "high": "5620.000",
#             "low": "5600.000",
#             "open": "5616.000",
#             "volume": "26752",
#             "wave": 0
#         },
#         {
#             "close": "5598.000",
#             "ctm": "1723601400",
#             "ctmfmt": "2024-08-14 10:10:00",
#             "high": "5604.000",
#             "low": "5594.000",
#             "open": "5602.000",
#             "volume": "19339",
#             "wave": 0
#         },
#         {
#             "close": "5592.000",
#             "ctm": "1723602900",
#             "ctmfmt": "2024-08-14 10:35:00",
#             "high": "5600.000",
#             "low": "5590.000",
#             "open": "5598.000",
#             "volume": "17096",
#             "wave": 0
#         },
#         {
#             "close": "5596.000",
#             "ctm": "1723603500",
#             "ctmfmt": "2024-08-14 10:45:00",
#             "high": "5600.000",
#             "low": "5590.000",
#             "open": "5590.000",
#             "volume": "14354",
#             "wave": 0
#         },
#         {
#             "close": "5590.000",
#             "ctm": "1723604100",
#             "ctmfmt": "2024-08-14 10:55:00",
#             "high": "5598.000",
#             "low": "5588.000",
#             "open": "5596.000",
#             "volume": "9872",
#             "wave": 0
#         },
#         {
#             "close": "5578.000",
#             "ctm": "1723604700",
#             "ctmfmt": "2024-08-14 11:05:00",
#             "high": "5594.000",
#             "low": "5578.000",
#             "open": "5590.000",
#             "volume": "20527",
#             "wave": 0
#         },
#         {
#             "close": "5576.000",
#             "ctm": "1723605300",
#             "ctmfmt": "2024-08-14 11:15:00",
#             "high": "5586.000",
#             "low": "5576.000",
#             "open": "5580.000",
#             "volume": "9427",
#             "wave": 0
#         },
#         {
#             "close": "5576.000",
#             "ctm": "1723605900",
#             "ctmfmt": "2024-08-14 11:25:00",
#             "high": "5578.000",
#             "low": "5572.000",
#             "open": "5576.000",
#             "volume": "13958",
#             "wave": 0
#         },
#         {
#             "close": "5580.000",
#             "ctm": "1723613700",
#             "ctmfmt": "2024-08-14 13:35:00",
#             "high": "5584.000",
#             "low": "5572.000",
#             "open": "5578.000",
#             "volume": "20165",
#             "wave": 0
#         },
#         {
#             "close": "5576.000",
#             "ctm": "1723614300",
#             "ctmfmt": "2024-08-14 13:45:00",
#             "high": "5586.000",
#             "low": "5576.000",
#             "open": "5580.000",
#             "volume": "11834",
#             "wave": 0
#         },
#         {
#             "close": "5580.000",
#             "ctm": "1723614900",
#             "ctmfmt": "2024-08-14 13:55:00",
#             "high": "5582.000",
#             "low": "5576.000",
#             "open": "5576.000",
#             "volume": "5069",
#             "wave": 0
#         },
#         {
#             "close": "5586.000",
#             "ctm": "1723615500",
#             "ctmfmt": "2024-08-14 14:05:00",
#             "high": "5596.000",
#             "low": "5580.000",
#             "open": "5580.000",
#             "volume": "11937",
#             "wave": 0
#         },
#         {
#             "close": "5590.000",
#             "ctm": "1723616100",
#             "ctmfmt": "2024-08-14 14:15:00",
#             "high": "5590.000",
#             "low": "5580.000",
#             "open": "5586.000",
#             "volume": "5385",
#             "wave": 0
#         },
#         {
#             "close": "5588.000",
#             "ctm": "1723616700",
#             "ctmfmt": "2024-08-14 14:25:00",
#             "high": "5592.000",
#             "low": "5584.000",
#             "open": "5590.000",
#             "volume": "8135",
#             "wave": 0
#         },
#         {
#             "close": "5582.000",
#             "ctm": "1723617300",
#             "ctmfmt": "2024-08-14 14:35:00",
#             "high": "5592.000",
#             "low": "5582.000",
#             "open": "5588.000",
#             "volume": "6765",
#             "wave": 0
#         },
#         {
#             "close": "5582.000",
#             "ctm": "1723617900",
#             "ctmfmt": "2024-08-14 14:45:00",
#             "high": "5586.000",
#             "low": "5580.000",
#             "open": "5580.000",
#             "volume": "5354",
#             "wave": 0
#         },
#         {
#             "close": "5584.000",
#             "ctm": "1723618500",
#             "ctmfmt": "2024-08-14 14:55:00",
#             "high": "5588.000",
#             "low": "5580.000",
#             "open": "5582.000",
#             "volume": "9628",
#             "wave": 0
#         },
#         {
#             "close": "5580.000",
#             "ctm": "1723618800",
#             "ctmfmt": "2024-08-14 15:00:00",
#             "high": "5586.000",
#             "low": "5572.000",
#             "open": "5584.000",
#             "volume": "16316",
#             "wave": 0
#         },
#         {
#             "close": "5562.000",
#             "ctm": "1723641000",
#             "ctmfmt": "2024-08-14 21:10:00",
#             "high": "5580.000",
#             "low": "5554.000",
#             "open": "5576.000",
#             "volume": "53252",
#             "wave": 0
#         },
#         {
#             "close": "5576.000",
#             "ctm": "1723641600",
#             "ctmfmt": "2024-08-14 21:20:00",
#             "high": "5578.000",
#             "low": "5562.000",
#             "open": "5562.000",
#             "volume": "17528",
#             "wave": 0
#         },
#         {
#             "close": "5568.000",
#             "ctm": "1723642200",
#             "ctmfmt": "2024-08-14 21:30:00",
#             "high": "5576.000",
#             "low": "5562.000",
#             "open": "5576.000",
#             "volume": "10854",
#             "wave": 0
#         },
#         {
#             "close": "5576.000",
#             "ctm": "1723642800",
#             "ctmfmt": "2024-08-14 21:40:00",
#             "high": "5576.000",
#             "low": "5562.000",
#             "open": "5566.000",
#             "volume": "12409",
#             "wave": 0
#         },
#         {
#             "close": "5582.000",
#             "ctm": "1723643400",
#             "ctmfmt": "2024-08-14 21:50:00",
#             "high": "5584.000",
#             "low": "5572.000",
#             "open": "5578.000",
#             "volume": "16402",
#             "wave": 0
#         },
#         {
#             "close": "5570.000",
#             "ctm": "1723644000",
#             "ctmfmt": "2024-08-14 22:00:00",
#             "high": "5582.000",
#             "low": "5570.000",
#             "open": "5580.000",
#             "volume": "8841",
#             "wave": 0
#         },
#         {
#             "close": "5562.000",
#             "ctm": "1723644600",
#             "ctmfmt": "2024-08-14 22:10:00",
#             "high": "5572.000",
#             "low": "5562.000",
#             "open": "5570.000",
#             "volume": "9453",
#             "wave": 0
#         },
#         {
#             "close": "5556.000",
#             "ctm": "1723645200",
#             "ctmfmt": "2024-08-14 22:20:00",
#             "high": "5564.000",
#             "low": "5554.000",
#             "open": "5562.000",
#             "volume": "11132",
#             "wave": 0
#         },
#         {
#             "close": "5552.000",
#             "ctm": "1723645800",
#             "ctmfmt": "2024-08-14 22:30:00",
#             "high": "5556.000",
#             "low": "5546.000",
#             "open": "5556.000",
#             "volume": "14763",
#             "wave": 0
#         },
#         {
#             "close": "5534.000",
#             "ctm": "1723646400",
#             "ctmfmt": "2024-08-14 22:40:00",
#             "high": "5550.000",
#             "low": "5532.000",
#             "open": "5550.000",
#             "volume": "25246",
#             "wave": 0
#         },
#         {
#             "close": "5526.000",
#             "ctm": "1723647000",
#             "ctmfmt": "2024-08-14 22:50:00",
#             "high": "5538.000",
#             "low": "5522.000",
#             "open": "5534.000",
#             "volume": "30633",
#             "wave": 0
#         },
#         {
#             "close": "5522.000",
#             "ctm": "1723647600",
#             "ctmfmt": "2024-08-14 23:00:00",
#             "high": "5530.000",
#             "low": "5520.000",
#             "open": "5526.000",
#             "volume": "16511",
#             "wave": 0
#         },
#         {
#             "close": "5492.000",
#             "ctm": "1723684200",
#             "ctmfmt": "2024-08-15 09:10:00",
#             "high": "5524.000",
#             "low": "5492.000",
#             "open": "5520.000",
#             "volume": "51697",
#             "wave": 0
#         },
#         {
#             "close": "5496.000",
#             "ctm": "1723684800",
#             "ctmfmt": "2024-08-15 09:20:00",
#             "high": "5512.000",
#             "low": "5494.000",
#             "open": "5494.000",
#             "volume": "31361",
#             "wave": 0
#         },
#         {
#             "close": "5478.000",
#             "ctm": "1723685400",
#             "ctmfmt": "2024-08-15 09:30:00",
#             "high": "5496.000",
#             "low": "5476.000",
#             "open": "5494.000",
#             "volume": "31387",
#             "wave": 0
#         },
#         {
#             "close": "5470.000",
#             "ctm": "1723686000",
#             "ctmfmt": "2024-08-15 09:40:00",
#             "high": "5486.000",
#             "low": "5468.000",
#             "open": "5478.000",
#             "volume": "26590",
#             "wave": 0
#         },
#         {
#             "close": "5448.000",
#             "ctm": "1723686600",
#             "ctmfmt": "2024-08-15 09:50:00",
#             "high": "5474.000",
#             "low": "5446.000",
#             "open": "5470.000",
#             "volume": "39735",
#             "wave": 0
#         },
#         {
#             "close": "5464.000",
#             "ctm": "1723687200",
#             "ctmfmt": "2024-08-15 10:00:00",
#             "high": "5464.000",
#             "low": "5432.000",
#             "open": "5448.000",
#             "volume": "46930",
#             "wave": 0
#         },
#         {
#             "close": "5454.000",
#             "ctm": "1723687800",
#             "ctmfmt": "2024-08-15 10:10:00",
#             "high": "5478.000",
#             "low": "5452.000",
#             "open": "5464.000",
#             "volume": "27504",
#             "wave": 0
#         },
#         {
#             "close": "5504.000",
#             "ctm": "1723689300",
#             "ctmfmt": "2024-08-15 10:35:00",
#             "high": "5504.000",
#             "low": "5454.000",
#             "open": "5456.000",
#             "volume": "53334",
#             "wave": 0
#         },
#         {
#             "close": "5514.000",
#             "ctm": "1723689900",
#             "ctmfmt": "2024-08-15 10:45:00",
#             "high": "5518.000",
#             "low": "5496.000",
#             "open": "5504.000",
#             "volume": "40011",
#             "wave": 0
#         },
#         {
#             "close": "5496.000",
#             "ctm": "1723690500",
#             "ctmfmt": "2024-08-15 10:55:00",
#             "high": "5510.000",
#             "low": "5494.000",
#             "open": "5510.000",
#             "volume": "14369",
#             "wave": 0
#         },
#         {
#             "close": "5492.000",
#             "ctm": "1723691100",
#             "ctmfmt": "2024-08-15 11:05:00",
#             "high": "5504.000",
#             "low": "5486.000",
#             "open": "5494.000",
#             "volume": "19903",
#             "wave": 0
#         },
#         {
#             "close": "5496.000",
#             "ctm": "1723691700",
#             "ctmfmt": "2024-08-15 11:15:00",
#             "high": "5506.000",
#             "low": "5490.000",
#             "open": "5492.000",
#             "volume": "16067",
#             "wave": 0
#         },
#         {
#             "close": "5482.000",
#             "ctm": "1723692300",
#             "ctmfmt": "2024-08-15 11:25:00",
#             "high": "5500.000",
#             "low": "5482.000",
#             "open": "5496.000",
#             "volume": "10811",
#             "wave": 0
#         }
#     ]
#     ready_data_15m = [
#         {
#             "close": "5846.000",
#             "ctm": "1721312100",
#             "ctmfmt": "2024-07-18 22:15:00",
#             "high": "5848.000",
#             "low": "5840.000",
#             "open": "5844.000",
#             "volume": "7762",
#             "wave": 0
#         },
#         {
#             "close": "5844.000",
#             "ctm": "1721313000",
#             "ctmfmt": "2024-07-18 22:30:00",
#             "high": "5846.000",
#             "low": "5840.000",
#             "open": "5846.000",
#             "volume": "5225",
#             "wave": 0
#         },
#         {
#             "close": "5842.000",
#             "ctm": "1721313900",
#             "ctmfmt": "2024-07-18 22:45:00",
#             "high": "5850.000",
#             "low": "5842.000",
#             "open": "5844.000",
#             "volume": "8793",
#             "wave": 0
#         },
#         {
#             "close": "5846.000",
#             "ctm": "1721314800",
#             "ctmfmt": "2024-07-18 23:00:00",
#             "high": "5846.000",
#             "low": "5840.000",
#             "open": "5844.000",
#             "volume": "14217",
#             "wave": 0
#         },
#         {
#             "close": "5844.000",
#             "ctm": "1721351700",
#             "ctmfmt": "2024-07-19 09:15:00",
#             "high": "5846.000",
#             "low": "5834.000",
#             "open": "5840.000",
#             "volume": "32538",
#             "wave": 0
#         },
#         {
#             "close": "5836.000",
#             "ctm": "1721352600",
#             "ctmfmt": "2024-07-19 09:30:00",
#             "high": "5848.000",
#             "low": "5836.000",
#             "open": "5844.000",
#             "volume": "23136",
#             "wave": 0
#         },
#         {
#             "close": "5834.000",
#             "ctm": "1721353500",
#             "ctmfmt": "2024-07-19 09:45:00",
#             "high": "5840.000",
#             "low": "5832.000",
#             "open": "5836.000",
#             "volume": "15172",
#             "wave": 0
#         },
#         {
#             "close": "5836.000",
#             "ctm": "1721354400",
#             "ctmfmt": "2024-07-19 10:00:00",
#             "high": "5838.000",
#             "low": "5834.000",
#             "open": "5836.000",
#             "volume": "6967",
#             "wave": 0
#         },
#         {
#             "close": "5838.000",
#             "ctm": "1721355300",
#             "ctmfmt": "2024-07-19 10:15:00",
#             "high": "5844.000",
#             "low": "5834.000",
#             "open": "5836.000",
#             "volume": "12133",
#             "wave": 0
#         },
#         {
#             "close": "5836.000",
#             "ctm": "1721357100",
#             "ctmfmt": "2024-07-19 10:45:00",
#             "high": "5842.000",
#             "low": "5834.000",
#             "open": "5840.000",
#             "volume": "8567",
#             "wave": 0
#         },
#         {
#             "close": "5836.000",
#             "ctm": "1721358000",
#             "ctmfmt": "2024-07-19 11:00:00",
#             "high": "5842.000",
#             "low": "5836.000",
#             "open": "5836.000",
#             "volume": "6213",
#             "wave": 0
#         },
#         {
#             "close": "5838.000",
#             "ctm": "1721358900",
#             "ctmfmt": "2024-07-19 11:15:00",
#             "high": "5838.000",
#             "low": "5834.000",
#             "open": "5838.000",
#             "volume": "12411",
#             "wave": 0
#         },
#         {
#             "close": "5848.000",
#             "ctm": "1721359800",
#             "ctmfmt": "2024-07-19 11:30:00",
#             "high": "5850.000",
#             "low": "5836.000",
#             "open": "5838.000",
#             "volume": "21742",
#             "wave": 0
#         },
#         {
#             "close": "5850.000",
#             "ctm": "1721367900",
#             "ctmfmt": "2024-07-19 13:45:00",
#             "high": "5854.000",
#             "low": "5846.000",
#             "open": "5848.000",
#             "volume": "30417",
#             "wave": 0
#         },
#         {
#             "close": "5848.000",
#             "ctm": "1721368800",
#             "ctmfmt": "2024-07-19 14:00:00",
#             "high": "5854.000",
#             "low": "5846.000",
#             "open": "5850.000",
#             "volume": "13510",
#             "wave": 0
#         },
#         {
#             "close": "5848.000",
#             "ctm": "1721369700",
#             "ctmfmt": "2024-07-19 14:15:00",
#             "high": "5850.000",
#             "low": "5844.000",
#             "open": "5848.000",
#             "volume": "7738",
#             "wave": 0
#         },
#         {
#             "close": "5848.000",
#             "ctm": "1721370600",
#             "ctmfmt": "2024-07-19 14:30:00",
#             "high": "5852.000",
#             "low": "5846.000",
#             "open": "5848.000",
#             "volume": "8753",
#             "wave": 0
#         },
#         {
#             "close": "5844.000",
#             "ctm": "1721371500",
#             "ctmfmt": "2024-07-19 14:45:00",
#             "high": "5848.000",
#             "low": "5842.000",
#             "open": "5848.000",
#             "volume": "8946",
#             "wave": 0
#         },
#         {
#             "close": "5842.000",
#             "ctm": "1721372400",
#             "ctmfmt": "2024-07-19 15:00:00",
#             "high": "5848.000",
#             "low": "5838.000",
#             "open": "5842.000",
#             "volume": "22194",
#             "wave": 0
#         },
#         {
#             "close": "5842.000",
#             "ctm": "1721394900",
#             "ctmfmt": "2024-07-19 21:15:00",
#             "high": "5858.000",
#             "low": "5840.000",
#             "open": "5854.000",
#             "volume": "200179",
#             "wave": 0
#         },
#         {
#             "close": "5832.000",
#             "ctm": "1721395800",
#             "ctmfmt": "2024-07-19 21:30:00",
#             "high": "5846.000",
#             "low": "5832.000",
#             "open": "5844.000",
#             "volume": "80969",
#             "wave": 0
#         },
#         {
#             "close": "5838.000",
#             "ctm": "1721396700",
#             "ctmfmt": "2024-07-19 21:45:00",
#             "high": "5840.000",
#             "low": "5832.000",
#             "open": "5832.000",
#             "volume": "55259",
#             "wave": 0
#         },
#         {
#             "close": "5848.000",
#             "ctm": "1721397600",
#             "ctmfmt": "2024-07-19 22:00:00",
#             "high": "5848.000",
#             "low": "5836.000",
#             "open": "5838.000",
#             "volume": "47041",
#             "wave": 0
#         },
#         {
#             "close": "5846.000",
#             "ctm": "1721398500",
#             "ctmfmt": "2024-07-19 22:15:00",
#             "high": "5848.000",
#             "low": "5842.000",
#             "open": "5846.000",
#             "volume": "37203",
#             "wave": 0
#         },
#         {
#             "close": "5840.000",
#             "ctm": "1721399400",
#             "ctmfmt": "2024-07-19 22:30:00",
#             "high": "5846.000",
#             "low": "5838.000",
#             "open": "5846.000",
#             "volume": "19831",
#             "wave": 0
#         },
#         {
#             "close": "5840.000",
#             "ctm": "1721400300",
#             "ctmfmt": "2024-07-19 22:45:00",
#             "high": "5844.000",
#             "low": "5838.000",
#             "open": "5840.000",
#             "volume": "31689",
#             "wave": 0
#         },
#         {
#             "close": "5820.000",
#             "ctm": "1721401200",
#             "ctmfmt": "2024-07-19 23:00:00",
#             "high": "5840.000",
#             "low": "5820.000",
#             "open": "5838.000",
#             "volume": "96867",
#             "wave": 0
#         },
#         {
#             "close": "5822.000",
#             "ctm": "1721610900",
#             "ctmfmt": "2024-07-22 09:15:00",
#             "high": "5826.000",
#             "low": "5810.000",
#             "open": "5820.000",
#             "volume": "308956",
#             "wave": 0
#         },
#         {
#             "close": "5818.000",
#             "ctm": "1721611800",
#             "ctmfmt": "2024-07-22 09:30:00",
#             "high": "5826.000",
#             "low": "5814.000",
#             "open": "5822.000",
#             "volume": "125569",
#             "wave": 0
#         },
#         {
#             "close": "5812.000",
#             "ctm": "1721612700",
#             "ctmfmt": "2024-07-22 09:45:00",
#             "high": "5820.000",
#             "low": "5812.000",
#             "open": "5816.000",
#             "volume": "62906",
#             "wave": 0
#         },
#         {
#             "close": "5812.000",
#             "ctm": "1721613600",
#             "ctmfmt": "2024-07-22 10:00:00",
#             "high": "5816.000",
#             "low": "5812.000",
#             "open": "5812.000",
#             "volume": "51798",
#             "wave": 0
#         },
#         {
#             "close": "5810.000",
#             "ctm": "1721614500",
#             "ctmfmt": "2024-07-22 10:15:00",
#             "high": "5820.000",
#             "low": "5808.000",
#             "open": "5812.000",
#             "volume": "48275",
#             "wave": 0
#         },
#         {
#             "close": "5820.000",
#             "ctm": "1721616300",
#             "ctmfmt": "2024-07-22 10:45:00",
#             "high": "5824.000",
#             "low": "5810.000",
#             "open": "5810.000",
#             "volume": "44876",
#             "wave": 0
#         },
#         {
#             "close": "5824.000",
#             "ctm": "1721617200",
#             "ctmfmt": "2024-07-22 11:00:00",
#             "high": "5828.000",
#             "low": "5820.000",
#             "open": "5822.000",
#             "volume": "41174",
#             "wave": 0
#         },
#         {
#             "close": "5828.000",
#             "ctm": "1721618100",
#             "ctmfmt": "2024-07-22 11:15:00",
#             "high": "5836.000",
#             "low": "5822.000",
#             "open": "5824.000",
#             "volume": "49768",
#             "wave": 0
#         },
#         {
#             "close": "5832.000",
#             "ctm": "1721619000",
#             "ctmfmt": "2024-07-22 11:30:00",
#             "high": "5836.000",
#             "low": "5826.000",
#             "open": "5828.000",
#             "volume": "33801",
#             "wave": 0
#         },
#         {
#             "close": "5840.000",
#             "ctm": "1721627100",
#             "ctmfmt": "2024-07-22 13:45:00",
#             "high": "5844.000",
#             "low": "5832.000",
#             "open": "5832.000",
#             "volume": "53061",
#             "wave": 0
#         },
#         {
#             "close": "5832.000",
#             "ctm": "1721628000",
#             "ctmfmt": "2024-07-22 14:00:00",
#             "high": "5842.000",
#             "low": "5828.000",
#             "open": "5842.000",
#             "volume": "36161",
#             "wave": 0
#         },
#         {
#             "close": "5828.000",
#             "ctm": "1721628900",
#             "ctmfmt": "2024-07-22 14:15:00",
#             "high": "5836.000",
#             "low": "5826.000",
#             "open": "5830.000",
#             "volume": "22751",
#             "wave": 0
#         },
#         {
#             "close": "5828.000",
#             "ctm": "1721629800",
#             "ctmfmt": "2024-07-22 14:30:00",
#             "high": "5834.000",
#             "low": "5824.000",
#             "open": "5828.000",
#             "volume": "20901",
#             "wave": 0
#         },
#         {
#             "close": "5828.000",
#             "ctm": "1721630700",
#             "ctmfmt": "2024-07-22 14:45:00",
#             "high": "5836.000",
#             "low": "5826.000",
#             "open": "5826.000",
#             "volume": "19949",
#             "wave": 0
#         },
#         {
#             "close": "5830.000",
#             "ctm": "1721631600",
#             "ctmfmt": "2024-07-22 15:00:00",
#             "high": "5832.000",
#             "low": "5824.000",
#             "open": "5826.000",
#             "volume": "18560",
#             "wave": 0
#         },
#         {
#             "close": "5818.000",
#             "ctm": "1721654100",
#             "ctmfmt": "2024-07-22 21:15:00",
#             "high": "5822.000",
#             "low": "5808.000",
#             "open": "5812.000",
#             "volume": "140392",
#             "wave": 0
#         },
#         {
#             "close": "5820.000",
#             "ctm": "1721655000",
#             "ctmfmt": "2024-07-22 21:30:00",
#             "high": "5822.000",
#             "low": "5816.000",
#             "open": "5818.000",
#             "volume": "20061",
#             "wave": 0
#         },
#         {
#             "close": "5816.000",
#             "ctm": "1721655900",
#             "ctmfmt": "2024-07-22 21:45:00",
#             "high": "5824.000",
#             "low": "5816.000",
#             "open": "5820.000",
#             "volume": "19464",
#             "wave": 0
#         },
#         {
#             "close": "5816.000",
#             "ctm": "1721656800",
#             "ctmfmt": "2024-07-22 22:00:00",
#             "high": "5820.000",
#             "low": "5814.000",
#             "open": "5816.000",
#             "volume": "19937",
#             "wave": 0
#         },
#         {
#             "close": "5824.000",
#             "ctm": "1721657700",
#             "ctmfmt": "2024-07-22 22:15:00",
#             "high": "5828.000",
#             "low": "5816.000",
#             "open": "5816.000",
#             "volume": "22865",
#             "wave": 0
#         },
#         {
#             "close": "5826.000",
#             "ctm": "1721658600",
#             "ctmfmt": "2024-07-22 22:30:00",
#             "high": "5830.000",
#             "low": "5822.000",
#             "open": "5824.000",
#             "volume": "24879",
#             "wave": 0
#         },
#         {
#             "close": "5822.000",
#             "ctm": "1721659500",
#             "ctmfmt": "2024-07-22 22:45:00",
#             "high": "5826.000",
#             "low": "5820.000",
#             "open": "5824.000",
#             "volume": "13634",
#             "wave": 0
#         },
#         {
#             "close": "5820.000",
#             "ctm": "1721660400",
#             "ctmfmt": "2024-07-22 23:00:00",
#             "high": "5822.000",
#             "low": "5818.000",
#             "open": "5820.000",
#             "volume": "21790",
#             "wave": 0
#         },
#         {
#             "close": "5824.000",
#             "ctm": "1721697300",
#             "ctmfmt": "2024-07-23 09:15:00",
#             "high": "5824.000",
#             "low": "5816.000",
#             "open": "5820.000",
#             "volume": "45646",
#             "wave": 0
#         },
#         {
#             "close": "5826.000",
#             "ctm": "1721698200",
#             "ctmfmt": "2024-07-23 09:30:00",
#             "high": "5828.000",
#             "low": "5820.000",
#             "open": "5822.000",
#             "volume": "24229",
#             "wave": 0
#         },
#         {
#             "close": "5830.000",
#             "ctm": "1721699100",
#             "ctmfmt": "2024-07-23 09:45:00",
#             "high": "5842.000",
#             "low": "5824.000",
#             "open": "5828.000",
#             "volume": "66718",
#             "wave": 0
#         },
#         {
#             "close": "5830.000",
#             "ctm": "1721700000",
#             "ctmfmt": "2024-07-23 10:00:00",
#             "high": "5834.000",
#             "low": "5826.000",
#             "open": "5830.000",
#             "volume": "22660",
#             "wave": 0
#         },
#         {
#             "close": "5830.000",
#             "ctm": "1721700900",
#             "ctmfmt": "2024-07-23 10:15:00",
#             "high": "5834.000",
#             "low": "5826.000",
#             "open": "5830.000",
#             "volume": "27783",
#             "wave": 0
#         },
#         {
#             "close": "5820.000",
#             "ctm": "1721702700",
#             "ctmfmt": "2024-07-23 10:45:00",
#             "high": "5830.000",
#             "low": "5818.000",
#             "open": "5830.000",
#             "volume": "23127",
#             "wave": 0
#         },
#         {
#             "close": "5820.000",
#             "ctm": "1721703600",
#             "ctmfmt": "2024-07-23 11:00:00",
#             "high": "5824.000",
#             "low": "5818.000",
#             "open": "5820.000",
#             "volume": "19253",
#             "wave": 0
#         },
#         {
#             "close": "5822.000",
#             "ctm": "1721704500",
#             "ctmfmt": "2024-07-23 11:15:00",
#             "high": "5824.000",
#             "low": "5820.000",
#             "open": "5820.000",
#             "volume": "12794",
#             "wave": 0
#         },
#         {
#             "close": "5824.000",
#             "ctm": "1721705400",
#             "ctmfmt": "2024-07-23 11:30:00",
#             "high": "5826.000",
#             "low": "5820.000",
#             "open": "5822.000",
#             "volume": "5257",
#             "wave": 0
#         },
#         {
#             "close": "5822.000",
#             "ctm": "1721713500",
#             "ctmfmt": "2024-07-23 13:45:00",
#             "high": "5828.000",
#             "low": "5820.000",
#             "open": "5824.000",
#             "volume": "9021",
#             "wave": 0
#         },
#         {
#             "close": "5818.000",
#             "ctm": "1721714400",
#             "ctmfmt": "2024-07-23 14:00:00",
#             "high": "5822.000",
#             "low": "5816.000",
#             "open": "5820.000",
#             "volume": "15161",
#             "wave": 0
#         },
#         {
#             "close": "5812.000",
#             "ctm": "1721715300",
#             "ctmfmt": "2024-07-23 14:15:00",
#             "high": "5820.000",
#             "low": "5808.000",
#             "open": "5820.000",
#             "volume": "27039",
#             "wave": 0
#         },
#         {
#             "close": "5816.000",
#             "ctm": "1721716200",
#             "ctmfmt": "2024-07-23 14:30:00",
#             "high": "5824.000",
#             "low": "5810.000",
#             "open": "5810.000",
#             "volume": "18170",
#             "wave": 0
#         },
#         {
#             "close": "5816.000",
#             "ctm": "1721717100",
#             "ctmfmt": "2024-07-23 14:45:00",
#             "high": "5818.000",
#             "low": "5812.000",
#             "open": "5816.000",
#             "volume": "9780",
#             "wave": 0
#         },
#         {
#             "close": "5810.000",
#             "ctm": "1721718000",
#             "ctmfmt": "2024-07-23 15:00:00",
#             "high": "5818.000",
#             "low": "5808.000",
#             "open": "5816.000",
#             "volume": "46524",
#             "wave": 0
#         },
#         {
#             "close": "5804.000",
#             "ctm": "1721740500",
#             "ctmfmt": "2024-07-23 21:15:00",
#             "high": "5808.000",
#             "low": "5798.000",
#             "open": "5800.000",
#             "volume": "75930",
#             "wave": 0
#         },
#         {
#             "close": "5804.000",
#             "ctm": "1721741400",
#             "ctmfmt": "2024-07-23 21:30:00",
#             "high": "5806.000",
#             "low": "5790.000",
#             "open": "5804.000",
#             "volume": "38806",
#             "wave": 0
#         },
#         {
#             "close": "5792.000",
#             "ctm": "1721742300",
#             "ctmfmt": "2024-07-23 21:45:00",
#             "high": "5810.000",
#             "low": "5792.000",
#             "open": "5804.000",
#             "volume": "25832",
#             "wave": 0
#         },
#         {
#             "close": "5784.000",
#             "ctm": "1721743200",
#             "ctmfmt": "2024-07-23 22:00:00",
#             "high": "5796.000",
#             "low": "5784.000",
#             "open": "5792.000",
#             "volume": "34110",
#             "wave": 0
#         },
#         {
#             "close": "5786.000",
#             "ctm": "1721744100",
#             "ctmfmt": "2024-07-23 22:15:00",
#             "high": "5790.000",
#             "low": "5784.000",
#             "open": "5784.000",
#             "volume": "14465",
#             "wave": 0
#         },
#         {
#             "close": "5790.000",
#             "ctm": "1721745000",
#             "ctmfmt": "2024-07-23 22:30:00",
#             "high": "5790.000",
#             "low": "5780.000",
#             "open": "5786.000",
#             "volume": "19692",
#             "wave": 0
#         },
#         {
#             "close": "5794.000",
#             "ctm": "1721745900",
#             "ctmfmt": "2024-07-23 22:45:00",
#             "high": "5798.000",
#             "low": "5788.000",
#             "open": "5790.000",
#             "volume": "9809",
#             "wave": 0
#         },
#         {
#             "close": "5784.000",
#             "ctm": "1721746800",
#             "ctmfmt": "2024-07-23 23:00:00",
#             "high": "5794.000",
#             "low": "5782.000",
#             "open": "5794.000",
#             "volume": "11643",
#             "wave": 0
#         },
#         {
#             "close": "5782.000",
#             "ctm": "1721783700",
#             "ctmfmt": "2024-07-24 09:15:00",
#             "high": "5790.000",
#             "low": "5782.000",
#             "open": "5788.000",
#             "volume": "18507",
#             "wave": 0
#         },
#         {
#             "close": "5778.000",
#             "ctm": "1721784600",
#             "ctmfmt": "2024-07-24 09:30:00",
#             "high": "5784.000",
#             "low": "5778.000",
#             "open": "5782.000",
#             "volume": "10125",
#             "wave": 0
#         },
#         {
#             "close": "5780.000",
#             "ctm": "1721785500",
#             "ctmfmt": "2024-07-24 09:45:00",
#             "high": "5788.000",
#             "low": "5778.000",
#             "open": "5780.000",
#             "volume": "13145",
#             "wave": 0
#         },
#         {
#             "close": "5776.000",
#             "ctm": "1721786400",
#             "ctmfmt": "2024-07-24 10:00:00",
#             "high": "5782.000",
#             "low": "5776.000",
#             "open": "5780.000",
#             "volume": "12106",
#             "wave": 0
#         },
#         {
#             "close": "5776.000",
#             "ctm": "1721787300",
#             "ctmfmt": "2024-07-24 10:15:00",
#             "high": "5780.000",
#             "low": "5774.000",
#             "open": "5776.000",
#             "volume": "10962",
#             "wave": 0
#         },
#         {
#             "close": "5776.000",
#             "ctm": "1721789100",
#             "ctmfmt": "2024-07-24 10:45:00",
#             "high": "5784.000",
#             "low": "5776.000",
#             "open": "5778.000",
#             "volume": "11381",
#             "wave": 0
#         },
#         {
#             "close": "5782.000",
#             "ctm": "1721790000",
#             "ctmfmt": "2024-07-24 11:00:00",
#             "high": "5782.000",
#             "low": "5774.000",
#             "open": "5778.000",
#             "volume": "11223",
#             "wave": 0
#         },
#         {
#             "close": "5784.000",
#             "ctm": "1721790900",
#             "ctmfmt": "2024-07-24 11:15:00",
#             "high": "5784.000",
#             "low": "5778.000",
#             "open": "5782.000",
#             "volume": "11713",
#             "wave": 0
#         },
#         {
#             "close": "5786.000",
#             "ctm": "1721791800",
#             "ctmfmt": "2024-07-24 11:30:00",
#             "high": "5790.000",
#             "low": "5782.000",
#             "open": "5784.000",
#             "volume": "10312",
#             "wave": 0
#         },
#         {
#             "close": "5780.000",
#             "ctm": "1721799900",
#             "ctmfmt": "2024-07-24 13:45:00",
#             "high": "5790.000",
#             "low": "5780.000",
#             "open": "5786.000",
#             "volume": "13746",
#             "wave": 0
#         },
#         {
#             "close": "5776.000",
#             "ctm": "1721800800",
#             "ctmfmt": "2024-07-24 14:00:00",
#             "high": "5784.000",
#             "low": "5774.000",
#             "open": "5780.000",
#             "volume": "17321",
#             "wave": 0
#         },
#         {
#             "close": "5796.000",
#             "ctm": "1721801700",
#             "ctmfmt": "2024-07-24 14:15:00",
#             "high": "5796.000",
#             "low": "5774.000",
#             "open": "5776.000",
#             "volume": "17883",
#             "wave": 0
#         },
#         {
#             "close": "5808.000",
#             "ctm": "1721802600",
#             "ctmfmt": "2024-07-24 14:30:00",
#             "high": "5810.000",
#             "low": "5794.000",
#             "open": "5796.000",
#             "volume": "34930",
#             "wave": 0
#         },
#         {
#             "close": "5810.000",
#             "ctm": "1721803500",
#             "ctmfmt": "2024-07-24 14:45:00",
#             "high": "5816.000",
#             "low": "5804.000",
#             "open": "5806.000",
#             "volume": "25897",
#             "wave": 0
#         },
#         {
#             "close": "5802.000",
#             "ctm": "1721804400",
#             "ctmfmt": "2024-07-24 15:00:00",
#             "high": "5812.000",
#             "low": "5800.000",
#             "open": "5810.000",
#             "volume": "22122",
#             "wave": 0
#         },
#         {
#             "close": "5796.000",
#             "ctm": "1721826900",
#             "ctmfmt": "2024-07-24 21:15:00",
#             "high": "5814.000",
#             "low": "5796.000",
#             "open": "5814.000",
#             "volume": "87176",
#             "wave": 0
#         },
#         {
#             "close": "5796.000",
#             "ctm": "1721827800",
#             "ctmfmt": "2024-07-24 21:30:00",
#             "high": "5804.000",
#             "low": "5790.000",
#             "open": "5798.000",
#             "volume": "37963",
#             "wave": 0
#         },
#         {
#             "close": "5794.000",
#             "ctm": "1721828700",
#             "ctmfmt": "2024-07-24 21:45:00",
#             "high": "5802.000",
#             "low": "5792.000",
#             "open": "5796.000",
#             "volume": "22041",
#             "wave": 0
#         },
#         {
#             "close": "5794.000",
#             "ctm": "1721829600",
#             "ctmfmt": "2024-07-24 22:00:00",
#             "high": "5798.000",
#             "low": "5792.000",
#             "open": "5794.000",
#             "volume": "16864",
#             "wave": 0
#         },
#         {
#             "close": "5792.000",
#             "ctm": "1721830500",
#             "ctmfmt": "2024-07-24 22:15:00",
#             "high": "5798.000",
#             "low": "5792.000",
#             "open": "5792.000",
#             "volume": "11955",
#             "wave": 0
#         },
#         {
#             "close": "5798.000",
#             "ctm": "1721831400",
#             "ctmfmt": "2024-07-24 22:30:00",
#             "high": "5798.000",
#             "low": "5792.000",
#             "open": "5794.000",
#             "volume": "7744",
#             "wave": 0
#         },
#         {
#             "close": "5792.000",
#             "ctm": "1721832300",
#             "ctmfmt": "2024-07-24 22:45:00",
#             "high": "5804.000",
#             "low": "5792.000",
#             "open": "5800.000",
#             "volume": "25335",
#             "wave": 0
#         },
#         {
#             "close": "5778.000",
#             "ctm": "1721833200",
#             "ctmfmt": "2024-07-24 23:00:00",
#             "high": "5792.000",
#             "low": "5774.000",
#             "open": "5792.000",
#             "volume": "55432",
#             "wave": 0
#         },
#         {
#             "close": "5768.000",
#             "ctm": "1721870100",
#             "ctmfmt": "2024-07-25 09:15:00",
#             "high": "5782.000",
#             "low": "5768.000",
#             "open": "5778.000",
#             "volume": "54015",
#             "wave": 0
#         },
#         {
#             "close": "5772.000",
#             "ctm": "1721871000",
#             "ctmfmt": "2024-07-25 09:30:00",
#             "high": "5774.000",
#             "low": "5766.000",
#             "open": "5768.000",
#             "volume": "20845",
#             "wave": 0
#         },
#         {
#             "close": "5768.000",
#             "ctm": "1721871900",
#             "ctmfmt": "2024-07-25 09:45:00",
#             "high": "5782.000",
#             "low": "5766.000",
#             "open": "5774.000",
#             "volume": "15642",
#             "wave": 0
#         },
#         {
#             "close": "5770.000",
#             "ctm": "1721872800",
#             "ctmfmt": "2024-07-25 10:00:00",
#             "high": "5770.000",
#             "low": "5766.000",
#             "open": "5770.000",
#             "volume": "7266",
#             "wave": 0
#         },
#         {
#             "close": "5754.000",
#             "ctm": "1721873700",
#             "ctmfmt": "2024-07-25 10:15:00",
#             "high": "5770.000",
#             "low": "5744.000",
#             "open": "5768.000",
#             "volume": "63742",
#             "wave": 0
#         },
#         {
#             "close": "5752.000",
#             "ctm": "1721875500",
#             "ctmfmt": "2024-07-25 10:45:00",
#             "high": "5758.000",
#             "low": "5738.000",
#             "open": "5754.000",
#             "volume": "63593",
#             "wave": 0
#         },
#         {
#             "close": "5744.000",
#             "ctm": "1721876400",
#             "ctmfmt": "2024-07-25 11:00:00",
#             "high": "5752.000",
#             "low": "5740.000",
#             "open": "5750.000",
#             "volume": "21688",
#             "wave": 0
#         },
#         {
#             "close": "5738.000",
#             "ctm": "1721877300",
#             "ctmfmt": "2024-07-25 11:15:00",
#             "high": "5744.000",
#             "low": "5738.000",
#             "open": "5744.000",
#             "volume": "13271",
#             "wave": 0
#         },
#         {
#             "close": "5748.000",
#             "ctm": "1721878200",
#             "ctmfmt": "2024-07-25 11:30:00",
#             "high": "5750.000",
#             "low": "5738.000",
#             "open": "5740.000",
#             "volume": "14279",
#             "wave": 0
#         },
#         {
#             "close": "5746.000",
#             "ctm": "1721886300",
#             "ctmfmt": "2024-07-25 13:45:00",
#             "high": "5750.000",
#             "low": "5740.000",
#             "open": "5746.000",
#             "volume": "14705",
#             "wave": 0
#         },
#         {
#             "close": "5744.000",
#             "ctm": "1721887200",
#             "ctmfmt": "2024-07-25 14:00:00",
#             "high": "5750.000",
#             "low": "5738.000",
#             "open": "5748.000",
#             "volume": "15199",
#             "wave": 0
#         },
#         {
#             "close": "5750.000",
#             "ctm": "1721888100",
#             "ctmfmt": "2024-07-25 14:15:00",
#             "high": "5752.000",
#             "low": "5740.000",
#             "open": "5744.000",
#             "volume": "14642",
#             "wave": 0
#         },
#         {
#             "close": "5748.000",
#             "ctm": "1721889000",
#             "ctmfmt": "2024-07-25 14:30:00",
#             "high": "5752.000",
#             "low": "5742.000",
#             "open": "5750.000",
#             "volume": "10941",
#             "wave": 0
#         },
#         {
#             "close": "5744.000",
#             "ctm": "1721889900",
#             "ctmfmt": "2024-07-25 14:45:00",
#             "high": "5748.000",
#             "low": "5738.000",
#             "open": "5746.000",
#             "volume": "10143",
#             "wave": 0
#         },
#         {
#             "close": "5734.000",
#             "ctm": "1721890800",
#             "ctmfmt": "2024-07-25 15:00:00",
#             "high": "5744.000",
#             "low": "5732.000",
#             "open": "5744.000",
#             "volume": "37724",
#             "wave": 0
#         },
#         {
#             "close": "5732.000",
#             "ctm": "1721913300",
#             "ctmfmt": "2024-07-25 21:15:00",
#             "high": "5738.000",
#             "low": "5706.000",
#             "open": "5728.000",
#             "volume": "475816",
#             "wave": 0
#         },
#         {
#             "close": "5738.000",
#             "ctm": "1721914200",
#             "ctmfmt": "2024-07-25 21:30:00",
#             "high": "5744.000",
#             "low": "5732.000",
#             "open": "5732.000",
#             "volume": "130430",
#             "wave": 0
#         },
#         {
#             "close": "5738.000",
#             "ctm": "1721915100",
#             "ctmfmt": "2024-07-25 21:45:00",
#             "high": "5740.000",
#             "low": "5730.000",
#             "open": "5738.000",
#             "volume": "111285",
#             "wave": 0
#         },
#         {
#             "close": "5722.000",
#             "ctm": "1721916000",
#             "ctmfmt": "2024-07-25 22:00:00",
#             "high": "5740.000",
#             "low": "5720.000",
#             "open": "5738.000",
#             "volume": "72897",
#             "wave": 0
#         },
#         {
#             "close": "5724.000",
#             "ctm": "1721916900",
#             "ctmfmt": "2024-07-25 22:15:00",
#             "high": "5726.000",
#             "low": "5718.000",
#             "open": "5722.000",
#             "volume": "76790",
#             "wave": 0
#         },
#         {
#             "close": "5734.000",
#             "ctm": "1721917800",
#             "ctmfmt": "2024-07-25 22:30:00",
#             "high": "5736.000",
#             "low": "5726.000",
#             "open": "5726.000",
#             "volume": "54127",
#             "wave": 0
#         },
#         {
#             "close": "5730.000",
#             "ctm": "1721918700",
#             "ctmfmt": "2024-07-25 22:45:00",
#             "high": "5734.000",
#             "low": "5726.000",
#             "open": "5732.000",
#             "volume": "38135",
#             "wave": 0
#         },
#         {
#             "close": "5752.000",
#             "ctm": "1721919600",
#             "ctmfmt": "2024-07-25 23:00:00",
#             "high": "5752.000",
#             "low": "5726.000",
#             "open": "5728.000",
#             "volume": "124611",
#             "wave": 0
#         },
#         {
#             "close": "5758.000",
#             "ctm": "1721956500",
#             "ctmfmt": "2024-07-26 09:15:00",
#             "high": "5762.000",
#             "low": "5750.000",
#             "open": "5752.000",
#             "volume": "253989",
#             "wave": 0
#         },
#         {
#             "close": "5770.000",
#             "ctm": "1721957400",
#             "ctmfmt": "2024-07-26 09:30:00",
#             "high": "5770.000",
#             "low": "5752.000",
#             "open": "5758.000",
#             "volume": "99657",
#             "wave": 0
#         },
#         {
#             "close": "5792.000",
#             "ctm": "1721958300",
#             "ctmfmt": "2024-07-26 09:45:00",
#             "high": "5792.000",
#             "low": "5766.000",
#             "open": "5770.000",
#             "volume": "161824",
#             "wave": 0
#         },
#         {
#             "close": "5802.000",
#             "ctm": "1721959200",
#             "ctmfmt": "2024-07-26 10:00:00",
#             "high": "5808.000",
#             "low": "5786.000",
#             "open": "5790.000",
#             "volume": "148959",
#             "wave": 0
#         },
#         {
#             "close": "5790.000",
#             "ctm": "1721960100",
#             "ctmfmt": "2024-07-26 10:15:00",
#             "high": "5800.000",
#             "low": "5786.000",
#             "open": "5800.000",
#             "volume": "87553",
#             "wave": 0
#         },
#         {
#             "close": "5788.000",
#             "ctm": "1721961900",
#             "ctmfmt": "2024-07-26 10:45:00",
#             "high": "5790.000",
#             "low": "5782.000",
#             "open": "5790.000",
#             "volume": "32020",
#             "wave": 0
#         },
#         {
#             "close": "5792.000",
#             "ctm": "1721962800",
#             "ctmfmt": "2024-07-26 11:00:00",
#             "high": "5796.000",
#             "low": "5788.000",
#             "open": "5788.000",
#             "volume": "22780",
#             "wave": 0
#         },
#         {
#             "close": "5798.000",
#             "ctm": "1721963700",
#             "ctmfmt": "2024-07-26 11:15:00",
#             "high": "5798.000",
#             "low": "5792.000",
#             "open": "5792.000",
#             "volume": "24456",
#             "wave": 0
#         },
#         {
#             "close": "5794.000",
#             "ctm": "1721964600",
#             "ctmfmt": "2024-07-26 11:30:00",
#             "high": "5802.000",
#             "low": "5794.000",
#             "open": "5798.000",
#             "volume": "22251",
#             "wave": 0
#         },
#         {
#             "close": "5788.000",
#             "ctm": "1721972700",
#             "ctmfmt": "2024-07-26 13:45:00",
#             "high": "5794.000",
#             "low": "5786.000",
#             "open": "5794.000",
#             "volume": "27987",
#             "wave": 0
#         },
#         {
#             "close": "5792.000",
#             "ctm": "1721973600",
#             "ctmfmt": "2024-07-26 14:00:00",
#             "high": "5794.000",
#             "low": "5782.000",
#             "open": "5788.000",
#             "volume": "25557",
#             "wave": 0
#         },
#         {
#             "close": "5790.000",
#             "ctm": "1721974500",
#             "ctmfmt": "2024-07-26 14:15:00",
#             "high": "5794.000",
#             "low": "5788.000",
#             "open": "5792.000",
#             "volume": "12541",
#             "wave": 0
#         },
#         {
#             "close": "5794.000",
#             "ctm": "1721975400",
#             "ctmfmt": "2024-07-26 14:30:00",
#             "high": "5796.000",
#             "low": "5788.000",
#             "open": "5788.000",
#             "volume": "18413",
#             "wave": 0
#         },
#         {
#             "close": "5798.000",
#             "ctm": "1721976300",
#             "ctmfmt": "2024-07-26 14:45:00",
#             "high": "5800.000",
#             "low": "5792.000",
#             "open": "5794.000",
#             "volume": "11817",
#             "wave": 0
#         },
#         {
#             "close": "5794.000",
#             "ctm": "1721977200",
#             "ctmfmt": "2024-07-26 15:00:00",
#             "high": "5800.000",
#             "low": "5792.000",
#             "open": "5798.000",
#             "volume": "21234",
#             "wave": 0
#         },
#         {
#             "close": "5788.000",
#             "ctm": "1721999700",
#             "ctmfmt": "2024-07-26 21:15:00",
#             "high": "5794.000",
#             "low": "5776.000",
#             "open": "5776.000",
#             "volume": "43770",
#             "wave": 0
#         },
#         {
#             "close": "5782.000",
#             "ctm": "1722000600",
#             "ctmfmt": "2024-07-26 21:30:00",
#             "high": "5792.000",
#             "low": "5780.000",
#             "open": "5790.000",
#             "volume": "19254",
#             "wave": 0
#         },
#         {
#             "close": "5788.000",
#             "ctm": "1722001500",
#             "ctmfmt": "2024-07-26 21:45:00",
#             "high": "5790.000",
#             "low": "5778.000",
#             "open": "5780.000",
#             "volume": "14517",
#             "wave": 0
#         },
#         {
#             "close": "5784.000",
#             "ctm": "1722002400",
#             "ctmfmt": "2024-07-26 22:00:00",
#             "high": "5792.000",
#             "low": "5780.000",
#             "open": "5790.000",
#             "volume": "7676",
#             "wave": 0
#         },
#         {
#             "close": "5776.000",
#             "ctm": "1722003300",
#             "ctmfmt": "2024-07-26 22:15:00",
#             "high": "5784.000",
#             "low": "5774.000",
#             "open": "5784.000",
#             "volume": "12732",
#             "wave": 0
#         },
#         {
#             "close": "5766.000",
#             "ctm": "1722004200",
#             "ctmfmt": "2024-07-26 22:30:00",
#             "high": "5778.000",
#             "low": "5764.000",
#             "open": "5778.000",
#             "volume": "27959",
#             "wave": 0
#         },
#         {
#             "close": "5762.000",
#             "ctm": "1722005100",
#             "ctmfmt": "2024-07-26 22:45:00",
#             "high": "5768.000",
#             "low": "5756.000",
#             "open": "5764.000",
#             "volume": "20607",
#             "wave": 0
#         },
#         {
#             "close": "5752.000",
#             "ctm": "1722006000",
#             "ctmfmt": "2024-07-26 23:00:00",
#             "high": "5768.000",
#             "low": "5750.000",
#             "open": "5762.000",
#             "volume": "16314",
#             "wave": 0
#         },
#         {
#             "close": "5788.000",
#             "ctm": "1722215700",
#             "ctmfmt": "2024-07-29 09:15:00",
#             "high": "5798.000",
#             "low": "5776.000",
#             "open": "5778.000",
#             "volume": "58858",
#             "wave": 0
#         },
#         {
#             "close": "5774.000",
#             "ctm": "1722216600",
#             "ctmfmt": "2024-07-29 09:30:00",
#             "high": "5790.000",
#             "low": "5774.000",
#             "open": "5788.000",
#             "volume": "18284",
#             "wave": 0
#         },
#         {
#             "close": "5770.000",
#             "ctm": "1722217500",
#             "ctmfmt": "2024-07-29 09:45:00",
#             "high": "5778.000",
#             "low": "5770.000",
#             "open": "5776.000",
#             "volume": "16885",
#             "wave": 0
#         },
#         {
#             "close": "5774.000",
#             "ctm": "1722218400",
#             "ctmfmt": "2024-07-29 10:00:00",
#             "high": "5774.000",
#             "low": "5768.000",
#             "open": "5770.000",
#             "volume": "12906",
#             "wave": 0
#         },
#         {
#             "close": "5764.000",
#             "ctm": "1722219300",
#             "ctmfmt": "2024-07-29 10:15:00",
#             "high": "5774.000",
#             "low": "5762.000",
#             "open": "5772.000",
#             "volume": "10162",
#             "wave": 0
#         },
#         {
#             "close": "5766.000",
#             "ctm": "1722221100",
#             "ctmfmt": "2024-07-29 10:45:00",
#             "high": "5768.000",
#             "low": "5760.000",
#             "open": "5764.000",
#             "volume": "10002",
#             "wave": 0
#         },
#         {
#             "close": "5764.000",
#             "ctm": "1722222000",
#             "ctmfmt": "2024-07-29 11:00:00",
#             "high": "5768.000",
#             "low": "5760.000",
#             "open": "5766.000",
#             "volume": "13941",
#             "wave": 0
#         },
#         {
#             "close": "5762.000",
#             "ctm": "1722222900",
#             "ctmfmt": "2024-07-29 11:15:00",
#             "high": "5768.000",
#             "low": "5756.000",
#             "open": "5764.000",
#             "volume": "9316",
#             "wave": 0
#         },
#         {
#             "close": "5774.000",
#             "ctm": "1722223800",
#             "ctmfmt": "2024-07-29 11:30:00",
#             "high": "5776.000",
#             "low": "5758.000",
#             "open": "5760.000",
#             "volume": "9204",
#             "wave": 0
#         },
#         {
#             "close": "5782.000",
#             "ctm": "1722231900",
#             "ctmfmt": "2024-07-29 13:45:00",
#             "high": "5784.000",
#             "low": "5776.000",
#             "open": "5780.000",
#             "volume": "17388",
#             "wave": 0
#         },
#         {
#             "close": "5784.000",
#             "ctm": "1722232800",
#             "ctmfmt": "2024-07-29 14:00:00",
#             "high": "5790.000",
#             "low": "5780.000",
#             "open": "5780.000",
#             "volume": "14511",
#             "wave": 0
#         },
#         {
#             "close": "5786.000",
#             "ctm": "1722233700",
#             "ctmfmt": "2024-07-29 14:15:00",
#             "high": "5788.000",
#             "low": "5782.000",
#             "open": "5782.000",
#             "volume": "8138",
#             "wave": 0
#         },
#         {
#             "close": "5780.000",
#             "ctm": "1722234600",
#             "ctmfmt": "2024-07-29 14:30:00",
#             "high": "5786.000",
#             "low": "5778.000",
#             "open": "5784.000",
#             "volume": "7040",
#             "wave": 0
#         },
#         {
#             "close": "5778.000",
#             "ctm": "1722235500",
#             "ctmfmt": "2024-07-29 14:45:00",
#             "high": "5784.000",
#             "low": "5776.000",
#             "open": "5780.000",
#             "volume": "7238",
#             "wave": 0
#         },
#         {
#             "close": "5768.000",
#             "ctm": "1722236400",
#             "ctmfmt": "2024-07-29 15:00:00",
#             "high": "5778.000",
#             "low": "5764.000",
#             "open": "5776.000",
#             "volume": "22321",
#             "wave": 0
#         },
#         {
#             "close": "5750.000",
#             "ctm": "1722258900",
#             "ctmfmt": "2024-07-29 21:15:00",
#             "high": "5764.000",
#             "low": "5744.000",
#             "open": "5762.000",
#             "volume": "55484",
#             "wave": 0
#         },
#         {
#             "close": "5752.000",
#             "ctm": "1722259800",
#             "ctmfmt": "2024-07-29 21:30:00",
#             "high": "5756.000",
#             "low": "5744.000",
#             "open": "5748.000",
#             "volume": "18168",
#             "wave": 0
#         },
#         {
#             "close": "5746.000",
#             "ctm": "1722260700",
#             "ctmfmt": "2024-07-29 21:45:00",
#             "high": "5756.000",
#             "low": "5744.000",
#             "open": "5752.000",
#             "volume": "16032",
#             "wave": 0
#         },
#         {
#             "close": "5748.000",
#             "ctm": "1722261600",
#             "ctmfmt": "2024-07-29 22:00:00",
#             "high": "5752.000",
#             "low": "5744.000",
#             "open": "5746.000",
#             "volume": "12240",
#             "wave": 0
#         },
#         {
#             "close": "5746.000",
#             "ctm": "1722262500",
#             "ctmfmt": "2024-07-29 22:15:00",
#             "high": "5756.000",
#             "low": "5746.000",
#             "open": "5748.000",
#             "volume": "9657",
#             "wave": 0
#         },
#         {
#             "close": "5746.000",
#             "ctm": "1722263400",
#             "ctmfmt": "2024-07-29 22:30:00",
#             "high": "5748.000",
#             "low": "5740.000",
#             "open": "5746.000",
#             "volume": "8426",
#             "wave": 0
#         },
#         {
#             "close": "5738.000",
#             "ctm": "1722264300",
#             "ctmfmt": "2024-07-29 22:45:00",
#             "high": "5746.000",
#             "low": "5736.000",
#             "open": "5746.000",
#             "volume": "12797",
#             "wave": 0
#         },
#         {
#             "close": "5734.000",
#             "ctm": "1722265200",
#             "ctmfmt": "2024-07-29 23:00:00",
#             "high": "5740.000",
#             "low": "5730.000",
#             "open": "5738.000",
#             "volume": "13657",
#             "wave": 0
#         },
#         {
#             "close": "5710.000",
#             "ctm": "1722302100",
#             "ctmfmt": "2024-07-30 09:15:00",
#             "high": "5730.000",
#             "low": "5710.000",
#             "open": "5730.000",
#             "volume": "39475",
#             "wave": 0
#         },
#         {
#             "close": "5716.000",
#             "ctm": "1722303000",
#             "ctmfmt": "2024-07-30 09:30:00",
#             "high": "5720.000",
#             "low": "5704.000",
#             "open": "5710.000",
#             "volume": "35454",
#             "wave": 0
#         },
#         {
#             "close": "5714.000",
#             "ctm": "1722303900",
#             "ctmfmt": "2024-07-30 09:45:00",
#             "high": "5726.000",
#             "low": "5714.000",
#             "open": "5718.000",
#             "volume": "18484",
#             "wave": 0
#         },
#         {
#             "close": "5710.000",
#             "ctm": "1722304800",
#             "ctmfmt": "2024-07-30 10:00:00",
#             "high": "5716.000",
#             "low": "5708.000",
#             "open": "5716.000",
#             "volume": "14979",
#             "wave": 0
#         },
#         {
#             "close": "5704.000",
#             "ctm": "1722305700",
#             "ctmfmt": "2024-07-30 10:15:00",
#             "high": "5712.000",
#             "low": "5702.000",
#             "open": "5708.000",
#             "volume": "20550",
#             "wave": 0
#         },
#         {
#             "close": "5710.000",
#             "ctm": "1722307500",
#             "ctmfmt": "2024-07-30 10:45:00",
#             "high": "5712.000",
#             "low": "5702.000",
#             "open": "5704.000",
#             "volume": "17323",
#             "wave": 0
#         },
#         {
#             "close": "5700.000",
#             "ctm": "1722308400",
#             "ctmfmt": "2024-07-30 11:00:00",
#             "high": "5718.000",
#             "low": "5698.000",
#             "open": "5712.000",
#             "volume": "24079",
#             "wave": 0
#         },
#         {
#             "close": "5702.000",
#             "ctm": "1722309300",
#             "ctmfmt": "2024-07-30 11:15:00",
#             "high": "5706.000",
#             "low": "5698.000",
#             "open": "5698.000",
#             "volume": "9443",
#             "wave": 0
#         },
#         {
#             "close": "5698.000",
#             "ctm": "1722310200",
#             "ctmfmt": "2024-07-30 11:30:00",
#             "high": "5704.000",
#             "low": "5694.000",
#             "open": "5702.000",
#             "volume": "11688",
#             "wave": 0
#         },
#         {
#             "close": "5704.000",
#             "ctm": "1722318300",
#             "ctmfmt": "2024-07-30 13:45:00",
#             "high": "5706.000",
#             "low": "5688.000",
#             "open": "5698.000",
#             "volume": "30585",
#             "wave": 0
#         },
#         {
#             "close": "5692.000",
#             "ctm": "1722319200",
#             "ctmfmt": "2024-07-30 14:00:00",
#             "high": "5706.000",
#             "low": "5686.000",
#             "open": "5702.000",
#             "volume": "22337",
#             "wave": 0
#         },
#         {
#             "close": "5696.000",
#             "ctm": "1722320100",
#             "ctmfmt": "2024-07-30 14:15:00",
#             "high": "5698.000",
#             "low": "5688.000",
#             "open": "5692.000",
#             "volume": "13711",
#             "wave": 0
#         },
#         {
#             "close": "5692.000",
#             "ctm": "1722321000",
#             "ctmfmt": "2024-07-30 14:30:00",
#             "high": "5698.000",
#             "low": "5686.000",
#             "open": "5698.000",
#             "volume": "12087",
#             "wave": 0
#         },
#         {
#             "close": "5690.000",
#             "ctm": "1722321900",
#             "ctmfmt": "2024-07-30 14:45:00",
#             "high": "5694.000",
#             "low": "5688.000",
#             "open": "5694.000",
#             "volume": "10781",
#             "wave": 0
#         },
#         {
#             "close": "5698.000",
#             "ctm": "1722322800",
#             "ctmfmt": "2024-07-30 15:00:00",
#             "high": "5700.000",
#             "low": "5682.000",
#             "open": "5688.000",
#             "volume": "29201",
#             "wave": 0
#         },
#         {
#             "close": "5702.000",
#             "ctm": "1722345300",
#             "ctmfmt": "2024-07-30 21:15:00",
#             "high": "5708.000",
#             "low": "5684.000",
#             "open": "5690.000",
#             "volume": "77379",
#             "wave": 0
#         },
#         {
#             "close": "5704.000",
#             "ctm": "1722346200",
#             "ctmfmt": "2024-07-30 21:30:00",
#             "high": "5708.000",
#             "low": "5698.000",
#             "open": "5706.000",
#             "volume": "17918",
#             "wave": 0
#         },
#         {
#             "close": "5696.000",
#             "ctm": "1722347100",
#             "ctmfmt": "2024-07-30 21:45:00",
#             "high": "5708.000",
#             "low": "5696.000",
#             "open": "5704.000",
#             "volume": "14968",
#             "wave": 0
#         },
#         {
#             "close": "5690.000",
#             "ctm": "1722348000",
#             "ctmfmt": "2024-07-30 22:00:00",
#             "high": "5698.000",
#             "low": "5686.000",
#             "open": "5698.000",
#             "volume": "13642",
#             "wave": 0
#         },
#         {
#             "close": "5694.000",
#             "ctm": "1722348900",
#             "ctmfmt": "2024-07-30 22:15:00",
#             "high": "5700.000",
#             "low": "5686.000",
#             "open": "5690.000",
#             "volume": "15336",
#             "wave": 0
#         },
#         {
#             "close": "5708.000",
#             "ctm": "1722349800",
#             "ctmfmt": "2024-07-30 22:30:00",
#             "high": "5708.000",
#             "low": "5694.000",
#             "open": "5694.000",
#             "volume": "14112",
#             "wave": 0
#         },
#         {
#             "close": "5702.000",
#             "ctm": "1722350700",
#             "ctmfmt": "2024-07-30 22:45:00",
#             "high": "5716.000",
#             "low": "5700.000",
#             "open": "5708.000",
#             "volume": "16126",
#             "wave": 0
#         },
#         {
#             "close": "5694.000",
#             "ctm": "1722351600",
#             "ctmfmt": "2024-07-30 23:00:00",
#             "high": "5704.000",
#             "low": "5692.000",
#             "open": "5700.000",
#             "volume": "14736",
#             "wave": 0
#         },
#         {
#             "close": "5698.000",
#             "ctm": "1722388500",
#             "ctmfmt": "2024-07-31 09:15:00",
#             "high": "5710.000",
#             "low": "5698.000",
#             "open": "5700.000",
#             "volume": "20200",
#             "wave": 0
#         },
#         {
#             "close": "5714.000",
#             "ctm": "1722389400",
#             "ctmfmt": "2024-07-31 09:30:00",
#             "high": "5714.000",
#             "low": "5698.000",
#             "open": "5698.000",
#             "volume": "19805",
#             "wave": 0
#         },
#         {
#             "close": "5720.000",
#             "ctm": "1722390300",
#             "ctmfmt": "2024-07-31 09:45:00",
#             "high": "5722.000",
#             "low": "5706.000",
#             "open": "5712.000",
#             "volume": "26420",
#             "wave": 0
#         },
#         {
#             "close": "5726.000",
#             "ctm": "1722391200",
#             "ctmfmt": "2024-07-31 10:00:00",
#             "high": "5726.000",
#             "low": "5718.000",
#             "open": "5722.000",
#             "volume": "17063",
#             "wave": 0
#         },
#         {
#             "close": "5730.000",
#             "ctm": "1722392100",
#             "ctmfmt": "2024-07-31 10:15:00",
#             "high": "5736.000",
#             "low": "5722.000",
#             "open": "5726.000",
#             "volume": "24484",
#             "wave": 0
#         },
#         {
#             "close": "5748.000",
#             "ctm": "1722393900",
#             "ctmfmt": "2024-07-31 10:45:00",
#             "high": "5748.000",
#             "low": "5732.000",
#             "open": "5734.000",
#             "volume": "33199",
#             "wave": 0
#         },
#         {
#             "close": "5740.000",
#             "ctm": "1722394800",
#             "ctmfmt": "2024-07-31 11:00:00",
#             "high": "5748.000",
#             "low": "5738.000",
#             "open": "5748.000",
#             "volume": "16314",
#             "wave": 0
#         },
#         {
#             "close": "5756.000",
#             "ctm": "1722395700",
#             "ctmfmt": "2024-07-31 11:15:00",
#             "high": "5758.000",
#             "low": "5740.000",
#             "open": "5740.000",
#             "volume": "26220",
#             "wave": 0
#         }
#     ]
#     ready_data_30m = [
#         {
#             "close": "5916.000",
#             "ctm": "1716300000",
#             "ctmfmt": "2024-05-21 22:00:00",
#             "high": "5924.000",
#             "low": "5912.000",
#             "open": "5916.000",
#             "volume": "47339",
#             "wave": 0
#         },
#         {
#             "close": "5922.000",
#             "ctm": "1716301800",
#             "ctmfmt": "2024-05-21 22:30:00",
#             "high": "5922.000",
#             "low": "5910.000",
#             "open": "5914.000",
#             "volume": "25557",
#             "wave": 0
#         },
#         {
#             "close": "5918.000",
#             "ctm": "1716303600",
#             "ctmfmt": "2024-05-21 23:00:00",
#             "high": "5924.000",
#             "low": "5914.000",
#             "open": "5922.000",
#             "volume": "29590",
#             "wave": 0
#         },
#         {
#             "close": "5920.000",
#             "ctm": "1716341400",
#             "ctmfmt": "2024-05-22 09:30:00",
#             "high": "5922.000",
#             "low": "5906.000",
#             "open": "5906.000",
#             "volume": "51865",
#             "wave": 0
#         },
#         {
#             "close": "5912.000",
#             "ctm": "1716343200",
#             "ctmfmt": "2024-05-22 10:00:00",
#             "high": "5922.000",
#             "low": "5912.000",
#             "open": "5918.000",
#             "volume": "30586",
#             "wave": 0
#         },
#         {
#             "close": "5900.000",
#             "ctm": "1716345900",
#             "ctmfmt": "2024-05-22 10:45:00",
#             "high": "5916.000",
#             "low": "5898.000",
#             "open": "5912.000",
#             "volume": "39614",
#             "wave": 0
#         },
#         {
#             "close": "5910.000",
#             "ctm": "1716347700",
#             "ctmfmt": "2024-05-22 11:15:00",
#             "high": "5910.000",
#             "low": "5894.000",
#             "open": "5902.000",
#             "volume": "28403",
#             "wave": 0
#         },
#         {
#             "close": "5896.000",
#             "ctm": "1716356700",
#             "ctmfmt": "2024-05-22 13:45:00",
#             "high": "5908.000",
#             "low": "5888.000",
#             "open": "5904.000",
#             "volume": "32522",
#             "wave": 0
#         },
#         {
#             "close": "5896.000",
#             "ctm": "1716358500",
#             "ctmfmt": "2024-05-22 14:15:00",
#             "high": "5902.000",
#             "low": "5894.000",
#             "open": "5900.000",
#             "volume": "12475",
#             "wave": 0
#         },
#         {
#             "close": "5894.000",
#             "ctm": "1716360300",
#             "ctmfmt": "2024-05-22 14:45:00",
#             "high": "5900.000",
#             "low": "5890.000",
#             "open": "5898.000",
#             "volume": "25766",
#             "wave": 0
#         },
#         {
#             "close": "5896.000",
#             "ctm": "1716361200",
#             "ctmfmt": "2024-05-22 15:00:00",
#             "high": "5898.000",
#             "low": "5892.000",
#             "open": "5892.000",
#             "volume": "14306",
#             "wave": 0
#         },
#         {
#             "close": "5908.000",
#             "ctm": "1716384600",
#             "ctmfmt": "2024-05-22 21:30:00",
#             "high": "5914.000",
#             "low": "5890.000",
#             "open": "5894.000",
#             "volume": "83026",
#             "wave": 0
#         },
#         {
#             "close": "5908.000",
#             "ctm": "1716386400",
#             "ctmfmt": "2024-05-22 22:00:00",
#             "high": "5916.000",
#             "low": "5904.000",
#             "open": "5910.000",
#             "volume": "45528",
#             "wave": 0
#         },
#         {
#             "close": "5906.000",
#             "ctm": "1716388200",
#             "ctmfmt": "2024-05-22 22:30:00",
#             "high": "5908.000",
#             "low": "5894.000",
#             "open": "5908.000",
#             "volume": "45480",
#             "wave": 0
#         },
#         {
#             "close": "5910.000",
#             "ctm": "1716390000",
#             "ctmfmt": "2024-05-22 23:00:00",
#             "high": "5912.000",
#             "low": "5900.000",
#             "open": "5906.000",
#             "volume": "29538",
#             "wave": 0
#         },
#         {
#             "close": "5896.000",
#             "ctm": "1716427800",
#             "ctmfmt": "2024-05-23 09:30:00",
#             "high": "5906.000",
#             "low": "5880.000",
#             "open": "5890.000",
#             "volume": "99940",
#             "wave": 0
#         },
#         {
#             "close": "5884.000",
#             "ctm": "1716429600",
#             "ctmfmt": "2024-05-23 10:00:00",
#             "high": "5896.000",
#             "low": "5880.000",
#             "open": "5896.000",
#             "volume": "29104",
#             "wave": 0
#         },
#         {
#             "close": "5886.000",
#             "ctm": "1716432300",
#             "ctmfmt": "2024-05-23 10:45:00",
#             "high": "5892.000",
#             "low": "5882.000",
#             "open": "5886.000",
#             "volume": "22765",
#             "wave": 0
#         },
#         {
#             "close": "5882.000",
#             "ctm": "1716434100",
#             "ctmfmt": "2024-05-23 11:15:00",
#             "high": "5890.000",
#             "low": "5880.000",
#             "open": "5886.000",
#             "volume": "19600",
#             "wave": 0
#         },
#         {
#             "close": "5874.000",
#             "ctm": "1716443100",
#             "ctmfmt": "2024-05-23 13:45:00",
#             "high": "5886.000",
#             "low": "5874.000",
#             "open": "5880.000",
#             "volume": "40607",
#             "wave": 0
#         },
#         {
#             "close": "5878.000",
#             "ctm": "1716444900",
#             "ctmfmt": "2024-05-23 14:15:00",
#             "high": "5884.000",
#             "low": "5870.000",
#             "open": "5874.000",
#             "volume": "33578",
#             "wave": 0
#         },
#         {
#             "close": "5882.000",
#             "ctm": "1716446700",
#             "ctmfmt": "2024-05-23 14:45:00",
#             "high": "5882.000",
#             "low": "5876.000",
#             "open": "5880.000",
#             "volume": "21509",
#             "wave": 0
#         },
#         {
#             "close": "5884.000",
#             "ctm": "1716447600",
#             "ctmfmt": "2024-05-23 15:00:00",
#             "high": "5886.000",
#             "low": "5878.000",
#             "open": "5880.000",
#             "volume": "32100",
#             "wave": 0
#         },
#         {
#             "close": "5918.000",
#             "ctm": "1716471000",
#             "ctmfmt": "2024-05-23 21:30:00",
#             "high": "5930.000",
#             "low": "5912.000",
#             "open": "5912.000",
#             "volume": "172281",
#             "wave": 0
#         },
#         {
#             "close": "5910.000",
#             "ctm": "1716472800",
#             "ctmfmt": "2024-05-23 22:00:00",
#             "high": "5924.000",
#             "low": "5910.000",
#             "open": "5920.000",
#             "volume": "48226",
#             "wave": 0
#         },
#         {
#             "close": "5910.000",
#             "ctm": "1716474600",
#             "ctmfmt": "2024-05-23 22:30:00",
#             "high": "5914.000",
#             "low": "5908.000",
#             "open": "5910.000",
#             "volume": "30492",
#             "wave": 0
#         },
#         {
#             "close": "5908.000",
#             "ctm": "1716476400",
#             "ctmfmt": "2024-05-23 23:00:00",
#             "high": "5912.000",
#             "low": "5904.000",
#             "open": "5910.000",
#             "volume": "42644",
#             "wave": 0
#         },
#         {
#             "close": "5922.000",
#             "ctm": "1716514200",
#             "ctmfmt": "2024-05-24 09:30:00",
#             "high": "5922.000",
#             "low": "5890.000",
#             "open": "5894.000",
#             "volume": "105137",
#             "wave": 0
#         },
#         {
#             "close": "5918.000",
#             "ctm": "1716516000",
#             "ctmfmt": "2024-05-24 10:00:00",
#             "high": "5928.000",
#             "low": "5916.000",
#             "open": "5922.000",
#             "volume": "32839",
#             "wave": 0
#         },
#         {
#             "close": "5914.000",
#             "ctm": "1716518700",
#             "ctmfmt": "2024-05-24 10:45:00",
#             "high": "5924.000",
#             "low": "5910.000",
#             "open": "5918.000",
#             "volume": "34017",
#             "wave": 0
#         },
#         {
#             "close": "5914.000",
#             "ctm": "1716520500",
#             "ctmfmt": "2024-05-24 11:15:00",
#             "high": "5922.000",
#             "low": "5910.000",
#             "open": "5914.000",
#             "volume": "19660",
#             "wave": 0
#         },
#         {
#             "close": "5918.000",
#             "ctm": "1716529500",
#             "ctmfmt": "2024-05-24 13:45:00",
#             "high": "5920.000",
#             "low": "5910.000",
#             "open": "5912.000",
#             "volume": "28017",
#             "wave": 0
#         },
#         {
#             "close": "5922.000",
#             "ctm": "1716531300",
#             "ctmfmt": "2024-05-24 14:15:00",
#             "high": "5924.000",
#             "low": "5914.000",
#             "open": "5916.000",
#             "volume": "18630",
#             "wave": 0
#         },
#         {
#             "close": "5912.000",
#             "ctm": "1716533100",
#             "ctmfmt": "2024-05-24 14:45:00",
#             "high": "5926.000",
#             "low": "5912.000",
#             "open": "5924.000",
#             "volume": "30206",
#             "wave": 0
#         },
#         {
#             "close": "5922.000",
#             "ctm": "1716534000",
#             "ctmfmt": "2024-05-24 15:00:00",
#             "high": "5924.000",
#             "low": "5910.000",
#             "open": "5914.000",
#             "volume": "23351",
#             "wave": 0
#         },
#         {
#             "close": "5942.000",
#             "ctm": "1716557400",
#             "ctmfmt": "2024-05-24 21:30:00",
#             "high": "5962.000",
#             "low": "5926.000",
#             "open": "5930.000",
#             "volume": "248888",
#             "wave": 0
#         },
#         {
#             "close": "5940.000",
#             "ctm": "1716559200",
#             "ctmfmt": "2024-05-24 22:00:00",
#             "high": "5950.000",
#             "low": "5936.000",
#             "open": "5942.000",
#             "volume": "45344",
#             "wave": 0
#         },
#         {
#             "close": "5944.000",
#             "ctm": "1716561000",
#             "ctmfmt": "2024-05-24 22:30:00",
#             "high": "5946.000",
#             "low": "5938.000",
#             "open": "5938.000",
#             "volume": "30194",
#             "wave": 0
#         },
#         {
#             "close": "5946.000",
#             "ctm": "1716562800",
#             "ctmfmt": "2024-05-24 23:00:00",
#             "high": "5948.000",
#             "low": "5936.000",
#             "open": "5944.000",
#             "volume": "44004",
#             "wave": 0
#         },
#         {
#             "close": "5948.000",
#             "ctm": "1716773400",
#             "ctmfmt": "2024-05-27 09:30:00",
#             "high": "5956.000",
#             "low": "5942.000",
#             "open": "5950.000",
#             "volume": "71220",
#             "wave": 0
#         },
#         {
#             "close": "5948.000",
#             "ctm": "1716775200",
#             "ctmfmt": "2024-05-27 10:00:00",
#             "high": "5952.000",
#             "low": "5946.000",
#             "open": "5948.000",
#             "volume": "18744",
#             "wave": 0
#         },
#         {
#             "close": "5952.000",
#             "ctm": "1716777900",
#             "ctmfmt": "2024-05-27 10:45:00",
#             "high": "5958.000",
#             "low": "5944.000",
#             "open": "5946.000",
#             "volume": "45761",
#             "wave": 0
#         },
#         {
#             "close": "5956.000",
#             "ctm": "1716779700",
#             "ctmfmt": "2024-05-27 11:15:00",
#             "high": "5956.000",
#             "low": "5946.000",
#             "open": "5950.000",
#             "volume": "22770",
#             "wave": 0
#         },
#         {
#             "close": "5956.000",
#             "ctm": "1716788700",
#             "ctmfmt": "2024-05-27 13:45:00",
#             "high": "5958.000",
#             "low": "5950.000",
#             "open": "5956.000",
#             "volume": "38719",
#             "wave": 0
#         },
#         {
#             "close": "5950.000",
#             "ctm": "1716790500",
#             "ctmfmt": "2024-05-27 14:15:00",
#             "high": "5958.000",
#             "low": "5942.000",
#             "open": "5956.000",
#             "volume": "35196",
#             "wave": 0
#         },
#         {
#             "close": "5946.000",
#             "ctm": "1716792300",
#             "ctmfmt": "2024-05-27 14:45:00",
#             "high": "5952.000",
#             "low": "5946.000",
#             "open": "5950.000",
#             "volume": "12486",
#             "wave": 0
#         },
#         {
#             "close": "5944.000",
#             "ctm": "1716793200",
#             "ctmfmt": "2024-05-27 15:00:00",
#             "high": "5948.000",
#             "low": "5942.000",
#             "open": "5948.000",
#             "volume": "21130",
#             "wave": 0
#         },
#         {
#             "close": "5956.000",
#             "ctm": "1716816600",
#             "ctmfmt": "2024-05-27 21:30:00",
#             "high": "5968.000",
#             "low": "5950.000",
#             "open": "5954.000",
#             "volume": "106151",
#             "wave": 0
#         },
#         {
#             "close": "5952.000",
#             "ctm": "1716818400",
#             "ctmfmt": "2024-05-27 22:00:00",
#             "high": "5958.000",
#             "low": "5950.000",
#             "open": "5954.000",
#             "volume": "23542",
#             "wave": 0
#         },
#         {
#             "close": "5946.000",
#             "ctm": "1716820200",
#             "ctmfmt": "2024-05-27 22:30:00",
#             "high": "5956.000",
#             "low": "5946.000",
#             "open": "5952.000",
#             "volume": "22267",
#             "wave": 0
#         },
#         {
#             "close": "5944.000",
#             "ctm": "1716822000",
#             "ctmfmt": "2024-05-27 23:00:00",
#             "high": "5948.000",
#             "low": "5940.000",
#             "open": "5946.000",
#             "volume": "36532",
#             "wave": 0
#         },
#         {
#             "close": "5946.000",
#             "ctm": "1716859800",
#             "ctmfmt": "2024-05-28 09:30:00",
#             "high": "5952.000",
#             "low": "5944.000",
#             "open": "5948.000",
#             "volume": "46151",
#             "wave": 0
#         },
#         {
#             "close": "5944.000",
#             "ctm": "1716861600",
#             "ctmfmt": "2024-05-28 10:00:00",
#             "high": "5950.000",
#             "low": "5942.000",
#             "open": "5946.000",
#             "volume": "15959",
#             "wave": 0
#         },
#         {
#             "close": "5944.000",
#             "ctm": "1716864300",
#             "ctmfmt": "2024-05-28 10:45:00",
#             "high": "5950.000",
#             "low": "5940.000",
#             "open": "5944.000",
#             "volume": "22950",
#             "wave": 0
#         },
#         {
#             "close": "5948.000",
#             "ctm": "1716866100",
#             "ctmfmt": "2024-05-28 11:15:00",
#             "high": "5950.000",
#             "low": "5944.000",
#             "open": "5944.000",
#             "volume": "27325",
#             "wave": 0
#         },
#         {
#             "close": "5936.000",
#             "ctm": "1716875100",
#             "ctmfmt": "2024-05-28 13:45:00",
#             "high": "5948.000",
#             "low": "5930.000",
#             "open": "5948.000",
#             "volume": "34908",
#             "wave": 0
#         },
#         {
#             "close": "5928.000",
#             "ctm": "1716876900",
#             "ctmfmt": "2024-05-28 14:15:00",
#             "high": "5940.000",
#             "low": "5928.000",
#             "open": "5938.000",
#             "volume": "31652",
#             "wave": 0
#         },
#         {
#             "close": "5926.000",
#             "ctm": "1716878700",
#             "ctmfmt": "2024-05-28 14:45:00",
#             "high": "5930.000",
#             "low": "5920.000",
#             "open": "5928.000",
#             "volume": "20523",
#             "wave": 0
#         },
#         {
#             "close": "5918.000",
#             "ctm": "1716879600",
#             "ctmfmt": "2024-05-28 15:00:00",
#             "high": "5930.000",
#             "low": "5916.000",
#             "open": "5924.000",
#             "volume": "24316",
#             "wave": 0
#         },
#         {
#             "close": "5932.000",
#             "ctm": "1716903000",
#             "ctmfmt": "2024-05-28 21:30:00",
#             "high": "5938.000",
#             "low": "5926.000",
#             "open": "5928.000",
#             "volume": "79237",
#             "wave": 0
#         },
#         {
#             "close": "5928.000",
#             "ctm": "1716904800",
#             "ctmfmt": "2024-05-28 22:00:00",
#             "high": "5942.000",
#             "low": "5926.000",
#             "open": "5934.000",
#             "volume": "34884",
#             "wave": 0
#         },
#         {
#             "close": "5930.000",
#             "ctm": "1716906600",
#             "ctmfmt": "2024-05-28 22:30:00",
#             "high": "5932.000",
#             "low": "5916.000",
#             "open": "5928.000",
#             "volume": "36957",
#             "wave": 0
#         },
#         {
#             "close": "5934.000",
#             "ctm": "1716908400",
#             "ctmfmt": "2024-05-28 23:00:00",
#             "high": "5936.000",
#             "low": "5926.000",
#             "open": "5930.000",
#             "volume": "22197",
#             "wave": 0
#         },
#         {
#             "close": "5954.000",
#             "ctm": "1716946200",
#             "ctmfmt": "2024-05-29 09:30:00",
#             "high": "5962.000",
#             "low": "5940.000",
#             "open": "5942.000",
#             "volume": "106215",
#             "wave": 0
#         },
#         {
#             "close": "5950.000",
#             "ctm": "1716948000",
#             "ctmfmt": "2024-05-29 10:00:00",
#             "high": "5958.000",
#             "low": "5948.000",
#             "open": "5954.000",
#             "volume": "21668",
#             "wave": 0
#         },
#         {
#             "close": "5946.000",
#             "ctm": "1716950700",
#             "ctmfmt": "2024-05-29 10:45:00",
#             "high": "5954.000",
#             "low": "5944.000",
#             "open": "5954.000",
#             "volume": "17008",
#             "wave": 0
#         },
#         {
#             "close": "5952.000",
#             "ctm": "1716952500",
#             "ctmfmt": "2024-05-29 11:15:00",
#             "high": "5954.000",
#             "low": "5938.000",
#             "open": "5946.000",
#             "volume": "24784",
#             "wave": 0
#         },
#         {
#             "close": "5950.000",
#             "ctm": "1716961500",
#             "ctmfmt": "2024-05-29 13:45:00",
#             "high": "5956.000",
#             "low": "5944.000",
#             "open": "5952.000",
#             "volume": "32456",
#             "wave": 0
#         },
#         {
#             "close": "5950.000",
#             "ctm": "1716963300",
#             "ctmfmt": "2024-05-29 14:15:00",
#             "high": "5954.000",
#             "low": "5942.000",
#             "open": "5946.000",
#             "volume": "14532",
#             "wave": 0
#         },
#         {
#             "close": "5950.000",
#             "ctm": "1716965100",
#             "ctmfmt": "2024-05-29 14:45:00",
#             "high": "5954.000",
#             "low": "5948.000",
#             "open": "5948.000",
#             "volume": "20995",
#             "wave": 0
#         },
#         {
#             "close": "5954.000",
#             "ctm": "1716966000",
#             "ctmfmt": "2024-05-29 15:00:00",
#             "high": "5958.000",
#             "low": "5948.000",
#             "open": "5950.000",
#             "volume": "31838",
#             "wave": 0
#         },
#         {
#             "close": "5974.000",
#             "ctm": "1716989400",
#             "ctmfmt": "2024-05-29 21:30:00",
#             "high": "5980.000",
#             "low": "5956.000",
#             "open": "5956.000",
#             "volume": "148511",
#             "wave": 0
#         },
#         {
#             "close": "5964.000",
#             "ctm": "1716991200",
#             "ctmfmt": "2024-05-29 22:00:00",
#             "high": "5978.000",
#             "low": "5952.000",
#             "open": "5976.000",
#             "volume": "40083",
#             "wave": 0
#         },
#         {
#             "close": "5970.000",
#             "ctm": "1716993000",
#             "ctmfmt": "2024-05-29 22:30:00",
#             "high": "5976.000",
#             "low": "5962.000",
#             "open": "5964.000",
#             "volume": "33619",
#             "wave": 0
#         },
#         {
#             "close": "5966.000",
#             "ctm": "1716994800",
#             "ctmfmt": "2024-05-29 23:00:00",
#             "high": "5976.000",
#             "low": "5964.000",
#             "open": "5968.000",
#             "volume": "34978",
#             "wave": 0
#         },
#         {
#             "close": "5990.000",
#             "ctm": "1717032600",
#             "ctmfmt": "2024-05-30 09:30:00",
#             "high": "5994.000",
#             "low": "5960.000",
#             "open": "5962.000",
#             "volume": "87364",
#             "wave": 0
#         },
#         {
#             "close": "5982.000",
#             "ctm": "1717034400",
#             "ctmfmt": "2024-05-30 10:00:00",
#             "high": "5994.000",
#             "low": "5982.000",
#             "open": "5992.000",
#             "volume": "55183",
#             "wave": 0
#         },
#         {
#             "close": "5996.000",
#             "ctm": "1717037100",
#             "ctmfmt": "2024-05-30 10:45:00",
#             "high": "6010.000",
#             "low": "5984.000",
#             "open": "5984.000",
#             "volume": "79061",
#             "wave": 0
#         },
#         {
#             "close": "6012.000",
#             "ctm": "1717038900",
#             "ctmfmt": "2024-05-30 11:15:00",
#             "high": "6014.000",
#             "low": "5988.000",
#             "open": "5994.000",
#             "volume": "18222",
#             "wave": 0
#         },
#         {
#             "close": "6034.000",
#             "ctm": "1717047900",
#             "ctmfmt": "2024-05-30 13:45:00",
#             "high": "6038.000",
#             "low": "6004.000",
#             "open": "6012.000",
#             "volume": "106098",
#             "wave": 0
#         },
#         {
#             "close": "6008.000",
#             "ctm": "1717049700",
#             "ctmfmt": "2024-05-30 14:15:00",
#             "high": "6036.000",
#             "low": "5998.000",
#             "open": "6034.000",
#             "volume": "49709",
#             "wave": 0
#         },
#         {
#             "close": "6008.000",
#             "ctm": "1717051500",
#             "ctmfmt": "2024-05-30 14:45:00",
#             "high": "6020.000",
#             "low": "6008.000",
#             "open": "6016.000",
#             "volume": "8092",
#             "wave": 0
#         },
#         {
#             "close": "6024.000",
#             "ctm": "1717052400",
#             "ctmfmt": "2024-05-30 15:00:00",
#             "high": "6026.000",
#             "low": "6010.000",
#             "open": "6012.000",
#             "volume": "6473",
#             "wave": 0
#         },
#         {
#             "close": "5992.000",
#             "ctm": "1717075800",
#             "ctmfmt": "2024-05-30 21:30:00",
#             "high": "6022.000",
#             "low": "5992.000",
#             "open": "6016.000",
#             "volume": "139240",
#             "wave": 0
#         },
#         {
#             "close": "6012.000",
#             "ctm": "1717077600",
#             "ctmfmt": "2024-05-30 22:00:00",
#             "high": "6014.000",
#             "low": "5992.000",
#             "open": "5994.000",
#             "volume": "50002",
#             "wave": 0
#         },
#         {
#             "close": "6004.000",
#             "ctm": "1717079400",
#             "ctmfmt": "2024-05-30 22:30:00",
#             "high": "6014.000",
#             "low": "6000.000",
#             "open": "6012.000",
#             "volume": "25275",
#             "wave": 0
#         },
#         {
#             "close": "6016.000",
#             "ctm": "1717081200",
#             "ctmfmt": "2024-05-30 23:00:00",
#             "high": "6018.000",
#             "low": "6002.000",
#             "open": "6004.000",
#             "volume": "31894",
#             "wave": 0
#         },
#         {
#             "close": "6004.000",
#             "ctm": "1717119000",
#             "ctmfmt": "2024-05-31 09:30:00",
#             "high": "6008.000",
#             "low": "5988.000",
#             "open": "6000.000",
#             "volume": "89958",
#             "wave": 0
#         },
#         {
#             "close": "6004.000",
#             "ctm": "1717120800",
#             "ctmfmt": "2024-05-31 10:00:00",
#             "high": "6010.000",
#             "low": "5994.000",
#             "open": "6004.000",
#             "volume": "36276",
#             "wave": 0
#         },
#         {
#             "close": "5982.000",
#             "ctm": "1717123500",
#             "ctmfmt": "2024-05-31 10:45:00",
#             "high": "6008.000",
#             "low": "5982.000",
#             "open": "6004.000",
#             "volume": "43493",
#             "wave": 0
#         },
#         {
#             "close": "5970.000",
#             "ctm": "1717125300",
#             "ctmfmt": "2024-05-31 11:15:00",
#             "high": "5986.000",
#             "low": "5966.000",
#             "open": "5984.000",
#             "volume": "78472",
#             "wave": 0
#         },
#         {
#             "close": "5980.000",
#             "ctm": "1717134300",
#             "ctmfmt": "2024-05-31 13:45:00",
#             "high": "5988.000",
#             "low": "5966.000",
#             "open": "5968.000",
#             "volume": "35931",
#             "wave": 0
#         },
#         {
#             "close": "5988.000",
#             "ctm": "1717136100",
#             "ctmfmt": "2024-05-31 14:15:00",
#             "high": "5992.000",
#             "low": "5980.000",
#             "open": "5980.000",
#             "volume": "26710",
#             "wave": 0
#         },
#         {
#             "close": "5988.000",
#             "ctm": "1717137900",
#             "ctmfmt": "2024-05-31 14:45:00",
#             "high": "5992.000",
#             "low": "5980.000",
#             "open": "5988.000",
#             "volume": "22949",
#             "wave": 0
#         },
#         {
#             "close": "5990.000",
#             "ctm": "1717138800",
#             "ctmfmt": "2024-05-31 15:00:00",
#             "high": "5992.000",
#             "low": "5980.000",
#             "open": "5988.000",
#             "volume": "24472",
#             "wave": 0
#         },
#         {
#             "close": "5994.000",
#             "ctm": "1717162200",
#             "ctmfmt": "2024-05-31 21:30:00",
#             "high": "6012.000",
#             "low": "5986.000",
#             "open": "6006.000",
#             "volume": "89175",
#             "wave": 0
#         },
#         {
#             "close": "5980.000",
#             "ctm": "1717164000",
#             "ctmfmt": "2024-05-31 22:00:00",
#             "high": "5996.000",
#             "low": "5974.000",
#             "open": "5992.000",
#             "volume": "36579",
#             "wave": 0
#         },
#         {
#             "close": "5968.000",
#             "ctm": "1717165800",
#             "ctmfmt": "2024-05-31 22:30:00",
#             "high": "5980.000",
#             "low": "5966.000",
#             "open": "5978.000",
#             "volume": "35529",
#             "wave": 0
#         },
#         {
#             "close": "5958.000",
#             "ctm": "1717167600",
#             "ctmfmt": "2024-05-31 23:00:00",
#             "high": "5970.000",
#             "low": "5950.000",
#             "open": "5968.000",
#             "volume": "81434",
#             "wave": 0
#         },
#         {
#             "close": "5942.000",
#             "ctm": "1717378200",
#             "ctmfmt": "2024-06-03 09:30:00",
#             "high": "5954.000",
#             "low": "5934.000",
#             "open": "5954.000",
#             "volume": "80065",
#             "wave": 0
#         },
#         {
#             "close": "5942.000",
#             "ctm": "1717380000",
#             "ctmfmt": "2024-06-03 10:00:00",
#             "high": "5948.000",
#             "low": "5938.000",
#             "open": "5940.000",
#             "volume": "33856",
#             "wave": 0
#         },
#         {
#             "close": "5932.000",
#             "ctm": "1717382700",
#             "ctmfmt": "2024-06-03 10:45:00",
#             "high": "5944.000",
#             "low": "5930.000",
#             "open": "5942.000",
#             "volume": "53308",
#             "wave": 0
#         },
#         {
#             "close": "5908.000",
#             "ctm": "1717384500",
#             "ctmfmt": "2024-06-03 11:15:00",
#             "high": "5934.000",
#             "low": "5908.000",
#             "open": "5934.000",
#             "volume": "76935",
#             "wave": 0
#         },
#         {
#             "close": "5914.000",
#             "ctm": "1717393500",
#             "ctmfmt": "2024-06-03 13:45:00",
#             "high": "5914.000",
#             "low": "5908.000",
#             "open": "5914.000",
#             "volume": "33073",
#             "wave": 0
#         },
#         {
#             "close": "5910.000",
#             "ctm": "1717395300",
#             "ctmfmt": "2024-06-03 14:15:00",
#             "high": "5918.000",
#             "low": "5910.000",
#             "open": "5914.000",
#             "volume": "26188",
#             "wave": 0
#         },
#         {
#             "close": "5908.000",
#             "ctm": "1717397100",
#             "ctmfmt": "2024-06-03 14:45:00",
#             "high": "5912.000",
#             "low": "5902.000",
#             "open": "5910.000",
#             "volume": "2591",
#             "wave": 0
#         },
#         {
#             "close": "5910.000",
#             "ctm": "1717398000",
#             "ctmfmt": "2024-06-03 15:00:00",
#             "high": "5914.000",
#             "low": "5908.000",
#             "open": "5910.000",
#             "volume": "11378",
#             "wave": 0
#         },
#         {
#             "close": "5914.000",
#             "ctm": "1717421400",
#             "ctmfmt": "2024-06-03 21:30:00",
#             "high": "5926.000",
#             "low": "5910.000",
#             "open": "5912.000",
#             "volume": "80013",
#             "wave": 0
#         },
#         {
#             "close": "5896.000",
#             "ctm": "1717423200",
#             "ctmfmt": "2024-06-03 22:00:00",
#             "high": "5920.000",
#             "low": "5892.000",
#             "open": "5914.000",
#             "volume": "62394",
#             "wave": 0
#         },
#         {
#             "close": "5890.000",
#             "ctm": "1717425000",
#             "ctmfmt": "2024-06-03 22:30:00",
#             "high": "5904.000",
#             "low": "5888.000",
#             "open": "5896.000",
#             "volume": "58498",
#             "wave": 0
#         },
#         {
#             "close": "5888.000",
#             "ctm": "1717426800",
#             "ctmfmt": "2024-06-03 23:00:00",
#             "high": "5898.000",
#             "low": "5886.000",
#             "open": "5890.000",
#             "volume": "32113",
#             "wave": 0
#         },
#         {
#             "close": "5850.000",
#             "ctm": "1717464600",
#             "ctmfmt": "2024-06-04 09:30:00",
#             "high": "5886.000",
#             "low": "5850.000",
#             "open": "5884.000",
#             "volume": "138847",
#             "wave": 0
#         },
#         {
#             "close": "5844.000",
#             "ctm": "1717466400",
#             "ctmfmt": "2024-06-04 10:00:00",
#             "high": "5854.000",
#             "low": "5838.000",
#             "open": "5850.000",
#             "volume": "94648",
#             "wave": 0
#         },
#         {
#             "close": "5854.000",
#             "ctm": "1717469100",
#             "ctmfmt": "2024-06-04 10:45:00",
#             "high": "5856.000",
#             "low": "5840.000",
#             "open": "5844.000",
#             "volume": "58830",
#             "wave": 0
#         },
#         {
#             "close": "5844.000",
#             "ctm": "1717470900",
#             "ctmfmt": "2024-06-04 11:15:00",
#             "high": "5858.000",
#             "low": "5844.000",
#             "open": "5854.000",
#             "volume": "34667",
#             "wave": 0
#         },
#         {
#             "close": "5834.000",
#             "ctm": "1717479900",
#             "ctmfmt": "2024-06-04 13:45:00",
#             "high": "5846.000",
#             "low": "5832.000",
#             "open": "5844.000",
#             "volume": "56114",
#             "wave": 0
#         },
#         {
#             "close": "5842.000",
#             "ctm": "1717481700",
#             "ctmfmt": "2024-06-04 14:15:00",
#             "high": "5842.000",
#             "low": "5832.000",
#             "open": "5834.000",
#             "volume": "41598",
#             "wave": 0
#         },
#         {
#             "close": "5844.000",
#             "ctm": "1717483500",
#             "ctmfmt": "2024-06-04 14:45:00",
#             "high": "5848.000",
#             "low": "5838.000",
#             "open": "5842.000",
#             "volume": "27436",
#             "wave": 0
#         },
#         {
#             "close": "5848.000",
#             "ctm": "1717484400",
#             "ctmfmt": "2024-06-04 15:00:00",
#             "high": "5852.000",
#             "low": "5842.000",
#             "open": "5846.000",
#             "volume": "57752",
#             "wave": 0
#         },
#         {
#             "close": "5862.000",
#             "ctm": "1717507800",
#             "ctmfmt": "2024-06-04 21:30:00",
#             "high": "5862.000",
#             "low": "5838.000",
#             "open": "5848.000",
#             "volume": "144638",
#             "wave": 0
#         },
#         {
#             "close": "5854.000",
#             "ctm": "1717509600",
#             "ctmfmt": "2024-06-04 22:00:00",
#             "high": "5862.000",
#             "low": "5848.000",
#             "open": "5860.000",
#             "volume": "51964",
#             "wave": 0
#         },
#         {
#             "close": "5866.000",
#             "ctm": "1717511400",
#             "ctmfmt": "2024-06-04 22:30:00",
#             "high": "5866.000",
#             "low": "5852.000",
#             "open": "5852.000",
#             "volume": "35451",
#             "wave": 0
#         },
#         {
#             "close": "5860.000",
#             "ctm": "1717513200",
#             "ctmfmt": "2024-06-04 23:00:00",
#             "high": "5866.000",
#             "low": "5856.000",
#             "open": "5866.000",
#             "volume": "26079",
#             "wave": 0
#         },
#         {
#             "close": "5868.000",
#             "ctm": "1717551000",
#             "ctmfmt": "2024-06-05 09:30:00",
#             "high": "5876.000",
#             "low": "5858.000",
#             "open": "5860.000",
#             "volume": "89727",
#             "wave": 0
#         },
#         {
#             "close": "5886.000",
#             "ctm": "1717552800",
#             "ctmfmt": "2024-06-05 10:00:00",
#             "high": "5892.000",
#             "low": "5860.000",
#             "open": "5868.000",
#             "volume": "81407",
#             "wave": 0
#         },
#         {
#             "close": "5870.000",
#             "ctm": "1717555500",
#             "ctmfmt": "2024-06-05 10:45:00",
#             "high": "5892.000",
#             "low": "5866.000",
#             "open": "5888.000",
#             "volume": "89044",
#             "wave": 0
#         },
#         {
#             "close": "5866.000",
#             "ctm": "1717557300",
#             "ctmfmt": "2024-06-05 11:15:00",
#             "high": "5878.000",
#             "low": "5862.000",
#             "open": "5868.000",
#             "volume": "33750",
#             "wave": 0
#         },
#         {
#             "close": "5862.000",
#             "ctm": "1717566300",
#             "ctmfmt": "2024-06-05 13:45:00",
#             "high": "5874.000",
#             "low": "5862.000",
#             "open": "5864.000",
#             "volume": "35142",
#             "wave": 0
#         },
#         {
#             "close": "5866.000",
#             "ctm": "1717568100",
#             "ctmfmt": "2024-06-05 14:15:00",
#             "high": "5874.000",
#             "low": "5862.000",
#             "open": "5864.000",
#             "volume": "27595",
#             "wave": 0
#         },
#         {
#             "close": "5868.000",
#             "ctm": "1717569900",
#             "ctmfmt": "2024-06-05 14:45:00",
#             "high": "5874.000",
#             "low": "5866.000",
#             "open": "5868.000",
#             "volume": "21143",
#             "wave": 0
#         },
#         {
#             "close": "5866.000",
#             "ctm": "1717570800",
#             "ctmfmt": "2024-06-05 15:00:00",
#             "high": "5872.000",
#             "low": "5862.000",
#             "open": "5868.000",
#             "volume": "31511",
#             "wave": 0
#         },
#         {
#             "close": "5874.000",
#             "ctm": "1717594200",
#             "ctmfmt": "2024-06-05 21:30:00",
#             "high": "5890.000",
#             "low": "5870.000",
#             "open": "5890.000",
#             "volume": "104743",
#             "wave": 0
#         },
#         {
#             "close": "5874.000",
#             "ctm": "1717596000",
#             "ctmfmt": "2024-06-05 22:00:00",
#             "high": "5880.000",
#             "low": "5868.000",
#             "open": "5874.000",
#             "volume": "36297",
#             "wave": 0
#         },
#         {
#             "close": "5874.000",
#             "ctm": "1717597800",
#             "ctmfmt": "2024-06-05 22:30:00",
#             "high": "5878.000",
#             "low": "5866.000",
#             "open": "5874.000",
#             "volume": "39437",
#             "wave": 0
#         },
#         {
#             "close": "5870.000",
#             "ctm": "1717599600",
#             "ctmfmt": "2024-06-05 23:00:00",
#             "high": "5880.000",
#             "low": "5868.000",
#             "open": "5874.000",
#             "volume": "24311",
#             "wave": 0
#         },
#         {
#             "close": "5892.000",
#             "ctm": "1717637400",
#             "ctmfmt": "2024-06-06 09:30:00",
#             "high": "5896.000",
#             "low": "5880.000",
#             "open": "5890.000",
#             "volume": "59562",
#             "wave": 0
#         },
#         {
#             "close": "5870.000",
#             "ctm": "1717639200",
#             "ctmfmt": "2024-06-06 10:00:00",
#             "high": "5894.000",
#             "low": "5868.000",
#             "open": "5892.000",
#             "volume": "55320",
#             "wave": 0
#         },
#         {
#             "close": "5874.000",
#             "ctm": "1717641900",
#             "ctmfmt": "2024-06-06 10:45:00",
#             "high": "5878.000",
#             "low": "5864.000",
#             "open": "5868.000",
#             "volume": "33039",
#             "wave": 0
#         },
#         {
#             "close": "5870.000",
#             "ctm": "1717643700",
#             "ctmfmt": "2024-06-06 11:15:00",
#             "high": "5880.000",
#             "low": "5868.000",
#             "open": "5874.000",
#             "volume": "36896",
#             "wave": 0
#         },
#         {
#             "close": "5874.000",
#             "ctm": "1717652700",
#             "ctmfmt": "2024-06-06 13:45:00",
#             "high": "5882.000",
#             "low": "5862.000",
#             "open": "5870.000",
#             "volume": "46190",
#             "wave": 0
#         },
#         {
#             "close": "5860.000",
#             "ctm": "1717654500",
#             "ctmfmt": "2024-06-06 14:15:00",
#             "high": "5878.000",
#             "low": "5858.000",
#             "open": "5874.000",
#             "volume": "46689",
#             "wave": 0
#         },
#         {
#             "close": "5872.000",
#             "ctm": "1717656300",
#             "ctmfmt": "2024-06-06 14:45:00",
#             "high": "5872.000",
#             "low": "5856.000",
#             "open": "5860.000",
#             "volume": "36910",
#             "wave": 0
#         },
#         {
#             "close": "5864.000",
#             "ctm": "1717657200",
#             "ctmfmt": "2024-06-06 15:00:00",
#             "high": "5872.000",
#             "low": "5862.000",
#             "open": "5872.000",
#             "volume": "19790",
#             "wave": 0
#         },
#         {
#             "close": "5858.000",
#             "ctm": "1717680600",
#             "ctmfmt": "2024-06-06 21:30:00",
#             "high": "5864.000",
#             "low": "5842.000",
#             "open": "5862.000",
#             "volume": "91655",
#             "wave": 0
#         },
#         {
#             "close": "5862.000",
#             "ctm": "1717682400",
#             "ctmfmt": "2024-06-06 22:00:00",
#             "high": "5868.000",
#             "low": "5854.000",
#             "open": "5858.000",
#             "volume": "30179",
#             "wave": 0
#         },
#         {
#             "close": "5868.000",
#             "ctm": "1717684200",
#             "ctmfmt": "2024-06-06 22:30:00",
#             "high": "5870.000",
#             "low": "5858.000",
#             "open": "5860.000",
#             "volume": "24975",
#             "wave": 0
#         },
#         {
#             "close": "5872.000",
#             "ctm": "1717686000",
#             "ctmfmt": "2024-06-06 23:00:00",
#             "high": "5874.000",
#             "low": "5866.000",
#             "open": "5868.000",
#             "volume": "26044",
#             "wave": 0
#         },
#         {
#             "close": "5874.000",
#             "ctm": "1717723800",
#             "ctmfmt": "2024-06-07 09:30:00",
#             "high": "5892.000",
#             "low": "5872.000",
#             "open": "5888.000",
#             "volume": "62034",
#             "wave": 0
#         },
#         {
#             "close": "5870.000",
#             "ctm": "1717725600",
#             "ctmfmt": "2024-06-07 10:00:00",
#             "high": "5878.000",
#             "low": "5866.000",
#             "open": "5874.000",
#             "volume": "32459",
#             "wave": 0
#         },
#         {
#             "close": "5888.000",
#             "ctm": "1717728300",
#             "ctmfmt": "2024-06-07 10:45:00",
#             "high": "5890.000",
#             "low": "5868.000",
#             "open": "5872.000",
#             "volume": "42531",
#             "wave": 0
#         },
#         {
#             "close": "5888.000",
#             "ctm": "1717730100",
#             "ctmfmt": "2024-06-07 11:15:00",
#             "high": "5898.000",
#             "low": "5882.000",
#             "open": "5888.000",
#             "volume": "53489",
#             "wave": 0
#         },
#         {
#             "close": "5884.000",
#             "ctm": "1717739100",
#             "ctmfmt": "2024-06-07 13:45:00",
#             "high": "5896.000",
#             "low": "5884.000",
#             "open": "5886.000",
#             "volume": "34553",
#             "wave": 0
#         },
#         {
#             "close": "5904.000",
#             "ctm": "1717740900",
#             "ctmfmt": "2024-06-07 14:15:00",
#             "high": "5904.000",
#             "low": "5882.000",
#             "open": "5884.000",
#             "volume": "50298",
#             "wave": 0
#         },
#         {
#             "close": "5892.000",
#             "ctm": "1717742700",
#             "ctmfmt": "2024-06-07 14:45:00",
#             "high": "5904.000",
#             "low": "5886.000",
#             "open": "5904.000",
#             "volume": "48873",
#             "wave": 0
#         },
#         {
#             "close": "5888.000",
#             "ctm": "1717743600",
#             "ctmfmt": "2024-06-07 15:00:00",
#             "high": "5894.000",
#             "low": "5886.000",
#             "open": "5890.000",
#             "volume": "25640",
#             "wave": 0
#         },
#         {
#             "close": "5922.000",
#             "ctm": "1718069400",
#             "ctmfmt": "2024-06-11 09:30:00",
#             "high": "5926.000",
#             "low": "5912.000",
#             "open": "5914.000",
#             "volume": "132601",
#             "wave": 0
#         },
#         {
#             "close": "5918.000",
#             "ctm": "1718071200",
#             "ctmfmt": "2024-06-11 10:00:00",
#             "high": "5922.000",
#             "low": "5910.000",
#             "open": "5920.000",
#             "volume": "52681",
#             "wave": 0
#         },
#         {
#             "close": "5908.000",
#             "ctm": "1718073900",
#             "ctmfmt": "2024-06-11 10:45:00",
#             "high": "5920.000",
#             "low": "5900.000",
#             "open": "5918.000",
#             "volume": "39343",
#             "wave": 0
#         },
#         {
#             "close": "5914.000",
#             "ctm": "1718075700",
#             "ctmfmt": "2024-06-11 11:15:00",
#             "high": "5916.000",
#             "low": "5900.000",
#             "open": "5908.000",
#             "volume": "34132",
#             "wave": 0
#         },
#         {
#             "close": "5944.000",
#             "ctm": "1718084700",
#             "ctmfmt": "2024-06-11 13:45:00",
#             "high": "5946.000",
#             "low": "5910.000",
#             "open": "5914.000",
#             "volume": "90543",
#             "wave": 0
#         },
#         {
#             "close": "5936.000",
#             "ctm": "1718086500",
#             "ctmfmt": "2024-06-11 14:15:00",
#             "high": "5948.000",
#             "low": "5930.000",
#             "open": "5944.000",
#             "volume": "47363",
#             "wave": 0
#         },
#         {
#             "close": "5938.000",
#             "ctm": "1718088300",
#             "ctmfmt": "2024-06-11 14:45:00",
#             "high": "5946.000",
#             "low": "5932.000",
#             "open": "5938.000",
#             "volume": "39522",
#             "wave": 0
#         },
#         {
#             "close": "5946.000",
#             "ctm": "1718089200",
#             "ctmfmt": "2024-06-11 15:00:00",
#             "high": "5950.000",
#             "low": "5936.000",
#             "open": "5938.000",
#             "volume": "39758",
#             "wave": 0
#         },
#         {
#             "close": "5948.000",
#             "ctm": "1718112600",
#             "ctmfmt": "2024-06-11 21:30:00",
#             "high": "5950.000",
#             "low": "5938.000",
#             "open": "5944.000",
#             "volume": "77849",
#             "wave": 0
#         },
#         {
#             "close": "5938.000",
#             "ctm": "1718114400",
#             "ctmfmt": "2024-06-11 22:00:00",
#             "high": "5952.000",
#             "low": "5936.000",
#             "open": "5948.000",
#             "volume": "41532",
#             "wave": 0
#         },
#         {
#             "close": "5944.000",
#             "ctm": "1718116200",
#             "ctmfmt": "2024-06-11 22:30:00",
#             "high": "5946.000",
#             "low": "5936.000",
#             "open": "5938.000",
#             "volume": "19934",
#             "wave": 0
#         },
#         {
#             "close": "5950.000",
#             "ctm": "1718118000",
#             "ctmfmt": "2024-06-11 23:00:00",
#             "high": "5954.000",
#             "low": "5942.000",
#             "open": "5944.000",
#             "volume": "29172",
#             "wave": 0
#         },
#         {
#             "close": "5958.000",
#             "ctm": "1718155800",
#             "ctmfmt": "2024-06-12 09:30:00",
#             "high": "5966.000",
#             "low": "5954.000",
#             "open": "5958.000",
#             "volume": "68192",
#             "wave": 0
#         },
#         {
#             "close": "5954.000",
#             "ctm": "1718157600",
#             "ctmfmt": "2024-06-12 10:00:00",
#             "high": "5960.000",
#             "low": "5946.000",
#             "open": "5960.000",
#             "volume": "53515",
#             "wave": 0
#         },
#         {
#             "close": "5952.000",
#             "ctm": "1718160300",
#             "ctmfmt": "2024-06-12 10:45:00",
#             "high": "5958.000",
#             "low": "5946.000",
#             "open": "5956.000",
#             "volume": "33910",
#             "wave": 0
#         },
#         {
#             "close": "5970.000",
#             "ctm": "1718162100",
#             "ctmfmt": "2024-06-12 11:15:00",
#             "high": "5970.000",
#             "low": "5950.000",
#             "open": "5952.000",
#             "volume": "41688",
#             "wave": 0
#         },
#         {
#             "close": "5974.000",
#             "ctm": "1718171100",
#             "ctmfmt": "2024-06-12 13:45:00",
#             "high": "5974.000",
#             "low": "5964.000",
#             "open": "5968.000",
#             "volume": "43477",
#             "wave": 0
#         },
#         {
#             "close": "5970.000",
#             "ctm": "1718172900",
#             "ctmfmt": "2024-06-12 14:15:00",
#             "high": "5974.000",
#             "low": "5968.000",
#             "open": "5974.000",
#             "volume": "27597",
#             "wave": 0
#         },
#         {
#             "close": "5962.000",
#             "ctm": "1718174700",
#             "ctmfmt": "2024-06-12 14:45:00",
#             "high": "5974.000",
#             "low": "5962.000",
#             "open": "5970.000",
#             "volume": "32032",
#             "wave": 0
#         },
#         {
#             "close": "5960.000",
#             "ctm": "1718175600",
#             "ctmfmt": "2024-06-12 15:00:00",
#             "high": "5970.000",
#             "low": "5960.000",
#             "open": "5962.000",
#             "volume": "35371",
#             "wave": 0
#         },
#         {
#             "close": "5964.000",
#             "ctm": "1718199000",
#             "ctmfmt": "2024-06-12 21:30:00",
#             "high": "5980.000",
#             "low": "5962.000",
#             "open": "5976.000",
#             "volume": "67774",
#             "wave": 0
#         },
#         {
#             "close": "5964.000",
#             "ctm": "1718200800",
#             "ctmfmt": "2024-06-12 22:00:00",
#             "high": "5968.000",
#             "low": "5956.000",
#             "open": "5966.000",
#             "volume": "37755",
#             "wave": 0
#         },
#         {
#             "close": "5972.000",
#             "ctm": "1718202600",
#             "ctmfmt": "2024-06-12 22:30:00",
#             "high": "5976.000",
#             "low": "5962.000",
#             "open": "5966.000",
#             "volume": "32029",
#             "wave": 0
#         },
#         {
#             "close": "5952.000",
#             "ctm": "1718204400",
#             "ctmfmt": "2024-06-12 23:00:00",
#             "high": "5972.000",
#             "low": "5952.000",
#             "open": "5970.000",
#             "volume": "53411",
#             "wave": 0
#         },
#         {
#             "close": "5948.000",
#             "ctm": "1718242200",
#             "ctmfmt": "2024-06-13 09:30:00",
#             "high": "5954.000",
#             "low": "5936.000",
#             "open": "5954.000",
#             "volume": "58217",
#             "wave": 0
#         },
#         {
#             "close": "5950.000",
#             "ctm": "1718244000",
#             "ctmfmt": "2024-06-13 10:00:00",
#             "high": "5956.000",
#             "low": "5942.000",
#             "open": "5948.000",
#             "volume": "17703",
#             "wave": 0
#         },
#         {
#             "close": "5954.000",
#             "ctm": "1718246700",
#             "ctmfmt": "2024-06-13 10:45:00",
#             "high": "5960.000",
#             "low": "5946.000",
#             "open": "5960.000",
#             "volume": "10188",
#             "wave": 0
#         },
#         {
#             "close": "5948.000",
#             "ctm": "1718248500",
#             "ctmfmt": "2024-06-13 11:15:00",
#             "high": "5958.000",
#             "low": "5942.000",
#             "open": "5956.000",
#             "volume": "19513",
#             "wave": 0
#         },
#         {
#             "close": "5938.000",
#             "ctm": "1718257500",
#             "ctmfmt": "2024-06-13 13:45:00",
#             "high": "5950.000",
#             "low": "5932.000",
#             "open": "5948.000",
#             "volume": "42039",
#             "wave": 0
#         },
#         {
#             "close": "5938.000",
#             "ctm": "1718259300",
#             "ctmfmt": "2024-06-13 14:15:00",
#             "high": "5948.000",
#             "low": "5936.000",
#             "open": "5940.000",
#             "volume": "20493",
#             "wave": 0
#         },
#         {
#             "close": "5948.000",
#             "ctm": "1718261100",
#             "ctmfmt": "2024-06-13 14:45:00",
#             "high": "5948.000",
#             "low": "5934.000",
#             "open": "5938.000",
#             "volume": "15655",
#             "wave": 0
#         },
#         {
#             "close": "5946.000",
#             "ctm": "1718262000",
#             "ctmfmt": "2024-06-13 15:00:00",
#             "high": "5950.000",
#             "low": "5940.000",
#             "open": "5948.000",
#             "volume": "19803",
#             "wave": 0
#         },
#         {
#             "close": "5948.000",
#             "ctm": "1718285400",
#             "ctmfmt": "2024-06-13 21:30:00",
#             "high": "5958.000",
#             "low": "5946.000",
#             "open": "5948.000",
#             "volume": "66766",
#             "wave": 0
#         },
#         {
#             "close": "5946.000",
#             "ctm": "1718287200",
#             "ctmfmt": "2024-06-13 22:00:00",
#             "high": "5954.000",
#             "low": "5944.000",
#             "open": "5950.000",
#             "volume": "19871",
#             "wave": 0
#         },
#         {
#             "close": "5952.000",
#             "ctm": "1718289000",
#             "ctmfmt": "2024-06-13 22:30:00",
#             "high": "5954.000",
#             "low": "5944.000",
#             "open": "5946.000",
#             "volume": "17194",
#             "wave": 0
#         },
#         {
#             "close": "5952.000",
#             "ctm": "1718290800",
#             "ctmfmt": "2024-06-13 23:00:00",
#             "high": "5958.000",
#             "low": "5948.000",
#             "open": "5952.000",
#             "volume": "26365",
#             "wave": 0
#         },
#         {
#             "close": "5930.000",
#             "ctm": "1718328600",
#             "ctmfmt": "2024-06-14 09:30:00",
#             "high": "5946.000",
#             "low": "5924.000",
#             "open": "5936.000",
#             "volume": "62137",
#             "wave": 0
#         },
#         {
#             "close": "5936.000",
#             "ctm": "1718330400",
#             "ctmfmt": "2024-06-14 10:00:00",
#             "high": "5940.000",
#             "low": "5928.000",
#             "open": "5930.000",
#             "volume": "31530",
#             "wave": 0
#         },
#         {
#             "close": "5946.000",
#             "ctm": "1718333100",
#             "ctmfmt": "2024-06-14 10:45:00",
#             "high": "5952.000",
#             "low": "5934.000",
#             "open": "5936.000",
#             "volume": "33133",
#             "wave": 0
#         },
#         {
#             "close": "5944.000",
#             "ctm": "1718334900",
#             "ctmfmt": "2024-06-14 11:15:00",
#             "high": "5948.000",
#             "low": "5938.000",
#             "open": "5946.000",
#             "volume": "22113",
#             "wave": 0
#         },
#         {
#             "close": "5962.000",
#             "ctm": "1718343900",
#             "ctmfmt": "2024-06-14 13:45:00",
#             "high": "5966.000",
#             "low": "5940.000",
#             "open": "5946.000",
#             "volume": "59476",
#             "wave": 0
#         },
#         {
#             "close": "5950.000",
#             "ctm": "1718345700",
#             "ctmfmt": "2024-06-14 14:15:00",
#             "high": "5962.000",
#             "low": "5948.000",
#             "open": "5962.000",
#             "volume": "29164",
#             "wave": 0
#         },
#         {
#             "close": "5952.000",
#             "ctm": "1718347500",
#             "ctmfmt": "2024-06-14 14:45:00",
#             "high": "5962.000",
#             "low": "5946.000",
#             "open": "5950.000",
#             "volume": "26925",
#             "wave": 0
#         }
#     ]
#     ready_data_60m = [
#         {
#             "close": "5900.000",
#             "ctm": "1704438000",
#             "ctmfmt": "2024-01-05 15:00:00",
#             "high": "5926.000",
#             "low": "5890.000",
#             "open": "5898.000",
#             "volume": "144615",
#             "wave": 0
#         },
#         {
#             "close": "5916.000",
#             "ctm": "1704463200",
#             "ctmfmt": "2024-01-05 22:00:00",
#             "high": "5924.000",
#             "low": "5872.000",
#             "open": "5894.000",
#             "volume": "212427",
#             "wave": 0
#         },
#         {
#             "close": "5944.000",
#             "ctm": "1704466800",
#             "ctmfmt": "2024-01-05 23:00:00",
#             "high": "5952.000",
#             "low": "5916.000",
#             "open": "5916.000",
#             "volume": "190440",
#             "wave": 0
#         },
#         {
#             "close": "5836.000",
#             "ctm": "1704679200",
#             "ctmfmt": "2024-01-08 10:00:00",
#             "high": "5940.000",
#             "low": "5834.000",
#             "open": "5940.000",
#             "volume": "350305",
#             "wave": 0
#         },
#         {
#             "close": "5788.000",
#             "ctm": "1704683700",
#             "ctmfmt": "2024-01-08 11:15:00",
#             "high": "5838.000",
#             "low": "5772.000",
#             "open": "5836.000",
#             "volume": "314589",
#             "wave": 0
#         },
#         {
#             "close": "5792.000",
#             "ctm": "1704694500",
#             "ctmfmt": "2024-01-08 14:15:00",
#             "high": "5804.000",
#             "low": "5776.000",
#             "open": "5788.000",
#             "volume": "125477",
#             "wave": 0
#         },
#         {
#             "close": "5776.000",
#             "ctm": "1704697200",
#             "ctmfmt": "2024-01-08 15:00:00",
#             "high": "5794.000",
#             "low": "5766.000",
#             "open": "5792.000",
#             "volume": "144334",
#             "wave": 0
#         },
#         {
#             "close": "5744.000",
#             "ctm": "1704722400",
#             "ctmfmt": "2024-01-08 22:00:00",
#             "high": "5772.000",
#             "low": "5740.000",
#             "open": "5766.000",
#             "volume": "191790",
#             "wave": 0
#         },
#         {
#             "close": "5736.000",
#             "ctm": "1704726000",
#             "ctmfmt": "2024-01-08 23:00:00",
#             "high": "5746.000",
#             "low": "5726.000",
#             "open": "5742.000",
#             "volume": "124915",
#             "wave": 0
#         },
#         {
#             "close": "5730.000",
#             "ctm": "1704765600",
#             "ctmfmt": "2024-01-09 10:00:00",
#             "high": "5758.000",
#             "low": "5720.000",
#             "open": "5748.000",
#             "volume": "164384",
#             "wave": 0
#         },
#         {
#             "close": "5744.000",
#             "ctm": "1704770100",
#             "ctmfmt": "2024-01-09 11:15:00",
#             "high": "5748.000",
#             "low": "5726.000",
#             "open": "5730.000",
#             "volume": "91147",
#             "wave": 0
#         },
#         {
#             "close": "5712.000",
#             "ctm": "1704780900",
#             "ctmfmt": "2024-01-09 14:15:00",
#             "high": "5760.000",
#             "low": "5712.000",
#             "open": "5744.000",
#             "volume": "152099",
#             "wave": 0
#         },
#         {
#             "close": "5714.000",
#             "ctm": "1704783600",
#             "ctmfmt": "2024-01-09 15:00:00",
#             "high": "5728.000",
#             "low": "5706.000",
#             "open": "5712.000",
#             "volume": "102775",
#             "wave": 0
#         },
#         {
#             "close": "5736.000",
#             "ctm": "1704808800",
#             "ctmfmt": "2024-01-09 22:00:00",
#             "high": "5760.000",
#             "low": "5734.000",
#             "open": "5754.000",
#             "volume": "220860",
#             "wave": 0
#         },
#         {
#             "close": "5736.000",
#             "ctm": "1704812400",
#             "ctmfmt": "2024-01-09 23:00:00",
#             "high": "5754.000",
#             "low": "5734.000",
#             "open": "5738.000",
#             "volume": "75950",
#             "wave": 0
#         },
#         {
#             "close": "5760.000",
#             "ctm": "1704852000",
#             "ctmfmt": "2024-01-10 10:00:00",
#             "high": "5776.000",
#             "low": "5734.000",
#             "open": "5740.000",
#             "volume": "191071",
#             "wave": 0
#         },
#         {
#             "close": "5748.000",
#             "ctm": "1704856500",
#             "ctmfmt": "2024-01-10 11:15:00",
#             "high": "5774.000",
#             "low": "5740.000",
#             "open": "5760.000",
#             "volume": "109356",
#             "wave": 0
#         },
#         {
#             "close": "5734.000",
#             "ctm": "1704867300",
#             "ctmfmt": "2024-01-10 14:15:00",
#             "high": "5756.000",
#             "low": "5730.000",
#             "open": "5748.000",
#             "volume": "122191",
#             "wave": 0
#         },
#         {
#             "close": "5744.000",
#             "ctm": "1704870000",
#             "ctmfmt": "2024-01-10 15:00:00",
#             "high": "5746.000",
#             "low": "5728.000",
#             "open": "5736.000",
#             "volume": "94980",
#             "wave": 0
#         },
#         {
#             "close": "5756.000",
#             "ctm": "1704895200",
#             "ctmfmt": "2024-01-10 22:00:00",
#             "high": "5766.000",
#             "low": "5716.000",
#             "open": "5742.000",
#             "volume": "181999",
#             "wave": 0
#         },
#         {
#             "close": "5748.000",
#             "ctm": "1704898800",
#             "ctmfmt": "2024-01-10 23:00:00",
#             "high": "5758.000",
#             "low": "5740.000",
#             "open": "5756.000",
#             "volume": "72474",
#             "wave": 0
#         },
#         {
#             "close": "5718.000",
#             "ctm": "1704938400",
#             "ctmfmt": "2024-01-11 10:00:00",
#             "high": "5744.000",
#             "low": "5696.000",
#             "open": "5714.000",
#             "volume": "251617",
#             "wave": 0
#         },
#         {
#             "close": "5708.000",
#             "ctm": "1704942900",
#             "ctmfmt": "2024-01-11 11:15:00",
#             "high": "5726.000",
#             "low": "5690.000",
#             "open": "5718.000",
#             "volume": "128152",
#             "wave": 0
#         },
#         {
#             "close": "5730.000",
#             "ctm": "1704953700",
#             "ctmfmt": "2024-01-11 14:15:00",
#             "high": "5746.000",
#             "low": "5708.000",
#             "open": "5710.000",
#             "volume": "126001",
#             "wave": 0
#         },
#         {
#             "close": "5734.000",
#             "ctm": "1704956400",
#             "ctmfmt": "2024-01-11 15:00:00",
#             "high": "5740.000",
#             "low": "5726.000",
#             "open": "5732.000",
#             "volume": "78483",
#             "wave": 0
#         },
#         {
#             "close": "5746.000",
#             "ctm": "1704981600",
#             "ctmfmt": "2024-01-11 22:00:00",
#             "high": "5768.000",
#             "low": "5742.000",
#             "open": "5754.000",
#             "volume": "189785",
#             "wave": 0
#         },
#         {
#             "close": "5742.000",
#             "ctm": "1704985200",
#             "ctmfmt": "2024-01-11 23:00:00",
#             "high": "5760.000",
#             "low": "5736.000",
#             "open": "5746.000",
#             "volume": "85471",
#             "wave": 0
#         },
#         {
#             "close": "5812.000",
#             "ctm": "1705024800",
#             "ctmfmt": "2024-01-12 10:00:00",
#             "high": "5818.000",
#             "low": "5746.000",
#             "open": "5748.000",
#             "volume": "288779",
#             "wave": 0
#         },
#         {
#             "close": "5784.000",
#             "ctm": "1705029300",
#             "ctmfmt": "2024-01-12 11:15:00",
#             "high": "5814.000",
#             "low": "5778.000",
#             "open": "5814.000",
#             "volume": "128570",
#             "wave": 0
#         },
#         {
#             "close": "5784.000",
#             "ctm": "1705040100",
#             "ctmfmt": "2024-01-12 14:15:00",
#             "high": "5788.000",
#             "low": "5772.000",
#             "open": "5786.000",
#             "volume": "68030",
#             "wave": 0
#         },
#         {
#             "close": "5778.000",
#             "ctm": "1705042800",
#             "ctmfmt": "2024-01-12 15:00:00",
#             "high": "5788.000",
#             "low": "5766.000",
#             "open": "5784.000",
#             "volume": "75843",
#             "wave": 0
#         },
#         {
#             "close": "5796.000",
#             "ctm": "1705068000",
#             "ctmfmt": "2024-01-12 22:00:00",
#             "high": "5822.000",
#             "low": "5788.000",
#             "open": "5802.000",
#             "volume": "216411",
#             "wave": 0
#         },
#         {
#             "close": "5800.000",
#             "ctm": "1705071600",
#             "ctmfmt": "2024-01-12 23:00:00",
#             "high": "5808.000",
#             "low": "5784.000",
#             "open": "5796.000",
#             "volume": "101412",
#             "wave": 0
#         },
#         {
#             "close": "5774.000",
#             "ctm": "1705284000",
#             "ctmfmt": "2024-01-15 10:00:00",
#             "high": "5782.000",
#             "low": "5746.000",
#             "open": "5772.000",
#             "volume": "220981",
#             "wave": 0
#         },
#         {
#             "close": "5790.000",
#             "ctm": "1705288500",
#             "ctmfmt": "2024-01-15 11:15:00",
#             "high": "5804.000",
#             "low": "5772.000",
#             "open": "5772.000",
#             "volume": "116668",
#             "wave": 0
#         },
#         {
#             "close": "5776.000",
#             "ctm": "1705299300",
#             "ctmfmt": "2024-01-15 14:15:00",
#             "high": "5792.000",
#             "low": "5770.000",
#             "open": "5790.000",
#             "volume": "82924",
#             "wave": 0
#         },
#         {
#             "close": "5764.000",
#             "ctm": "1705302000",
#             "ctmfmt": "2024-01-15 15:00:00",
#             "high": "5780.000",
#             "low": "5762.000",
#             "open": "5776.000",
#             "volume": "77204",
#             "wave": 0
#         },
#         {
#             "close": "5788.000",
#             "ctm": "1705327200",
#             "ctmfmt": "2024-01-15 22:00:00",
#             "high": "5796.000",
#             "low": "5738.000",
#             "open": "5750.000",
#             "volume": "169748",
#             "wave": 0
#         },
#         {
#             "close": "5794.000",
#             "ctm": "1705330800",
#             "ctmfmt": "2024-01-15 23:00:00",
#             "high": "5808.000",
#             "low": "5786.000",
#             "open": "5790.000",
#             "volume": "96958",
#             "wave": 0
#         },
#         {
#             "close": "5838.000",
#             "ctm": "1705370400",
#             "ctmfmt": "2024-01-16 10:00:00",
#             "high": "5842.000",
#             "low": "5796.000",
#             "open": "5808.000",
#             "volume": "195031",
#             "wave": 0
#         },
#         {
#             "close": "5830.000",
#             "ctm": "1705374900",
#             "ctmfmt": "2024-01-16 11:15:00",
#             "high": "5846.000",
#             "low": "5820.000",
#             "open": "5840.000",
#             "volume": "104475",
#             "wave": 0
#         },
#         {
#             "close": "5822.000",
#             "ctm": "1705385700",
#             "ctmfmt": "2024-01-16 14:15:00",
#             "high": "5838.000",
#             "low": "5816.000",
#             "open": "5832.000",
#             "volume": "87800",
#             "wave": 0
#         },
#         {
#             "close": "5828.000",
#             "ctm": "1705388400",
#             "ctmfmt": "2024-01-16 15:00:00",
#             "high": "5830.000",
#             "low": "5806.000",
#             "open": "5824.000",
#             "volume": "99380",
#             "wave": 0
#         },
#         {
#             "close": "5832.000",
#             "ctm": "1705413600",
#             "ctmfmt": "2024-01-16 22:00:00",
#             "high": "5850.000",
#             "low": "5826.000",
#             "open": "5836.000",
#             "volume": "172320",
#             "wave": 0
#         },
#         {
#             "close": "5820.000",
#             "ctm": "1705417200",
#             "ctmfmt": "2024-01-16 23:00:00",
#             "high": "5842.000",
#             "low": "5818.000",
#             "open": "5830.000",
#             "volume": "69918",
#             "wave": 0
#         },
#         {
#             "close": "5818.000",
#             "ctm": "1705456800",
#             "ctmfmt": "2024-01-17 10:00:00",
#             "high": "5830.000",
#             "low": "5800.000",
#             "open": "5816.000",
#             "volume": "149898",
#             "wave": 0
#         },
#         {
#             "close": "5832.000",
#             "ctm": "1705461300",
#             "ctmfmt": "2024-01-17 11:15:00",
#             "high": "5836.000",
#             "low": "5808.000",
#             "open": "5820.000",
#             "volume": "114887",
#             "wave": 0
#         },
#         {
#             "close": "5814.000",
#             "ctm": "1705472100",
#             "ctmfmt": "2024-01-17 14:15:00",
#             "high": "5836.000",
#             "low": "5812.000",
#             "open": "5834.000",
#             "volume": "78791",
#             "wave": 0
#         },
#         {
#             "close": "5814.000",
#             "ctm": "1705474800",
#             "ctmfmt": "2024-01-17 15:00:00",
#             "high": "5824.000",
#             "low": "5806.000",
#             "open": "5816.000",
#             "volume": "95886",
#             "wave": 0
#         },
#         {
#             "close": "5828.000",
#             "ctm": "1705500000",
#             "ctmfmt": "2024-01-17 22:00:00",
#             "high": "5848.000",
#             "low": "5788.000",
#             "open": "5802.000",
#             "volume": "272746",
#             "wave": 0
#         },
#         {
#             "close": "5834.000",
#             "ctm": "1705503600",
#             "ctmfmt": "2024-01-17 23:00:00",
#             "high": "5848.000",
#             "low": "5818.000",
#             "open": "5826.000",
#             "volume": "155648",
#             "wave": 0
#         },
#         {
#             "close": "5844.000",
#             "ctm": "1705543200",
#             "ctmfmt": "2024-01-18 10:00:00",
#             "high": "5874.000",
#             "low": "5832.000",
#             "open": "5860.000",
#             "volume": "319098",
#             "wave": 0
#         },
#         {
#             "close": "5832.000",
#             "ctm": "1705547700",
#             "ctmfmt": "2024-01-18 11:15:00",
#             "high": "5846.000",
#             "low": "5812.000",
#             "open": "5846.000",
#             "volume": "143527",
#             "wave": 0
#         },
#         {
#             "close": "5862.000",
#             "ctm": "1705558500",
#             "ctmfmt": "2024-01-18 14:15:00",
#             "high": "5876.000",
#             "low": "5828.000",
#             "open": "5832.000",
#             "volume": "161711",
#             "wave": 0
#         },
#         {
#             "close": "5844.000",
#             "ctm": "1705561200",
#             "ctmfmt": "2024-01-18 15:00:00",
#             "high": "5868.000",
#             "low": "5844.000",
#             "open": "5862.000",
#             "volume": "117095",
#             "wave": 0
#         },
#         {
#             "close": "5856.000",
#             "ctm": "1705586400",
#             "ctmfmt": "2024-01-18 22:00:00",
#             "high": "5860.000",
#             "low": "5836.000",
#             "open": "5844.000",
#             "volume": "170121",
#             "wave": 0
#         },
#         {
#             "close": "5842.000",
#             "ctm": "1705590000",
#             "ctmfmt": "2024-01-18 23:00:00",
#             "high": "5860.000",
#             "low": "5836.000",
#             "open": "5856.000",
#             "volume": "72245",
#             "wave": 0
#         },
#         {
#             "close": "5878.000",
#             "ctm": "1705629600",
#             "ctmfmt": "2024-01-19 10:00:00",
#             "high": "5884.000",
#             "low": "5858.000",
#             "open": "5862.000",
#             "volume": "199236",
#             "wave": 0
#         },
#         {
#             "close": "5886.000",
#             "ctm": "1705634100",
#             "ctmfmt": "2024-01-19 11:15:00",
#             "high": "5888.000",
#             "low": "5866.000",
#             "open": "5878.000",
#             "volume": "91442",
#             "wave": 0
#         },
#         {
#             "close": "5896.000",
#             "ctm": "1705644900",
#             "ctmfmt": "2024-01-19 14:15:00",
#             "high": "5902.000",
#             "low": "5872.000",
#             "open": "5886.000",
#             "volume": "114487",
#             "wave": 0
#         },
#         {
#             "close": "5898.000",
#             "ctm": "1705647600",
#             "ctmfmt": "2024-01-19 15:00:00",
#             "high": "5904.000",
#             "low": "5882.000",
#             "open": "5898.000",
#             "volume": "119709",
#             "wave": 0
#         },
#         {
#             "close": "5904.000",
#             "ctm": "1705672800",
#             "ctmfmt": "2024-01-19 22:00:00",
#             "high": "5908.000",
#             "low": "5880.000",
#             "open": "5888.000",
#             "volume": "131373",
#             "wave": 0
#         },
#         {
#             "close": "5904.000",
#             "ctm": "1705676400",
#             "ctmfmt": "2024-01-19 23:00:00",
#             "high": "5910.000",
#             "low": "5888.000",
#             "open": "5902.000",
#             "volume": "74095",
#             "wave": 0
#         },
#         {
#             "close": "5918.000",
#             "ctm": "1705888800",
#             "ctmfmt": "2024-01-22 10:00:00",
#             "high": "5920.000",
#             "low": "5874.000",
#             "open": "5882.000",
#             "volume": "195000",
#             "wave": 0
#         },
#         {
#             "close": "5944.000",
#             "ctm": "1705893300",
#             "ctmfmt": "2024-01-22 11:15:00",
#             "high": "5946.000",
#             "low": "5914.000",
#             "open": "5918.000",
#             "volume": "118238",
#             "wave": 0
#         },
#         {
#             "close": "5934.000",
#             "ctm": "1705904100",
#             "ctmfmt": "2024-01-22 14:15:00",
#             "high": "5948.000",
#             "low": "5920.000",
#             "open": "5944.000",
#             "volume": "104663",
#             "wave": 0
#         },
#         {
#             "close": "5928.000",
#             "ctm": "1705906800",
#             "ctmfmt": "2024-01-22 15:00:00",
#             "high": "5938.000",
#             "low": "5914.000",
#             "open": "5934.000",
#             "volume": "59570",
#             "wave": 0
#         },
#         {
#             "close": "5912.000",
#             "ctm": "1705932000",
#             "ctmfmt": "2024-01-22 22:00:00",
#             "high": "5930.000",
#             "low": "5900.000",
#             "open": "5930.000",
#             "volume": "157149",
#             "wave": 0
#         },
#         {
#             "close": "5922.000",
#             "ctm": "1705935600",
#             "ctmfmt": "2024-01-22 23:00:00",
#             "high": "5928.000",
#             "low": "5908.000",
#             "open": "5912.000",
#             "volume": "73930",
#             "wave": 0
#         },
#         {
#             "close": "5948.000",
#             "ctm": "1705975200",
#             "ctmfmt": "2024-01-23 10:00:00",
#             "high": "5952.000",
#             "low": "5924.000",
#             "open": "5928.000",
#             "volume": "144712",
#             "wave": 0
#         },
#         {
#             "close": "5934.000",
#             "ctm": "1705979700",
#             "ctmfmt": "2024-01-23 11:15:00",
#             "high": "5956.000",
#             "low": "5928.000",
#             "open": "5948.000",
#             "volume": "78620",
#             "wave": 0
#         },
#         {
#             "close": "5968.000",
#             "ctm": "1705990500",
#             "ctmfmt": "2024-01-23 14:15:00",
#             "high": "5970.000",
#             "low": "5930.000",
#             "open": "5932.000",
#             "volume": "101723",
#             "wave": 0
#         },
#         {
#             "close": "5982.000",
#             "ctm": "1705993200",
#             "ctmfmt": "2024-01-23 15:00:00",
#             "high": "5986.000",
#             "low": "5964.000",
#             "open": "5970.000",
#             "volume": "122485",
#             "wave": 0
#         },
#         {
#             "close": "5978.000",
#             "ctm": "1706018400",
#             "ctmfmt": "2024-01-23 22:00:00",
#             "high": "5990.000",
#             "low": "5968.000",
#             "open": "5972.000",
#             "volume": "190569",
#             "wave": 0
#         },
#         {
#             "close": "5974.000",
#             "ctm": "1706022000",
#             "ctmfmt": "2024-01-23 23:00:00",
#             "high": "5980.000",
#             "low": "5964.000",
#             "open": "5978.000",
#             "volume": "104003",
#             "wave": 0
#         },
#         {
#             "close": "5988.000",
#             "ctm": "1706061600",
#             "ctmfmt": "2024-01-24 10:00:00",
#             "high": "5996.000",
#             "low": "5962.000",
#             "open": "5972.000",
#             "volume": "125465",
#             "wave": 0
#         },
#         {
#             "close": "6000.000",
#             "ctm": "1706066100",
#             "ctmfmt": "2024-01-24 11:15:00",
#             "high": "6010.000",
#             "low": "5982.000",
#             "open": "5988.000",
#             "volume": "116698",
#             "wave": 0
#         },
#         {
#             "close": "6010.000",
#             "ctm": "1706076900",
#             "ctmfmt": "2024-01-24 14:15:00",
#             "high": "6016.000",
#             "low": "5996.000",
#             "open": "6000.000",
#             "volume": "116815",
#             "wave": 0
#         },
#         {
#             "close": "6028.000",
#             "ctm": "1706079600",
#             "ctmfmt": "2024-01-24 15:00:00",
#             "high": "6040.000",
#             "low": "6006.000",
#             "open": "6010.000",
#             "volume": "143443",
#             "wave": 0
#         },
#         {
#             "close": "6040.000",
#             "ctm": "1706104800",
#             "ctmfmt": "2024-01-24 22:00:00",
#             "high": "6088.000",
#             "low": "6026.000",
#             "open": "6050.000",
#             "volume": "455983",
#             "wave": 0
#         },
#         {
#             "close": "6022.000",
#             "ctm": "1706108400",
#             "ctmfmt": "2024-01-24 23:00:00",
#             "high": "6042.000",
#             "low": "6008.000",
#             "open": "6042.000",
#             "volume": "161462",
#             "wave": 0
#         },
#         {
#             "close": "6024.000",
#             "ctm": "1706148000",
#             "ctmfmt": "2024-01-25 10:00:00",
#             "high": "6042.000",
#             "low": "6016.000",
#             "open": "6028.000",
#             "volume": "114323",
#             "wave": 0
#         },
#         {
#             "close": "6028.000",
#             "ctm": "1706152500",
#             "ctmfmt": "2024-01-25 11:15:00",
#             "high": "6040.000",
#             "low": "6022.000",
#             "open": "6024.000",
#             "volume": "88918",
#             "wave": 0
#         },
#         {
#             "close": "6046.000",
#             "ctm": "1706163300",
#             "ctmfmt": "2024-01-25 14:15:00",
#             "high": "6048.000",
#             "low": "6014.000",
#             "open": "6028.000",
#             "volume": "121483",
#             "wave": 0
#         },
#         {
#             "close": "6014.000",
#             "ctm": "1706166000",
#             "ctmfmt": "2024-01-25 15:00:00",
#             "high": "6054.000",
#             "low": "6012.000",
#             "open": "6048.000",
#             "volume": "121371",
#             "wave": 0
#         },
#         {
#             "close": "6048.000",
#             "ctm": "1706191200",
#             "ctmfmt": "2024-01-25 22:00:00",
#             "high": "6050.000",
#             "low": "6010.000",
#             "open": "6010.000",
#             "volume": "195706",
#             "wave": 0
#         },
#         {
#             "close": "6050.000",
#             "ctm": "1706194800",
#             "ctmfmt": "2024-01-25 23:00:00",
#             "high": "6058.000",
#             "low": "6034.000",
#             "open": "6048.000",
#             "volume": "100604",
#             "wave": 0
#         },
#         {
#             "close": "6038.000",
#             "ctm": "1706234400",
#             "ctmfmt": "2024-01-26 10:00:00",
#             "high": "6092.000",
#             "low": "6030.000",
#             "open": "6060.000",
#             "volume": "228683",
#             "wave": 0
#         },
#         {
#             "close": "6066.000",
#             "ctm": "1706238900",
#             "ctmfmt": "2024-01-26 11:15:00",
#             "high": "6066.000",
#             "low": "6034.000",
#             "open": "6038.000",
#             "volume": "94694",
#             "wave": 0
#         },
#         {
#             "close": "6040.000",
#             "ctm": "1706249700",
#             "ctmfmt": "2024-01-26 14:15:00",
#             "high": "6070.000",
#             "low": "6036.000",
#             "open": "6064.000",
#             "volume": "124660",
#             "wave": 0
#         },
#         {
#             "close": "6040.000",
#             "ctm": "1706252400",
#             "ctmfmt": "2024-01-26 15:00:00",
#             "high": "6044.000",
#             "low": "6024.000",
#             "open": "6040.000",
#             "volume": "106097",
#             "wave": 0
#         },
#         {
#             "close": "6018.000",
#             "ctm": "1706277600",
#             "ctmfmt": "2024-01-26 22:00:00",
#             "high": "6042.000",
#             "low": "6012.000",
#             "open": "6032.000",
#             "volume": "182265",
#             "wave": 0
#         },
#         {
#             "close": "6022.000",
#             "ctm": "1706281200",
#             "ctmfmt": "2024-01-26 23:00:00",
#             "high": "6030.000",
#             "low": "5994.000",
#             "open": "6018.000",
#             "volume": "149119",
#             "wave": 0
#         },
#         {
#             "close": "6052.000",
#             "ctm": "1706493600",
#             "ctmfmt": "2024-01-29 10:00:00",
#             "high": "6060.000",
#             "low": "6036.000",
#             "open": "6042.000",
#             "volume": "212002",
#             "wave": 0
#         },
#         {
#             "close": "6036.000",
#             "ctm": "1706498100",
#             "ctmfmt": "2024-01-29 11:15:00",
#             "high": "6054.000",
#             "low": "6028.000",
#             "open": "6050.000",
#             "volume": "85564",
#             "wave": 0
#         },
#         {
#             "close": "6020.000",
#             "ctm": "1706508900",
#             "ctmfmt": "2024-01-29 14:15:00",
#             "high": "6048.000",
#             "low": "6020.000",
#             "open": "6036.000",
#             "volume": "81128",
#             "wave": 0
#         },
#         {
#             "close": "6028.000",
#             "ctm": "1706511600",
#             "ctmfmt": "2024-01-29 15:00:00",
#             "high": "6032.000",
#             "low": "6012.000",
#             "open": "6020.000",
#             "volume": "84393",
#             "wave": 0
#         },
#         {
#             "close": "5994.000",
#             "ctm": "1706536800",
#             "ctmfmt": "2024-01-29 22:00:00",
#             "high": "6024.000",
#             "low": "5982.000",
#             "open": "6024.000",
#             "volume": "212066",
#             "wave": 0
#         },
#         {
#             "close": "5994.000",
#             "ctm": "1706540400",
#             "ctmfmt": "2024-01-29 23:00:00",
#             "high": "6004.000",
#             "low": "5980.000",
#             "open": "5994.000",
#             "volume": "90193",
#             "wave": 0
#         },
#         {
#             "close": "6008.000",
#             "ctm": "1706580000",
#             "ctmfmt": "2024-01-30 10:00:00",
#             "high": "6010.000",
#             "low": "5988.000",
#             "open": "5992.000",
#             "volume": "124671",
#             "wave": 0
#         },
#         {
#             "close": "6016.000",
#             "ctm": "1706584500",
#             "ctmfmt": "2024-01-30 11:15:00",
#             "high": "6018.000",
#             "low": "6000.000",
#             "open": "6006.000",
#             "volume": "87048",
#             "wave": 0
#         },
#         {
#             "close": "6008.000",
#             "ctm": "1706595300",
#             "ctmfmt": "2024-01-30 14:15:00",
#             "high": "6032.000",
#             "low": "6002.000",
#             "open": "6016.000",
#             "volume": "127316",
#             "wave": 0
#         },
#         {
#             "close": "6014.000",
#             "ctm": "1706598000",
#             "ctmfmt": "2024-01-30 15:00:00",
#             "high": "6018.000",
#             "low": "5996.000",
#             "open": "6010.000",
#             "volume": "79257",
#             "wave": 0
#         },
#         {
#             "close": "5962.000",
#             "ctm": "1706623200",
#             "ctmfmt": "2024-01-30 22:00:00",
#             "high": "6022.000",
#             "low": "5948.000",
#             "open": "6008.000",
#             "volume": "319989",
#             "wave": 0
#         },
#         {
#             "close": "5978.000",
#             "ctm": "1706626800",
#             "ctmfmt": "2024-01-30 23:00:00",
#             "high": "5986.000",
#             "low": "5956.000",
#             "open": "5960.000",
#             "volume": "105205",
#             "wave": 0
#         },
#         {
#             "close": "5954.000",
#             "ctm": "1706666400",
#             "ctmfmt": "2024-01-31 10:00:00",
#             "high": "6002.000",
#             "low": "5948.000",
#             "open": "5992.000",
#             "volume": "143648",
#             "wave": 0
#         },
#         {
#             "close": "5974.000",
#             "ctm": "1706670900",
#             "ctmfmt": "2024-01-31 11:15:00",
#             "high": "5980.000",
#             "low": "5946.000",
#             "open": "5954.000",
#             "volume": "103561",
#             "wave": 0
#         },
#         {
#             "close": "5974.000",
#             "ctm": "1706681700",
#             "ctmfmt": "2024-01-31 14:15:00",
#             "high": "5988.000",
#             "low": "5970.000",
#             "open": "5974.000",
#             "volume": "98290",
#             "wave": 0
#         },
#         {
#             "close": "5968.000",
#             "ctm": "1706684400",
#             "ctmfmt": "2024-01-31 15:00:00",
#             "high": "5980.000",
#             "low": "5964.000",
#             "open": "5974.000",
#             "volume": "61657",
#             "wave": 0
#         },
#         {
#             "close": "5960.000",
#             "ctm": "1706709600",
#             "ctmfmt": "2024-01-31 22:00:00",
#             "high": "5968.000",
#             "low": "5946.000",
#             "open": "5960.000",
#             "volume": "131331",
#             "wave": 0
#         },
#         {
#             "close": "5958.000",
#             "ctm": "1706713200",
#             "ctmfmt": "2024-01-31 23:00:00",
#             "high": "5976.000",
#             "low": "5956.000",
#             "open": "5958.000",
#             "volume": "79854",
#             "wave": 0
#         },
#         {
#             "close": "5924.000",
#             "ctm": "1706752800",
#             "ctmfmt": "2024-02-01 10:00:00",
#             "high": "5946.000",
#             "low": "5912.000",
#             "open": "5946.000",
#             "volume": "234982",
#             "wave": 0
#         },
#         {
#             "close": "5908.000",
#             "ctm": "1706757300",
#             "ctmfmt": "2024-02-01 11:15:00",
#             "high": "5938.000",
#             "low": "5906.000",
#             "open": "5924.000",
#             "volume": "98407",
#             "wave": 0
#         },
#         {
#             "close": "5878.000",
#             "ctm": "1706768100",
#             "ctmfmt": "2024-02-01 14:15:00",
#             "high": "5914.000",
#             "low": "5870.000",
#             "open": "5908.000",
#             "volume": "191052",
#             "wave": 0
#         },
#         {
#             "close": "5878.000",
#             "ctm": "1706770800",
#             "ctmfmt": "2024-02-01 15:00:00",
#             "high": "5884.000",
#             "low": "5874.000",
#             "open": "5878.000",
#             "volume": "70286",
#             "wave": 0
#         },
#         {
#             "close": "5890.000",
#             "ctm": "1706796000",
#             "ctmfmt": "2024-02-01 22:00:00",
#             "high": "5902.000",
#             "low": "5866.000",
#             "open": "5878.000",
#             "volume": "165392",
#             "wave": 0
#         },
#         {
#             "close": "5892.000",
#             "ctm": "1706799600",
#             "ctmfmt": "2024-02-01 23:00:00",
#             "high": "5898.000",
#             "low": "5878.000",
#             "open": "5890.000",
#             "volume": "73159",
#             "wave": 0
#         },
#         {
#             "close": "5854.000",
#             "ctm": "1706839200",
#             "ctmfmt": "2024-02-02 10:00:00",
#             "high": "5878.000",
#             "low": "5850.000",
#             "open": "5858.000",
#             "volume": "178086",
#             "wave": 0
#         },
#         {
#             "close": "5844.000",
#             "ctm": "1706843700",
#             "ctmfmt": "2024-02-02 11:15:00",
#             "high": "5856.000",
#             "low": "5840.000",
#             "open": "5854.000",
#             "volume": "97299",
#             "wave": 0
#         },
#         {
#             "close": "5832.000",
#             "ctm": "1706854500",
#             "ctmfmt": "2024-02-02 14:15:00",
#             "high": "5846.000",
#             "low": "5824.000",
#             "open": "5842.000",
#             "volume": "72760",
#             "wave": 0
#         },
#         {
#             "close": "5846.000",
#             "ctm": "1706857200",
#             "ctmfmt": "2024-02-02 15:00:00",
#             "high": "5856.000",
#             "low": "5830.000",
#             "open": "5832.000",
#             "volume": "53433",
#             "wave": 0
#         },
#         {
#             "close": "5828.000",
#             "ctm": "1706882400",
#             "ctmfmt": "2024-02-02 22:00:00",
#             "high": "5846.000",
#             "low": "5824.000",
#             "open": "5844.000",
#             "volume": "110882",
#             "wave": 0
#         },
#         {
#             "close": "5830.000",
#             "ctm": "1706886000",
#             "ctmfmt": "2024-02-02 23:00:00",
#             "high": "5834.000",
#             "low": "5822.000",
#             "open": "5828.000",
#             "volume": "64660",
#             "wave": 0
#         },
#         {
#             "close": "5848.000",
#             "ctm": "1707098400",
#             "ctmfmt": "2024-02-05 10:00:00",
#             "high": "5858.000",
#             "low": "5830.000",
#             "open": "5832.000",
#             "volume": "123434",
#             "wave": 0
#         },
#         {
#             "close": "5856.000",
#             "ctm": "1707102900",
#             "ctmfmt": "2024-02-05 11:15:00",
#             "high": "5864.000",
#             "low": "5836.000",
#             "open": "5848.000",
#             "volume": "80720",
#             "wave": 0
#         },
#         {
#             "close": "5858.000",
#             "ctm": "1707113700",
#             "ctmfmt": "2024-02-05 14:15:00",
#             "high": "5870.000",
#             "low": "5850.000",
#             "open": "5856.000",
#             "volume": "58377",
#             "wave": 0
#         },
#         {
#             "close": "5852.000",
#             "ctm": "1707116400",
#             "ctmfmt": "2024-02-05 15:00:00",
#             "high": "5860.000",
#             "low": "5848.000",
#             "open": "5860.000",
#             "volume": "40996",
#             "wave": 0
#         },
#         {
#             "close": "5848.000",
#             "ctm": "1707141600",
#             "ctmfmt": "2024-02-05 22:00:00",
#             "high": "5852.000",
#             "low": "5834.000",
#             "open": "5846.000",
#             "volume": "108202",
#             "wave": 0
#         },
#         {
#             "close": "5842.000",
#             "ctm": "1707145200",
#             "ctmfmt": "2024-02-05 23:00:00",
#             "high": "5852.000",
#             "low": "5838.000",
#             "open": "5848.000",
#             "volume": "58027",
#             "wave": 0
#         },
#         {
#             "close": "5848.000",
#             "ctm": "1707184800",
#             "ctmfmt": "2024-02-06 10:00:00",
#             "high": "5862.000",
#             "low": "5840.000",
#             "open": "5860.000",
#             "volume": "91613",
#             "wave": 0
#         },
#         {
#             "close": "5860.000",
#             "ctm": "1707189300",
#             "ctmfmt": "2024-02-06 11:15:00",
#             "high": "5864.000",
#             "low": "5844.000",
#             "open": "5848.000",
#             "volume": "58861",
#             "wave": 0
#         },
#         {
#             "close": "5872.000",
#             "ctm": "1707200100",
#             "ctmfmt": "2024-02-06 14:15:00",
#             "high": "5896.000",
#             "low": "5854.000",
#             "open": "5860.000",
#             "volume": "81544",
#             "wave": 0
#         },
#         {
#             "close": "5882.000",
#             "ctm": "1707202800",
#             "ctmfmt": "2024-02-06 15:00:00",
#             "high": "5886.000",
#             "low": "5868.000",
#             "open": "5870.000",
#             "volume": "64444",
#             "wave": 0
#         },
#         {
#             "close": "5890.000",
#             "ctm": "1707228000",
#             "ctmfmt": "2024-02-06 22:00:00",
#             "high": "5898.000",
#             "low": "5878.000",
#             "open": "5888.000",
#             "volume": "105671",
#             "wave": 0
#         },
#         {
#             "close": "5900.000",
#             "ctm": "1707231600",
#             "ctmfmt": "2024-02-06 23:00:00",
#             "high": "5920.000",
#             "low": "5882.000",
#             "open": "5888.000",
#             "volume": "110900",
#             "wave": 0
#         },
#         {
#             "close": "5906.000",
#             "ctm": "1707271200",
#             "ctmfmt": "2024-02-07 10:00:00",
#             "high": "5910.000",
#             "low": "5892.000",
#             "open": "5900.000",
#             "volume": "93656",
#             "wave": 0
#         },
#         {
#             "close": "5892.000",
#             "ctm": "1707275700",
#             "ctmfmt": "2024-02-07 11:15:00",
#             "high": "5918.000",
#             "low": "5884.000",
#             "open": "5906.000",
#             "volume": "74834",
#             "wave": 0
#         },
#         {
#             "close": "5896.000",
#             "ctm": "1707286500",
#             "ctmfmt": "2024-02-07 14:15:00",
#             "high": "5904.000",
#             "low": "5884.000",
#             "open": "5890.000",
#             "volume": "62305",
#             "wave": 0
#         },
#         {
#             "close": "5902.000",
#             "ctm": "1707289200",
#             "ctmfmt": "2024-02-07 15:00:00",
#             "high": "5908.000",
#             "low": "5896.000",
#             "open": "5896.000",
#             "volume": "45953",
#             "wave": 0
#         },
#         {
#             "close": "5914.000",
#             "ctm": "1707314400",
#             "ctmfmt": "2024-02-07 22:00:00",
#             "high": "5922.000",
#             "low": "5902.000",
#             "open": "5912.000",
#             "volume": "98176",
#             "wave": 0
#         },
#         {
#             "close": "5900.000",
#             "ctm": "1707318000",
#             "ctmfmt": "2024-02-07 23:00:00",
#             "high": "5922.000",
#             "low": "5900.000",
#             "open": "5914.000",
#             "volume": "57638",
#             "wave": 0
#         },
#         {
#             "close": "5922.000",
#             "ctm": "1707357600",
#             "ctmfmt": "2024-02-08 10:00:00",
#             "high": "5928.000",
#             "low": "5900.000",
#             "open": "5906.000",
#             "volume": "80397",
#             "wave": 0
#         },
#         {
#             "close": "5942.000",
#             "ctm": "1707362100",
#             "ctmfmt": "2024-02-08 11:15:00",
#             "high": "5944.000",
#             "low": "5916.000",
#             "open": "5920.000",
#             "volume": "69551",
#             "wave": 0
#         },
#         {
#             "close": "5930.000",
#             "ctm": "1707372900",
#             "ctmfmt": "2024-02-08 14:15:00",
#             "high": "5948.000",
#             "low": "5928.000",
#             "open": "5942.000",
#             "volume": "45657",
#             "wave": 0
#         },
#         {
#             "close": "5914.000",
#             "ctm": "1707375600",
#             "ctmfmt": "2024-02-08 15:00:00",
#             "high": "5934.000",
#             "low": "5908.000",
#             "open": "5930.000",
#             "volume": "70650",
#             "wave": 0
#         },
#         {
#             "close": "6000.000",
#             "ctm": "1708308000",
#             "ctmfmt": "2024-02-19 10:00:00",
#             "high": "6018.000",
#             "low": "5966.000",
#             "open": "5976.000",
#             "volume": "248421",
#             "wave": 0
#         },
#         {
#             "close": "5996.000",
#             "ctm": "1708312500",
#             "ctmfmt": "2024-02-19 11:15:00",
#             "high": "6004.000",
#             "low": "5966.000",
#             "open": "6000.000",
#             "volume": "129731",
#             "wave": 0
#         },
#         {
#             "close": "5988.000",
#             "ctm": "1708323300",
#             "ctmfmt": "2024-02-19 14:15:00",
#             "high": "6000.000",
#             "low": "5976.000",
#             "open": "5998.000",
#             "volume": "61109",
#             "wave": 0
#         },
#         {
#             "close": "5972.000",
#             "ctm": "1708326000",
#             "ctmfmt": "2024-02-19 15:00:00",
#             "high": "5990.000",
#             "low": "5972.000",
#             "open": "5986.000",
#             "volume": "47909",
#             "wave": 0
#         },
#         {
#             "close": "5960.000",
#             "ctm": "1708351200",
#             "ctmfmt": "2024-02-19 22:00:00",
#             "high": "5982.000",
#             "low": "5956.000",
#             "open": "5976.000",
#             "volume": "149354",
#             "wave": 0
#         },
#         {
#             "close": "5958.000",
#             "ctm": "1708354800",
#             "ctmfmt": "2024-02-19 23:00:00",
#             "high": "5962.000",
#             "low": "5948.000",
#             "open": "5958.000",
#             "volume": "59121",
#             "wave": 0
#         },
#         {
#             "close": "5950.000",
#             "ctm": "1708394400",
#             "ctmfmt": "2024-02-20 10:00:00",
#             "high": "5964.000",
#             "low": "5940.000",
#             "open": "5954.000",
#             "volume": "108944",
#             "wave": 0
#         },
#         {
#             "close": "5940.000",
#             "ctm": "1708398900",
#             "ctmfmt": "2024-02-20 11:15:00",
#             "high": "5952.000",
#             "low": "5934.000",
#             "open": "5950.000",
#             "volume": "74720",
#             "wave": 0
#         },
#         {
#             "close": "5922.000",
#             "ctm": "1708409700",
#             "ctmfmt": "2024-02-20 14:15:00",
#             "high": "5950.000",
#             "low": "5922.000",
#             "open": "5940.000",
#             "volume": "125211",
#             "wave": 0
#         },
#         {
#             "close": "5914.000",
#             "ctm": "1708412400",
#             "ctmfmt": "2024-02-20 15:00:00",
#             "high": "5924.000",
#             "low": "5890.000",
#             "open": "5922.000",
#             "volume": "141976",
#             "wave": 0
#         },
#         {
#             "close": "5908.000",
#             "ctm": "1708437600",
#             "ctmfmt": "2024-02-20 22:00:00",
#             "high": "5910.000",
#             "low": "5882.000",
#             "open": "5898.000",
#             "volume": "141847",
#             "wave": 0
#         },
#         {
#             "close": "5908.000",
#             "ctm": "1708441200",
#             "ctmfmt": "2024-02-20 23:00:00",
#             "high": "5924.000",
#             "low": "5906.000",
#             "open": "5908.000",
#             "volume": "69717",
#             "wave": 0
#         },
#         {
#             "close": "5900.000",
#             "ctm": "1708480800",
#             "ctmfmt": "2024-02-21 10:00:00",
#             "high": "5910.000",
#             "low": "5890.000",
#             "open": "5900.000",
#             "volume": "101838",
#             "wave": 0
#         },
#         {
#             "close": "5928.000",
#             "ctm": "1708485300",
#             "ctmfmt": "2024-02-21 11:15:00",
#             "high": "5938.000",
#             "low": "5892.000",
#             "open": "5902.000",
#             "volume": "93266",
#             "wave": 0
#         },
#         {
#             "close": "5924.000",
#             "ctm": "1708496100",
#             "ctmfmt": "2024-02-21 14:15:00",
#             "high": "5950.000",
#             "low": "5922.000",
#             "open": "5930.000",
#             "volume": "102290",
#             "wave": 0
#         },
#         {
#             "close": "5914.000",
#             "ctm": "1708498800",
#             "ctmfmt": "2024-02-21 15:00:00",
#             "high": "5930.000",
#             "low": "5910.000",
#             "open": "5924.000",
#             "volume": "59837",
#             "wave": 0
#         },
#         {
#             "close": "5918.000",
#             "ctm": "1708524000",
#             "ctmfmt": "2024-02-21 22:00:00",
#             "high": "5924.000",
#             "low": "5900.000",
#             "open": "5906.000",
#             "volume": "106898",
#             "wave": 0
#         },
#         {
#             "close": "5948.000",
#             "ctm": "1708527600",
#             "ctmfmt": "2024-02-21 23:00:00",
#             "high": "5964.000",
#             "low": "5920.000",
#             "open": "5920.000",
#             "volume": "128888",
#             "wave": 0
#         },
#         {
#             "close": "5972.000",
#             "ctm": "1708567200",
#             "ctmfmt": "2024-02-22 10:00:00",
#             "high": "5976.000",
#             "low": "5944.000",
#             "open": "5964.000",
#             "volume": "124645",
#             "wave": 0
#         },
#         {
#             "close": "5958.000",
#             "ctm": "1708571700",
#             "ctmfmt": "2024-02-22 11:15:00",
#             "high": "5972.000",
#             "low": "5940.000",
#             "open": "5972.000",
#             "volume": "86919",
#             "wave": 0
#         },
#         {
#             "close": "5960.000",
#             "ctm": "1708582500",
#             "ctmfmt": "2024-02-22 14:15:00",
#             "high": "5968.000",
#             "low": "5954.000",
#             "open": "5958.000",
#             "volume": "73072",
#             "wave": 0
#         },
#         {
#             "close": "5964.000",
#             "ctm": "1708585200",
#             "ctmfmt": "2024-02-22 15:00:00",
#             "high": "5972.000",
#             "low": "5956.000",
#             "open": "5962.000",
#             "volume": "78844",
#             "wave": 0
#         },
#         {
#             "close": "5954.000",
#             "ctm": "1708610400",
#             "ctmfmt": "2024-02-22 22:00:00",
#             "high": "5988.000",
#             "low": "5954.000",
#             "open": "5960.000",
#             "volume": "197830",
#             "wave": 0
#         },
#         {
#             "close": "5970.000",
#             "ctm": "1708614000",
#             "ctmfmt": "2024-02-22 23:00:00",
#             "high": "5974.000",
#             "low": "5950.000",
#             "open": "5954.000",
#             "volume": "61544",
#             "wave": 0
#         },
#         {
#             "close": "5966.000",
#             "ctm": "1708653600",
#             "ctmfmt": "2024-02-23 10:00:00",
#             "high": "5978.000",
#             "low": "5960.000",
#             "open": "5974.000",
#             "volume": "75368",
#             "wave": 0
#         },
#         {
#             "close": "5940.000",
#             "ctm": "1708658100",
#             "ctmfmt": "2024-02-23 11:15:00",
#             "high": "5970.000",
#             "low": "5936.000",
#             "open": "5964.000",
#             "volume": "85487",
#             "wave": 0
#         },
#         {
#             "close": "5916.000",
#             "ctm": "1708668900",
#             "ctmfmt": "2024-02-23 14:15:00",
#             "high": "5942.000",
#             "low": "5906.000",
#             "open": "5940.000",
#             "volume": "192947",
#             "wave": 0
#         },
#         {
#             "close": "5922.000",
#             "ctm": "1708671600",
#             "ctmfmt": "2024-02-23 15:00:00",
#             "high": "5924.000",
#             "low": "5910.000",
#             "open": "5916.000",
#             "volume": "80026",
#             "wave": 0
#         },
#         {
#             "close": "5928.000",
#             "ctm": "1708696800",
#             "ctmfmt": "2024-02-23 22:00:00",
#             "high": "5930.000",
#             "low": "5904.000",
#             "open": "5908.000",
#             "volume": "136823",
#             "wave": 0
#         },
#         {
#             "close": "5922.000",
#             "ctm": "1708700400",
#             "ctmfmt": "2024-02-23 23:00:00",
#             "high": "5932.000",
#             "low": "5912.000",
#             "open": "5930.000",
#             "volume": "67640",
#             "wave": 0
#         },
#         {
#             "close": "5878.000",
#             "ctm": "1708912800",
#             "ctmfmt": "2024-02-26 10:00:00",
#             "high": "5914.000",
#             "low": "5876.000",
#             "open": "5908.000",
#             "volume": "191605",
#             "wave": 0
#         },
#         {
#             "close": "5862.000",
#             "ctm": "1708917300",
#             "ctmfmt": "2024-02-26 11:15:00",
#             "high": "5882.000",
#             "low": "5860.000",
#             "open": "5878.000",
#             "volume": "141189",
#             "wave": 0
#         },
#         {
#             "close": "5860.000",
#             "ctm": "1708928100",
#             "ctmfmt": "2024-02-26 14:15:00",
#             "high": "5870.000",
#             "low": "5858.000",
#             "open": "5860.000",
#             "volume": "82200",
#             "wave": 0
#         },
#         {
#             "close": "5866.000",
#             "ctm": "1708930800",
#             "ctmfmt": "2024-02-26 15:00:00",
#             "high": "5868.000",
#             "low": "5858.000",
#             "open": "5862.000",
#             "volume": "73556",
#             "wave": 0
#         },
#         {
#             "close": "5866.000",
#             "ctm": "1708956000",
#             "ctmfmt": "2024-02-26 22:00:00",
#             "high": "5876.000",
#             "low": "5860.000",
#             "open": "5872.000",
#             "volume": "99751",
#             "wave": 0
#         },
#         {
#             "close": "5872.000",
#             "ctm": "1708959600",
#             "ctmfmt": "2024-02-26 23:00:00",
#             "high": "5882.000",
#             "low": "5864.000",
#             "open": "5866.000",
#             "volume": "52598",
#             "wave": 0
#         },
#         {
#             "close": "5888.000",
#             "ctm": "1708999200",
#             "ctmfmt": "2024-02-27 10:00:00",
#             "high": "5898.000",
#             "low": "5882.000",
#             "open": "5884.000",
#             "volume": "115349",
#             "wave": 0
#         },
#         {
#             "close": "5900.000",
#             "ctm": "1709003700",
#             "ctmfmt": "2024-02-27 11:15:00",
#             "high": "5904.000",
#             "low": "5884.000",
#             "open": "5886.000",
#             "volume": "66842",
#             "wave": 0
#         },
#         {
#             "close": "5946.000",
#             "ctm": "1709014500",
#             "ctmfmt": "2024-02-27 14:15:00",
#             "high": "5956.000",
#             "low": "5898.000",
#             "open": "5898.000",
#             "volume": "224448",
#             "wave": 0
#         },
#         {
#             "close": "5944.000",
#             "ctm": "1709017200",
#             "ctmfmt": "2024-02-27 15:00:00",
#             "high": "5950.000",
#             "low": "5938.000",
#             "open": "5946.000",
#             "volume": "121894",
#             "wave": 0
#         },
#         {
#             "close": "5952.000",
#             "ctm": "1709042400",
#             "ctmfmt": "2024-02-27 22:00:00",
#             "high": "5962.000",
#             "low": "5946.000",
#             "open": "5952.000",
#             "volume": "153398",
#             "wave": 0
#         },
#         {
#             "close": "5966.000",
#             "ctm": "1709046000",
#             "ctmfmt": "2024-02-27 23:00:00",
#             "high": "5966.000",
#             "low": "5952.000",
#             "open": "5952.000",
#             "volume": "71638",
#             "wave": 0
#         },
#         {
#             "close": "5984.000",
#             "ctm": "1709085600",
#             "ctmfmt": "2024-02-28 10:00:00",
#             "high": "5984.000",
#             "low": "5958.000",
#             "open": "5968.000",
#             "volume": "141685",
#             "wave": 0
#         },
#         {
#             "close": "5966.000",
#             "ctm": "1709090100",
#             "ctmfmt": "2024-02-28 11:15:00",
#             "high": "5994.000",
#             "low": "5964.000",
#             "open": "5988.000",
#             "volume": "150599",
#             "wave": 0
#         },
#         {
#             "close": "5952.000",
#             "ctm": "1709100900",
#             "ctmfmt": "2024-02-28 14:15:00",
#             "high": "5970.000",
#             "low": "5952.000",
#             "open": "5966.000",
#             "volume": "82960",
#             "wave": 0
#         },
#         {
#             "close": "5940.000",
#             "ctm": "1709103600",
#             "ctmfmt": "2024-02-28 15:00:00",
#             "high": "5954.000",
#             "low": "5930.000",
#             "open": "5952.000",
#             "volume": "125319",
#             "wave": 0
#         },
#         {
#             "close": "5956.000",
#             "ctm": "1709128800",
#             "ctmfmt": "2024-02-28 22:00:00",
#             "high": "5960.000",
#             "low": "5930.000",
#             "open": "5934.000",
#             "volume": "133948",
#             "wave": 0
#         },
#         {
#             "close": "5950.000",
#             "ctm": "1709132400",
#             "ctmfmt": "2024-02-28 23:00:00",
#             "high": "5962.000",
#             "low": "5950.000",
#             "open": "5956.000",
#             "volume": "65147",
#             "wave": 0
#         },
#         {
#             "close": "5932.000",
#             "ctm": "1709172000",
#             "ctmfmt": "2024-02-29 10:00:00",
#             "high": "5948.000",
#             "low": "5908.000",
#             "open": "5928.000",
#             "volume": "179491",
#             "wave": 0
#         },
#         {
#             "close": "5930.000",
#             "ctm": "1709176500",
#             "ctmfmt": "2024-02-29 11:15:00",
#             "high": "5940.000",
#             "low": "5926.000",
#             "open": "5930.000",
#             "volume": "71207",
#             "wave": 0
#         },
#         {
#             "close": "5924.000",
#             "ctm": "1709187300",
#             "ctmfmt": "2024-02-29 14:15:00",
#             "high": "5936.000",
#             "low": "5918.000",
#             "open": "5932.000",
#             "volume": "74989",
#             "wave": 0
#         },
#         {
#             "close": "5940.000",
#             "ctm": "1709190000",
#             "ctmfmt": "2024-02-29 15:00:00",
#             "high": "5952.000",
#             "low": "5924.000",
#             "open": "5924.000",
#             "volume": "82501",
#             "wave": 0
#         },
#         {
#             "close": "5916.000",
#             "ctm": "1709215200",
#             "ctmfmt": "2024-02-29 22:00:00",
#             "high": "5942.000",
#             "low": "5900.000",
#             "open": "5938.000",
#             "volume": "215964",
#             "wave": 0
#         },
#         {
#             "close": "5906.000",
#             "ctm": "1709218800",
#             "ctmfmt": "2024-02-29 23:00:00",
#             "high": "5918.000",
#             "low": "5896.000",
#             "open": "5916.000",
#             "volume": "119902",
#             "wave": 0
#         },
#         {
#             "close": "5894.000",
#             "ctm": "1709258400",
#             "ctmfmt": "2024-03-01 10:00:00",
#             "high": "5912.000",
#             "low": "5890.000",
#             "open": "5906.000",
#             "volume": "114767",
#             "wave": 0
#         },
#         {
#             "close": "5914.000",
#             "ctm": "1709262900",
#             "ctmfmt": "2024-03-01 11:15:00",
#             "high": "5916.000",
#             "low": "5892.000",
#             "open": "5894.000",
#             "volume": "68120",
#             "wave": 0
#         },
#         {
#             "close": "5916.000",
#             "ctm": "1709273700",
#             "ctmfmt": "2024-03-01 14:15:00",
#             "high": "5920.000",
#             "low": "5906.000",
#             "open": "5916.000",
#             "volume": "63610",
#             "wave": 0
#         },
#         {
#             "close": "5908.000",
#             "ctm": "1709276400",
#             "ctmfmt": "2024-03-01 15:00:00",
#             "high": "5916.000",
#             "low": "5896.000",
#             "open": "5916.000",
#             "volume": "73247",
#             "wave": 0
#         }
#     ]
#     ks = KlineService()
#
#     all_futures = get_all_futures()
#     for future_code in all_futures:
#         ks.save_klines(klines=ready_data_5m, prex='tf_futures_trade', cycle=5, code=future_code["symbol"])
#         time.sleep(0.2)
#     for future_code in all_futures:
#         ks.save_klines(klines=ready_data_10m, prex='tf_futures_trade', cycle=10, code=future_code["symbol"])
#         time.sleep(0.2)
#     for future_code in all_futures:
#         ks.save_klines(klines=ready_data_15m, prex='tf_futures_trade', cycle=15, code=future_code["symbol"])
#         time.sleep(0.2)
#     for future_code in all_futures:
#         ks.save_klines(klines=ready_data_30m, prex='tf_futures_trade', cycle=30, code=future_code["symbol"])
#         time.sleep(0.2)
#     for future_code in all_futures:
#         ks.save_klines(klines=ready_data_60m, prex='tf_futures_trade', cycle=60, code=future_code["symbol"])
#         time.sleep(0.2)
#     print('所有初始数据写入完毕')