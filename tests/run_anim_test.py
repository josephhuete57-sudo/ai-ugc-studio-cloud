import requests, time

r = requests.post('http://127.0.0.1:8001/api/animation/run', json={
  'source_path': r'C:\AI_UGC_STUDIO\LivePortrait\assets\examples\source\s0.jpg',
  'driving_path': r'C:\AI_UGC_STUDIO\LivePortrait\assets\examples\driving\d0.mp4',
  'project_id': 1})
print('ANIM', r.status_code, r.text[:200])
jid = r.json()['job_id']
start = time.time()
while time.time() - start < 1500:
    j = requests.get(f'http://127.0.0.1:8001/api/jobs/{jid}').json()
    print(f"[{int(time.time()-start)}s] STATUS={j['status']} STEP={j['step']} PROG={j['progress']} RESULT={j.get('result_path')}", flush=True)
    if j['status'] in ('done', 'error', 'cancelled'):
        print('LOG_TAIL:')
        print((j.get('log') or '')[-2000:])
        print('ERR:', (j.get('error') or '')[:1000])
        break
    time.sleep(10)
