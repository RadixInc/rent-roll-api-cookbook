param(
  [string]$InstallDir = (Split-Path -Parent $MyInvocation.MyCommand.Path)
)

$ErrorActionPreference = "Stop"

# -- Shared constants ----------------------------------------------------------
$MenuText     = "Upload Rent Roll (redIQ)"
$configDir    = Join-Path $env:APPDATA "RedIQ\RentRollUploader"
$configPath   = Join-Path $configDir  "config.json"
$credTarget   = "RedIQ-RentRoll-Uploader"
$uploadScript = Join-Path $InstallDir "upload.ps1"

# ==============================================================
#  Helper functions
# ==============================================================

function Initialize-CredentialManager {
  if (-not (Get-Module -ListAvailable -Name CredentialManager)) {
    Write-Host "  Installing CredentialManager module (one-time, CurrentUser)..." -ForegroundColor Yellow
    Install-Module CredentialManager -Scope CurrentUser -Force
  }
  Import-Module CredentialManager
}

# -- Context-menu install ------------------------------------------------------
function Install-ContextMenu {
  if (!(Test-Path $uploadScript)) {
    throw "upload.ps1 not found in $InstallDir - cannot register context menu."
  }

  # Clean up legacy per-extension entries
  $oldExtensions = @('.xls', '.xlsx', '.xlm', '.xlsm', '.csv', '.pdf', '.ods')
  foreach ($ext in $oldExtensions) {
    $old = "HKCU:\Software\Classes\SystemFileAssociations\$ext\shell\$MenuText"
    if (Test-Path $old) { Remove-Item $old -Recurse -Force }
  }

  # Clean up legacy AllFilesystemObjects entries
  $legacyPaths = @(
    "HKCU:\Software\Classes\AllFilesystemObjects\shell\RedIQ",
    "HKCU:\Software\Classes\AllFilesystemObjects\shell\RedIQ Upload Rent Rolls",
    "HKCU:\Software\Classes\AllFilesystemObjects\shell\Upload Rent Rolls (RedIQ)",
    "HKCU:\Software\Classes\AllFilesystemObjects\shell\Upload Rent Roll (RedIQ)",
    "HKCU:\Software\Classes\AllFilesystemObjects\shell\$MenuText"
  )
  foreach ($p in $legacyPaths) {
    if (Test-Path $p) { Remove-Item $p -Recurse -Force }
  }

  # Register under HKCU:\...\*\shell for reliable multi-select support.
  # Uses the .NET Registry API because the literal "*" in the path causes
  # PowerShell's provider to treat it as a wildcard and hang.
  $cmd = "powershell.exe -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$uploadScript`" -Collect -Path `"%1`""
  $regBasePath = "Software\Classes\*\shell\$MenuText"

  $regKey = [Microsoft.Win32.Registry]::CurrentUser.CreateSubKey($regBasePath)
  $regKey.SetValue("MultiSelectModel", "Document", [Microsoft.Win32.RegistryValueKind]::String)
  $regKey.SetValue("MUIVerb",          $MenuText,  [Microsoft.Win32.RegistryValueKind]::String)
  $iconPath = Join-Path $InstallDir "radixfavico.ico"
  if (Test-Path $iconPath) {
    $regKey.SetValue("Icon", $iconPath, [Microsoft.Win32.RegistryValueKind]::String)
  }
  else {
    $regKey.SetValue("Icon", "shell32.dll,70", [Microsoft.Win32.RegistryValueKind]::String)
  }
  $regKey.DeleteValue("AppliesTo", $false)   # remove stale value from previous installs
  $regKey.Close()

  $cmdKey = [Microsoft.Win32.Registry]::CurrentUser.CreateSubKey("$regBasePath\command")
  $cmdKey.SetValue("", $cmd, [Microsoft.Win32.RegistryValueKind]::String)
  $cmdKey.Close()

  Write-Host "  Context menu installed (multi-select supported)." -ForegroundColor Green
  Write-Host "  Right-click any file(s) -> Show more options (Win11) -> $MenuText" -ForegroundColor DarkGray
}

