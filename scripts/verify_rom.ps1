param(
    [Parameter(Mandatory = $false)]
    [string]$RomPath = (Join-Path $PSScriptRoot '..\Slap Stick (J).smc')
)

$resolved = Resolve-Path -LiteralPath $RomPath -ErrorAction Stop
$bytes = [System.IO.File]::ReadAllBytes($resolved.Path)
$expectedLength = 1572864
$expectedSha256 = '08144EA1CE3CF6AB107837278D308E4E859574A047A2EE8EB456F7900AD4BE21'

$hash = (Get-FileHash -LiteralPath $resolved.Path -Algorithm SHA256).Hash.ToUpperInvariant()
$headerOffset = 0xFFC0

if ($bytes.Length -le ($headerOffset + 0x1F)) {
    throw "ROM is too small to contain the expected HiROM header."
}

$title = [Text.Encoding]::ASCII.GetString($bytes[$headerOffset..($headerOffset + 20)]).Trim()
$mapMode = $bytes[$headerOffset + 0x15]
$romType = $bytes[$headerOffset + 0x16]
$romSize = $bytes[$headerOffset + 0x17]
$sramSize = $bytes[$headerOffset + 0x18]
$checksum = $bytes[$headerOffset + 0x1E] + (256 * $bytes[$headerOffset + 0x1F])

[pscustomobject]@{
    Path = $resolved.Path
    Length = $bytes.Length
    SHA256 = $hash
    Title = $title
    MapMode = ('0x{0:X2}' -f $mapMode)
    ROMType = ('0x{0:X2}' -f $romType)
    ROMSizeCode = ('0x{0:X2}' -f $romSize)
    SRAMSizeCode = ('0x{0:X2}' -f $sramSize)
    Checksum = ('0x{0:X4}' -f $checksum)
    LengthMatchesKnownDump = ($bytes.Length -eq $expectedLength)
    SHA256MatchesKnownDump = ($hash -eq $expectedSha256)
} | Format-List

if ($bytes.Length -ne $expectedLength) {
    throw "Unexpected ROM length: $($bytes.Length) bytes; expected $expectedLength bytes."
}

if ($hash -ne $expectedSha256) {
    throw "SHA-256 does not match the known clean Japanese dump."
}

if ($mapMode -ne 0x31) {
    throw "Unexpected map mode: 0x$('{0:X2}' -f $mapMode); expected 0x31 (HiROM/FastROM)."
}

Write-Host 'ROM verification passed.' -ForegroundColor Green

