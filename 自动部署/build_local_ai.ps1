$ErrorActionPreference='Stop'
$Compiler=Join-Path $env:WINDIR 'Microsoft.NET\Framework64\v4.0.30319\csc.exe'
$Output=Join-Path $PSScriptRoot '一键部署本地AI.exe'
& $Compiler /nologo /target:winexe /platform:anycpu /optimize+ /codepage:65001 "/out:$Output" /reference:System.Windows.Forms.dll /reference:System.Web.Extensions.dll (Join-Path $PSScriptRoot 'LocalAI.cs')
if($LASTEXITCODE -ne 0) { throw 'Local AI launcher compilation failed.' }
Get-FileHash -LiteralPath $Output -Algorithm SHA256
