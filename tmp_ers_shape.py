import base64, json, uuid, requests
BASE='http://127.0.0.1:8758'
TINY_PNG=base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==')
s=requests.Session()
project=s.post(BASE+'/api/projects', json={'name':'ERS SHAPE '+uuid.uuid4().hex[:8]}, timeout=60).json(); pid=project['id']; sid=project['scenes'][0]['id']
try:
  map_id=s.post(BASE+f'/api/spatial-map/projects/{pid}/maps', json={'title':'Map','sceneId':sid,'masterEnvironmentPrompt':'Atrium'}, timeout=60).json()['document']['id']
  def prop(tool,args):
    return s.post(BASE+f'/api/codirector/projects/{pid}/tools/proposals', json={'toolId':tool,'arguments':args,'requestId':'r'+uuid.uuid4().hex[:8],'createdBy':'user'}, timeout=60).json()['id']
  def app(x):
    return s.post(BASE+f'/api/codirector/projects/{pid}/proposals/{x}/approve', json={'decidedBy':'user'}, timeout=60).json()
  create=app(prop('ers.create_sheet', {'name':'Helios','description':'Glass roof atrium','sceneId':sid})); sheet_id=create['toolResult']['sheetId']
  app(prop('ers.attach_spatial_map', {'sheetId':sheet_id,'spatialMapId':map_id}))
  aid=s.post(BASE+f'/api/projects/{pid}/assets', files={'file':('north.png',TINY_PNG,'image/png')}, data={'tag':'North','kind':'image'}, timeout=60).json()['id']
  rec=app(prop('ers.approve_direction', {'sheetId':sheet_id,'direction':'north','assetId':aid}))
  print(json.dumps(rec, indent=2)[:4000])
finally:
  s.delete(BASE+f'/api/projects/{pid}', timeout=60)
