# Captures d'ecran du chantier v3 : un PNG par ecran de l'application.
#
#   powershell -File tests\captures_v3.ps1 [-Sortie <dossier>] [-Densite normale]
#
# Chaque ecran est ouvert par tests\manuel_fumee_v3.py, capture, puis ferme :
# deterministe, contrairement a une bascule d'onglets chronometree.
param(
  [string]$Sortie = 'D:\SNE\Projets\IntellaFeeder\captures_gui',
  [string]$Densite = '',
  [string]$Prefixe = 'v3',
  [string[]]$Ecrans = @('inventaire','detail','import','profils','profils-types','maintenance','options','mime','fichiers','aide'),
  # Sources FICTIVES injectees : une capture parlante sans donnee de cas reel.
  [switch]$Demo
)

Add-Type -AssemblyName System.Windows.Forms, System.Drawing
Add-Type -TypeDefinition @'
using System;
using System.Runtime.InteropServices;
public class DpiHelper { [DllImport("user32.dll")] public static extern bool SetProcessDPIAware(); }
'@ -ErrorAction SilentlyContinue
[void][DpiHelper]::SetProcessDPIAware()

$script = 'D:\SNE\Projets\IntellaFeeder\Script\tests\manuel_fumee_v3.py'
New-Item -ItemType Directory -Force -Path $Sortie | Out-Null
$i = 0
foreach ($e in $Ecrans) {
  $i++
  # $args est une variable AUTOMATIQUE en PowerShell : l'assigner ne fait rien
  # et le script partait sans arguments (ecran par defaut, aucune capture).
  $argv = @($script, $e, '--secondes', '9')
  if ($Densite) { $argv += @('--densite', $Densite) }
  if ($Demo) { $argv += '--demo' }
  $p = Start-Process -FilePath 'python.exe' -ArgumentList $argv -PassThru -WindowStyle Normal
  Start-Sleep -Seconds 4
  $b = [System.Windows.Forms.Screen]::PrimaryScreen.Bounds
  $bmp = New-Object System.Drawing.Bitmap $b.Width, $b.Height
  $g = [System.Drawing.Graphics]::FromImage($bmp)
  $g.CopyFromScreen($b.Location, [System.Drawing.Point]::Empty, $b.Size)
  $nom = '{0}_{1:d2}_{2}.png' -f $Prefixe, $i, ($e -replace '[^a-z0-9\-]','')
  $bmp.Save((Join-Path $Sortie $nom), [System.Drawing.Imaging.ImageFormat]::Png)
  $g.Dispose(); $bmp.Dispose()
  try { if (-not $p.HasExited) { Stop-Process -Id $p.Id -Force } } catch {}
  Start-Sleep -Milliseconds 400
  "$nom"
}
