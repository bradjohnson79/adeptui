# Load beta-local.env into environment, then start the Studio API on port 8759.
$RepoRoot = "C:\AdeptFilmWorks\AIVideoStudio"
$envFiles = @(
    (Join-Path $RepoRoot "config\beta-local.env"),
    (Join-Path $RepoRoot "config\beta-local.local.env")
)
foreach ($file in $envFiles) {
    if (-not (Test-Path $file)) { continue }
    foreach ($line in (Get-Content $file -Encoding UTF8)) {
        $line = $line.Trim()
        if (-not $line -or $line.StartsWith("#")) { continue }
        $eq = $line.IndexOf("=")
        if ($eq -lt 1) { continue }
        $key = $line.Substring(0, $eq).Trim()
        $val = $line.Substring($eq + 1).Trim()
        if (($val.StartsWith('"') -and $val.EndsWith('"')) -or ($val.StartsWith("'") -and $val.EndsWith("'"))) {
            $val = $val.Substring(1, $val.Length - 2)
        }
        Set-Item -Path "Env:$key" -Value $val
    }
}
Write-Host "STUDIO_FEATURE_CODIRECTOR_OPERATIONAL_AGENT_V1 = $env:STUDIO_FEATURE_CODIRECTOR_OPERATIONAL_AGENT_V1"
Set-Location "$RepoRoot\studio-api"
& ".\.venv\Scripts\python.exe" -m uvicorn app.main:app --host 127.0.0.1 --port 8759