# -- Context-menu uninstall -----------------------------------------------------
function Uninstall-ContextMenu {
  $removed = 0

  # Current * registration
  $starParent = "Software\Classes\*\shell"
  $parentKey  = [Microsoft.Win32.Registry]::CurrentUser.OpenSubKey($starParent, $true)
  if ($null -ne $parentKey) {
    try {
      $parentKey.DeleteSubKeyTree($MenuText, $false)
      $removed++
    }
    finally { $parentKey.Close() }
  }

  # Old per-extension entries
  $oldExtensions = @('.xls', '.xlsx', '.xlm', '.xlsm', '.csv', '.pdf', '.ods')
  foreach ($ext in $oldExtensions) {
    $key = "HKCU:\Software\Classes\SystemFileAssociations\$ext\shell\$MenuText"
    if (Test-Path $key) {
      Remove-Item -Path $key -Recurse -Force
      $removed++
    }
  }

  # Legacy AllFilesystemObjects entries
  $legacyPaths = @(
    "HKCU:\Software\Classes\AllFilesystemObjects\shell\$MenuText",
    "HKCU:\Software\Classes\AllFilesystemObjects\shell\RedIQ",
    "HKCU:\Software\Classes\AllFilesystemObjects\shell\RedIQ Upload Rent Rolls",
    "HKCU:\Software\Classes\AllFilesystemObjects\shell\Upload Rent Rolls (RedIQ)",
    "HKCU:\Software\Classes\AllFilesystemObjects\shell\Upload Rent Roll (RedIQ)"
  )
  foreach ($p in $legacyPaths) {
    if (Test-Path $p) {
      Remove-Item -Path $p -Recurse -Force
      $removed++
    }
  }

  if ($removed -eq 0) {
    Write-Host "  No context menu entries found." -ForegroundColor DarkGray
  }
  else {
    Write-Host "  Removed $removed context menu entry/entries." -ForegroundColor Green
  }
}

# -- Helper: mask API key for display ------------------------------------------
function Get-MaskedApiKey {
  param([string]$Key)
  if ([string]::IsNullOrWhiteSpace($Key)) { return "(not set)" }
  if ($Key.Length -le 12) { return "****" + $Key.Substring([Math]::Max(0, $Key.Length - 4)) }
  return $Key.Substring(0, 9) + "..." + $Key.Substring($Key.Length - 4)
}

# -- Helper: persist notification config to disk -------------------------------
function Save-NotificationConfig {
  param([string]$Email, [string]$Webhook)
  $methods = @()
  if (-not [string]::IsNullOrWhiteSpace($Email))   { $methods += @{ type = "email";   entry = $Email } }
  if (-not [string]::IsNullOrWhiteSpace($Webhook)) { $methods += @{ type = "webhook"; entry = $Webhook } }
  $cfg = @{
    serverBaseUrl       = "https://connect.rediq.io"
    notificationMethods = $methods
  }
  New-Item -ItemType Directory -Force -Path $configDir | Out-Null
  $cfg | ConvertTo-Json -Depth 6 | Set-Content -Path $configPath -Encoding UTF8
}

