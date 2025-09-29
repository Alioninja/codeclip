#!/usr/bin/env python3
"""
Launcher for the Codebase to Clipboard Web Application
"""

if __name__ == '__main__':
    try:
        from app import app, open_browser
        from threading import Timer
        import webbrowser
        import socket

        def probe_host_port(host, port, timeout=1.0):
            """Try to bind a temporary socket to host:port to check availability and permissions."""
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(timeout)
            try:
                # Allow immediate reuse on some platforms
                s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                s.bind((host, port))
                s.listen(1)
                s.close()
                return True, None
            except Exception as e:
                try:
                    s.close()
                except Exception:
                    pass
                return False, e

        hosts_to_try = ['127.0.0.1', 'localhost', '0.0.0.0']
        ports_to_try = list(range(5000, 5011))  # try 5000..5010
        # If those are blocked (common on some Windows setups due to URLACL or AV),
        # try a high ephemeral range as a fallback.
        ports_to_try.extend(list(range(55000, 55011)))  # try 55000..55010

        selected = None
        probe_errors = []
        for host in hosts_to_try:
            for port in ports_to_try:
                ok, err = probe_host_port(host, port)
                if ok:
                    selected = (host, port)
                    break
                else:
                    probe_errors.append((host, port, err))
            if selected:
                break

        if not selected:
            print(
                "Error: Unable to bind to any tried host/port (127.0.0.1:5000..5010 and 55000..55010).")
            print("Common causes: another process is using the port, a firewall/AV is blocking socket binds, or a URL reservation (HTTP.sys) requires elevated permissions.")
            print("Helpful checks:")
            print(
                " - Run 'netstat -ano | findstr :5000' to see if a process is listening on port 5000")
            print(
                " - Run an elevated PowerShell and 'netsh http show urlacl' to see URL reservations")
            print(
                " - Try running this script as Administrator to see if permission issues go away")
            print("Detailed probe errors (first 5):")
            for h, p, e in probe_errors[:5]:
                print(f"  {h}:{p} -> {repr(e)}")
            print(
                '\nYou can run the bundled diagnostic script: python diagnose_socket.py')
            raise RuntimeError('No available host/port to bind')

        host, port = selected

        url_host = host if host != '0.0.0.0' else '127.0.0.1'
        url = f'http://{url_host}:{port}'

        # Open browser after a short delay
        Timer(1.5, lambda: webbrowser.open(url)).start()

        print("Starting Codebase to Clipboard Web Application...")
        print(f"Open your browser to: {url}")
        print("The application will open automatically in a moment.")
        print("Press Ctrl+C to stop the server")

        app.run(debug=False, host=host, port=port, threaded=True)

    except ImportError as e:
        print(f"Missing dependencies: {e}")
        print("Please install requirements with: pip install -r requirements.txt")
    except Exception as e:
        print(f"Error starting application: {e}")
        import traceback
        traceback.print_exc()
