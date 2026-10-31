# Import controls, background generation and recovery

## Explicit import choices

Under **Column types & missing values**, select a file and choose Auto, Text/identifier, Number,
Yes/no, or one of the three explicit date formats for each column. Apply the settings before
generating a plan. Preview, model metadata and local execution use the same choices.

- Text retains leading zeros and literal identifiers.
- Number converts numeric cells and rejects nonnumeric or infinite values.
- Yes/no accepts true/false, yes/no and 1/0; missing values remain missing.
- Dates use YYYY-MM-DD, DD/MM/YYYY or MM/DD/YYYY explicitly. Ambiguous dates are not guessed.
- Empty cells are missing. NA, N/A, NULL, None and '-' stay literal unless selected as markers.
- Invalid settings leave the original preview and type editor available so they can be corrected.
- Raw uploaded bytes remain unchanged and can be downloaded separately.

Changing import settings invalidates the prior plan/result; it never regenerates a plan automatically.
**Save import settings** produces a JSON map keyed by filename. The run audit includes this map.
For saved-plan execution from the terminal:

```powershell
.\.venv\Scripts\python.exe -m prompt_compiler workflow.json --inputs inputs --output outputs --import-settings import_settings.json
```

## Responsive generation

Generate plan starts a session-owned background job. A fragment polls status without repeatedly
rebuilding the whole page. Progress describes real phases: planning, generation, meaning review,
or provider retry wait. No fabricated percentage is shown.

The task and input controls are locked while that job is active. Cancel stops future requests and
discards a returned result; a request already sent cannot be remotely undone and may still count
against quota. An active network call can take up to the configured 45-second timeout to return.
Starting a new workspace or changing generation inputs invalidates/cancels an obsolete job.

No worker thread reads or writes Streamlit session state. A finished result is installed only if its
input/settings fingerprint still matches. No API request starts on app launch or from a preview.

## Rate limits

The interactive provider permits one retry after HTTP 429. Retry-After seconds or HTTP-date is
respected, with a maximum automatic wait of 90 seconds. Longer requested waits are reported instead
of ignored. The wait is cancelable. Without a usable header, the bounded default wait is five seconds.
After the retry limit, the task and uploads remain available; the user need not re-enter the request.

The provider counts physical request attempts, including a rate-limit retry. Compilation/audit uses
that count. Provider attempts are different from correction attempts; neither implies a billable
success. No account upgrade, alternate model or unlimited retry loop is used.

Evaluation defaults to no automatic rate retries so quota failures are visible in its measurements.

## Reports

Multiple exported reports have a selector, so the preview is tied to an actual export rather than
implicitly displaying whichever table happened to be last. Session snapshots include the report
name and are retained within the existing five-snapshot/20 MB limits. Comparisons use the selected
report and allow the user to choose the previous report explicitly.

Preview/inventory caches are session-local and bounded. They are cleared when inputs are replaced
or cleared. They make no model calls and do not write uploaded data to disk.