# ==============================================================
#  Setup / Configure
# ==============================================================
function Invoke-SetupConfigure {
  Write-Host ""
  New-Item -ItemType Directory -Force -Path $configDir | Out-Null
  Initialize-CredentialManager

  # -- Load any existing values ------------------------------------------------
  $currentKey     = ""
  $currentEmail   = ""
  $currentWebhook = ""

  $cred = Get-StoredCredential -Target $credTarget -ErrorAction SilentlyContinue
  if ($null -ne $cred) {
    $currentKey = [System.Net.NetworkCredential]::new("", $cred.Password).Password
  }

  if (Test-Path $configPath) {
    try {
      $existing = Get-Content $configPath -Raw | ConvertFrom-Json
      foreach ($m in $existing.notificationMethods) {
        if ($m.type -eq "email")   { $currentEmail   = $m.entry }
        if ($m.type -eq "webhook") { $currentWebhook = $m.entry }
      }
    }
    catch { }
  }

  $hasExisting = (-not [string]::IsNullOrWhiteSpace($currentKey)) -or
                 (-not [string]::IsNullOrWhiteSpace($currentEmail)) -or
                 (-not [string]::IsNullOrWhiteSpace($currentWebhook))

  # ==========================================================================
  #  Fresh install  (no stored values found) - guided linear flow
  # ==========================================================================
  if (-not $hasExisting) {
    Write-Host "  Step 1 of 3 - API Key" -ForegroundColor Cyan
    Write-Host "  ---------------------" -ForegroundColor Cyan

    $apiKey = Read-Host "  Paste your API key (e.g., riq_live_...)"
    $apiKey = $apiKey.Trim()

    if ([string]::IsNullOrWhiteSpace($apiKey)) {
      throw "API key cannot be blank."
    }
    if ($apiKey -notmatch '^riq_(live|test|dev)_') {
      Write-Warning "  That key doesn't look like a typical redIQ key (expected riq_live_... etc)."
    }

    Remove-StoredCredential -Target $credTarget -ErrorAction SilentlyContinue
    New-StoredCredential -Target $credTarget -UserName $env:USERNAME -Password $apiKey -Persist LocalMachine | Out-Null
    Write-Host "  API key saved to Windows Credential Manager." -ForegroundColor Green

    Write-Host ""
    Write-Host "  Step 2 of 3 - Notifications" -ForegroundColor Cyan
    Write-Host "  ---------------------------" -ForegroundColor Cyan

    $email = Read-Host "  Notification email (blank to skip)"
    $email = $email.Trim()

    $webhook = Read-Host "  Webhook URL (blank to skip)"
    $webhook = $webhook.Trim()

    $methods = @()
    if (-not [string]::IsNullOrWhiteSpace($email))   { $methods += @{ type = "email";   entry = $email } }
    if (-not [string]::IsNullOrWhiteSpace($webhook)) { $methods += @{ type = "webhook"; entry = $webhook } }

    if ($methods.Count -eq 0) {
      Write-Warning "  No notification methods provided. Uploads require at least one. Re-run setup to fix."
    }

    $config = @{
      serverBaseUrl       = "https://connect.rediq.io"
      notificationMethods = $methods
    }

    $config | ConvertTo-Json -Depth 6 | Set-Content -Path $configPath -Encoding UTF8
    Write-Host "  Config saved to: $configPath" -ForegroundColor Green

    Write-Host ""
    Write-Host "  Step 3 of 3 - Context Menu" -ForegroundColor Cyan
    Write-Host "  --------------------------" -ForegroundColor Cyan

    Install-ContextMenu

    Write-Host ""
    Write-Host "  Setup complete. You're ready to go!" -ForegroundColor Green
    Write-Host ""
    Write-Host "  If the context menu doesn't appear immediately, restart Explorer:" -ForegroundColor Yellow
    Write-Host "    Task Manager -> Windows Explorer -> Restart" -ForegroundColor Yellow
    return
  }

  # ==========================================================================
  #  Existing config found - per-item update menu
  # ==========================================================================
  :updateMenu while ($true) {
    Write-Host ""
    Write-Host "  Current Configuration" -ForegroundColor Cyan
    Write-Host "  ---------------------" -ForegroundColor Cyan

    $keyDisplay     = Get-MaskedApiKey $currentKey
    $emailDisplay   = if ([string]::IsNullOrWhiteSpace($currentEmail))   { "(not set)" } else { $currentEmail }
    $webhookDisplay = if ([string]::IsNullOrWhiteSpace($currentWebhook)) { "(not set)" } else { $currentWebhook }

    Write-Host "  API Key ........ $keyDisplay"     -ForegroundColor White
    Write-Host "  Email .......... $emailDisplay"   -ForegroundColor White
    Write-Host "  Webhook URL .... $webhookDisplay" -ForegroundColor White
    Write-Host ""
    Write-Host "  What would you like to update?" -ForegroundColor Cyan
    Write-Host "  [1]  API Key"                    -ForegroundColor White
    Write-Host "  [2]  Notification Email"         -ForegroundColor White
    Write-Host "  [3]  Webhook URL"                -ForegroundColor White
    Write-Host "  [4]  Reinstall Context Menu"     -ForegroundColor White
    Write-Host "  [5]  Update All (fresh start)"   -ForegroundColor White
    Write-Host "  [6]  Done / Exit"                -ForegroundColor White
    Write-Host ""

    $pick = Read-Host "  Select an option (1-6)"

    switch ($pick) {

      "1" {   # ---- Update API Key ----
        Write-Host ""
        $apiKey = Read-Host "  Paste your new API key (e.g., riq_live_...)"
        $apiKey = $apiKey.Trim()
        if ([string]::IsNullOrWhiteSpace($apiKey)) {
          Write-Warning "  API key cannot be blank. No changes made."
        }
        else {
          if ($apiKey -notmatch '^riq_(live|test|dev)_') {
            Write-Warning "  That key doesn't look like a typical redIQ key (expected riq_live_... etc)."
          }
          Remove-StoredCredential -Target $credTarget -ErrorAction SilentlyContinue
          New-StoredCredential -Target $credTarget -UserName $env:USERNAME -Password $apiKey -Persist LocalMachine | Out-Null
          $currentKey = $apiKey
          Write-Host "  API key updated." -ForegroundColor Green
        }
      }

      "2" {   # ---- Update Email ----
        Write-Host ""
        $email = Read-Host "  Notification email (blank to clear)"
        $currentEmail = $email.Trim()
        Save-NotificationConfig $currentEmail $currentWebhook
        if ([string]::IsNullOrWhiteSpace($currentEmail)) {
          Write-Host "  Email cleared. Config saved." -ForegroundColor Green
        }
        else {
          Write-Host "  Email updated. Config saved." -ForegroundColor Green
        }
      }

      "3" {   # ---- Update Webhook ----
        Write-Host ""
        $webhook = Read-Host "  Webhook URL (blank to clear)"
        $currentWebhook = $webhook.Trim()
        Save-NotificationConfig $currentEmail $currentWebhook
        if ([string]::IsNullOrWhiteSpace($currentWebhook)) {
          Write-Host "  Webhook URL cleared. Config saved." -ForegroundColor Green
        }
        else {
          Write-Host "  Webhook URL updated. Config saved." -ForegroundColor Green
        }
      }

      "4" {   # ---- Reinstall Context Menu ----
        Write-Host ""
        Install-ContextMenu
      }

      "5" {   # ---- Update All (fresh start) ----
        Remove-StoredCredential -Target $credTarget -ErrorAction SilentlyContinue
        if (Test-Path $configPath) { Remove-Item $configPath -Force }

        Write-Host ""
        Write-Host "  Starting fresh setup..." -ForegroundColor Cyan
        Write-Host ""
        Write-Host "  Step 1 of 3 - API Key" -ForegroundColor Cyan
        Write-Host "  ---------------------" -ForegroundColor Cyan

        $apiKey = Read-Host "  Paste your API key (e.g., riq_live_...)"
        $apiKey = $apiKey.Trim()

        if ([string]::IsNullOrWhiteSpace($apiKey)) {
          throw "API key cannot be blank."
        }
        if ($apiKey -notmatch '^riq_(live|test|dev)_') {
          Write-Warning "  That key doesn't look like a typical redIQ key (expected riq_live_... etc)."
        }

        Remove-StoredCredential -Target $credTarget -ErrorAction SilentlyContinue
        New-StoredCredential -Target $credTarget -UserName $env:USERNAME -Password $apiKey -Persist LocalMachine | Out-Null
        $currentKey = $apiKey
        Write-Host "  API key saved to Windows Credential Manager." -ForegroundColor Green

        Write-Host ""
        Write-Host "  Step 2 of 3 - Notifications" -ForegroundColor Cyan
        Write-Host "  ---------------------------" -ForegroundColor Cyan

        $email = Read-Host "  Notification email (blank to skip)"
        $currentEmail = $email.Trim()

        $webhook = Read-Host "  Webhook URL (blank to skip)"
        $currentWebhook = $webhook.Trim()

        Save-NotificationConfig $currentEmail $currentWebhook
        Write-Host "  Config saved." -ForegroundColor Green

        Write-Host ""
        Write-Host "  Step 3 of 3 - Context Menu" -ForegroundColor Cyan
        Write-Host "  --------------------------" -ForegroundColor Cyan

        Install-ContextMenu

        Write-Host ""
        Write-Host "  Setup complete. You're ready to go!" -ForegroundColor Green
        Write-Host ""
        Write-Host "  If the context menu doesn't appear immediately, restart Explorer:" -ForegroundColor Yellow
        Write-Host "    Task Manager -> Windows Explorer -> Restart" -ForegroundColor Yellow
        break updateMenu
      }

      "6" {   # ---- Done / Exit ----
        if ([string]::IsNullOrWhiteSpace($currentEmail) -and [string]::IsNullOrWhiteSpace($currentWebhook)) {
          Write-Warning "  Heads up: no notification methods configured. Uploads require at least one."
        }
        Write-Host "  Done. No further changes." -ForegroundColor DarkGray
        break updateMenu
      }

      default {
        Write-Host "  Invalid selection. Please choose 1-6." -ForegroundColor Red
      }
    }
  }
}

