[CmdletBinding()]
param()
$ErrorActionPreference = 'Stop'
$deployDir = $PSScriptRoot
$buildDir = Join-Path $deployDir 'build'
$tempDir = Join-Path $buildDir 'tmp'
New-Item -ItemType Directory -Path $tempDir -Force | Out-Null
$env:TEMP = $tempDir
$env:TMP = $tempDir
$compiler = Join-Path $env:WINDIR 'Microsoft.NET\Framework64\v4.0.30319\csc.exe'
if (-not (Test-Path -LiteralPath $compiler)) {
    $compiler = Join-Path $env:WINDIR 'Microsoft.NET\Framework\v4.0.30319\csc.exe'
}
if (-not (Test-Path -LiteralPath $compiler)) { throw 'The Windows .NET Framework C# compiler is not installed.' }
# Unicode output name constructed here also works on Windows PowerShell 5.1.
$exeName = -join ([char[]]@(0x542f, 0x52a8, 0x672c, 0x5730, 0x7f51, 0x7ad9))
$output = Join-Path $deployDir ($exeName + '.exe')
& $compiler /nologo /target:winexe /platform:anycpu /optimize+ /codepage:65001 "/out:$output" /reference:System.Windows.Forms.dll /reference:System.Drawing.dll (Join-Path $deployDir 'Launcher.cs')
if ($LASTEXITCODE -ne 0) { throw 'Launcher compilation failed.' }
Write-Output "Built: $output"
Get-FileHash -LiteralPath $output -Algorithm SHA256
