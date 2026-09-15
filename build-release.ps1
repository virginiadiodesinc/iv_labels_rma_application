# build-release.ps1
# Run this from your dev machine when you want to publish a new version of
# one or more sections. It zips the section folder(s), hashes the zip, and
# updates manifest.json on the share so clients pick it up on next launch.
#
# Examples:
#   .\build-release.ps1 -Sections app
#   .\build-release.ps1 -Sections app,setup
#   .\build-release.ps1 -Sections python -Version 2026.09.01

param(
    [Parameter(Mandatory)]
    [ValidateSet("python", "app", "setup")]
    [string[]]$Sections,

    [string]$Version = (Get-Date -Format "yyyy.MM.dd"),

    # Where your local, working copies of app/ python/ setup/ live -
    # defaults to the folder this script's parent sits in. Adjust if you
    # run this from somewhere else.
    [string]$SourceRoot = ($PSScriptRoot),

    [string]$ReleasesDir  = "\\linkserver\PythonDrive\Python3\IV and Labels\",
    [string]$ManifestPath = "\\linkserver\PythonDrive\Python3\IV and Labels\manifest.production.json"
)

function Set-ManifestSection {
    param($Manifest, [string]$SectionName, $Value)
    if ($Manifest.PSObject.Properties.Name -contains $SectionName) {
        $Manifest.$SectionName = $Value
    } else {
        $Manifest | Add-Member -NotePropertyName $SectionName -NotePropertyValue $Value
    }
    return $Manifest
}

if (-not (Test-Path $ReleasesDir)) {
    Write-Error "Can't reach releases folder: $ReleasesDir"
    exit 1
}

# Load existing manifest, or start a fresh one if this is the first release.
if (Test-Path $ManifestPath) {
    $manifest = Get-Content $ManifestPath -Raw | ConvertFrom-Json
} else {
    $manifest = [PSCustomObject]@{}
}

foreach ($section in $Sections) {
    $sourceDir = Join-Path $SourceRoot $section
    if (-not (Test-Path $sourceDir)) {
        Write-Error "Source folder not found: $sourceDir - skipping $section"
        continue
    }

    $zipName = "$section-$Version.zip"
    $zipPath = Join-Path $ReleasesDir $zipName

    Write-Host "Zipping $section -> $zipName ..."
    # The \* zips the CONTENTS of the folder, not the folder itself, so
    # extraction on the client produces the files directly - matching what
    # updater.ps1 expects when it renames the extracted temp folder in place.
    Compress-Archive -Path (Join-Path $sourceDir "*") -DestinationPath $zipPath -Force

    Write-Host "Hashing $zipName ..."
    $hash = (Get-FileHash -Path $zipPath -Algorithm SHA256).Hash

    $manifest = Set-ManifestSection -Manifest $manifest -SectionName $section -Value @{
        version = $Version
        file    = $zipPath
        sha256  = $hash
    }

    Write-Host "  $section -> $Version  (sha256: $hash)"
}

$manifest | ConvertTo-Json -Depth 5 | Set-Content -Path $ManifestPath -Encoding UTF8
Write-Host "`nManifest updated at $ManifestPath"
