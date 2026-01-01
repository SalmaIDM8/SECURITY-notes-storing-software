param(
    [string]$SourceUrl = "http://127.0.0.1:8000",
    [string]$DestUrl = "http://127.0.0.1:8001",
    [string]$UserId = "userA"
)

Write-Host "Fetching events for user '$UserId' from $SourceUrl"

# We'll fetch the raw JSON response directly into a temp file to avoid ConvertTo-Json edge cases.
$temp = Join-Path -Path $env:TEMP -ChildPath ("events_{0}.json" -f $UserId)
$sourceUrlWithQuery = "$SourceUrl/replicate/events?user_id=$UserId"

# Prefer curl.exe for raw GET if available
$curlCmd = Get-Command curl.exe -ErrorAction SilentlyContinue
if ($null -ne $curlCmd) {
    try {
        & curl.exe -s -X GET "$sourceUrlWithQuery" -o "$temp"
    } catch {
        Write-Warning ("curl GET failed: {0}" -f $_.Exception.Message)
    }
} else {
    try {
        Invoke-WebRequest -Uri $sourceUrlWithQuery -Method Get -OutFile $temp -UseBasicParsing
    } catch {
        Write-Error ("Failed to GET events from {0}: {1}" -f $SourceUrl, $_.Exception.Message)
        exit 1
    }
}

# Quick sanity checks
try { $fi = Get-Item -Path $temp -ErrorAction Stop } catch { Write-Error ("Temporary events file not found: {0}" -f $temp); exit 1 }
if ($fi.Length -eq 0) { Write-Error ("Temporary events file is empty: {0}" -f $temp); exit 1 }

# Load and normalize the JSON shape: accept either { value: [...] } or [...]
try {
    # Read raw bytes and turn into UTF8 string (preserve any BOM)
    $bytes = [System.IO.File]::ReadAllBytes($temp)
    if ($bytes.Length -eq 0) {
        Write-Error ("Events file is empty after download: {0}" -f $temp)
        exit 1
    }
    # Detect BOM-only files (EF BB BF) which appear as 3 bytes but no content
    if ($bytes.Length -eq 3 -and $bytes[0] -eq 0xEF -and $bytes[1] -eq 0xBB -and $bytes[2] -eq 0xBF) {
        Write-Error ("Events file contains only a UTF-8 BOM (no JSON payload): {0}" -f $temp)
        exit 1
    }
    $rawText = [System.Text.Encoding]::UTF8.GetString($bytes)
    # Strip any leading BOM char if present
    $rawText = $rawText.TrimStart([char]0xFEFF)
    # Do textual normalization: extract JSON array between first '[' and last ']' if present,
    # otherwise require rawText to begin with '['.
    $trim = $rawText.Trim()
    $arrText = $null
    $firstIdx = $trim.IndexOf('[')
    $lastIdx = $trim.LastIndexOf(']')
    if ($firstIdx -ge 0 -and $lastIdx -gt $firstIdx) {
        $arrText = $trim.Substring($firstIdx, $lastIdx - $firstIdx + 1)
    } elseif ($trim.StartsWith('[')) {
        $arrText = $trim
    } else {
        # Not an array; attempt to see if it's an object with a 'value' field using a light parse
        try {
            $tmp = $trim | ConvertFrom-Json -ErrorAction Stop
            if ($null -ne $tmp.value) {
                # convert the value to string (it may already be an array); use ConvertTo-Json but keep raw as fallback
                $arrText = ($tmp.value | ConvertTo-Json -Depth 12)
            }
        } catch {
            # fall through
        }
    }
    if (-not $arrText) {
        throw [System.Exception] "Could not find JSON array in response"
    }
    # Validate arrText parses as JSON array
    $parsed = $arrText | ConvertFrom-Json -ErrorAction Stop
} catch {
    Write-Error ("Events file does not contain valid JSON: {0}" -f $_.Exception.Message)
    Write-Host "--- File contents start (raw bytes hex) ---"
    [System.IO.File]::ReadAllBytes($temp) | ForEach-Object { '{0:X2}' -f $_ } -join ' ' | Write-Host
    Write-Host "--- File contents end ---"
    Write-Host "Raw text (first 1000 chars):"
    if ($rawText) { $rawText.Substring(0, [math]::Min(1000, $rawText.Length)) | Write-Host }
    exit 1
}

if ($null -ne $parsed.value) {
    $events = $parsed.value
} elseif ($parsed -is [System.Array]) {
    $events = $parsed
} else {
    $events = @($parsed)
}

$count = 0
if ($null -ne $events) { $count = $events.Count }
Write-Host "Found $count event(s)"

