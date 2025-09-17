# Project: Instagram Auto Poster — Playwright + GitHub Actions
# Files included below (copy these into your repository):


# ---------- README.md ----------
# Instagram Auto Poster (Playwright + GitHub Actions)
# Description:
# - Uploads the same video to Instagram daily at a fixed time using Playwright (headless Chromium).
# - Automatically generates a caption with a day counter (Day 1, Day 2, ...).
# - Fetches "fresh" hashtags daily using Google Trends (pytrends) and simple keyword-to-hashtag conversion.
#
# Important notes:
# 1) This uses web automation (Playwright) to control Instagram web UI. That can violate Instagram's Terms of Service and may risk your account.
# 2) Store Instagram credentials as GitHub Secrets (IG_USERNAME, IG_PASSWORD). Do NOT commit credentials.
# 3) Place your video file at `assets/video.mp4` in the repo or modify the script to download from a hosted link.
# 4) Scheduling is done by GitHub Actions cron. GitHub Actions runs in UTC; set CRON_SCHEDULE secret to control time.
# 5) This is provided for educational / automation experimentation only. Official alternative: Meta Business Suite.


# ---------- requirements.txt ----------
# Playwright and pytrends
playwright==1.40.0
pytrends==4.11.0
requests==2.31.0
