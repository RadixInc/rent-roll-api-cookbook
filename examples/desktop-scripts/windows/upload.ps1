param(
  [Parameter(Mandatory = $true)]
  [string[]]$Path,
  [switch]$Collect   # Context-menu batch mode: accumulate multi-selected files via temp queue
)

$ErrorActionPreference = "Stop"

# ---------- Constants ----------
$allowedExtensions = @('.xlsx', '.xls', '.xlsm', '.csv', '.ods')
$maxFiles = 20

# ---------- Logging ----------
$logDir = Join-Path $env:APPDATA "RedIQ\RentRollUploader"
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
$logPath = Join-Path $logDir "uploader.log"

function Log([string]$line) {
  $ts = (Get-Date).ToString("yyyy-MM-dd HH:mm:ss")
  Add-Content -Path $logPath -Value "[$ts] $line"
}

# ---------- Batch-collection for context-menu multi-select ----------
# When the shell verb fires once per file (MultiSelectModel=Single), each
# instance appends its path to a shared temp queue, waits for the queue to
# stabilise, then ONE instance claims and uploads the full batch.
if ($Collect) {
  $queueFile = Join-Path $env:TEMP "rediq-upload-batch.txt"
  $mutexName = "Global\RedIQ-UploadBatch"

  $mutex = [System.Threading.Mutex]::new($false, $mutexName)

  # --- Phase 1: append this file to the queue ---
  try {
    $mutex.WaitOne() | Out-Null
    # Discard stale queue from a previous (possibly crashed) run
    if ((Test-Path $queueFile) -and ((Get-Item $queueFile).LastWriteTime -lt (Get-Date).AddSeconds(-10))) {
      Remove-Item $queueFile -Force
    }
    Add-Content -Path $queueFile -Value ($Path[0])
    $mutex.ReleaseMutex()
  }
  catch {
    try { $mutex.ReleaseMutex() } catch { }
    throw
  }

  # --- Phase 2: wait for all instances to finish writing ---
  Start-Sleep -Milliseconds 1500

  # Brief stability check — ensure no new files are still being appended
  for ($i = 0; $i -lt 3; $i++) {
    $lastWrite = (Get-Item $queueFile -ErrorAction SilentlyContinue).LastWriteTime
    Start-Sleep -Milliseconds 300
    $newWrite  = (Get-Item $queueFile -ErrorAction SilentlyContinue).LastWriteTime
    if ($lastWrite -eq $newWrite) { break }
  }

  # --- Phase 3: claim the queue (first writer wins) ---
  $collectedPaths = $null
  try {
    $mutex.WaitOne() | Out-Null
    if (Test-Path $queueFile) {
      $collectedPaths = @(Get-Content $queueFile | Where-Object { $_ -ne '' })
      Remove-Item $queueFile -Force
    }
    $mutex.ReleaseMutex()
  }
  catch {
    try { $mutex.ReleaseMutex() } catch { }
  }
  finally {
    $mutex.Dispose()
  }

  if ($null -eq $collectedPaths -or $collectedPaths.Count -eq 0) {
    # Another instance already processed the queue — nothing left to do
    exit 0
  }

  # Replace $Path with the full collected batch
  $Path = $collectedPaths
}

"=== started $(Get-Date) | Files=$($Path.Count) | Paths=$($Path -join '; ') ===" | Add-Content -Path $logPath

# ---------- UI helpers ----------
function Show-Popup(
  [string]$title,
  [string]$message,
  [ValidateSet("Information","Error","Warning")]
  [string]$icon = "Information"
) {
  Add-Type -AssemblyName System.Windows.Forms | Out-Null
  $buttons = [System.Windows.Forms.MessageBoxButtons]::OK
  $mbIcon  = [System.Windows.Forms.MessageBoxIcon]::$icon
  [System.Windows.Forms.MessageBox]::Show($message, $title, $buttons, $mbIcon) | Out-Null
}

function Show-YesNo(
  [string]$title,
  [string]$message
) {
  Add-Type -AssemblyName System.Windows.Forms | Out-Null
  $buttons = [System.Windows.Forms.MessageBoxButtons]::YesNo
  $mbIcon  = [System.Windows.Forms.MessageBoxIcon]::Warning
  return [System.Windows.Forms.MessageBox]::Show($message, $title, $buttons, $mbIcon)
}

