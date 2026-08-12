import base64, json, uuid, requests
BASE='http://127.0.0.1:8758'
TINY_PNG=base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==')

s=requests.Session()
name='ERS FLOW '+uuid.uuid4().hex[:8]
project=s.post(BASE+'/api/projects', json={'name':name}, timeout=60).json()
project_id=project['id']
scene_id=project['scenes'][0]['id']
print('project', project_id)
try:
    doc=s.post(BASE+f'/api/spatial-map/projects/{project_id}/maps', json={
        'title':'Helios Research Atrium Map',
        'sceneId': scene_id,
        'masterEnvironmentPrompt':'Glass-roofed research atrium with layered gardens and cool daylight.'
    }, timeout=60).json()['document']
    map_id=doc['id']
    print('map', map_id)
    def prop(toolId,args):
        body=s.post(BASE+f'/api/codirector/projects/{project_id}/tools/proposals', json={
            'toolId': toolId, 'arguments': args, 'requestId': f't-{uuid.uuid4().hex[:8]}', 'createdBy':'user'
        }, timeout=60)
        print('prop', toolId, body.status_code)
        body.raise_for_status()
        return body.json()['id']
    def approve(pid):
        body=s.post(BASE+f'/api/codirector/projects/{project_id}/proposals/{pid}/approve', json={'decidedBy':'user'}, timeout=60)
        print('approve', pid, body.status_code)
        body.raise_for_status()
        return body.json()
    create_id=prop('ers.create_sheet', {
        'name':'Helios Research Atrium',
        'description':'Glass-roofed atrium with hanging gardens, reflective stone, cool daylight, and quiet research balconies.',
        'sceneId': scene_id,
        'creatorNotes':'Keep the environment calm and precise.'
    })
    create_receipt=approve(create_id)
    sheet_id=create_receipt['toolResult']['sheetId']
    attach_id=prop('ers.attach_spatial_map', {'sheetId': sheet_id, 'spatialMapId': map_id})
    approve(attach_id)
    assets={}
    for direction in ['north','east','south','west']:
        res=s.post(BASE+f'/api/projects/{project_id}/assets', files={
            'file': (f'{direction}.png', TINY_PNG, 'image/png')
        }, data={'tag':f'{direction.title()} view','kind':'image'}, timeout=60)
        print('upload', direction, res.status_code)
        res.raise_for_status()
        assets[direction]=res.json()['id']
    north_prop=prop('ers.approve_direction', {'sheetId':sheet_id,'direction':'north','assetId':assets['north']})
    north_receipt=approve(north_prop)
    print('north continuity', north_receipt['toolResult']['sheet']['continuity']['status'])
    validate_prop=prop('ers.validate_continuity', {'sheetId':sheet_id})
    validate_receipt=approve(validate_prop)
    print('preserved', validate_receipt['toolResult']['continuity']['preservedDirections'])
    for direction in ['east','south','west']:
        approve(prop('ers.approve_direction', {'sheetId':sheet_id,'direction':direction,'assetId':assets[direction]}))
    validate2=approve(prop('ers.validate_continuity', {'sheetId':sheet_id}))
    print('final continuity', validate2['toolResult']['continuity']['status'])
    compose=approve(prop('ers.compose_sheet', {'sheetId':sheet_id}))
    print('composition keys', compose['toolResult']['composition'].keys())
    for kind in ['png','pdf','offline_html']:
        receipt=approve(prop('ers.export_sheet', {'sheetId':sheet_id,'exportKind':kind}))
        print('export', kind, receipt['toolResult']['export']['status'], receipt['toolResult']['export']['filePath'])
    detail=s.get(BASE+f'/api/environment-reference-sheets/projects/{project_id}/{sheet_id}', timeout=60).json()['sheet']
    print('north lock', detail['spatialMap']['northLockDirection'])
    print('exports', [(e['exportKind'], e['status']) for e in detail['exports']])
except Exception as e:
    print('ERROR', type(e).__name__, e)
    raise
finally:
    d=s.delete(BASE+f'/api/projects/{project_id}', timeout=60)
    print('delete', d.status_code)
