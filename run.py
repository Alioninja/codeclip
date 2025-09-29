#!/usr/bin/env python3
"""
Launcher for the Codebase to Clipboard Web Application
"""

if __name__ == '__main__':
    try:
        from app import app, open_browser
        from threading import Timer
        import webbrowser

        # Open browser after a short delay
        Timer(1.5, lambda: webbrowser.open('http://127.0.0.1:5000')).start()

        print("Starting Codebase to Clipboard Web Application...")
        print("Open your browser to: http://127.0.0.1:5000")
        print("The application will open automatically in a moment.")
        print("Press Ctrl+C to stop the server")

        app.run(debug=False, host='127.0.0.1', port=5000, threaded=True)

    except ImportError as e:
        print(f"Missing dependencies: {e}")
        print("Please install requirements with: pip install -r requirements.txt")
    except Exception as e:
        print(f"Error starting application: {e}")
        import traceback
        traceback.print_exc()
