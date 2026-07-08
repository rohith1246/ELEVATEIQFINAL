import os
import sys

# Perform gevent monkey patching before importing any other modules
if os.getenv("USE_GEVENT", "true").lower() == "true":
    try:
        from gevent import monkey
        monkey.patch_all()
        try:
            from psycogreen.gevent import patch_psycopg
            patch_psycopg()
            print(" * gevent and psycogreen active: Database calls are now cooperative.")
        except ImportError:
            print(" * gevent active (psycogreen missing: DB calls are blocking).")
    except ImportError:
        print(" * gevent not installed. Running in multi-threaded fallback mode...")

from elevateiq_app import create_app

app = create_app()

if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    is_debug = os.getenv("FLASK_ENV") == "development"

    import socket
    def get_local_ip():
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            # Doesn't need to be reachable, just triggers local IP routing
            s.connect(('10.255.255.255', 1))
            IP = s.getsockname()[0]
        except Exception:
            IP = '127.0.0.1'
        finally:
            s.close()
        return IP

    local_ip = get_local_ip()
    print("\n" + "="*60)
    print(" * ElevateIQ Server Running Live on Local Network!")
    print(f" * Local Access:        http://localhost:{port}")
    print(f" * Wi-Fi/LAN Access:    http://{local_ip}:{port}")
    print("="*60 + "\n")

    try:
        from gevent.pywsgi import WSGIServer
        print(" * Starting WSGI server in high-performance asynchronous mode (gevent)...")
        server = WSGIServer(('0.0.0.0', port), app)
        server.serve_forever()
    except ImportError:
        print(" * Starting WSGI server in multi-threaded development mode...")
        app.run(host="0.0.0.0", port=port, threaded=True, debug=is_debug)
