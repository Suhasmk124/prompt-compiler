# Windows startup and widget warnings

## Preset picker warning

The app previously seeded `preset_picker` in session state and also passed `index=1` to the select box. Streamlit reports the competing initial values as a warning with a stack trace. It was not a workflow execution failure.

The picker now uses session state as its single initial-value source and passes `index=None`. The warning is addressed at its source, not hidden through logging settings.

Official reference: https://docs.streamlit.io/develop/api-reference/caching-and-state/st.session_state

## ConnectionResetError WinError 10054

The reported traceback occurs in Windows Proactor transport shutdown after the remote peer has closed the socket. The trace does not establish exactly why the peer closed; a browser refresh/disconnect is one plausible cause. It is separate from the widget warning and does not establish a model/API failure.

Use the project launcher:

```powershell
cd "C:\Sauce\PEGAI\Prompt Compiler"
.\.venv\Scripts\python.exe run_app.py
```

`run_app.py` configures the Windows Selector event-loop policy before starting Streamlit, avoiding the Proactor callback path. `start.ps1` uses the same launcher. Running Streamlit directly bypasses the mitigation.

This application does not use asynchronous subprocesses or pipes, which the Windows Selector loop does not support. Revisit this choice if those features are introduced. The launcher does not silence arbitrary exceptions or patch installed Python/Streamlit files.

Official reference: https://docs.python.org/3.11/library/asyncio-platforms.html

Policy selection is checked without starting the app. A browser disconnect has not been reproduced or browser-tested by the coding agent; the project owner verifies normal UI behavior.
