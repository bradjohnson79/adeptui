import base64, json, uuid, requests
BASE='http://127.0.0.1:8758'
TINY_PNG=base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==')
s=requests.Session()

def prop(pid, tool, args):
  return s.post(BASE+f'/api/codirector/projects/{pid}/tools/proposals', json={'toolId':tool,'arguments':args,'requestId':'r'+uuid.uuid4().hex[:8],'createdBy':'user'}, timeout=30).json()['id']
def approve(pid, propid):
  return s.post(BASE+f'/api/codirector/projects/{pid}/proposals/{propid}/approve', json={'decidedBy':'user'}, timeout=30).json()
def get_sheet(pid, sid):
  return s.get(BASE+f'/api/environment-reference-sheets/projects/{pid}/{sid}', timeout=30).json()['sheet']
def list_maps(pid):
  return s.get(BASE+f'/api/spatial-map/projects/{pid}/maps', timeout=30).json()['documents']
p=s.post(BASE+'/api/projects', json={'name':'ERS READY '+uuid.uuid4().hex[:8]}, timeout=30).json(); pid=p['id']; scene=p['scenes'][0]['id']
print('project', pid)
try:
  approve(pid, prop(pid,'spatial.create_map', {'title':'Map','sceneId':scene,'masterEnvironmentPrompt':'Atrium'}))
  doc=list_maps(pid)[0]
  print('warnings before camera', doc.get('warnings'))
  approve(pid, prop(pid,'spatial.create_camera', {'documentId':doc['id'],'label':'North Lock Camera','x':0,'y':1.6,'z':-4,'yawDegrees':0,'pitchDegrees':0,'lensMm':24,'hero':True,'lockedFor360':True}))
  doc=list_maps(pid)[0]
  print('warnings after camera', doc.get('warnings'))
  sheet_id=approve(pid, prop(pid,'ers.create_sheet', {'name':'Helios','description':'Glass roof atrium','sceneId':scene}))['toolResult']['sheetId']
  approve(pid, prop(pid,'ers.attach_spatial_map', {'sheetId':sheet_id,'spatialMapId':doc['id']}))
  assets={}
  for d in ['north','east','south','west']:
    assets[d]=s.post(BASE+f'/api/projects/{pid}/assets', files={'file':(f'{d}.png',TINY_PNG,'image/png')}, data={'tag':d,'kind':'image'}, timeout=30).json()['id']
    approve(pid, prop(pid,'ers.approve_direction', {'sheetId':sheet_id,'direction':d,'assetId':assets[d]}))
  approve(pid, prop(pid,'ers.validate_continuity', {'sheetId':sheet_id}))
  sh=get_sheet(pid,sheet_id)
  print('continuity', sh['continuity']['status'], sh['continuity']['findings'])
finally:
  s.delete(BASE+f'/api/projects/{pid}', timeout=30)
