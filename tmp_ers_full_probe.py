import base64, json, uuid, requests, sys
BASE='http://127.0.0.1:8758'
TINY_PNG=base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==')
s=requests.Session()

def log(*args):
    print(*args, flush=True)
p=s.post(BASE+'/api/projects', json={'name':'ERS FULL '+uuid.uuid4().hex[:8]}, timeout=60).json(); pid=p['id']; scene=p['scenes'][0]['id']
log('project', pid)
try:
  map_id=s.post(BASE+f'/api/spatial-map/projects/{pid}/maps', json={'title':'Map','sceneId':scene,'masterEnvironmentPrompt':'Glass-roofed research atrium with layered gardens and cool daylight.'}, timeout=60).json()['document']['id']
  log('map', map_id)
  def proposal(tool,args):
    res=s.post(BASE+f'/api/codirector/projects/{pid}/tools/proposals', json={'toolId':tool,'arguments':args,'requestId':'r'+uuid.uuid4().hex[:8],'createdBy':'user'}, timeout=120)
    log('proposal', tool, res.status_code)
    res.raise_for_status(); return res.json()['id']
  def approve(pid2):
    res=s.post(BASE+f'/api/codirector/projects/{pid}/proposals/{pid2}/approve', json={'decidedBy':'user'}, timeout=120)
    log('approve', pid2, res.status_code)
    res.raise_for_status(); return res.json()
  def sheet(sheet_id):
    res=s.get(BASE+f'/api/environment-reference-sheets/projects/{pid}/{sheet_id}', timeout=120)
    log('sheet', res.status_code)
    res.raise_for_status(); return res.json()['sheet']
  sheet_id=approve(proposal('ers.create_sheet', {'name':'Helios Research Atrium','description':'Glass-roofed atrium with hanging gardens, reflective stone, cool daylight, and quiet research balconies.','sceneId':scene}))['toolResult']['sheetId']
  log('sheet_id', sheet_id)
  approve(proposal('ers.attach_spatial_map', {'sheetId':sheet_id,'spatialMapId':map_id}))
  sh=sheet(sheet_id); log('after attach continuity', sh['continuity']['status'], sh['spatialMap']['northLockDirection'])
  assets={}
  for d in ['north','east','south','west']:
    res=s.post(BASE+f'/api/projects/{pid}/assets', files={'file':(f'{d}.png',TINY_PNG,'image/png')}, data={'tag':d,'kind':'image'}, timeout=120); log('upload', d, res.status_code); res.raise_for_status(); assets[d]=res.json()['id']
  approve(proposal('ers.approve_direction', {'sheetId':sheet_id,'direction':'north','assetId':assets['north']}))
  sh=sheet(sheet_id); log('after north', sh['continuity']['status'], sh['continuity']['preservedDirections'])
  approve(proposal('ers.validate_continuity', {'sheetId':sheet_id}))
  sh=sheet(sheet_id); log('after validate1', sh['continuity']['status'], sh['continuity']['preservedDirections'])
  for d in ['east','south','west']:
    approve(proposal('ers.approve_direction', {'sheetId':sheet_id,'direction':d,'assetId':assets[d]}))
  approve(proposal('ers.validate_continuity', {'sheetId':sheet_id}))
  sh=sheet(sheet_id); log('after validate2', sh['continuity']['status'], sh['continuity']['preservedDirections'])
  approve(proposal('ers.compose_sheet', {'sheetId':sheet_id}))
  sh=sheet(sheet_id); log('composition', sh['composition']['continuitySummary'])
  for kind in ['png','pdf','offline_html']:
    approve(proposal('ers.export_sheet', {'sheetId':sheet_id,'exportKind':kind}))
    log('exported', kind)
  sh=sheet(sheet_id); log('exports', [(e['exportKind'], e['status']) for e in sh['exports']])
except Exception as e:
  log('ERR', type(e).__name__, e)
  raise
finally:
  d=s.delete(BASE+f'/api/projects/{pid}', timeout=120)
  log('delete', d.status_code)
