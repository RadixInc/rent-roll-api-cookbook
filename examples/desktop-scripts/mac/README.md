# macOS Quick Action Script

Upload rent roll files to the Radix API by right-clicking them in Finder.

## Setup (Quick Action)

1. Open `send-to-radix.sh` in a text editor and set your values:
   ```bash
   API_KEY="riq_live_your_actual_key"
   NOTIFY_EMAIL="you@company.com"
   ```
2. Open **Automator** (Applications > Automator).
3. Create a **New Document** > choose **Quick Action**.
4. Set **"Workflow receives"** to **files or folders** in **Finder**.
5. Drag a **"Run Shell Script"** action into the workflow.
6. Set **"Pass input"** to **as arguments**.
7. Paste the contents of `send-to-radix.sh` into the script area.
8. Save as **"Send to Radix"**.

## Usage

1. Select one or more `.xlsx`, `.xls`, or `.csv` files in Finder.
2. Right-click the selection.
3. Choose **Quick Actions** > **Send to Radix**.
4. A notification will confirm the upload result.

You can also run the script directly from Terminal:

```bash
chmod +x send-to-radix.sh
./send-to-radix.sh rent-roll.xlsx another-file.xlsx
```

## Requirements

- macOS 10.14+ (Mojave or later for Quick Actions)
- curl (pre-installed on macOS)
- Optional: [jq](https://jqlang.github.io/jq/) for formatted JSON output

## Troubleshooting

| Problem                         | Solution                                                  |
| ------------------------------- | --------------------------------------------------------- |
| "Please edit this script..."    | Open the script and set your `API_KEY`                    |
| Permission denied               | Run `chmod +x send-to-radix.sh`                           |
| HTTP 401                        | Check that your API key is correct and not revoked         |
| HTTP 403                        | Your account may not have API access or credits remaining  |
| Quick Action not showing        | Restart Finder or check System Preferences > Extensions    |


