"""Gunicorn settings for the app container. Override with GUNICORN_* environment variables."""
import os

bind = "0.0.0.0:8000"
workers = int(os.environ.get("GUNICORN_WORKERS", "3"))
threads = int(os.environ.get("GUNICORN_THREADS", "2"))
# Technical file generation can take a while for large devices.
timeout = int(os.environ.get("GUNICORN_TIMEOUT", "180"))
graceful_timeout = 30
max_requests = 1000          # recycle workers to bound memory growth
max_requests_jitter = 100
accesslog = "-"
errorlog = "-"
# Only the Apache proxy on the private Docker network can reach the app.
forwarded_allow_ips = "*"
worker_tmp_dir = "/dev/shm"
