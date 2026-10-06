# Adept :8758 invoke for the Draft SD 1.5 CRS utility routes.
# Disposable synthetic subject only. Do not generate Korri.
param(
    [string]$Api = "http://127.0.0.1:8758",
    [string]$ProjectId = "2347bf46-3762-4763-86c5-4a6032522278",
    [string]$WorkflowKey = "sd15.txt2img"
)

$prompt = "a single generic adult mannequin standing facing camera, plain gray background, isolated subject, no collage, no sheet, no text"
$negative = "collage, grid, four panel, character sheet, multiple people, watermark"

$body = @{
    prompt = $prompt
    negative = $negative
    model = "sd15"
    modelFamilyPreference = "sd15"
    lockModelFamily = $true
    source = "local"
    forceWorkflowKey = $WorkflowKey
    allowDraft = $true
    width = 512
    height = 768
    steps = 20
    cfg = 7.0
    seed = 15
    taskType = "CRS_SINGLE_VIEW"
    view = "FRONT"
    character_count = 1
    extras = $false
    layout = "single_subject"
    purpose = "crs_single_view"
} | ConvertTo-Json -Depth 6

Write-Output "POST $Api/api/projects/$ProjectId/imagegen workflow=$WorkflowKey"
Invoke-RestMethod -Method Post -Uri "$Api/api/projects/$ProjectId/imagegen" -ContentType "application/json" -Body $body | ConvertTo-Json -Depth 8
