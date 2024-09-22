import requests


headers = {
    "Accept": "*/*",
    "Accept-Language": "zh-CN,zh;q=0.9",
    "Cache-Control": "no-cache",
    "Connection": "keep-alive",
    "Pragma": "no-cache",
    "Referer": "https://finance.sina.com.cn/futures/quotes/HC0.shtml",
    "Sec-Fetch-Dest": "script",
    "Sec-Fetch-Mode": "no-cors",
    "Sec-Fetch-Site": "cross-site",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36",
    "sec-ch-ua": "\"Google Chrome\";v=\"129\", \"Not=A?Brand\";v=\"8\", \"Chromium\";v=\"129\"",
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": "\"Windows\""
}
url = "https://hq.sinajs.cn/"
params = {
    "_": "1726825845034/",
    "list": "nf_HC0,nf_RB2501,nf_SA2501,nf_FG2501,nf_M2501,nf_RM2501,nf_AG2412,nf_TA2501,nf_HC2501,nf_V2501,nf_P2501,nf_FU2411,nf_I2501,nf_MA2501"
}
response = requests.get(url, headers=headers, params=params)

print(response.text)
