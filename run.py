#!/usr/bin/env python3
"""
Quick start script for The Pill
Run with: python run.py
"""

import os
import sys
import subprocess


def main():
    # Check for .env file
    if not os.path.exists('.env'):
        print("\n⚠️  No .env file found!")
        print("   Creating from .env.example...")

        if os.path.exists('.env.example'):
            with open('.env.example', 'r') as f:
                template = f.read()
            with open('.env', 'w') as f:
                f.write(template)
            print("   Created .env file. Please add your ANTHROPIC_API_KEY")
            print("\n   Edit .env and add your API key, then run again.")
            sys.exit(1)
        else:
            print("   ERROR: .env.example not found!")
            sys.exit(1)

    # Check for API key
    from dotenv import load_dotenv
    load_dotenv()

    api_key = os.getenv('ANTHROPIC_API_KEY')
    finnhub_key = os.getenv('FINNHUB_API_KEY')
    if (not api_key or api_key == 'your-api-key-here') and (not finnhub_key or finnhub_key == 'your-finnhub-api-key-here'):
        print("\n  Note: No API keys found. Running in degraded mode.")
        print("        - AI analysis will use a structured fallback")
        print("        - Real-time prices will use Yahoo Finance")
        print("        Add keys to .env for full features.")
    elif not api_key or api_key == 'your-api-key-here':
        print("\n  Note: ANTHROPIC_API_KEY not set.")
        print("        AI analysis will use a structured fallback.")
    elif not finnhub_key or finnhub_key == 'your-finnhub-api-key-here':
        print("\n  Note: FINNHUB_API_KEY not set.")
        print("        Real-time prices will use Yahoo Finance.")

    # Check dependencies
    try:
        import flask      # noqa: F401
        import anthropic  # noqa: F401
        import yfinance   # noqa: F401
    except ImportError as e:
        print(f"\n⚠️  Missing dependency: {e}")
        print("   Installing requirements...")
        subprocess.check_call(
            [sys.executable, '-m', 'pip', 'install', '-r', 'requirements.txt'])

    # Run the app
    print("\n" + "="*50)
    print("  💊 THE PILL - Shkreli Method Stock Analysis")
    print("="*50)
    print("\n  Starting server...")
    print("  Open: http://localhost:8080")
    print("  Press Ctrl+C to stop\n")

    # Import and run
    from app import app
    app.run(debug=True, host="0.0.0.0", port=8080, use_reloader=False, threaded=True)


if __name__ == '__main__':
    main()
