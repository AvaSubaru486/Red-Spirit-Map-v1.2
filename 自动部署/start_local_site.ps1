[CmdletBinding()]
param(
    [ValidateRange(1024, 65515)][int]$Port = 8010,
    [switch]$NoBrowser
)
$ErrorActionPreference = 'Stop'
$exeName = -join ([char[]]@(0x542f, 0x52a8, 0x672c, 0x5730, 0x7f51, 0x7ad9))
$exe = Join-Path $PSScriptRoot ($exeName + '.exe')
if (-not (Test-Path -LiteralPath $exe)) {
    & (Join-Path $PSScriptRoot 'build_launcher.ps1')
}
$launchArguments = @('--port', "$Port")
if ($NoBrowser) { $launchArguments += '--no-browser' }
$process = Start-Process -FilePath $exe -ArgumentList $launchArguments -WorkingDirectory $PSScriptRoot -PassThru -Wait
exit $process.ExitCode
