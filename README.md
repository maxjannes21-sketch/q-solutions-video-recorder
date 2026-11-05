# CSV-driven Browser Automation Video Recorder

A Python + Playwright tool that reads a semicolon-delimited CSV file and records a separate WebM video for every row.

Each recording demonstrates an injected SVG cursor, a yellow pointer highlight, smooth mouse movement, human-like typing, a DuckDuckGo search, click ripples, and opening the first search result.

## Requirements

- Python 3.9+
- Chromium installed through Playwright
- No third-party Python packages other than Playwright

## Setup

```bash
python -m pip install -r requirements.txt
python -m playwright install chromium
```

On Windows, run the same commands in PowerShell from the project directory.

## Run

```bash
python capture_video.py
```

Chromium runs in visible mode because DuckDuckGo can reject headless automation with an HTTP 418 response. Browser windows open and close automatically while the rows are processed.

The script reads `input.csv` and creates the `video` directory if necessary. Each successful row produces:

```text
video/<Company Name>.webm
```

The absolute path is printed after each successful recording. A failed row returns `None`, is reported in the console, and does not prevent the remaining rows from being processed. The process exits with a non-zero status if any row fails.

A real sample recording is included: [Q Solutions](video/Q%20Solutions.webm).

## CSV format

The file must be UTF-8 with `;` as the delimiter and `"` as the quote character. The header must be:

```text
URL;Company Name;Language;Country;Postcode;City;Street;HouseNo
```

Example:

```csv
https://duckduckgo.com/;Q Solutions;en-US;Belarus;220005;Minsk;Independence Avenue;1
```

## Project structure

```text
capture_video.py          CSV validation, row loop, and process exit status
qscript.py                Browser scenario, visual effects, and video finalization
requirements.txt          Pinned Playwright dependency
input.csv                 Two sample input rows
video/Q Solutions.webm    Real sample recording
```

## Implementation notes

- Uses the Playwright synchronous API and Chromium.
- Injects the cursor and effects into every new document, including the results page after navigation.
- Uses real Playwright mouse and keyboard actions rather than synthetic DOM clicks.
- Selects a visible search submit button because the current DuckDuckGo homepage also contains a hidden one.
- Closes the browser context before moving the finalized video to its company-based filename.
- Replaces an existing recording with the same company name on a repeated run.
- Removes a partial recording when the scenario fails.

DuckDuckGo markup can change. If the scenario stops finding an element, check the selectors listed in the original task first.
