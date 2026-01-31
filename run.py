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
    if not api_key or api_key == 'your-api-key-here':
        print("\n⚠️  ANTHROPIC_API_KEY not set!")
        print("   Edit your .env file and add your API key.")
        print("   Get one at: https://console.anthropic.com/")
        sys.exit(1)

    # Check dependencies
    try:
        import flask
        import anthropic
        import yfinance
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
    print("  Open: http://localhost:5000")
    print("  Press Ctrl+C to stop\n")

    # Import and run
    from app import app
    app.run(debug=True, port=5000, use_reloader=False)


if __name__ == '__main__':
    main()
