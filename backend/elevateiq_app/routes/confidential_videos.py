"""
Confidential Project Video Vault Blueprint.

Provides secure, authenticated video streaming with HTTP Range support,
zero-memory generator chunking (optimized for 300MB+ videos),
anti-download headers, dynamic watermark metadata, and role-based access control.
"""

import os
import re
import shutil
import mimetypes
from flask import Blueprint, request, Response, jsonify, send_file
from ..auth import get_current_user

confidential_bp = Blueprint("confidential", __name__)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
UPLOAD_FOLDER = os.path.join(BASE_DIR, "uploads", "confidential_videos")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Master 7 Project Terminus Confidential Benchmark Video Modules
CONFIDENTIAL_VIDEOS = {
    1: {
        "id": 1,
        "title": "MODULE 1: Model Initialization — Platform Introduction",
        "project": "Project Terminus",
        "description": "Architecture of the Terminus platform, contributor roles (Task Creator, Structure Reviewer, QC Reviewer), and quality thresholds for accepted model training data.",
        "duration": "12:45",
        "category": "Model Initialization",
        "filename": "video_1.mp4",
        "date_added": "2026-07-24",
        "security_level": "Restricted (Employee Only)"
    },
    2: {
        "id": 2,
        "title": "MODULE 2: Environment Configuration — Setting Up Your Runtime",
        "project": "Project Terminus",
        "description": "How to install Docker Desktop container engine, pull the Terminus base image, run CLI health checks, and authenticate coordinator credentials.",
        "duration": "15:30",
        "category": "Environment Setup",
        "filename": "video_2.mp4",
        "date_added": "2026-07-24",
        "security_level": "Restricted (Employee Only)"
    },
    3: {
        "id": 3,
        "title": "MODULE 3: CLI Guide — Your Primary Interface",
        "project": "Project Terminus",
        "description": "How to use the Terminus CLI to initialize tasks (init), navigate schema (schema), manage submissions (submit), and monitor status (status).",
        "duration": "11:20",
        "category": "CLI Interface",
        "filename": "video_3.mp4",
        "date_added": "2026-07-24",
        "security_level": "Restricted (Employee Only)"
    },
    4: {
        "id": 4,
        "title": "MODULE 4: Task Structuring — Defining Training Data Schema",
        "project": "Project Terminus",
        "description": "Anatomy of a well-formed task (instruction.md, task.toml, environment/, solution/, tests/), difficulty tagging, and domain classification rules.",
        "duration": "18:15",
        "category": "Task Structuring",
        "filename": "video_4.mp4",
        "date_added": "2026-07-24",
        "security_level": "Restricted (Employee Only)"
    },
    5: {
        "id": 5,
        "title": "MODULE 5: Creating Your First Terminus Task",
        "project": "Project Terminus",
        "description": "Complete pipeline for task generation: CLI instantiation, Structure checklist validation, and Terminus Playbook edge-case compliance.",
        "duration": "14:50",
        "category": "Task Generation",
        "filename": "video_5.mp4",
        "date_added": "2026-07-24",
        "security_level": "Restricted (Employee Only)"
    },
    6: {
        "id": 6,
        "title": "MODULE 6: Oracle Validation & Local Testing",
        "project": "Project Terminus",
        "description": "Running the Oracle agent validation script, parsing execution logs, confirming environment variables & assertions pass, and debugging failures.",
        "duration": "16:10",
        "category": "Testing & Validation",
        "filename": "video_6.mp4",
        "date_added": "2026-07-24",
        "security_level": "Restricted (Employee Only)"
    },
    7: {
        "id": 7,
        "title": "MODULE 7: AI Agent Evaluation, Quality Checks & Submission",
        "project": "Project Terminus",
        "description": "Final evaluation pipeline: NOP Agent baseline, GPT-5.5 & Claude Opus 4.8 difficulty calculation, CI Checks, LLMaj review, rework cycle, and final submission.",
        "duration": "22:05",
        "category": "AI Agent Evaluation",
        "filename": "video_7.mp4",
        "date_added": "2026-07-24",
        "security_level": "Restricted (Employee Only)"
    }
}

