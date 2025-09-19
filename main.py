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


# === Upload video using Instagram web flow ===
def upload_video(page, local_video_path, caption):
    print("Starting upload flow...")

    # Try clicking "New post" icon
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
        try:
            page.goto("https://www.instagram.com/create/details/", timeout=30000)
        except Exception:
            pass

    # Wait for file input
    try:
        file_input = page.wait_for_selector('input[type="file"]', timeout=60000)
    except PWTimeout:
        raise RuntimeError("Upload input not found in create dialog.")

    # Upload file
    file_input.set_input_files(str(local_video_path.resolve()))
    time.sleep(1)

    # Click Next (sometimes twice)
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

    # Fill caption
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
        print("⚠️ Caption textarea not found; continuing without caption.")

    # Click Share/Publish
    shared = False
    for sel in [
        'div[role="dialog"] button:has-text("Share")',
        'button:has-text("Share")',
        'button:has-text("Publish")',
        'button:has-text("Post")'
    ]:
        try:
            btn = page.query_selector(sel)
            if btn:
                btn.click()
                shared = True
                break
        except Exception:
            continue
    if not shared:
        try:
            page.keyboard.press("Enter")
            shared = True
        except Exception:
            raise RuntimeError("Could not find Share/Publish button; upload may have failed.")

    print("Waiting for post to finish processing (10s)...")
    page.wait_for_timeout(10000)
    print("✅ Upload flow finished (may still be processing on Instagram side).")


# === Main ===
def main():
    print("=== Instagram Auto Poster (cookie-based login only) ===")

    # Path to storage_state.json provided by workflow
    storage_state_path = os.getenv("IG_STORAGE_STATE_PATH")

    # Get current day
    current_day = read_day()
    print("Current day (will increment after successful post):", current_day)

    # Download video
    video_path = None
    try:
        video_path = download_random_video()
    except Exception as e:
        print("❌ Failed to download video:", e)
        raise

    # Hashtags
    try:
        tags = get_trending_hashtags()
        if isinstance(tags, (list, tuple)):
            hashtags_text = " ".join(f"#{t.lstrip('#')}" for t in tags[:25])
        else:
            hashtags_text = str(tags)
    except Exception as e:
        print("⚠️ Hashtags fetch failed, using fallback:", e)
        hashtags_text = "#instagood #picoftheday"

    caption = f"Reminder – Day {current_day}\n\n{hashtags_text}"
    print("Caption preview:", caption[:160])

    # Playwright automation
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

            # ✅ Require storage_state.json
            if storage_state_path and Path(storage_state_path).exists():
                print("Using storage state from:", storage_state_path)
                context = browser.new_context(storage_state=str(storage_state_path), **context_kwargs)
            else:
                raise EnvironmentError("❌ No storage_state.json found. Please set IG_STORAGE_STATE_JSON secret.")

            page = context.new_page()

            # Upload post
            upload_video(page, video_path, caption)

            # Increment day counter
            next_day = current_day + 1
            write_next_day(next_day)
            print("✅ Wrote next day:", next_day)

            # Cleanup
            try:
                if VIDEO_LOCAL.exists():
                    VIDEO_LOCAL.unlink()
            except Exception:
                pass

            context.close()
            browser.close()
    except Exception as exc:
        print("❌ ERROR during run:", exc)
        traceback.print_exc()
        raise

    print("🎉 Done.")


if __name__ == "__main__":
    main()
