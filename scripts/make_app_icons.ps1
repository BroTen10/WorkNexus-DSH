<#
  Generates the WorkNexus-DSH application icons and the Windows tray icon from the
  single brand source, replacing the T-021 placeholder artwork (blue tile + "W").

  Why this script exists: the icons under `apps/desktop/resources/` were placeholders
  because no brand artwork was available (T-021 裁决 R-3, C-1). The decision maker
  supplied the official mark on 2026-09-30 (already embedded in
  `packages/client/ui-brand-official/src/client/Brand.tsx` as a base64 PNG, the same
  single source the installer and welcome window use). This script paints that mark
  into the icon set so the desktop icon, the taskbar icon and the tray icon can never
  drift apart from the in-app brand mark.

  Artwork (the mark is never redrawn, only placed):
    resources/icon.png          512  bare mark, 1:1 canvas with ~4% margin (source artwork)
    resources/icon-windows.png  256  rounded tile, full bleed, mark at 62% of the edge
    resources/icon-macos.png    512  rounded tile inset to the macOS grid, mark at 62%
    resources/tray-windows.ico  7 PNG entries 16/20/24/32/40/48/64, mark enlarged 1.2x
    resources/icon{,-windows,-macos}.svg   same geometry, mark embedded as base64 PNG

  Geometry is shared between the raster outputs and the vector outputs, so both stay
  the same drawing; the tile surface reuses the light lockup gradient of the installer
  artwork (#FFFFFF centre -> #EDEFF3 edge from `scripts/make_brand_assets.ps1`).

  The tray bitmap set matches upstream `render-tray-icon.ts` (TRAY_ICON_SIZES) and its
  1.2x glyph enlargement; `pnpm --filter @deepseek-ai/dsh-desktop run render:tray-icon`
  reads `resources/icon-windows.svg` and stays usable as an equivalent producer.

  Usage:
    powershell -NoProfile -File scripts/make_app_icons.ps1
    powershell -NoProfile -File scripts/make_app_icons.ps1 -Out <dir>
#>
[CmdletBinding()]
param(
  [string]$Out
)

$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Drawing

$repo = Split-Path -Parent $PSScriptRoot
$upstream = Join-Path $repo 'repos/deepseek-harness'
$brandSource = Join-Path $upstream 'packages/client/ui-brand-official/src/client/Brand.tsx'

$wascii = New-Object System.Text.UTF8Encoding($false)

# -- Shared geometry (fractions of the square canvas) -------------------------
$tileCenter = '#FFFFFF'
$tileEdge = '#EDEFF3'
$windowsRadius = 0.180        # rounded-tile corner radius, Windows/DPI tile
$macInset = 0.098             # macOS icon grid: 824 of 1024 content square
$macRadius = 0.225            # macOS corner radius, relative to the content square
$markOfTile = 0.62            # mark edge as a fraction of the tile edge
$trayGlyphScale = 1.2         # upstream render-tray-icon.ts glyph enlargement
$bareMark = 0.92              # icon.png source artwork: 1:1 canvas, ~4% margin
$svgCanvas = 1024             # vector coordinate space, matches upstream renderer
$traySizes = @(16, 20, 24, 32, 40, 48, 64)

function Get-BrandMarkPng {
  $text = [IO.File]::ReadAllText($brandSource)
  $marker = "'data:image/png;base64,'"
  $start = $text.IndexOf($marker)
  if ($start -lt 0) { throw "brand source carries no PNG data URI: $brandSource" }
  $start += $marker.Length
  $end = $text.IndexOf('/**', $start)
  $chunk = $text.Substring($start, $end - $start)
  $b64 = (([regex]::Split(($chunk -replace "'", ''), "\r?\n\s*\+\s*") -join '') -replace '\s', '')
  # Typed so the return value stays a byte[] instead of an unrolled Object[].
  [byte[]]$bytes = [Convert]::FromBase64String($b64)
  return , $bytes
}

function New-RoundedPath([single]$x, [single]$y, [single]$w, [single]$h, [single]$r) {
  $path = New-Object System.Drawing.Drawing2D.GraphicsPath
  $d = $r * 2
  $path.AddArc($x, $y, $d, $d, 180, 90)
  $path.AddArc($x + $w - $d, $y, $d, $d, 270, 90)
  $path.AddArc($x + $w - $d, $y + $h - $d, $d, $d, 0, 90)
  $path.AddArc($x, $y + $h - $d, $d, $d, 90, 90)
  $path.CloseFigure()
  return $path
}

function New-Graphics([System.Drawing.Bitmap]$bitmap) {
  $g = [System.Drawing.Graphics]::FromImage($bitmap)
  $g.SmoothingMode = [System.Drawing.Drawing2D.SmoothingMode]::AntiAlias
  $g.InterpolationMode = [System.Drawing.Drawing2D.InterpolationMode]::HighQualityBicubic
  $g.PixelOffsetMode = [System.Drawing.Drawing2D.PixelOffsetMode]::HighQuality
  $g.CompositingQuality = [System.Drawing.Drawing2D.CompositingQuality]::HighQuality
  return $g
}

# -- Raster: tile + mark, supersampled then reduced (crisp at tray sizes) -----
function New-IconBitmap([int]$edge, [double]$inset, [double]$radiusFrac, [double]$markFrac, [int]$super) {
  $big = $edge * $super
  $canvas = New-Object System.Drawing.Bitmap($big, $big, [System.Drawing.Imaging.PixelFormat]::Format32bppArgb)
  $g = New-Graphics $canvas
  $g.Clear([System.Drawing.Color]::Transparent)
  try {
    $side = [single]($big * (1 - 2 * $inset))
    $origin = [single]($big * $inset)
    $path = New-RoundedPath $origin $origin $side $side ([single]($side * $radiusFrac))
    $brush = New-Object System.Drawing.Drawing2D.PathGradientBrush($path)
    $brush.CenterColor = [System.Drawing.ColorTranslator]::FromHtml($tileCenter)
    $brush.SurroundColors = @([System.Drawing.ColorTranslator]::FromHtml($tileEdge))
    $g.FillPath($brush, $path)
    $brush.Dispose(); $path.Dispose()

    $markSize = [single]($side * $markFrac)
    $markAt = [single](($big - $markSize) / 2)
    $g.DrawImage($script:mark, $markAt, $markAt, $markSize, $markSize)
  } finally {
    $g.Dispose()
  }
  if ($super -eq 1) { return $canvas }
  $reduced = New-Object System.Drawing.Bitmap($edge, $edge, [System.Drawing.Imaging.PixelFormat]::Format32bppArgb)
  $rg = New-Graphics $reduced
  $rg.Clear([System.Drawing.Color]::Transparent)
  $rg.DrawImage($canvas, 0, 0, $edge, $edge)
  $rg.Dispose(); $canvas.Dispose()
  return $reduced
}

function New-MarkOnlyBitmap([int]$edge, [double]$markFrac, [int]$super) {
  $big = $edge * $super
  $canvas = New-Object System.Drawing.Bitmap($big, $big, [System.Drawing.Imaging.PixelFormat]::Format32bppArgb)
  $g = New-Graphics $canvas
  $g.Clear([System.Drawing.Color]::Transparent)
  $markSize = [single]($big * $markFrac)
  $markAt = [single](($big - $markSize) / 2)
  $g.DrawImage($script:mark, $markAt, $markAt, $markSize, $markSize)
  $g.Dispose()
  if ($super -eq 1) { return $canvas }
  $reduced = New-Object System.Drawing.Bitmap($edge, $edge, [System.Drawing.Imaging.PixelFormat]::Format32bppArgb)
  $rg = New-Graphics $reduced
  $rg.Clear([System.Drawing.Color]::Transparent)
  $rg.DrawImage($canvas, 0, 0, $edge, $edge)
  $rg.Dispose(); $canvas.Dispose()
  return $reduced
}

function Save-Png([System.Drawing.Bitmap]$bitmap, [string]$path) {
  $bitmap.Save($path, [System.Drawing.Imaging.ImageFormat]::Png)
  $bitmap.Dispose()
}

# ICO container: 6-byte header + 16-byte directory entry per image + PNG payloads
# (Windows Vista+ and all mainstream browsers accept PNG-compressed entries).
# Entries are ordered `[pscustomobject]@{ Edge = <int>; Bytes = <byte[]> }` records;
# an ordered dictionary cannot carry integer keys (PowerShell indexes it positionally).
function Save-Ico([object[]]$entries, [string]$path) {
  $stream = New-Object System.IO.MemoryStream
  $writer = New-Object System.IO.BinaryWriter($stream)
  $writer.Write([UInt16]0)
  $writer.Write([UInt16]1)
  $writer.Write([UInt16]$entries.Count)
  $offset = 6 + 16 * $entries.Count
  foreach ($entry in $entries) {
    $size = [int]$entry.Edge
    $bytes = [byte[]]$entry.Bytes
    $edge = if ($size -ge 256) { 0 } else { $size }
    $writer.Write([Byte]$edge)
    $writer.Write([Byte]$edge)
    $writer.Write([Byte]0)
    $writer.Write([Byte]0)
    $writer.Write([UInt16]1)
    $writer.Write([UInt16]32)
    $writer.Write([UInt32]$bytes.Length)
    $writer.Write([UInt32]$offset)
    $offset += $bytes.Length
  }
  foreach ($entry in $entries) { $writer.Write([byte[]]$entry.Bytes) }
  $writer.Flush()
  [IO.File]::WriteAllBytes($path, $stream.ToArray())
  $stream.Dispose()
}

function Get-PngBytes([System.Drawing.Bitmap]$bitmap) {
  # PowerShell unrolls arrays on return: keep a single byte[] so BinaryWriter binds
  # to the byte[] overload (otherwise the ICO payload would be truncated).
  $stream = New-Object System.IO.MemoryStream
  $bitmap.Save($stream, [System.Drawing.Imaging.ImageFormat]::Png)
  $bitmap.Dispose()
  return , $stream.ToArray()
}

# -- Vector: same geometry, mark embedded as a base64 PNG ---------------------
function Get-IconSvg([int]$canvas, [double]$inset, [double]$radiusFrac, [double]$markFrac, [string]$base64) {
  $side = [Math]::Round($canvas * (1 - 2 * $inset), 2)
  $origin = [Math]::Round($canvas * $inset, 2)
  $radius = [Math]::Round($side * $radiusFrac, 2)
  $markSize = [Math]::Round($side * $markFrac, 2)
  $markAt = [Math]::Round(($canvas - $markSize) / 2, 2)
  $lines = @(
    ('<svg xmlns="http://www.w3.org/2000/svg" width="{0}" height="{0}" viewBox="0 0 {0} {0}" role="img" aria-label="WorkNexus-DSH icon">' -f $canvas),
    '  <defs>',
    '    <radialGradient id="worknexus-tile" cx="0.5" cy="0.5" r="0.5">',
    ('      <stop offset="0" stop-color="{0}"/>' -f $tileCenter),
    ('      <stop offset="1" stop-color="{0}"/>' -f $tileEdge),
    '    </radialGradient>',
    '  </defs>'
  )
  if ($inset -gt 0 -or $radiusFrac -gt 0) {
    $lines += ('  <rect x="{0}" y="{0}" width="{1}" height="{1}" rx="{2}" fill="url(#worknexus-tile)"/>' -f $origin, $side, $radius)
  }
  # `tray-glyph` marks the foreground for upstream `render:tray-icon.ts`.
  $lines += '  <g id="tray-glyph">'
  $lines += ('    <image x="{0}" y="{0}" width="{1}" height="{1}" href="data:image/png;base64,{2}"/>' -f $markAt, $markSize, $base64)
  $lines += '  </g>'
  $lines += '</svg>'
  # Fixed LF: the diffset patch is byte-exact input, CRLF drift would fake conflicts.
  return (($lines -join "`n") + "`n")
}

$targets = if ($Out) { $Out } else { Join-Path $upstream 'apps/desktop/resources' }
New-Item -ItemType Directory -Force -Path $targets | Out-Null

$markBytes = Get-BrandMarkPng
$markStream = New-Object System.IO.MemoryStream
$markStream.Write($markBytes, 0, $markBytes.Length)
$markStream.Position = 0
$script:mark = [System.Drawing.Image]::FromStream($markStream)
try {
  Save-Png (New-MarkOnlyBitmap 512 $bareMark 2) (Join-Path $targets 'icon.png')
  Save-Png (New-IconBitmap 256 0 $windowsRadius $markOfTile 4) (Join-Path $targets 'icon-windows.png')
  Save-Png (New-IconBitmap 512 $macInset $macRadius $markOfTile 2) (Join-Path $targets 'icon-macos.png')

  $entries = @()
  foreach ($size in $traySizes) {
    $entries += [pscustomobject]@{
      Edge = $size
      Bytes = Get-PngBytes (New-IconBitmap $size 0 $windowsRadius ($markOfTile * $trayGlyphScale) 8)
    }
  }
  Save-Ico $entries (Join-Path $targets 'tray-windows.ico')

  $base64 = [Convert]::ToBase64String($markBytes)
  [IO.File]::WriteAllText((Join-Path $targets 'icon.svg'),
    (Get-IconSvg $svgCanvas 0 0 $bareMark $base64), $wascii)
  [IO.File]::WriteAllText((Join-Path $targets 'icon-windows.svg'),
    (Get-IconSvg $svgCanvas 0 $windowsRadius $markOfTile $base64), $wascii)
  [IO.File]::WriteAllText((Join-Path $targets 'icon-macos.svg'),
    (Get-IconSvg $svgCanvas $macInset $macRadius $markOfTile $base64), $wascii)
} finally {
  $script:mark.Dispose()
  $markStream.Dispose()
}

foreach ($name in @('icon.png', 'icon-windows.png', 'icon-macos.png', 'tray-windows.ico',
                    'icon.svg', 'icon-windows.svg', 'icon-macos.svg')) {
  $info = [IO.FileInfo](Join-Path $targets $name)
  Write-Output ("[OK] {0,-18} {1,8} bytes" -f $name, $info.Length)
}
