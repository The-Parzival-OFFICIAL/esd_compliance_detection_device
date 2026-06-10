#!/usr/bin/python3
from flask import Flask
from flask import render_template
from flask import jsonify
from flask import request

import subprocess

from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

# ==========================================================
# APP
# ==========================================================

app = Flask(__name__)

# ==========================================================
# RATE LIMITER
# ==========================================================

limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=["60 per minute"]
)

# ==========================================================
# API KEY
# ==========================================================

API_KEY = "esd_secure_key"

def authorized():

    return (
        request.headers.get("X-API-KEY")
        == API_KEY
    )

# ==========================================================
# START MONITOR
# ==========================================================

@app.route("/start", methods=["POST"])
@limiter.limit("5 per minute")
def start():

    if not authorized():

        return jsonify({
            "status": "error",
            "message": "Unauthorized"
        }), 401

    try:

        subprocess.run(
            [
                "sudo",
                "systemctl",
                "start",
                "esd-monitor"
            ],
            check=True
        )

        return jsonify({
            "status": "success",
            "message": "MONITOR STARTED"
        })

    except Exception as e:

        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500

# ==========================================================
# STOP MONITOR
# ==========================================================

@app.route("/stop", methods=["POST"])
@limiter.limit("5 per minute")
def stop():

    if not authorized():

        return jsonify({
            "status": "error",
            "message": "Unauthorized"
        }), 401

    try:

        subprocess.run(
            [
                "sudo",
                "systemctl",
                "stop",
                "esd-monitor"
            ],
            check=True
        )

        return jsonify({
            "status": "success",
            "message": "MONITOR STOPPED"
        })

    except Exception as e:

        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500

# ==========================================================
# SERVICE STATUS
# ==========================================================

@app.route("/status")
@limiter.limit("120 per minute")
def status():

    try:

        result = subprocess.run(
            [
                "systemctl",
                "is-active",
                "esd-monitor"
            ],
            capture_output=True,
            text=True,
        )

        return jsonify({
            "status": "success",
            "monitor_status":
                result.stdout.strip()
        })

    except Exception as e:

        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500

# ==========================================================
# HEALTH CHECK
# ==========================================================

@app.route("/health")
@limiter.limit("60 per minute")
def health():

    try:

        return jsonify({
            "status": "healthy",
            "service": "esd-control-server"
        })

    except Exception as e:

        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500

# ==========================================================
# MAIN PAGE
# ==========================================================

@app.route("/")
def index():

    try:

        return render_template(
            "main.html"
        )

    except Exception as e:

        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500

# ==========================================================
# RUN SERVER
# ==========================================================

if __name__ == "__main__":

    app.run(
        host="0.0.0.0",
        port=8008,
        debug=False
    )