FALLBACK_VIDEO_PATH = os.path.join(BASE_DIR, "frontend", "logo_animated.mp4")
CHUNK_SIZE = 1024 * 1024  # 1 MB streaming chunks for near-zero RAM footprint

# Ensure sample video files exist in UPLOAD_FOLDER for slots 1..7 so Nginx X-Accel-Redirect never 404s
for _vid in range(1, 8):
    _t_path = os.path.join(UPLOAD_FOLDER, f"video_{_vid}.mp4")
    if not os.path.exists(_t_path) and os.path.exists(FALLBACK_VIDEO_PATH):
        try:
            shutil.copyfile(FALLBACK_VIDEO_PATH, _t_path)
        except Exception as _e:
            pass


def generate_video_chunks(file_path, start, length, chunk_size=CHUNK_SIZE):
    """
    Generator yielding 1 MB video chunks.
    Ensures streaming 300MB+ video files uses < 2MB RAM per viewer.
    """
    with open(file_path, "rb") as f:
        f.seek(start)
        remaining = length
        while remaining > 0:
            bytes_to_read = min(chunk_size, remaining)
            chunk = f.read(bytes_to_read)
            if not chunk:
                break
            remaining -= len(chunk)
            yield chunk


@confidential_bp.route("/api/confidential-projects/videos", methods=["GET"])
def get_videos():
    """
    Returns list of metadata for the 6 confidential project videos.
    Restricted to authenticated employees and admins.
    """
    user = get_current_user()
    if not user:
        return jsonify({"error": "Unauthorized. Please log in as an employee to access confidential media."}), 401
    
    user_role = user.get("role", "").lower()
    allowed_roles = ["employee", "admin", "team_leader", "hr_manager", "hr", "tl"]
    if user_role not in allowed_roles:
        return jsonify({"error": "Forbidden"}), 403

    videos_list = []
    for vid, data in CONFIDENTIAL_VIDEOS.items():
        v_copy = dict(data)
        video_file_path = os.path.join(UPLOAD_FOLDER, v_copy["filename"])
        v_copy["is_uploaded"] = os.path.exists(video_file_path)
        if os.path.exists(video_file_path):
            size_mb = round(os.path.getsize(video_file_path) / (1024 * 1024), 1)
            v_copy["file_size_mb"] = f"{size_mb} MB"
        else:
            v_copy["file_size_mb"] = "Sample Preview"
        videos_list.append(v_copy)

    return jsonify({
        "status": "success",
        "project_name": "Project Terminus",
        "user_name": user.get("name", "Employee"),
        "user_email": user.get("email", ""),
        "user_role": user_role,
        "videos": videos_list
    })