# ==============================================================
#  Uninstall
# ==============================================================
function Invoke-Uninstall {
  Write-Host ""
  Write-Host "  This will remove all redIQ Rent Roll Uploader components:" -ForegroundColor White
  Write-Host "    - Right-click context menu entry" -ForegroundColor DarkGray
  Write-Host "    - Stored API key (Windows Credential Manager)" -ForegroundColor DarkGray
  Write-Host "    - Configuration and log files" -ForegroundColor DarkGray
  Write-Host ""

  $confirm = Read-Host "  Type YES to confirm uninstall"
  if ($confirm -ne "YES") {
    Write-Host "  Uninstall cancelled." -ForegroundColor Yellow
    return
  }

  Write-Host ""

  # 1. Context menu
  Write-Host "  Removing context menu..." -ForegroundColor White
  Uninstall-ContextMenu

  # 2. Stored credential
  Write-Host "  Removing stored API key..." -ForegroundColor White
  try {
    Initialize-CredentialManager
    $cred = Get-StoredCredential -Target $credTarget -ErrorAction SilentlyContinue
    if ($null -ne $cred) {
      Remove-StoredCredential -Target $credTarget -ErrorAction SilentlyContinue
      Write-Host "  API key removed from Credential Manager." -ForegroundColor Green
    }
    else {
      Write-Host "  No stored API key found." -ForegroundColor DarkGray
    }
  }
  catch {
    Write-Host "  Could not remove credential (CredentialManager module unavailable)." -ForegroundColor DarkGray
  }

  # 3. Config directory (config.json + uploader.log)
  Write-Host "  Removing config and log files..." -ForegroundColor White
  if (Test-Path $configDir) {
    Remove-Item $configDir -Recurse -Force
    Write-Host "  Removed: $configDir" -ForegroundColor Green
  }
  else {
    Write-Host "  Config directory not found." -ForegroundColor DarkGray
  }

  Write-Host ""
  Write-Host "  Uninstall complete. All redIQ components have been removed." -ForegroundColor Green
  Write-Host ""
  Write-Host "  If the context menu still appears, restart Explorer:" -ForegroundColor Yellow
  Write-Host "    Task Manager -> Windows Explorer -> Restart" -ForegroundColor Yellow
}