# ---------- Deal selection ----------
function Show-DealChooser {
  Add-Type -AssemblyName System.Windows.Forms | Out-Null
  Add-Type -AssemblyName System.Drawing | Out-Null

  $form = [System.Windows.Forms.Form]::new()
  $form.Text = "Associate with a Deal - redIQ"
  $form.Size = [System.Drawing.Size]::new(320, 245)
  $form.StartPosition = "CenterScreen"
  $form.FormBorderStyle = "FixedDialog"
  $form.MaximizeBox = $false
  $form.MinimizeBox = $false

  $script:result = "cancel"

  $btnRecent = [System.Windows.Forms.Button]::new()
  $btnRecent.Text = "Select Recent Deal"
  $btnRecent.Size = [System.Drawing.Size]::new(264, 34)
  $btnRecent.Location = [System.Drawing.Point]::new(20, 16)
  $btnRecent.Add_Click({ $script:result = "recent"; $form.Close() })

  $btnSearch = [System.Windows.Forms.Button]::new()
  $btnSearch.Text = "Search Deal by Name"
  $btnSearch.Size = [System.Drawing.Size]::new(264, 34)
  $btnSearch.Location = [System.Drawing.Point]::new(20, 58)
  $btnSearch.Add_Click({ $script:result = "search"; $form.Close() })

  $btnCreate = [System.Windows.Forms.Button]::new()
  $btnCreate.Text = "Create New Deal"
  $btnCreate.Size = [System.Drawing.Size]::new(264, 34)
  $btnCreate.Location = [System.Drawing.Point]::new(20, 100)
  $btnCreate.Add_Click({ $script:result = "create"; $form.Close() })

  $btnSkip = [System.Windows.Forms.Button]::new()
  $btnSkip.Text = "Upload Without Deal"
  $btnSkip.Size = [System.Drawing.Size]::new(264, 34)
  $btnSkip.Location = [System.Drawing.Point]::new(20, 142)
  $btnSkip.Add_Click({ $script:result = "skip"; $form.Close() })

  $form.Controls.AddRange(@($btnRecent, $btnSearch, $btnCreate, $btnSkip))
  try { $form.ShowDialog() | Out-Null } finally { $form.Dispose() }
  return $script:result
}

function Show-SearchBox {
  Add-Type -AssemblyName System.Windows.Forms | Out-Null
  Add-Type -AssemblyName System.Drawing | Out-Null

  $form = [System.Windows.Forms.Form]::new()
  $form.Text = "Search Deals - redIQ"
  $form.Size = [System.Drawing.Size]::new(370, 130)
  $form.StartPosition = "CenterScreen"
  $form.FormBorderStyle = "FixedDialog"
  $form.MaximizeBox = $false
  $form.MinimizeBox = $false

  $lbl = [System.Windows.Forms.Label]::new()
  $lbl.Text = "Enter deal name to search:"
  $lbl.Location = [System.Drawing.Point]::new(16, 16)
  $lbl.Size = [System.Drawing.Size]::new(320, 20)

  $txt = [System.Windows.Forms.TextBox]::new()
  $txt.Location = [System.Drawing.Point]::new(16, 40)
  $txt.Size = [System.Drawing.Size]::new(240, 24)

  $btnSearch = [System.Windows.Forms.Button]::new()
  $btnSearch.Text = "Search"
  $btnSearch.Location = [System.Drawing.Point]::new(264, 38)
  $btnSearch.Size = [System.Drawing.Size]::new(74, 28)
  $btnSearch.DialogResult = [System.Windows.Forms.DialogResult]::OK

  $form.AcceptButton = $btnSearch
  $form.Controls.AddRange(@($lbl, $txt, $btnSearch))

  try { $dlgResult = $form.ShowDialog() } finally { $form.Dispose() }
  if ($dlgResult -ne [System.Windows.Forms.DialogResult]::OK) { return $null }
  $term = $txt.Text.Trim()
  if ([string]::IsNullOrWhiteSpace($term)) { return $null }
  return $term
}

function Get-RecentDeals([string]$baseUrl, [string]$authHeader) {
  $uri = "$baseUrl/api/external/v1/deals?limit=100"
  $response = Invoke-RestMethod -Uri $uri -Method Get `
    -Headers @{ Authorization = $authHeader }
  return @($response.data.deals)
}

function Get-DealsBySearch([string]$baseUrl, [string]$authHeader, [string]$searchTerm) {
  $encoded = [System.Uri]::EscapeDataString($searchTerm)
  $uri = "$baseUrl/api/external/v1/deals?search=$encoded&limit=100"
  $response = Invoke-RestMethod -Uri $uri -Method Get `
    -Headers @{ Authorization = $authHeader }
  return @($response.data.deals)
}

