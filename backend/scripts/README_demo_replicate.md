# Replication Demo — README

Purpose
- Quick guide to demonstrate event replication between two running servers using the provided PowerShell script `scripts/demo_replicate.ps1`.

Prerequisites
- Python environment: activate the project's virtual environment:

```powershell
.\.venv\Scripts\Activate.ps1
```

- Two backend instances (FastAPI + uvicorn) running on different ports.
- PowerShell (Windows). `curl.exe` is preferred but not required — the script falls back to `Invoke-WebRequest`.

Start two servers (example)
- Open two PowerShell terminals.
- Server A (source, events provider):

```powershell
$env:APP_DATA_DIR = "C:\tmp\notes_data_A"
uvicorn app.main:app --reload --port 8000
```

- Server B (destination, receiver):

```powershell
$env:APP_DATA_DIR = "C:\tmp\notes_data_B"
uvicorn app.main:app --reload --port 8001
```

Run the replication demo
- From the repository `backend` folder, run:

```powershell
.\scripts\demo_replicate.ps1 -SourceUrl http://127.0.0.1:8000 -DestUrl http://127.0.0.1:8001 -UserId userA
```

Expected output summary
- `Found N event(s)` — number of events fetched from source.
- `Wrote events array to ... (bytes: ...)` — shows size of the prepared JSON file.
- `Apply response: {"applied": X}` — number of events applied on the destination (X may be 0 if already applied).

Manual verification
- List notes on destination for `userA`:

```powershell
Invoke-RestMethod -Uri "http://127.0.0.1:8001/notes" -Headers @{ "X-User-Id" = "userA" }
```

- Fetch a specific note (use an actual `note_id` from the list):

```powershell
Invoke-RestMethod -Uri "http://127.0.0.1:8001/notes/<note_id>" -Headers @{ "X-User-Id" = "userA" }
```

Troubleshooting
- If the script prints `Temporary events file is empty` or `Invalid JSON`:
  - Confirm Server A is reachable and returns JSON:

```powershell
curl.exe -v "http://127.0.0.1:8000/replicate/events?user_id=userA" -o raw_events.json
Get-Item raw_events.json | Select-Object Name,Length
Get-Content -Raw -Encoding utf8 raw_events.json | Select-Object -First 1
```

  - Manually POST the saved file to server B to verify it accepts the payload:

```powershell
curl.exe -v -X POST "http://127.0.0.1:8001/replicate/events" -H "Content-Type: application/json" --data-binary "@raw_events.json"
```

  - If `curl` isn't available, use PowerShell:

```powershell
Invoke-WebRequest -Uri "http://127.0.0.1:8000/replicate/events?user_id=userA" -OutFile raw_events.json -UseBasicParsing
Invoke-WebRequest -Uri "http://127.0.0.1:8001/replicate/events" -Method Post -InFile .\raw_events.json -ContentType "application/json" -UseBasicParsing -OutFile post_response.txt
Get-Content -Raw post_response.txt
```

  - Common cause: temporary file contained only a UTF-8 BOM (3 bytes) or was written incorrectly. The current script includes fallbacks: it fetches raw JSON, extracts the JSON array textually, writes the file with .NET writer, and prefers `curl.exe` for uploads.

- The demo uses a simple pull/push approach and the destination.