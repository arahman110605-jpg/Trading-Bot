import urllib.request, json, time

res = urllib.request.urlopen('http://localhost:8765/signals')
data = json.loads(res.read())
sig = data['signals'].get('EURUSD', {})
reason = sig.get('reason', 'n/a')
signal = sig.get('signal', 'none')
age = time.time() - sig.get('timestamp', time.time())
print("EURUSD Signal:", signal)
print("Reason:", reason)
print("Age:", round(age), "seconds")
print("Bridge: LIVE")
