import pymysql


# 连接到MySQL数据库

class mysql_conn:

    def __init__(self):
        self.conn = pymysql.connect(
            host='104.233.215.58',
            database='debt',
            user='debt',
            password='dZF6Pirb7dm6taBs',
            cursorclass=pymysql.cursors.DictCursor
        )

    def get_single_symbol_info(self, symbol_code):

        try:
            with self.conn.cursor() as cursor:
                # 创建查询语句
                query = """SELECT * FROM rf_addon_tf_futures_symbol WHERE code2 = %s"""
                cursor.execute(query, (symbol_code,))
                symbol = cursor.fetchone()
                # 如果 symbol 不为空，返回结果
                if symbol:
                    return symbol
                else:
                    print("No matching record found.")
        except:
            print("从mysql数据库查询单条symbol信息时出错")
            return None
