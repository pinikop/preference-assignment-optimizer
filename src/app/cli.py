"""CLI entry point for the Streamlit app."""

import sys
from pathlib import Path


def main() -> None:
    """Launch the Streamlit app."""
    from streamlit.web.cli import main as st_main

    # Get the path to streamlit.py relative to this file
    app_path = Path(__file__).parent / "streamlit.py"

    # Set up sys.argv for streamlit
    sys.argv = ["streamlit", "run", str(app_path), "--server.headless", "true"]
    st_main()


if __name__ == "__main__":
    main()
