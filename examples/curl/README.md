# cURL Example

A shell-based CLI example for the RedIQ external API using `curl` and `jq`.

## Prerequisites

- [curl](https://curl.se/)
- [jq](https://jqlang.github.io/jq/download/)
- Bash

Windows users: this example is a Bash script (`upload.sh`), so run it from one of these environments (reccomended):

- [Git Bash](https://gitforwindows.org/)
- [WSL](https://learn.microsoft.com/windows/wsl/install)

## Setup

macOS / Linux:

```bash
export RADIX_API_KEY="riq_live_your_api_key_here"
export RADIX_API_URL="https://connect.rediq.io" # optional
chmod +x upload.sh
```

Windows PowerShell:

```powershell
$env:RADIX_API_KEY = "riq_live_your_api_key_here"
$env:RADIX_API_URL = "https://connect.rediq.io" # optional
bash ./upload.sh --help
```

Windows Command Prompt:

```bat
set RADIX_API_KEY=riq_live_your_api_key_here
set RADIX_API_URL=https://connect.rediq.io
bash .\upload.sh --help
```

If you are using Git Bash or WSL, you can also use the macOS / Linux commands directly.

## Commands

macOS / Linux, Git Bash, or WSL:

```bash
# Upload and poll
./upload.sh upload --email user@example.com rent-roll.xlsx

# Upload with webhook only
./upload.sh upload --webhook https://hooks.example.com/rent-roll rent-roll.xlsx

# Upload and attach the batch to a deal
./upload.sh upload --email user@example.com --deal-id 42 file1.xlsx file2.xlsx

# Upload only, skip polling
./upload.sh upload --email user@example.com --no-poll rent-roll.xlsx

# Check status for an existing batch
./upload.sh status 6af30011-af82-4425-a1ad-406db4b0995c

# Deals CRUD
./upload.sh deals create --deal-name "Sunset Plaza Apartments" --city Austin --state TX --unit-count 128
./upload.sh deals list --search Sunset
./upload.sh deals get 42
./upload.sh deals update 42 --deal-name "Sunset Plaza Phase II" --unit-count 132
./upload.sh deals delete 42
```

Windows PowerShell or Command Prompt:

```powershell
# Upload and poll
bash ./upload.sh upload --email user@example.com rent-roll.xlsx

# Upload with webhook only
bash ./upload.sh upload --webhook https://hooks.example.com/rent-roll rent-roll.xlsx

# Upload and attach the batch to a deal
bash ./upload.sh upload --email user@example.com --deal-id 42 file1.xlsx file2.xlsx

# Upload only, skip polling
bash ./upload.sh upload --email user@example.com --no-poll rent-roll.xlsx

# Check status for an existing batch
bash ./upload.sh status 6af30011-af82-4425-a1ad-406db4b0995c

# Deals CRUD
bash ./upload.sh deals create --deal-name "Sunset Plaza Apartments" --city Austin --state TX --unit-count 128
bash ./upload.sh deals list --search Sunset
bash ./upload.sh deals get 42
bash ./upload.sh deals update 42 --deal-name "Sunset Plaza Phase II" --unit-count 132
bash ./upload.sh deals delete 42
```

## Notes

- Upload requires at least one notification target: `--email`, `--webhook`, or both.
- Only one `--deal-id` can be attached to each upload request, so every file in that batch maps to the same deal.
- Batch polling uses the API batch status directly and surfaces `partially complete` as a non-success terminal state.
- On Windows, invoke the script with `bash ./upload.sh ...` unless you are already inside Git Bash or WSL.

## Output

Typical upload output:

```text
Uploading 2 file(s)...

Upload successful.
  Batch ID:       6af30011-af82-4425-a1ad-406db4b0995c
  Files uploaded: 2
  Tracking URL:   https://connect.rediq.io/api/external/v1/job/6af30011-af82-4425-a1ad-406db4b0995c/status
  Deal ID:        42
```
