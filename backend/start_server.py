#!/usr/bin/env python
"""Convenience script to start the FinAlly backend server."""

import subprocess
import sys


def main():
    """Start the uvicorn server."""
    print("=" * 60)
    print("  FinAlly Backend - Starting Server")
    print("=" * 60)
    print()
    print("Server will start on: http://localhost:8000")
    print("API docs available at: http://localhost:8000/docs")
    print()
    print("Press Ctrl+C to stop the server")
    print("=" * 60)
    print()

    try:
        subprocess.run(
            [sys.executable, "-m", "uvicorn", "app.main:app", "--reload", "--host", "0.0.0.0", "--port", "8000"],
            check=True,
        )
    except KeyboardInterrupt:
        print("\n" + "=" * 60)
        print("  Server stopped")
        print("=" * 60)
    except subprocess.CalledProcessError as e:
        print(f"\nError starting server: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