function Show-DealPicker([array]$deals) {
  if ($null -eq $deals -or $deals.Count -eq 0) { return $null }

  $gridItems = $deals | ForEach-Object {
    [PSCustomObject]@{
      ID      = $_.counterId
      Name    = $_.dealName
      Address = $_.address
      City    = $_.city
      State   = $_.state
      Zip     = $_.zip
      Units   = $_.unitCount
    }
  }

  return ($gridItems | Out-GridView -Title "Select a Deal - redIQ" -OutputMode Single)
}

function Show-CreateDealForm {
  Add-Type -AssemblyName System.Windows.Forms | Out-Null
  Add-Type -AssemblyName System.Drawing | Out-Null

  $form = [System.Windows.Forms.Form]::new()
  $form.Text = "Create New Deal - redIQ"
  $form.Size = [System.Drawing.Size]::new(390, 330)
  $form.StartPosition = "CenterScreen"
  $form.FormBorderStyle = "FixedDialog"
  $form.MaximizeBox = $false
  $form.MinimizeBox = $false

  $fieldDefs = [ordered]@{
    "dealName"  = "Deal Name"
    "address"   = "Address"
    "city"      = "City"
    "state"     = "State"
    "zip"       = "Zip"
    "unitCount" = "Unit Count"
  }

  $inputs = @{}
  $y = 16
  foreach ($key in $fieldDefs.Keys) {
    $lbl = [System.Windows.Forms.Label]::new()
    $lbl.Text = "$($fieldDefs[$key]) *"
    $lbl.Location = [System.Drawing.Point]::new(16, ($y + 2))
    $lbl.Size = [System.Drawing.Size]::new(110, 20)

    $txt = [System.Windows.Forms.TextBox]::new()
    $txt.Location = [System.Drawing.Point]::new(132, $y)
    $txt.Size = [System.Drawing.Size]::new(224, 24)
    $inputs[$key] = $txt

    $form.Controls.AddRange(@($lbl, $txt))
    $y += 34
  }

  $errLabel = [System.Windows.Forms.Label]::new()
  $errLabel.ForeColor = [System.Drawing.Color]::Red
  $errLabel.Location = [System.Drawing.Point]::new(16, $y)
  $errLabel.Size = [System.Drawing.Size]::new(348, 20)
  $form.Controls.Add($errLabel)
  $y += 28

  $btnCreate = [System.Windows.Forms.Button]::new()
  $btnCreate.Text = "Create"
  $btnCreate.Location = [System.Drawing.Point]::new(132, $y)
  $btnCreate.Size = [System.Drawing.Size]::new(104, 30)

  $btnCancel = [System.Windows.Forms.Button]::new()
  $btnCancel.Text = "Cancel"
  $btnCancel.Location = [System.Drawing.Point]::new(252, $y)
  $btnCancel.Size = [System.Drawing.Size]::new(104, 30)
  $btnCancel.DialogResult = [System.Windows.Forms.DialogResult]::Cancel
  $form.CancelButton = $btnCancel

  $script:formResult = $null

  $btnCreate.Add_Click({
    # Validate all fields present
    foreach ($k in $inputs.Keys) {
      if ([string]::IsNullOrWhiteSpace($inputs[$k].Text)) {
        $errLabel.Text = "All fields are required."
        return
      }
    }
    # Validate unitCount is a positive integer
    $ucInt = 0
    if (-not [int]::TryParse($inputs["unitCount"].Text.Trim(), [ref]$ucInt) -or $ucInt -le 0) {
      $errLabel.Text = "Unit Count must be a positive whole number."
      return
    }
    $script:formResult = [PSCustomObject]@{
      dealName  = $inputs["dealName"].Text.Trim()
      address   = $inputs["address"].Text.Trim()
      city      = $inputs["city"].Text.Trim()
      state     = $inputs["state"].Text.Trim()
      zip       = $inputs["zip"].Text.Trim()
      unitCount = $ucInt
    }
    $form.Close()
  })

  $form.AcceptButton = $btnCreate
  $form.Controls.AddRange(@($btnCreate, $btnCancel))
  try { $form.ShowDialog() | Out-Null } finally { $form.Dispose() }
  return $script:formResult
}

