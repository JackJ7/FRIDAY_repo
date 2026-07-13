# Create no-console shortcuts for FRIDAY: Desktop + Start Menu.
# Run:  powershell -ExecutionPolicy Bypass -File scripts\create_shortcuts.ps1

$root = Split-Path -Parent $PSScriptRoot          # the FRIDAY folder
$pythonw = Join-Path (Split-Path (Get-Command python).Source) "pythonw.exe"
$launcher = Join-Path $root "friday_app.py"

# Generate the icon from the same brand mark the tray uses (assets\friday.ico).
$assets = Join-Path $root "assets"
New-Item -ItemType Directory -Force $assets | Out-Null
python -c "import sys; sys.path.insert(0, r'$root'); from interface.app import make_icon_image; make_icon_image().save(r'$assets\friday.ico', sizes=[(16,16),(24,24),(32,32),(48,48),(64,64)])"

$shell = New-Object -ComObject WScript.Shell
$targets = @(
    (Join-Path ([Environment]::GetFolderPath('Desktop')) "FRIDAY.lnk"),
    (Join-Path $env:APPDATA "Microsoft\Windows\Start Menu\Programs\FRIDAY.lnk")
)
foreach ($lnkPath in $targets) {
    $lnk = $shell.CreateShortcut($lnkPath)
    $lnk.TargetPath = $pythonw                    # pythonw = no console window
    $lnk.Arguments = "`"$launcher`""
    $lnk.WorkingDirectory = $root
    $lnk.IconLocation = "$assets\friday.ico"
    $lnk.Description = "FRIDAY - local assistant"
    $lnk.Save()
    Write-Host "Created: $lnkPath"
}
