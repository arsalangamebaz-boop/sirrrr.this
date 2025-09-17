# main.py
import os
import time
import random
from pathlib import Path
from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout
from hashtags import get_trending_hashtags

VIDEOS_DIR = Path("videos")
DAY_COUNTER_FILE = Path("day_counter.txt")
UPLOAD_RETRY = 2

def read_and_increment_day():
    if not DAY_COUNTER_FILE.exists():
        DAY_COUNTER_FILE.write_text("1")
        return 1
    try:
        n = int(DAY_COUNTER_FILE.read_text().strip())
    except Exception:
        n = 1
    DAY_COUNTER_FILE.write_text(str(n + 1))
    return n

def choose_random_video():
    mp4s = sorted([p for p in VIDEOS_DIR.iterdir() if p.suffix.lower() in [".mp4", ".mov", ".mkv"]])
    if not mp4s:
        raise FileNotFoundError("No videos found in videos/ directory.")
    return random.choice(mp4s)

def login_with_credentials(page, username, password):
    page.goto("https://www.instagram.com/accounts/login/", timeout=60000)
    # wait for login inputs
    page.wait_for_selector('input[name="username"]', timeout=30000)
    page.fill('input[name="username"]', username)
    page.fill('input[name="password"]', password)
    page.click('button[type="submit"]')
    # possible post-login dialogs
    try:
        # dismiss "Save Your Login Info?" dialog
        page.wait_for_selector('//button[text()="Not Now" or text()="Not Now"]', timeout=10000)
        btns = page.query_selector_all('//button')
        for b in btns:
            txt = (b.inner_text() or "").strip().lower()
            if "not now" in txt:
                b.click()
                break
    except PWTimeout:
        pass
    try:
        # dismiss "Turn on Notifications" dialog
        page.wait_for_selector('//button[text()="Not Now"]', timeout=10000)
        page.click('//button[text()="Not Now"]')
    except PWTimeout:
        pass

def post_video_via_web(page, video_path: Path, caption: str):
    # Visit home to ensure UI is loaded
    page.goto("https://www.instagram.com/", timeout=60000)
    # Click the "Create" (+) button. Instagram has changed UI often; try several selectors.
    created = False
    create_selectors = [
        'svg[aria-label="New post"]',  # official aria-label
        'svg[aria-label="Create"]',
        'a[href="/create/style/"]',
        'div[role="menuitem"] svg[aria-label="New post"]',
    ]
    for sel in create_selectors:
        try:
            el = page.query_selector(sel)
            if el:
                el.click()
                created = True
                break
        except Exception:
            pass

    # Fallback: use direct create URL (sometimes Instagram uses /create)
    if not created:
        try:
            page.goto("https://www.instagram.com/create/details/", timeout=30000)
            created = True
        except Exception:
            pass

    # Wait for file input
    # Instagram file input may be <input type="file"> somewhere in shadow DOM - Playwright can locate input[type=file]
    try:
        # wait for a file input to appear
        file_input = page.wait_for_selector('input[type="file"]', timeout=20000)
    except PWTimeout:
        # Try alternative approach: open the "Create" dialog by keyboard shortcut (not reliable)
        raise RuntimeError("Could not find file input on Instagram create UI.")

    # Upload the file (Playwright supports set_input_files)
    file_input.set_input_files(str(video_path.resolve()))

    # Wait for thumbnail/next button to appear
    # Click "Next" buttons (may require two Next clicks: one after upload, one to go to final share screen)
    for _ in range(2):
        try:
            next_btn = page.wait_for_selector('//button[contains(.,"Next") or contains(.,"Next")]',
                                              timeout=20000)
            next_btn.click()
            time.sleep(1)
        except PWTimeout:
            # try English "Next" or localized alternatives
            break

    # Find caption box
    try:
        caption_area = page.wait_for_selector('textarea[aria-label="Write a caption…"]', timeout=15000)
    except PWTimeout:
        # try other possible textarea
        caption_area = page.query_selector('textarea')

    if not caption_area:
        raise RuntimeError("Caption textarea not found; the upload flow's DOM may have changed.")

    caption_area.fill(caption)

    # Click Share/Publish button
    share_selectors = [
        '//button/div[text()="Share"]/..',
        '//button[text()="Share"]',
        '//button[contains(.,"Publish") or contains(.,"Post")]',
    ]
    clicked_share = False
    for sel in share_selectors:
        try:
            btn = page.query_selector(sel)
            if btn:
                btn.click()
                clicked_share = True
                break
        except Exception:
            pass

    if not clicked_share:
        # try to find any button with role=button and text length small
        btns = page.query_selector_all('button')
        for b in btns:
            txt = (b.inner_text() or "").strip().lower()
            if txt in ("share", "publish", "post"):
                b.click()
                clicked_share = True
                break

    if not clicked_share:
        raise RuntimeError("Could not find Share/Publish button. Instagram UI may have changed.")

def run_using_credentials():
    IG_USER = os.getenv("IG_USER")
    IG_PASS = os.getenv("IG_PASS")
    if not IG_USER or not IG_PASS:
        raise EnvironmentError("Environment variables IG_USER and IG_PASS must be set.")

    day = read_and_increment_day()
    video = choose_random_video()
    hashtags = get_trending_hashtags()  # returns list
    hashtags_text = " ".join(f"#{h}" if not h.startswith("#") else h for h in hashtags[:20])
    caption = f"Reminder – Day {day}\n\n{hashtags_text}"

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()
        page = context.new_page()
        try:
            login_with_credentials(page, IG_USER, IG_PASS)
        except Exception as e:
            browser.close()
            raise

        # Wait a bit to ensure login succeeded (check profile link)
        try:
            page.wait_for_selector('a[href^="/' + IG_USER.split('@')[0] + '"]', timeout=10000)
        except Exception:
            # try to proceed anyway; login might still be successful
            pass

        attempted = 0
        while attempted < UPLOAD_RETRY:
            try:
                post_video_via_web(page, video, caption)
                print(f"Posted {video.name} with caption: {caption[:80]}...")
                break
            except Exception as e:
                attempted += 1
                print("Upload attempt failed:", e)
                if attempted >= UPLOAD_RETRY:
                    raise
                time.sleep(5)
        context.close()
        browser.close()

def run_using_storage_state(storage_state_path):
    # Alternative login using Playwright storage state (cookies + localStorage).
    # storage_state_path should be a JSON file path with saved state (from Playwright)
    if not Path(storage_state_path).exists():
        raise FileNotFoundError("storage_state.json not found at provided path.")
    day = read_and_increment_day()
    video = choose_random_video()
    hashtags = get_trending_hashtags()
    hashtags_text = " ".join(f"#{h}" if not h.startswith("#") else h for h in hashtags[:20])
    caption = f"Reminder – Day {day}\n\n{hashtags_text}"
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(storage_state=str(storage_state_path))
        page = context.new_page()
        page.goto("https://www.instagram.com/", timeout=30000)
        # If logged in, proceed to upload
        post_video_via_web(page, video, caption)
        context.close()
        browser.close()

if __name__ == "__main__":
    # Decide mode: if IG_SESSION_PATH env variable is set, use it (local path inside container)
    STORAGE_STATE_SECRET = os.getenv("IG_STORAGE_STATE_PATH")  # not typical in Actions; used if file available
    if STORAGE_STATE_SECRET and Path(STORAGE_STATE_SECRET).exists():
        run_using_storage_state(STORAGE_STATE_SECRET)
    else:
        run_using_credentials()
