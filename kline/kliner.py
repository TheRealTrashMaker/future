import json
import redis
from datetime import datetime, timedelta
import pytz


class KlineService:
    def __init__(self, host='127.0.0.1', port=6379):
        # 初始化 Redis 连接
        self.redis = redis.Redis(host=host, port=port, decode_responses=True)

        # K线周期定义
        self.cycles = {
            '1分钟': 1,
            '5分钟': 5,
            '10分钟': 10,
            '15分钟': 15,
            '30分钟': 30,
            '1小时': 60,
            '2小时': 120,
            '4小时': 240,
            '日K': 'day',
            '周K': 'week',
            '月K': 'month',
            '年K': 'year'
        }

    def save(self, ticket, prex='trade', func=None):
        # 存储票据和 K线
        if ticket and 'ctm' in ticket and 'code' in ticket:
            self.save_kline(ticket, prex)
            if self.save_ticket(ticket, prex) and callable(func):
                func(ticket, prex)

    def load_ticket(self, code=None, prex='trade'):
        # 获取最新报价
        if code:
            if self.redis.hexists(f"{prex}_ticket", code):
                return json.loads(self.redis.hget(f"{prex}_ticket", code))
        else:
            if self.redis.exists(f"{prex}_ticket"):
                return self.redis.hgetall(f"{prex}_ticket")
        return {}

    def load_kline(self, code, kline_type, prex='trade', limit=500):
        # 获取 K线数据
        return self.redis.lrange(f"{prex}_kline_{code}_{kline_type}", 0, limit)

    def save_ticket(self, ticket, prex='trade'):
        # 存储票据
        existing_ticket = self.redis.hget(f"{prex}_ticket", ticket['code'])
        if not existing_ticket:
            return self.redis.hset(f"{prex}_ticket", ticket['code'], json.dumps(ticket))
        else:
            existing_ticket = json.loads(existing_ticket)
            self.redis.hset(f"{prex}_ticket", ticket['code'], json.dumps(ticket))
            if (existing_ticket['price'] == ticket['price'] and
                    existing_ticket['ask'] == ticket['ask'] and
                    existing_ticket['bid'] == ticket['bid']):
                return False
            return True
