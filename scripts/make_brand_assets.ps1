<#
  Regenerates the WorkNexus-DSH brand artwork that the Windows installer and the
  desktop welcome window bake into bitmaps:

    apps/desktop/installer/assets/brand.png               600x196   (installer, light)
    apps/desktop/installer/assets/brand-2x.png           1200x392   (installer, light @2x)
    apps/desktop/installer/assets/brand-dark.png          600x196   (installer, dark)
    apps/desktop/installer/assets/brand-dark-2x.png      1200x392   (installer, dark @2x)
    apps/desktop/installer/assets/uninstaller-sidebar.png 164x314   (installer/uninstaller sidebar)
    apps/desktop/renderer/assets/welcome-brand-mark.png    80x80    (welcome window mark @2x)

  The mark is not retyped here: it is decoded from the single brand source
  `packages/client/ui-brand-official/src/client/Brand.tsx` (the base64 PNG the
  decision maker supplied on 2026-09-30), so the installer, the welcome window and
  the in-app sidebar can never drift apart.

  Layout is kept identical to the upstream artwork it replaces (same canvases, same
  circle centre/radius, same wordmark band), so no installer or window geometry
  changes: see docs/login-installer brand delivery note.

  Usage:
    powershell -NoProfile -File scripts/make_brand_assets.ps1
    powershell -NoProfile -File scripts/make_brand_assets.ps1 -Out <dir>
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

# ── Ink and surface tokens (light / dark lockups) ─────────────────────────────
$palette = @{
  light = @{ ink = '#0F1115'; circleCenter = '#FFFFFF'; circleEdge = '#EDEFF3' }
  dark  = @{ ink = '#F9FAFB'; circleCenter = '#3E3F45'; circleEdge = '#242528' }
}
$sidebarBackground = '#F3F4F6'
$sidebarCard = '#F9F9F9'
$wordmark = 'WorkNexus-DSH'
$wordmarkFont = 'Segoe UI Semibold'