# ==============================================================
#  Main - interactive menu
# ==============================================================
try {
  Clear-Host
  Write-Host ""
  Write-Host "  ========================================" -ForegroundColor Cyan
  Write-Host "    redIQ Rent Roll Uploader  -  Setup" -ForegroundColor Cyan
  Write-Host "  ========================================" -ForegroundColor Cyan
  Write-Host ""
  Write-Host "  [1]  Setup / Configure" -ForegroundColor White
  Write-Host "       Set API key, notification preferences," -ForegroundColor DarkGray
  Write-Host "       and install the right-click context menu." -ForegroundColor DarkGray
  Write-Host ""
  Write-Host "  [2]  Uninstall" -ForegroundColor White
  Write-Host "       Remove context menu, stored credentials," -ForegroundColor DarkGray
  Write-Host "       and configuration files." -ForegroundColor DarkGray
  Write-Host ""
  Write-Host "  [3]  Exit" -ForegroundColor White
  Write-Host ""

  $choice = Read-Host "  Select an option (1-3)"

  switch ($choice) {
    "1" { Invoke-SetupConfigure }
    "2" { Invoke-Uninstall }
    "3" { Write-Host "  Goodbye." -ForegroundColor DarkGray }
    default {
      Write-Host "  Invalid selection. Run setup again and choose 1, 2, or 3." -ForegroundColor Red
    }
  }
}
catch {
  Write-Host ""
  Write-Host "  ERROR: $($_.Exception.Message)" -ForegroundColor Red
  Write-Host ""
}

Write-Host ""
Read-Host "Press Enter to close"
