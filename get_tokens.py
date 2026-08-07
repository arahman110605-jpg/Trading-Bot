import urllib.request
import json
from config import WATCHLIST

url = 'https://margincalculator.angelbroking.com/OpenAPI_File/files/OpenAPIScripMaster.json'
req = urllib.request.urlopen(url)
data = json.loads(req.read().decode('utf-8'))

for item in data:
    if item['exch_seg'] == 'NSE':
        if item['symbol'].startswith('ZOMATO') or item['symbol'].startswith('TATAMOTORS'):
            print(f"Name: {item.get('name')}, Symbol: {item.get('symbol')}, Token: {item.get('token')}")