function Invoke-CreateDeal([PSCustomObject]$dealData, [string]$baseUrl, [string]$authHeader) {
  $uri  = "$baseUrl/api/external/v1/deals"
  $body = $dealData | ConvertTo-Json -Compress
  $response = Invoke-RestMethod -Uri $uri -Method Post `
    -Headers @{ Authorization = $authHeader } `
    -ContentType "application/json" `
    -Body $body
  return $response.data.counterId
}

function Resolve-DealId([string]$baseUrl, [string]$authHeader) {
  while ($true) {
    $choice = Show-DealChooser

    switch ($choice) {
      "recent" {
        try {
          $deals = Get-RecentDeals -baseUrl $baseUrl -authHeader $authHeader
          if ($deals.Count -eq 0) {
            Show-Popup "redIQ" "No deals found. Try creating one first." "Warning"
            continue
          }
          $selected = Show-DealPicker -deals $deals
          if ($null -ne $selected) { return [string]$selected.ID }
          # User closed Out-GridView without selecting — loop back to chooser
        }
        catch {
          Show-Popup "redIQ Deal Error" "Could not load deals:`n$($_.Exception.Message)" "Error"
        }
      }
      "search" {
        $term = Show-SearchBox
        if ($null -eq $term) { continue }
        try {
          $deals = Get-DealsBySearch -baseUrl $baseUrl -authHeader $authHeader -searchTerm $term
          if ($deals.Count -eq 0) {
            Show-Popup "redIQ" "No deals matched '$term'.`nTry a different search term." "Warning"
            continue
          }
          $selected = Show-DealPicker -deals $deals
          if ($null -ne $selected) { return [string]$selected.ID }
        }
        catch {
          Show-Popup "redIQ Deal Error" "Search failed:`n$($_.Exception.Message)" "Error"
        }
      }
      "create" {
        $formData = Show-CreateDealForm
        if ($null -eq $formData) { continue }
        try {
          $newId = Invoke-CreateDeal -dealData $formData -baseUrl $baseUrl -authHeader $authHeader
          Log "Created deal '$($formData.dealName)' -> counterId=$newId"
          return [string]$newId
        }
        catch {
          Show-Popup "redIQ Deal Error" "Could not create deal:`n$($_.Exception.Message)" "Error"
        }
      }
      "skip"   { return $null }
      default  {
        # "cancel" - user closed chooser with X button
        Log "User cancelled at deal selection."
        exit 0
      }
    }
  }
}

# ---------- Credential + config ----------
function Initialize-CredentialManager {
  if (-not (Get-Module -ListAvailable -Name CredentialManager)) {
    throw "CredentialManager module not found. Run setup.ps1 again (it installs the module)."
  }
  if (-not (Get-Module -Name CredentialManager)) {
    Write-Host "Loading CredentialManager module, please wait..." -ForegroundColor Yellow
    Import-Module CredentialManager
  }
}

function Get-ApiKey {
  Initialize-CredentialManager
  $target = "RedIQ-RentRoll-Uploader"

  $cred = Get-StoredCredential -Target $target
  if ($null -eq $cred) {
    throw "API key not found in Windows Credential Manager (target: $target). Run setup.ps1 again."
  }

  # Convert SecureString to plain text
  $plain = [System.Net.NetworkCredential]::new('', $cred.Password).Password

  if ([string]::IsNullOrWhiteSpace($plain)) {
    throw "API key is blank in Windows Credential Manager (target: $target). Run setup.ps1 again."
  }
  return $plain
}

function Get-Config {
  $configPath = Join-Path (Join-Path $env:APPDATA "RedIQ\RentRollUploader") "config.json"
  if (!(Test-Path $configPath)) { throw "Config not found. Run setup.ps1 first." }
  return Get-Content $configPath -Raw | ConvertFrom-Json
}

# ---------- MIME helper ----------
$mimeMap = @{
  '.xlsx' = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
  '.xls'  = 'application/vnd.ms-excel'
  '.xlsm' = 'application/vnd.ms-excel.sheet.macroEnabled.12'
  '.csv'  = 'text/csv'
  '.ods'  = 'application/vnd.oasis.opendocument.spreadsheet'
}

function Get-MimeType([string]$filePath) {
  $ext = [System.IO.Path]::GetExtension($filePath).ToLower()
  if ($mimeMap.ContainsKey($ext)) { return $mimeMap[$ext] }
  return 'application/octet-stream'
}

