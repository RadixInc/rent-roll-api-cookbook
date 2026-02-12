# Windows "Send To" Script

Upload rent roll files to the Radix API by right-clicking them in Windows Explorer.

## Setup

1. Open `send-to-radix.bat` in a text editor (e.g. Notepad).
2. Replace the placeholder values at the top:
   ```bat
   set "API_KEY=riq_live_your_actual_key"
   set "NOTIFY_EMAIL=you@company.com"
   ```
3. Press **Win + R**, type `shell:sendto`, and press Enter.
4. Copy `send-to-radix.bat` (or a shortcut to it) into the **SendTo** folder that opens.

## Usage

1. Select one or more `.xlsx`, `.xls`, or `.csv` files in File Explorer.
2. Right-click the selection.
3. Choose **Send to** > **send-to-radix**.
4. A command prompt window will show the upload progress and API response.
5. You will receive an email notification when processing is complete.

You can also drag files directly onto the `.bat` file.

## Requirements

- Windows 10 or later (curl is included by default)
- No additional software required

## Troubleshooting

| Problem                         | Solution                                                  |
| ------------------------------- | --------------------------------------------------------- |
| "Please edit this script..."    | Open the `.bat` file and set your `API_KEY`               |
| "curl is not recognized"        | Upgrade to Windows 10 1803+ or install curl manually      |
| HTTP 401                        | Check that your API key is correct and not revoked         |
| HTTP 403                        | Your account may not have API access or credits remaining  |