if ($count -eq 0) {
    Write-Host "No events to replicate for user $UserId. Exiting."
    exit 0
}

# Write the already-extracted array text directly to the temp file (avoid ConvertTo-Json re-serialization)
try {
    if (-not $arrText) { throw [System.Exception] "No array text available to write" }
    [System.IO.File]::WriteAllText($temp, $arrText, [System.Text.Encoding]::UTF8)
    $fi = Get-Item -Path $temp -ErrorAction Stop
    Write-Host "Wrote events array to $temp (bytes: $($fi.Length))"
    # show a short preview for debugging
    $preview = $arrText.Substring(0, [math]::Min(200, $arrText.Length))
    Write-Host "Preview (first 200 chars): $preview"
} catch {
    Write-Error ("Failed to write normalized events file: {0}" -f $_.Exception.Message)
    exit 1
}

Write-Host "Posting events to $DestUrl"

# Quick validation: ensure file is non-empty and contains valid JSON
try {
    $fi = Get-Item -Path $temp -ErrorAction Stop
} catch {
    Write-Error ("Temporary events file not found: {0}" -f $temp)
    exit 1
}
if ($fi.Length -eq 0) {
    Write-Error ("Temporary events file is empty: {0}" -f $temp)
    exit 1
}
try {
    $raw = Get-Content -Raw -Encoding utf8 $temp
    $null = $raw | ConvertFrom-Json -ErrorAction Stop
} catch {
    Write-Error ("Events file does not contain valid JSON: {0}" -f $_.Exception.Message)
    Write-Host "--- File contents start ---"
    Get-Content -Raw -Encoding utf8 $temp | Write-Host
    Write-Host "--- File contents end ---"
    exit 1
}

# Prefer curl.exe for exact binary file upload if available (avoids PowerShell JSON wrapping issues)
$curlCmd = Get-Command curl.exe -ErrorAction SilentlyContinue
if ($null -ne $curlCmd) {
    try {
        $curlArgs = @("-s", "-X", "POST", "$DestUrl/replicate/events", "-H", "Content-Type: application/json", "--data-binary", "@$temp")
        $out = & curl.exe @curlArgs
        if ($LASTEXITCODE -ne 0) {
            Write-Error ("curl.exe failed with exit code {0}" -f $LASTEXITCODE)
            exit 1
        }
        # attempt to parse JSON response
        try { $apply = $out | ConvertFrom-Json; Write-Host "Apply response: $($apply | ConvertTo-Json -Depth 6)" } catch { Write-Host "Raw response: $out" }
    } catch {
        Write-Error ("curl POST to {0} failed: {1}" -f $DestUrl, $_.Exception.Message)
        exit 1
    }
} else {
    try {
        # fallback to Invoke-WebRequest using the file as the request body (sends raw bytes)
        $resp = Invoke-WebRequest -Uri "$DestUrl/replicate/events" -Method Post -InFile $temp -ContentType "application/json" -UseBasicParsing
        $outBody = $resp.Content
        try { $apply = $outBody | ConvertFrom-Json; Write-Host "Apply response: $($apply | ConvertTo-Json -Depth 6)" } catch { Write-Host "Raw response: $outBody" }
    } catch {
        # try to extract response body if available
        if ($_.Exception.Response -ne $null) {
            try {
                $respStream = $_.Exception.Response.GetResponseStream()
                $sr = New-Object System.IO.StreamReader($respStream)
                $respText = $sr.ReadToEnd(); $sr.Close()
                Write-Error ("POST to {0} failed; response: {1}" -f $DestUrl, $respText)
            } catch {
                Write-Error ("POST to {0} failed: {1}" -f $DestUrl, $_.Exception.Message)
            }
        } else {
            Write-Error ("POST to {0} failed: {1}" -f $DestUrl, $_.Exception.Message)
        }
        exit 1
    }
}

# If events contain a payload with an id, check the first note was applied on the destination
$firstWithPayload = $events | Where-Object { $_.payload } | Select-Object -First 1
if ($null -ne $firstWithPayload) {
    $nid = $firstWithPayload.payload.id
    Write-Host "Verifying note $nid exists on destination..."
    try {
        $note = Invoke-RestMethod -Uri "$DestUrl/notes/$nid" -Headers @{ "X-User-Id" = $UserId }
        Write-Host "Note found on destination:"
        $note | ConvertTo-Json -Depth 6 | Write-Host
    } catch {
        Write-Warning "Note not found on destination or access denied: $_"
    }
}

Write-Host "Replication demo finished. Events file: $temp"