# ---------- Main ----------
try {
  # --- Normalize and de-duplicate paths ---
  $cleanPaths = @()
  foreach ($p in $Path) {
    $p = $p.Trim().Trim('"')
    if ([string]::IsNullOrWhiteSpace($p)) { continue }
    $cleanPaths += $ExecutionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath($p)
  }
  $cleanPaths = @($cleanPaths | Select-Object -Unique)

  if ($cleanPaths.Count -eq 0) { throw "No file paths provided." }

  # --- Check existence ---
  $missingFiles = @()
  $presentFiles = @()
  foreach ($p in $cleanPaths) {
    if (Test-Path $p -PathType Leaf) { $presentFiles += $p }
    else { $missingFiles += $p }
  }

  if ($missingFiles.Count -gt 0) {
    Log "Missing files: $($missingFiles -join '; ')"
  }
  if ($presentFiles.Count -eq 0) { throw "None of the specified files were found." }

  # --- Validate extensions ---
  $validFiles   = @()
  $skippedFiles = @()
  foreach ($p in $presentFiles) {
    $ext = [System.IO.Path]::GetExtension($p).ToLower()
    if ($allowedExtensions -contains $ext) { $validFiles += $p }
    else { $skippedFiles += $p }
  }

  if ($skippedFiles.Count -gt 0) {
    Log "Skipped (unsupported extension): $($skippedFiles -join '; ')"
  }

  # --- Summarize issues and prompt if any files were dropped ---
  $issues = @()
  if ($missingFiles.Count -gt 0) {
    $names = ($missingFiles | ForEach-Object { [System.IO.Path]::GetFileName($_) }) -join "`n  "
    $issues += "Not found:`n  $names"
  }
  if ($skippedFiles.Count -gt 0) {
    $names = ($skippedFiles | ForEach-Object { [System.IO.Path]::GetFileName($_) }) -join "`n  "
    $issues += "Unsupported format:`n  $names"
  }

  if ($issues.Count -gt 0) {
    if ($validFiles.Count -eq 0) {
      $msg  = "No uploadable files found.`n`n"
      $msg += ($issues -join "`n`n")
      $msg += "`n`nSupported formats: $($allowedExtensions -join ', ')"
      Show-Popup "redIQ Upload Error" $msg "Error"
      if (-not $Collect) { Read-Host "Press Enter to close" }
      exit 2
    }

    # Some valid, some not — ask user whether to proceed
    $validNames = ($validFiles | ForEach-Object { [System.IO.Path]::GetFileName($_) }) -join "`n  "
    $msg  = "Some files will be skipped:`n`n"
    $msg += ($issues -join "`n`n")
    $msg += "`n`n$($validFiles.Count) file(s) to upload:`n  $validNames"
    $msg += "`n`nSupported formats: $($allowedExtensions -join ', ')`n`nContinue with the upload?"

    $answer = Show-YesNo "redIQ Upload - File Issues" $msg
    if ($answer -ne [System.Windows.Forms.DialogResult]::Yes) {
      Log "User cancelled upload."
      exit 0
    }
  }

  # --- Enforce the 20-file API limit ---
  if ($validFiles.Count -gt $maxFiles) {
    $msg  = "You selected $($validFiles.Count) files, but the API allows a maximum of $maxFiles per upload.`n`n"
    $msg += "Only the first $maxFiles files will be submitted."
    Show-Popup "redIQ Upload Warning" $msg "Warning"
    $validFiles = @($validFiles[0..($maxFiles - 1)])
    Log "Truncated to $maxFiles files (API limit)."
  }

  # --- Config + API key ---
  $cfg    = Get-Config
  $apiKey = (Get-ApiKey).Trim()

  # Normalize common paste mistakes:
  # - user pastes "Authorization: ..."
  # - user pastes already-prefixed Bearer/ApiKey
  $apiKey = $apiKey -replace '^(?i)\s*Authorization:\s*', ''

  if ($apiKey -match '^(?i)\s*Bearer\s+') {
    $apiKey = "Bearer " + ($apiKey -replace '^(?i)\s*Bearer\s+', '').Trim()
  }
  elseif ($apiKey -match '^(?i)\s*ApiKey\s+') {
    $apiKey = "ApiKey " + ($apiKey -replace '^(?i)\s*ApiKey\s+', '').Trim()
  }
  else {
    # Keys are like riq_live_... ; default to Bearer to match common expectations
    $apiKey = "Bearer $apiKey"
  }

  $baseUrl   = ($cfg.serverBaseUrl).TrimEnd("/")
  $uploadUrl = "$baseUrl/api/external/v1/upload"

  $methods = @($cfg.notificationMethods)
  if ($methods.Count -eq 0) {
    throw "No notification methods configured. Run setup.ps1 again and set at least an email or webhook."
  }

  $notificationJson = ($methods | ConvertTo-Json -Compress)

  # --- Log upload summary ---
  Log "Uploading $($validFiles.Count) file(s) to $uploadUrl"
  Log ("Auth scheme: " + ($apiKey.Split(' ')[0]))
  if ($apiKey.Split(' ').Count -ge 2) {
    Log ("Key length: " + ($apiKey.Split(' ')[1].Length))
  }
  foreach ($f in $validFiles) {
    Log ("  File: " + [System.IO.Path]::GetFileName($f) + " | MIME: " + (Get-MimeType $f))
  }

  # ---------- Upload via .NET HttpClient ----------
  Add-Type -AssemblyName System.Net.Http

  $httpClient = [System.Net.Http.HttpClient]::new()
  $httpClient.DefaultRequestHeaders.Add("Authorization", $apiKey)

  try {
    $form = [System.Net.Http.MultipartFormDataContent]::new()

    # Add each file under the "files" field name (API accepts up to 20)
    foreach ($f in $validFiles) {
      $fName    = [System.IO.Path]::GetFileName($f)
      $fBytes   = [System.IO.File]::ReadAllBytes($f)
      $fContent = [System.Net.Http.ByteArrayContent]::new($fBytes)
      $fContent.Headers.ContentType = [System.Net.Http.Headers.MediaTypeHeaderValue]::Parse((Get-MimeType $f))
      $form.Add($fContent, "files", $fName)
    }

    # Add notification method as a plain string field
    $form.Add([System.Net.Http.StringContent]::new($notificationJson), "notificationMethod")

    Log "Sending request..."
    $response = $httpClient.PostAsync($uploadUrl, $form).Result
    $out      = $response.Content.ReadAsStringAsync().Result

    Log "HTTP status: $([int]$response.StatusCode)"
    if ($out) { Log "Response: $out" }
  }
  finally {
    $httpClient.Dispose()
  }

  # --- Parse JSON response best-effort ---
  $batchId     = $null
  $trackingUrl = $null
  $httpStatus  = [int]$response.StatusCode
  $errorMsg    = $null

  try {
    $obj = $out | ConvertFrom-Json
    $batchId     = $obj.data.batchId
    $trackingUrl = $obj.data.trackingUrl
    $errorMsg    = $obj.error.message
  } catch { }

  if ($httpStatus -ge 400) {
    $msg = "API returned an error (HTTP $httpStatus)."
    if ($errorMsg) { $msg += "`n`n$errorMsg" }
    $msg += "`n`nSee log:`n$logPath"
    Show-Popup "redIQ Upload Error" $msg "Error"
    if (-not $Collect) { Read-Host "Press Enter to close" }
    exit 3
  }

  # --- Success message ---
  $fileNames = ($validFiles | ForEach-Object { [System.IO.Path]::GetFileName($_) }) -join "`n  "
  $msg  = "Upload submitted successfully.`n`n"
  $msg += "$($validFiles.Count) file(s):`n  $fileNames"

  if ($batchId) {
    $msg += "`n`nbatchId: $batchId"
    if ($trackingUrl) {
      $msg += "`ntrackingUrl: $trackingUrl"
    } else {
      $msg += "`nstatus: $baseUrl/api/external/v1/job/$batchId/status"
    }
    $msg += "`n`nYou should receive a notification when processing completes."
  } else {
    $msg += "`n`nResponse:`n$out"
  }

  Show-Popup "redIQ Upload Submitted" $msg "Information"
  exit 0
}
catch {
  $errType  = $_.Exception.GetType().FullName
  $errMsg   = $_.Exception.Message
  $errStack = $_.ScriptStackTrace

  Log "ERROR TYPE: $errType"
  Log "ERROR MSG : $errMsg"
  if ($errStack) { Log "STACK    : $errStack" }

  Show-Popup "redIQ Upload Error" "$errMsg`n`nSee log:`n$logPath" "Error"
  if (-not $Collect) { Read-Host "Press Enter to close" }
  exit 1
}