function Get-BrandMarkPng {
  $text = [IO.File]::ReadAllText($brandSource)
  $marker = "'data:image/png;base64,'"
  $start = $text.IndexOf($marker)
  if ($start -lt 0) { throw "brand source carries no PNG data URI: $brandSource" }
  $start += $marker.Length
  $end = $text.IndexOf('/**', $start)
  $chunk = $text.Substring($start, $end - $start)
  $b64 = (([regex]::Split(($chunk -replace "'", ''), "\r?\n\s*\+\s*") -join '') -replace '\s', '')
  return [Convert]::FromBase64String($b64)
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

function New-Canvas([int]$w, [int]$h, [bool]$opaque, [string]$background) {
  # Opaque surfaces stay 24bpp like the upstream artwork, so the NSIS BMP conversion
  # and the packaged file keep the same channel layout they had before.
  $format = if ($opaque) { [System.Drawing.Imaging.PixelFormat]::Format24bppRgb } else { [System.Drawing.Imaging.PixelFormat]::Format32bppArgb }
  $bmp = New-Object System.Drawing.Bitmap($w, $h, $format)
  $g = [System.Drawing.Graphics]::FromImage($bmp)
  $g.SmoothingMode = [System.Drawing.Drawing2D.SmoothingMode]::AntiAlias
  $g.InterpolationMode = [System.Drawing.Drawing2D.InterpolationMode]::HighQualityBicubic
  $g.PixelOffsetMode = [System.Drawing.Drawing2D.PixelOffsetMode]::HighQuality
  $g.TextRenderingHint = [System.Drawing.Text.TextRenderingHint]::AntiAliasGridFit
  if ($opaque) { $g.Clear([System.Drawing.ColorTranslator]::FromHtml($background)) } else { $g.Clear([System.Drawing.Color]::Transparent) }
  return @{ Bitmap = $bmp; Graphics = $g }
}

# ── Lockup: soft circle + brand mark + wordmark (installer brand*.png) ────────
function Write-Lockup([string]$path, [int]$scale, [string]$theme) {
  $w = 600 * $scale
  $h = 196 * $scale
  $canvas = New-Canvas $w $h $false $null
  $bmp = $canvas.Bitmap
  $g = $canvas.Graphics
  try {
    $color = $palette[$theme]
    $cx = 300 * $scale
    $cy = 78 * $scale
    $r = 62 * $scale
    $rect = New-Object System.Drawing.RectangleF(($cx - $r), ($cy - $r), ($r * 2), ($r * 2))
    $circle = New-Object System.Drawing.Drawing2D.GraphicsPath
    $circle.AddEllipse($rect)
    $brush = New-Object System.Drawing.Drawing2D.PathGradientBrush($circle)
    $brush.CenterColor = [System.Drawing.ColorTranslator]::FromHtml($color.circleCenter)
    $brush.SurroundColors = @([System.Drawing.ColorTranslator]::FromHtml($color.circleEdge))
    $g.FillPath($brush, $circle)
    $brush.Dispose()
    $circle.Dispose()

    $markSize = 84 * $scale
    $g.DrawImage($script:mark, [int]($cx - $markSize / 2), [int]($cy - $markSize / 2), $markSize, $markSize)

    $font = New-Object System.Drawing.Font($wordmarkFont, (28 * $scale), [System.Drawing.FontStyle]::Regular, [System.Drawing.GraphicsUnit]::Pixel)
    $ink = New-Object System.Drawing.SolidBrush([System.Drawing.ColorTranslator]::FromHtml($color.ink))
    $format = New-Object System.Drawing.StringFormat
    $format.Alignment = [System.Drawing.StringAlignment]::Center
    $textRect = New-Object System.Drawing.RectangleF(0, (154 * $scale), $w, (44 * $scale))
    $g.DrawString($wordmark, $font, $ink, $textRect, $format)
    $ink.Dispose(); $font.Dispose(); $format.Dispose()

    $bmp.Save($path, [System.Drawing.Imaging.ImageFormat]::Png)
  } finally {
    $g.Dispose(); $bmp.Dispose()
  }
}

# ── Installer / uninstaller sidebar: light field + card + mark ───────────────
function Write-Sidebar([string]$path) {
  $canvas = New-Canvas 164 314 $true $sidebarBackground
  $bmp = $canvas.Bitmap
  $g = $canvas.Graphics
  try {
    $card = New-RoundedPath 22 89 120 120 22
    $cardBrush = New-Object System.Drawing.SolidBrush([System.Drawing.ColorTranslator]::FromHtml($sidebarCard))
    $g.FillPath($cardBrush, $card)
    $cardBrush.Dispose(); $card.Dispose()

    $markSize = 76
    $g.DrawImage($script:mark, [int](81.5 - $markSize / 2), [int](148.5 - $markSize / 2), $markSize, $markSize)
    $bmp.Save($path, [System.Drawing.Imaging.ImageFormat]::Png)
  } finally {
    $g.Dispose(); $bmp.Dispose()
  }
}

# ── Welcome window mark (the wordmark there is live text) ────────────────────
function Write-WelcomeMark([string]$path) {
  $canvas = New-Canvas 80 80 $false $null
  $bmp = $canvas.Bitmap
  $g = $canvas.Graphics
  try {
    $g.DrawImage($script:mark, 0, 0, 80, 80)
    $bmp.Save($path, [System.Drawing.Imaging.ImageFormat]::Png)
  } finally {
    $g.Dispose(); $bmp.Dispose()
  }
}

$targets = if ($Out) { $Out } else { $upstream }
$installerAssets = Join-Path $targets 'apps/desktop/installer/assets'
$rendererAssets = Join-Path $targets 'apps/desktop/renderer/assets'
New-Item -ItemType Directory -Force -Path $installerAssets, $rendererAssets | Out-Null

$markBytes = Get-BrandMarkPng
$markStream = New-Object System.IO.MemoryStream(, $markBytes)
$script:mark = [System.Drawing.Image]::FromStream($markStream)
try {
  Write-Lockup (Join-Path $installerAssets 'brand.png') 1 'light'
  Write-Lockup (Join-Path $installerAssets 'brand-2x.png') 2 'light'
  Write-Lockup (Join-Path $installerAssets 'brand-dark.png') 1 'dark'
  Write-Lockup (Join-Path $installerAssets 'brand-dark-2x.png') 2 'dark'
  Write-Sidebar (Join-Path $installerAssets 'uninstaller-sidebar.png')
  Write-WelcomeMark (Join-Path $rendererAssets 'welcome-brand-mark.png')
} finally {
  $script:mark.Dispose()
  $markStream.Dispose()
}

foreach ($file in @('brand.png', 'brand-2x.png', 'brand-dark.png', 'brand-dark-2x.png', 'uninstaller-sidebar.png')) {
  $info = [IO.FileInfo](Join-Path $installerAssets $file)
  Write-Output ("installer asset {0,-24} {1,8} bytes" -f $file, $info.Length)
}
$welcome = [IO.FileInfo](Join-Path $rendererAssets 'welcome-brand-mark.png')
Write-Output ("welcome mark  {0,-24} {1,8} bytes" -f 'welcome-brand-mark.png', $welcome.Length)
