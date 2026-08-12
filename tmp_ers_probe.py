import json, uuid, urllib.request, urllib.error
from pathlib import Path
BASE='http://127.0.0.1:8758'

def req(method, path, data=None, headers=None):
    body=None
    hdrs={'Content-Type':'application/json'} if data is not None else {}
    if headers: hdrs.update(headers)
    if data is not None:
        body=json.dumps(data).encode('utf-8')
    r=urllib.request.Request(BASE+path, data=body, headers=hdrs, method=method)
    with urllib.request.urlopen(r, timeout=60) as resp:
        return resp.status, json.loads(resp.read().decode('utf-8')) if 'application/json' in resp.headers.get('Content-Type','') else resp.read()

name='ERS PROBE '+str(uuid.uuid4())[:8]
_, project = req('POST','/api/projects', {'name':name})
project_id=project['id']
scene_id=project['scenes'][0]['id']
print('project', project_id, scene_id)
try:
    _, sm = req('POST', f'/api/spatial-map/projects/{project_id}/maps', {
        'title':'Helios Research Atrium Map',
        'sceneId': scene_id,
        'masterEnvironmentPrompt':'Glass-roofed research atrium with layered gardens and cool daylight.'
    })
    map_id = sm['document']['id']
    print('map', map_id)
    def create_prop(toolId, arguments):
        _, body = req('POST', f'/api/codirector/projects/{project_id}/tools/proposals', {
            'toolId': toolId,
            'arguments': arguments,
            'requestId': f'probe-{toolId}-{uuid.uuid4().hex[:8]}',
            'createdBy': 'user',
        })
        return body
    def approve_prop(pid):
        _, body = req('POST', f'/api/codirector/projects/{project_id}/proposals/{pid}/approve', {'decidedBy':'user'})
        return body
    p = create_prop('ers.create_sheet', {
        'name':'Helios Research Atrium',
        'description':'Glass-roofed atrium with hanging gardens, reflective stone, cool daylight, and quiet research balconies.',
        'sceneId': scene_id,
        'creatorNotes':'Keep the environment calm, precise, and suitable for a research campus.'
    })
    print('create prop', p['id'])
    receipt = approve_prop(p['id'])
    print('create receipt keys', receipt.keys())
    tool_result = receipt.get('toolResult') or {}
    sheet_id = tool_result.get('sheetId') or tool_result.get('sheet',{}).get('sheetId')
    print('sheet', sheet_id)
    p2 = create_prop('ers.attach_spatial_map', {'sheetId': sheet_id, 'spatialMapId': map_id})
    print('attach prop', p2['id'])
    r2 = approve_prop(p2['id'])
    print('attach status', r2.get('status'), (r2.get('toolResult') or {}).get('sheet',{}).get('spatialMap',{}).get('northLockDirection'))
    _, sheets = req('GET', f'/api/environment-reference-sheets/projects/{project_id}')
    print('sheet count', len(sheets['sheets']))
    _, detail = req('GET', f'/api/environment-reference-sheets/projects/{project_id}/{sheet_id}')
    print('directions', [v['direction'] for v in detail['sheet']['directionalViews']])
    print('continuity', detail['sheet']['continuity']['status'], detail['sheet']['continuity']['summary'])
finally:
    try:
        req('DELETE', f'/api/projects/{project_id}')
        print('deleted', project_id)
    except Exception as e:
        print('delete failed', e)
