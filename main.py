# main.py
import os
import random
import time
import traceback
from pathlib import Path
import requests
from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout
from hashtags import get_trending_hashtags

# Files
DAY_COUNTER_FILE = Path("day_counter.txt")
DRIVE_LINKS_FILE = Path("drive_links.txt")
VIDEO_LOCAL = Path("video.mp4")

# === Helpers for day counter ===
def read_day():
    if not DAY_COUNTER_FILE.exists():
        return 1
    try:
        return int(DAY_COUNTER_FILE.read_text().strip())
    except Exception:
        return 1

def write_next_day(next_day):
    DAY_COUNTER_FILE.write_text(str(next_day))


# === Download random video from drive_links.txt ===
def download_random_video():
    if not DRIVE_LINKS_FILE.exists():
        raise FileNotFoundError("drive_links.txt missing — add direct download links (uc?export=download&id=...)")
    with DRIVE_LINKS_FILE.open("r") as f:
        links = [line.strip() for line in f if line.strip()]
    if not links:
        raise ValueError("drive_links.txt is empty.")
    link = random.choice(links)
    print("Downloading video from:", link)
    resp = requests.get(link, stream=True, timeout=90)
    resp.raise_for_status()
    with VIDEO_LOCAL.open("wb") as out:
        for chunk in resp.iter_content(chunk_size=8192):
            if chunk:
                out.write(chunk)
    print("Downloaded to", VIDEO_LOCAL)
    return VIDEO_LOCAL


# === Login helpers ===
def is_logged_in(page):
    # quick heuristic: nav appears on logged-in homepage
    try:
        page.wait_for_selector("nav", timeout=5000)
        return True
    except PWTimeout:
        # try account link or profile icon
        try:
            page.wait_for_selector('a[href^="/accounts/edit/"]', timeout=2000)
            return True
        except PWTimeout:
            return False

def login_instagram(page, username, password):
    """
    Robust login: long timeouts, flexible selectors.
    Raises an exception on failure.
    """
    print("Opening Instagram login page...")
    page.goto("https://www.instagram.com/accounts/login/", timeout=90000)
    page.wait_for_timeout(5000)  # let assets load

    # try multiple possible input selectors
    selectors = [
        "input[name='username']",
        "input[name='email']",
        "input[aria-label='Phone number, username, or email']",
        "input[type='text']"
    ]
    found = None
    for sel in selectors:
        try:
            page.wait_for_selector(sel, timeout=15000)
            found = sel
            break
        except PWTimeout:
            continue

    if not found:
        # last effort: inspect page text for unusual blocking
        content = page.content()[:4000]
        print("Login inputs not found. Page snippet:", content[:800])
        raise RuntimeError("Login form not found on Instagram login page (blocked or changed).")

    # fill username
    try:
        if page.query_selector("input[name='username']"):
            page.fill("input[name='username']", username)
        elif page.query_selector("input[name='email']"):
            page.fill("input[name='email']", username)
        else:
            # fallback: fill the first visible text input
            page.fill(found, username)
    except Exception as e:
        print("Failed to fill username:", e)
        raise

    # fill password
    try:
        if page.query_selector("input[name='password']"):
            page.fill("input[name='password']", password)
        else:
            # try any password-like input
            page.fill("input[type='password']", password)
    except Exception as e:
        print("Failed to fill password:", e)
        raise

    # click login - try several selectors
    login_btn_selectors = [
        "button[type='submit']",
        "button:has-text('Log In')",
        "button:has-text('Log in')",
        "button:has-text('Log In')"
    ]
    clicked = False
    for sel in login_btn_selectors:
        try:
            btn = page.query_selector(sel)
            if btn:
                btn.click()
                clicked = True
                break
        except Exception:
            continue
    if not clicked:
        # last resort: press Enter in password field
        try:
            page.keyboard.press("Enter")
        except Exception:
            pass

    # wait for successful login (nav/profile) or detect challenge dialogs
    try:
        page.wait_for_selector("nav", timeout=90000)
        print("Login appears successful (nav found).")
        return
    except PWTimeout:
        # Could be a checkpoint/2FA — capture page snapshot for debugging
        print("Login did not complete within timeout. Checking for challenge or 2FA...")
        # Try to detect common texts
        if "two-factor" in page.content().lower() or "verification" in page.content().lower() or "challenge" in page.content().lower():
            raise RuntimeError("Instagram is asking for 2FA / checkpoint. Consider using storage_state.json or manual login.")
        raise RuntimeError("Login timeout — Instagram may be blocking automated logins.")


