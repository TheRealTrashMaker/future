import mysql.connector
import requests

# 连接到MySQL数据库
conn = mysql.connector.connect(
    host='104.233.215.58',
    database='debt',
    user='debt',
    password='dZF6Pirb7dm6taBs'
)
cursor = conn.cursor()

url = "http://127.0.0.1:5626//future/futures"
response = requests.get(url=url)
data = response.json()

for item in data:
    cursor.execute("INSERT INTO rf_addon_tf_futures_symbol (code, code2, name_code, name) VALUES (%s, %s, %s, %s)", (item["symbol"], item["symbol"], item["symbol"], item["name"]))

# 提交事务
conn.commit()

# 关闭连接
cursor.close()
conn.close()
