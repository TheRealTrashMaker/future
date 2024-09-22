from sqlalchemy import (
    Column, Integer, String, Float, DateTime, ForeignKey, Numeric
)
from sqlalchemy.orm import relationship
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime

Base = declarative_base()


class Order(Base):
    __tablename__ = 'addon_tf_futures_order'

    id = Column(Integer, primary_key=True)
    member_id = Column(Integer)
    volume = Column(Integer)
    lever_id = Column(Integer)
    rise_fall = Column(String)
    close_type = Column(String)
    order_number = Column(String)
    contract_size = Column(Numeric)
    service_fee = Column(Numeric)
    overfee = Column(Numeric)
    deposit = Column(Numeric)
    profit = Column(Numeric)
    open_price = Column(Numeric)
    close_price = Column(Numeric)
    stop_profit_price = Column(Numeric)
    stop_profit_point = Column(Numeric)
    stop_loss_price = Column(Numeric)
    stop_loss_point = Column(Numeric)
    open_time = Column(DateTime)
    close_time = Column(DateTime)
    expiration = Column(DateTime)
    reason_id = Column(Integer)
    symbol = Column(String(50))
    symbol_cn = Column(String(255))
    desc = Column(String(255))
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    state = Column(String)
    status = Column(String)

    member_info = relationship("Member", back_populates="orders")

    @staticmethod
    def is_trade_time(tradestr='', weekend=True, early=300):
        if not weekend and datetime.now().weekday() in [5, 6]:  # Saturday/Sunday
            return False

        times = []
        trade_periods = tradestr.split(';')
        for trade in trade_periods:
            start, end = trade.split('-')
            times.append({'start': start, 'end': end})

        now = datetime.now()
        for item in times:
            start = datetime.strptime(item['start'], '%H:%M').replace(year=now.year, month=now.month, day=now.day)
            end = datetime.strptime(item['end'], '%H:%M').replace(year=now.year, month=now.month, day=now.day)

            if start > end:
                if now > start or now < (end - timedelta(seconds=early)):
                    return True
            else:
                if now > start and now < (end - timedelta(seconds=early)):
                    return True
        return False

    @staticmethod
    def check_price(product, productcmd, rise_fall, price, stop_profit_price=0, stop_loss_price=0):
        if isinstance(product, int):
            product = Symbol.query.filter_by(id=product).first()

        if not product:
            raise Exception('Product does not exist')

        if productcmd not in ['NOW', 'GT', 'LT'] or rise_fall not in ['RISE', 'FALL']:
            raise Exception('Invalid buy/sell direction')

        kline_service = KlineService()
        new_price = kline_service.load_ticket(product.code)

        if new_price['price'] is None:
            raise Exception('Failed to get latest price')

        product_price = new_price['price']

        if productcmd == 'GT' and price <= product_price:
            raise Exception(f'Order price cannot be less than {product_price}')
        elif productcmd == 'LT' and price >= product_price:
            raise Exception(f'Order price cannot be greater than {product_price}')

        # Additional checks...
        # Implementing max/min checks similar to your PHP code

        return {'code': 200, 'msg': 'ok'}

    @staticmethod
    def compute_profit(symbol, order, close_price=None):
        if not symbol:
            raise Exception('Missing product order')

        product = Symbol.query.filter_by(code=symbol).first()
        if not product:
            raise Exception('Product does not exist')

        if isinstance(order, int):
            order = Order.query.filter_by(id=order).first()

        if not order:
            raise Exception('Order does not exist')

        if close_price is None:
            kline_service = KlineService()
            close_price = kline_service.load_ticket(product.code)['price']

        # Profit calculations...
        # Implementing the same logic from your PHP computeProfit method

        return close_price, profit_amount

# Make sure to adjust relationships and imports according to your application structure.
