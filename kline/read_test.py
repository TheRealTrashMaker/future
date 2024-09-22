import json
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from kliner import KlineService
import requests


from kliner import KlineService

ks = KlineService()

print(ks.load_ticket('LC2508', prex='tf_futures_trade'))