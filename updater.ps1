# updater.ps1
# Lives at true root next to launcher.bat. Checks a manifest on a network
# share against manifest.local.json and swaps in any section (python / app /
# setup) that's out of date. Never touches app.log or the shortcuts.

param(
    [string]$ManifestPath = "\\linkserver\PythonDrive\Python3\IV and Labels\manifest.production.json"
)

$RootDir            = Split-Path -Parent $MyInvocation.MyCommand.Path
$LocalManifestPath  = Join-Path $RootDir "manifest.local.json"

function Get-LocalManifest {
    if (Test-Path $LocalManifestPath) {
        return Get-Content $LocalManifestPath -Raw | ConvertFrom-Json
    }
    # No local manifest yet (first run after adopting the updater).
    # Treat everything as ancient so the first check pulls fresh copies once.
    return [PSCustomObject]@{ python = "0000.00.00"; app = "0000.00.00"; setup = "0000.00.00" }
}

function Save-LocalManifest($manifest) {
    $manifest | ConvertTo-Json | Set-Content -Path $LocalManifestPath -Encoding UTF8
}

function Update-Section {
    param(
        [string]$SectionName,
        [PSCustomObject]$RemoteInfo,
        [PSCustomObject]$LocalManifest
    )

    $sectionDir  = Join-Path $RootDir $SectionName
    $tempZip     = Join-Path $env:TEMP "$SectionName-$($RemoteInfo.version).zip"
    $tempExtract = Join-Path $env:TEMP "$SectionName-$($RemoteInfo.version)-extracted"

    Write-Host "Updating $SectionName to $($RemoteInfo.version)..."

    # $RemoteInfo.file is the full network path to that section's zip,
    # e.g. \\YOUR-SERVER\releases\app-2026.08.14.zip
    try {
        Copy-Item -Path $RemoteInfo.file -Destination $tempZip -Force -ErrorAction Stop
    } catch {
        Write-Host "  Copy failed for $SectionName - will retry next launch."
        return
    }

    $hash = (Get-FileHash -Path $tempZip -Algorithm SHA256).Hash
    if ($hash -ne $RemoteInfo.sha256) {
        Write-Host "  Hash mismatch for $SectionName - discarding, will retry next launch."
        Remove-Item $tempZip -Force -ErrorAction SilentlyContinue
        return
    }

    if (Test-Path $tempExtract) { Remove-Item $tempExtract -Recurse -Force }
    Expand-Archive -Path $tempZip -DestinationPath $tempExtract -Force
    Remove-Item $tempZip -Force

    # Atomic-ish swap: rename old out of the way, rename new into place,
    # then clean up. If anything above this point fails, the existing
    # section is never touched.
    $oldDir = "$sectionDir.old"
    if (Test-Path $oldDir) { Remove-Item $oldDir -Recurse -Force -ErrorAction SilentlyContinue }
    if (Test-Path $sectionDir) { Rename-Item -Path $sectionDir -NewName "$SectionName.old" }
    Move-Item -Path $tempExtract -Destination $sectionDir
    if (Test-Path $oldDir) { Remove-Item $oldDir -Recurse -Force -ErrorAction SilentlyContinue }

    $LocalManifest.$SectionName = $RemoteInfo.version
    Save-LocalManifest $LocalManifest
    Write-Host "  $SectionName updated to $($RemoteInfo.version)."
}

# --- Main ---

$localManifest = Get-LocalManifest

try {
    $remoteManifest = Get-Content -Path $ManifestPath -Raw -ErrorAction Stop | ConvertFrom-Json
} catch {
    Write-Host "Could not reach the update share - continuing with current version."
    exit 0
}

# Order matters: python before app (app may depend on interpreter/package
# changes), setup last (it's the entry point, so it should be the final
# thing to flip once everything it depends on is already current).
foreach ($section in @("python", "app", "setup")) {
    $remoteInfo   = $remoteManifest.$section
    $localVersion = $localManifest.$section

    if ($null -eq $remoteInfo) { continue }

    if ($remoteInfo.version -gt $localVersion) {
        Update-Section -SectionName $section -RemoteInfo $remoteInfo -LocalManifest $localManifest
    }
}