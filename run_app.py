"""Launch the local app with a Windows-compatible socket event loop."""
import asyncio
from pathlib import Path
import sys


def configure_event_loop():
    # This app has no asynchronous subprocess/pipe operations. On Windows,
    # Selector avoids the Proactor pipe shutdown callback seen on abrupt disconnects.
    # Do not suppress unrelated socket exceptions or modify the installed runtime.
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


def main():
    if sys.platform == 'win32':
        for stream in (sys.stdout, sys.stderr):
            if hasattr(stream, 'reconfigure'):
                stream.reconfigure(encoding='utf-8', errors='replace')
    configure_event_loop()
    from streamlit.web import cli
    sys.argv = ['streamlit', 'run', str(Path(__file__).with_name('app.py')), '--server.headless=true', *sys.argv[1:]]
    return cli.main()


if __name__ == '__main__':
    raise SystemExit(main())
