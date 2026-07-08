import os
from flask import Flask

base_dir = os.path.dirname(os.path.abspath(__file__))
frontend_dir = os.path.abspath(os.path.join(base_dir, "../frontend"))

app = Flask(__name__, static_url_path="", static_folder=frontend_dir)
print("static_url_path:", app.static_url_path)
print("static_folder:", app.static_folder)
print("Files in static_folder:", os.listdir(app.static_folder) if os.path.exists(app.static_folder) else "Not Found")
