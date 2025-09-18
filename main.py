import os
import random
import requests
from pathlib import Path
from playwright.sync_api import sync_playwright
from hashtags import get_trending_hashtags

# === File Paths ===
DAY_COUNTER_FILE = "day_counter.txt"
DRIVE_LINKS_FILE = "drive_links.txt"
VIDEO_FILE = "video.mp4"


# === Step 1: Handle Day Counter ===
def get_and_increment_day():
    if not os.path.exists(DAY_COUNTER_FILE):
        with open(DAY_COUNTER_FILE, "w") as f:
            f.write("1")
        return 1
    with open(DAY_COUNTER_FILE, "r+") as f:
        day = int(f.read().strip())
        day += 1
        f.seek(0)
        f.write(str(day))
        f.truncate()
    return day


# === Step 2: Download Random Video from Google Drive ===
def download_random_video():
    if not os.path.exists(DRIVE_LINKS_FILE):
        raise FileNotFoundError("drive_links.txt not found. Please add your Drive links.")

    with open(DRIVE_LINKS_FILE, "r") as f:
        links = [line.strip() for line in f if line.strip()]

    if not links:
        raise ValueError("drive_links.txt is empty. Add Google Drive direct download links.")

    link = random.choice(links)
    print(f"Downloading video from: {link}")

    r = requests.get(link, stream=True, timeout=60)
    r.raise_for_status()
    with open(VIDEO_FILE, "wb") as f_out:
        for chunk in r.iter_content(chunk_size=8192):
            if chunk:
                f_out.write(chunk)
    return VIDEO_FILE


# === Step 3: Instagram Login ===
def login_instagram(page, username, password):
    page.goto("https://www.instagram.com/accounts/login/", timeout=60000)

    # Wait for either 'username' or 'email' input
    page.wait_for_selector("input[name='username'], input[name='email']", timeout=60000)

    # Fill login form
    try:
        page.fill("input[name='username']", username)
    except:
        page.fill("input[name='email']", username)

    page.fill("input[name='password']", password)

    # Click Login button
    page.click("button[type='submit']")

    # Wait for homepage (nav bar appears after login)
    page.wait_for_selector("nav", timeout=60000)


# === Step 4: Upload Video ===
def upload_video(page, video_path, caption):
    # Click Create button
    page.click("svg[aria-label='New post']")

    # Upload file
    file_input = page.query_selector("input[type='file']")
    file_input.set_input_files(video_path)

    # Click Next (twice sometimes)
    page.wait_for_selector("text=Next", timeout=60000)
    page.click("text=Next")
    page.wait_for_selector("text=Next", timeout=60000)
    page.click("text=Next")

    # Add caption
    page.wait_for_selector("textarea[aria-label='Write a caption…']", timeout=60000)
    page.fill("textarea[aria-label='Write a caption…']", caption)

    # Share
    page.click("text=Share")
    page.wait_for_timeout(5000)


# === Main Script ===
def main():
    username = os.getenv("IG_USER")
    password = os.getenv("IG_PASS")

    if not username or not password:
        raise EnvironmentError("IG_USER and IG_PASS must be set as environment variables.")

    # Get day counter
    day = get_and_increment_day()

    # Download random video
    video_file = download_random_video()

    # Get hashtags
    hashtags = get_trending_hashtags()
    caption = f"Reminder – Day {day}\n\n{hashtags}"

    # Run Playwright
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()
        page = context.new_page()

        login_instagram(page, username, password)
        upload_video(page, video_file, caption)

        context.close()
        browser.close()

    print("✅ Video posted successfully!")


if __name__ == "__main__":
    main()

