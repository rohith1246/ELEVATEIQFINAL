import os
from elevateiq_app import create_app

app = create_app()

if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    is_debug = os.getenv("FLASK_ENV") != "production"
    app.run(debug=is_debug, port=port)
