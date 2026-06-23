"""Check Wan T2V generation status."""
import json, urllib.request, os

pid = '60bba2dc-db3c-4e93-b382-fd6e60aa277c'
url = f'http://127.0.0.1:8188/history/{pid}'

try:
    r = urllib.request.urlopen(url, timeout=10)
    t = r.read().decode().strip()
    if t and t != 'null':
        d = json.loads(t)
        for nid, out in d.get('outputs', {}).items():
            for img in out.get('images', []):
                fn = img['filename']
                for p in [f'G:/ComfyUI/temp/{fn}', f'G:/ComfyUI/output/{fn}']:
                    if os.path.exists(p):
                        print(f'WAN T2V SUCCESS! {fn} ({os.path.getsize(p)} bytes)')
                        break
        if d.get('status', {}).get('completed'):
            print('Status: COMPLETED')
        else:
            print('History exists but no images yet')
    else:
        qr = urllib.request.urlopen('http://127.0.0.1:8188/queue', timeout=10)
        q = json.loads(qr.read().decode())
        rq = q.get('queue_running', [])
        pq = q.get('queue_pending', [])
        print(f'Queue: {len(rq)} running, {len(pq)} pending')
        if not rq:
            print('Nothing running - may have failed. Check ComfyUI terminal for errors.')
except Exception as e:
    print(f'Error: {e}')