#git pull https://github.com/TheRealTrashMaker/future.git
    def save_klines(self, klines, prex='trade', cycle=None, code=None):
        # 存储多个 K线
        self.redis.delete(f"{prex}_kline_{code}_{cycle}")
        klines = sorted(klines, key=lambda x: x['Tick'], reverse=True)
        for kline in klines:
            new_kline = {
                'open': kline['O'],
                'high': kline['H'],
                'close': kline['C'],
                'low': kline['L'],
                'wave': 0,
                'volume': kline['V'],
                'ctm': kline['Tick'],
                'ctmfmt': datetime.fromtimestamp(int(kline['Tick'])).strftime('%Y-%m-%d %H:%M:%S')
            }
            self.redis.rpush(f"{prex}_kline_{code}_{cycle}", json.dumps(new_kline))

        print(f"{code}***{cycle}线完成")

    def save_kline(self, ticket, prex='trade', is_ask=True):
        # 存储单条 K线
        for cycle in self.cycles:
            kline_data = self.redis.lrange(f"{prex}_kline_{ticket['code']}_{cycle}", 0, 0)
            if kline_data:
                kline = json.loads(kline_data[0])
            else:
                kline = {'open': 0, 'high': 0, 'close': 0, 'low': 0, 'wave': 0, 'volume': 0}

            price = round(ticket['ask'] if is_ask else ticket['bid'], ticket['digit'])
            price = price if price != 0 else ticket['price']
            this_ctmfmt = self.get_key(cycle, ticket['ctmfmt'])
            this_ctm = int(datetime.strptime(this_ctmfmt, '%Y-%m-%d %H:%M:%S').timestamp())

            if this_ctm:
                if 'ctm' in kline and this_ctm == kline['ctm']:
                    # 更新 K线数据
                    kline['high'] = max(kline['open'], kline['high'], kline['low'], kline['close'], price)
                    kline['low'] = min(kline['open'], kline['high'], kline['low'], kline['close'], price) or ticket['price']
                    kline['close'] = price
                    kline['wave'] = ticket.get('wave')
                    kline['volume'] = ticket.get('volume')
                    kline['price'] = ticket.get('price')
                    kline['ctm'] = this_ctm
                    kline['ctmfmt'] = this_ctmfmt

                    self.redis.lset(f"{prex}_kline_{ticket['code']}_{cycle}", 0, json.dumps(kline))
                    last_kline_data = self.redis.lrange(f"{prex}_kline_{ticket['code']}_{cycle}", 1, 1)
                    if last_kline_data and 'ctm' in json.loads(last_kline_data[0]) and this_ctm == json.loads(last_kline_data[0])['ctm']:
                        self.redis.lpop('list')
                else:
                    # 创建新的 K线数据
                    kline = {
                        'open': price,
                        'high': price,
                        'low': price,
                        'close': price,
                        'wave': ticket.get('wave'),
                        'volume': ticket.get('volume'),
                        'price': ticket.get('price'),
                        'ctm': this_ctm,
                        'ctmfmt': this_ctmfmt
                    }
                    self.redis.lpush(f"{prex}_kline_{ticket['code']}_{cycle}", json.dumps(kline))

                if self.redis.llen(f"{prex}_kline_{ticket['code']}_{cycle}") > 500:
                    self.redis.ltrim(f"{prex}_kline_{ticket['code']}_{cycle}", 0, 499)  # 保留前500个元素

    def get_key(self, m, datetime_str, previous_key=False):
        # 获取键的时间格式
        datetime_obj = datetime.strptime(datetime_str, '%Y-%m-%d %H:%M:%S')

        if isinstance(m, int):
            if m < 60:  # 处理分钟
                if m == 1:
                    return (datetime_obj - timedelta(minutes=1)).strftime('%Y-%m-%d %H:%M') if previous_key else datetime_obj.strftime('%Y-%m-%d %H:%M')

                min_list = [0]
                nums = 60 // m
                for i in range(nums):
                    last = min_list[-1]
                    min_list.append(last + m)

                for lk, lv in enumerate(min_list):
                    if datetime_obj.minute <= lv:
                        if datetime_obj.minute == lv:
                            now_date = datetime_obj.replace(second=0, microsecond=0)
                        else:
                            now_date = datetime_obj.replace(minute=min_list[lk - 1], second=0, microsecond=0)

                        return (now_date - timedelta(minutes=m)).strftime('%Y-%m-%d %H:%M') if previous_key else now_date.strftime('%Y-%m-%d %H:%M')

            if m == 60:
                now_date = datetime_obj.replace(minute=0, second=0)
                return (now_date - timedelta(hours=1)).strftime('%Y-%m-%d %H:%M') if previous_key else now_date.strftime('%Y-%m-%d %H:%M')

            if m > 60:  # 处理小时
                hour_list = [0]
                if m == 240:
                    nums = (24 * 60) // m
                    for i in range(nums):
                        last = hour_list[-1]
                        hour_list.append(last + 4)

                    for lk, lv in enumerate(hour_list):
                        if datetime_obj.hour <= lv:
                            now_date = datetime_obj
                            if datetime_obj.hour == lv:
                                now_date = now_date.replace(minute=0, second=0)
                            else:
                                now_date = now_date.replace(hour=hour_list[lk - 1], minute=0, second=0)

                            return (now_date - timedelta(minutes=m)).strftime('%Y-%m-%d %H:%M') if previous_key else now_date.strftime('%Y-%m-%d %H:%M')

        elif m == 'day':
            return (datetime_obj - timedelta(days=1)).strftime('%Y-%m-%d') if previous_key else datetime_obj.strftime('%Y-%m-%d')
        elif m == 'week':
            start_of_week = datetime_obj - timedelta(days=datetime_obj.weekday())
            return (start_of_week - timedelta(weeks=1)).strftime('%Y-%m-%d') if previous_key else start_of_week.strftime('%Y-%m-%d')
        elif m == 'month':
            first_day_of_month = datetime_obj.replace(day=1)
            return (first_day_of_month - timedelta(days=first_day_of_month.day)).strftime('%Y-%m-%d') if previous_key else first_day_of_month.strftime('%Y-%m-%d')
        elif m == 'year':
            first_day_of_year = datetime_obj.replace(month=1, day=1)
            return (first_day_of_year - timedelta(days=first_day_of_year.day)).strftime('%Y-%m-%d') if previous_key else first_day_of_year.strftime('%Y-%m-%d')