# === Upload video using web create flow ===
def upload_video(page, local_video_path, caption):
    print("Starting upload flow...")
    # try clicking New post icon first
    clicked = False
    create_selectors = [
        'svg[aria-label="New post"]',
        'svg[aria-label="Create"]',
        'a[href="/create/style/"]',
        'div[role="menuitem"] svg[aria-label="New post"]'
    ]
    for sel in create_selectors:
        try:
            el = page.query_selector(sel)
            if el:
                el.click()
                clicked = True
                break
        except Exception:
            continue

    if not clicked:
        # fallback to direct create URL
        try:
            page.goto("https://www.instagram.com/create/details/", timeout=30000)
        except Exception:
            pass

    # wait for input[type=file]
    try:
        file_input = page.wait_for_selector('input[type="file"]', timeout=60000)
    except PWTimeout:
        raise RuntimeError("Upload input not found in create dialog.")

    # upload file
    file_input.set_input_files(str(local_video_path.resolve()))
    time.sleep(1)

    # Click Next (may need twice)
    for _ in range(3):
        try:
            btn = page.query_selector('div[role="dialog"] button:has-text("Next")')
            if btn:
                btn.click()
                time.sleep(1)
                continue
        except Exception:
            pass
        break

    # caption textarea - try a few selectors
    textarea_selectors = [
        "textarea[aria-label='Write a caption…']",
        "textarea[aria-label='Write a caption...']",
        "textarea"
    ]
    caption_done = False
    for sel in textarea_selectors:
        try:
            ta = page.query_selector(sel)
            if ta:
                ta.fill(caption)
                caption_done = True
                break
        except Exception:
            continue
    if not caption_done:
        print("Warning: Caption textarea not found; continuing without caption.")

    # click Share/Publish
    shared = False
    for sel in ['div[role="dialog"] button:has-text("Share")', 'button:has-text("Share")', 'button:has-text("Publish")', 'button:has-text("Post")']:
        try:
            btn = page.query_selector(sel)
            if btn:
                btn.click()
                shared = True
                break
        except Exception:
            continue
    if not shared:
        # last resort: press Enter
        try:
            page.keyboard.press("Enter")
            shared = True
        except Exception:
            raise RuntimeError("Could not find Share/Publish button; upload may have failed.")

    # Wait a bit for the post to process
    print("Waiting for post to finish processing (10s)...")
    page.wait_for_timeout(10000)
    print("Upload flow finished (may still be processing on Instagram side).")


# === Main ===
def main():
    print("=== Instagram Auto Poster (headed-mode safe) ===")
    storage_state_path = os.getenv("IG_STORAGE_STATE_PATH")  # workflow can set this path (e.g. storage_state.json)
    username = os.getenv("IG_USER")
    password = os.getenv("IG_PASS")

    # Get current day (do NOT increment now; increment only after successful post)
    current_day = read_day()
    print("Current day (will increment after successful post):", current_day)

    # Download video from Drive links
    video_path = None
    try:
        video_path = download_random_video()
    except Exception as e:
        print("Failed to download video:", e)
        raise

    # Hashtags (pytrends fallback handled inside your hashtags.py)
    try:
        tags = get_trending_hashtags()
        if isinstance(tags, (list, tuple)):
            hashtags_text = " ".join(f"#{t.lstrip('#')}" for t in tags[:25])
        else:
            hashtags_text = str(tags)
    except Exception as e:
        print("Hashtags fetch failed, using fallback:", e)
        hashtags_text = "#instagood #picoftheday"

    caption = f"Reminder – Day {current_day}\n\n{hashtags_text}"
    print("Caption preview:", caption[:160])

        # Playwright run
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=False,
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--disable-infobars",
                    "--window-size=1280,800",
                    "--no-sandbox",
                    "--disable-setuid-sandbox",
                    "--disable-dev-shm-usage",
                ],
            )

            ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            context_kwargs = {
                "user_agent": ua,
                "viewport": {"width": 1280, "height": 800},
                "locale": "en-US",
                "timezone_id": "Asia/Karachi",
            }

            used_storage = False
            if storage_state_path and Path(storage_state_path).exists():
                print("✅ Attempting to use storage_state.json:", storage_state_path)
                context = browser.new_context(storage_state=str(storage_state_path), **context_kwargs)
                page = context.new_page()
                if is_logged_in(page):
                    print("✅ Logged in via storage_state.json")
                    used_storage = True
                else:
                    print("⚠️ Storage state present but NOT logged in. Will try username/password fallback.")
                    context.close()
                    context = browser.new_context(**context_kwargs)
                    page = context.new_page()

            else:
                context = browser.new_context(**context_kwargs)
                page = context.new_page()

            if not used_storage:
                if not username or not password:
                    raise EnvironmentError("❌ IG_USER/IG_PASS missing and storage_state.json didn’t work.")
                print("🔑 Logging in with username/password…")
                login_instagram(page, username, password)

            # Upload
            upload_video(page, video_path, caption)

            # success -> increment
            next_day = current_day + 1
            write_next_day(next_day)
            print("📈 Day counter incremented:", next_day)

            # cleanup
            try:
                if VIDEO_LOCAL.exists():
                    VIDEO_LOCAL.unlink()
            except Exception:
                pass

            context.close()
            browser.close()

    except Exception as exc:
        print("ERROR during run:", exc)
        traceback.print_exc()
        raise

    print("Done.")

if __name__ == "__main__":
    main()

