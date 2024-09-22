import asyncio
import datetime
import mysql.connector
from mysql.connector import Error

def create_connection():
    """ Create a database connection to the MySQL database """
    connection = None
    try:
        connection = mysql.connector.connect(
            host='104.233.215.58',
            database='debt',
            user='debt',
            password='dZF6Pirb7dm6taBs'
        )
        if connection.is_connected():
            print("Connection to MySQL DB successful")
    except Error as e:
        print(f"The error '{e}' occurred")
    return connection

async def check_expiry_and_overtime():
    db = create_connection()
    while True:
        # Check for expired contracts
        levels = db.query("SELECT * FROM rf_addon_tf_futures_member_lever WHERE state='正常'")
        date_today = datetime.datetime.now().date()

        for level in levels:
            edate = level['edate'].date()
            if edate < date_today:
                db.execute(f"UPDATE rf_addon_tf_futures_member_lever SET state='过期' WHERE id={level['id']}")

        # Check for overtime fees
        symbols = Symbol.find().filter(status='1', on_sale='on').all()
        for symbol in symbols:
            orders = Order.find().filter(symbol=symbol.code, state='持仓', status='1').all()
            for order in orders:
                if (datetime.datetime.now().time() >= symbol.overtime and
                        date_today >= order.overtime.date()):
                    order_instance = Order.find().filter(id=order.id).one()
                    member_price = Member.find().filter(member_id=order.member_id).one()

                    data = datetime.datetime.now()
                    order_instance.overfee += (order_instance.deposit * symbol.overfee / 10000)
                    order_instance.overtime = data
                    order_instance.save()

        # Wait for a specified time before repeating
        await asyncio.sleep(1)


async def main():
    await check_expiry_and_overtime()


if __name__ == '__main__':
    asyncio.run(main())