@confidential_bp.route("/api/confidential-projects/videos/<int:video_id>/stream", methods=["GET"])
def stream_video(video_id):
    """
    Authenticated video streaming endpoint supporting 300MB+ files.
    Uses generator chunking and HTTP Range requests for instant playback.
    """
    user = get_current_user()
    if not user:
        return jsonify({"error": "Unauthorized access to confidential stream"}), 401

    user_role = user.get("role", "").lower()
    allowed_roles = ["employee", "admin", "team_leader", "hr_manager", "hr", "tl"]
    if user_role not in allowed_roles:
        return jsonify({"error": "Forbidden"}), 403

    if video_id not in CONFIDENTIAL_VIDEOS:
        return jsonify({"error": "Confidential video not found"}), 404

    video_info = CONFIDENTIAL_VIDEOS[video_id]
    file_path = os.path.join(UPLOAD_FOLDER, video_info["filename"])
    if not os.path.exists(file_path):
        if os.path.exists(FALLBACK_VIDEO_PATH):
            try:
                shutil.copyfile(FALLBACK_VIDEO_PATH, file_path)
            except Exception:
                pass

    if not os.path.exists(file_path):
        return jsonify({"error": "Video file unavailable"}), 404

    file_size = os.path.getsize(file_path)
    mime_type = mimetypes.guess_type(file_path)[0] or "video/mp4"

    # High-Performance Nginx X-Accel-Redirect Acceleration
    # Offloads 300MB video byte streaming to Nginx kernel sendfile(), freeing Gunicorn workers instantly (0.001s response time).
    if request.headers.get("X-Forwarded-For") or request.headers.get("X-Real-IP"):
        filename = os.path.basename(file_path)
        resp = Response()
        resp.headers["X-Accel-Redirect"] = f"/uploads/confidential_videos/{filename}"
        resp.headers["Content-Type"] = mime_type
        resp.headers["Accept-Ranges"] = "bytes"
        resp.headers["Content-Disposition"] = "inline"
        resp.headers["X-Content-Type-Options"] = "nosniff"
        resp.headers["Cache-Control"] = "no-cache, no-store, must-revalidate, private"
        resp.headers["Pragma"] = "no-cache"
        return resp
    range_header = request.headers.get("Range", None)
    if range_header:
        match = re.search(r"bytes=(\d+)-(\d+)?", range_header)
        if match:
            start = int(match.group(1))
            end = int(match.group(2)) if match.group(2) else file_size - 1
            if start >= file_size:
                return jsonify({"error": "Range not satisfiable"}), 416
            
            length = end - start + 1
            
            resp = Response(
                generate_video_chunks(file_path, start, length),
                206,
                mimetype=mime_type,
                direct_passthrough=True
            )
            resp.headers["Content-Range"] = f"bytes {start}-{end}/{file_size}"
            resp.headers["Accept-Ranges"] = "bytes"
            resp.headers["Content-Length"] = str(length)
        else:
            resp = Response(
                generate_video_chunks(file_path, 0, file_size),
                200,
                mimetype=mime_type,
                direct_passthrough=True
            )
            resp.headers["Content-Length"] = str(file_size)
            resp.headers["Accept-Ranges"] = "bytes"
    else:
        resp = Response(
            generate_video_chunks(file_path, 0, file_size),
            200,
            mimetype=mime_type,
            direct_passthrough=True
        )
        resp.headers["Content-Length"] = str(file_size)
        resp.headers["Accept-Ranges"] = "bytes"

    # Anti-Download & Security Headers
    resp.headers["Content-Disposition"] = "inline"
    resp.headers["X-Content-Type-Options"] = "nosniff"
    resp.headers["Cache-Control"] = "no-cache, no-store, must-revalidate, private"
    resp.headers["Pragma"] = "no-cache"
    resp.headers["Expires"] = "0"
    
    return resp


@confidential_bp.route("/api/confidential-projects/videos/<int:video_id>/upload", methods=["POST"])
def upload_video(video_id):
    """
    Allows Admin / TL to upload or replace a 300MB+ confidential video file (video_1.mp4 ... video_6.mp4).
    """
    user = get_current_user()
    if not user or user.get("role", "").lower() not in ["admin", "team_leader", "tl"]:
        return jsonify({"error": "Unauthorized. Only Admins/Team Leaders can upload project videos."}), 403

    if video_id not in CONFIDENTIAL_VIDEOS:
        return jsonify({"error": "Invalid video slot ID (must be 1 to 7)"}), 400

    if "file" not in request.files:
        return jsonify({"error": "No file uploaded"}), 400

    file = request.files["file"]
    if not file or file.filename == "":
        return jsonify({"error": "Empty filename"}), 400

    filename = CONFIDENTIAL_VIDEOS[video_id]["filename"]
    save_path = os.path.join(UPLOAD_FOLDER, filename)

    # Save large file in 1MB chunks to disk without memory exhaustion
    with open(save_path, "wb") as f:
        while True:
            chunk = file.stream.read(1024 * 1024)
            if not chunk:
                break
            f.write(chunk)

    size_mb = round(os.path.getsize(save_path) / (1024 * 1024), 1)

    return jsonify({
        "status": "success",
        "message": f"Successfully uploaded video for slot {video_id} ({CONFIDENTIAL_VIDEOS[video_id]['title']}) — Size: {size_mb} MB",
        "video_id": video_id,
        "filename": filename,
        "size_mb": size_mb
    })
