# main.py - Updated with better Instagram upload handling

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

# === Environment Detection ===
def is_ci_environment():
    """Detect if running in CI environment like GitHub Actions"""
    ci_indicators = [
        'CI', 'CONTINUOUS_INTEGRATION', 'GITHUB_ACTIONS', 
        'GITLAB_CI', 'TRAVIS', 'JENKINS_URL', 'BAMBOO_BUILD_NUMBER'
    ]
    return any(os.getenv(indicator) for indicator in ci_indicators)

def get_browser_config():
    """Get browser configuration based on environment"""
    # Check for explicit headless environment variable
    headless_env = os.getenv('PLAYWRIGHT_HEADLESS', '').lower()
    if headless_env in ['true', '1', 'yes']:
        return True
    elif headless_env in ['false', '0', 'no']:
        return False

    # Auto-detect based on environment
    if is_ci_environment():
        print("🔍 CI environment detected - using headless mode")
        return True
    else:
        print("🔍 Local environment detected - using headed mode")
        return False

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

    try:
        resp = requests.get(link, stream=True, timeout=90)
        resp.raise_for_status()

        with VIDEO_LOCAL.open("wb") as out:
            for chunk in resp.iter_content(chunk_size=8192):
                if chunk:
                    out.write(chunk)

        print("Downloaded to", VIDEO_LOCAL)
        return VIDEO_LOCAL

    except requests.RequestException as e:
        print(f"❌ Download failed: {e}")
        raise

# === Upload video using Instagram web flow with improved selectors ===
def upload_video(page, local_video_path, caption):
    print("Starting upload flow...")

    try:
        # Navigate to Instagram and wait for page to stabilize
        print("📍 Navigating to Instagram...")
        page.goto("https://www.instagram.com/", timeout=30000)
        page.wait_for_load_state('networkidle')

        # Take screenshot for debugging
        page.screenshot(path="debug_homepage.png")
        print("📸 Homepage screenshot saved")

        # Try multiple methods to access create post
        clicked = False

        # Method 1: Try clicking create button directly
        create_selectors = [
            'svg[aria-label="New post"]',
            'svg[aria-label="Create"]',
            '[data-testid="new-post-button"]',
            'a[href*="/create/"]',
            'div[role="menuitem"] svg[aria-label="New post"]',
            '[aria-label="New post"] svg',
            'button[aria-label="New post"]'
        ]

        for sel in create_selectors:
            try:
                print(f"🔍 Trying selector: {sel}")
                element = page.wait_for_selector(sel, timeout=5000)
                if element and element.is_visible():
                    element.click()
                    clicked = True
                    print(f"✅ Clicked create button with: {sel}")
                    break
            except PWTimeout:
                continue
            except Exception as e:
                print(f"⚠️ Error with selector {sel}: {e}")
                continue

        # Method 2: Try direct navigation if button clicking failed
        if not clicked:
            print("🔄 Trying direct navigation to create page...")
            try:
                page.goto("https://www.instagram.com/create/details/", timeout=30000)
                page.wait_for_load_state('networkidle')
            except Exception as e:
                print(f"⚠️ Direct navigation failed: {e}")

        # Method 3: Try keyboard shortcut as last resort
        if not clicked:
            print("⌨️ Trying keyboard shortcut Ctrl+Shift+C...")
            try:
                page.keyboard.press('Control+Shift+C')
                time.sleep(2)
            except Exception:
                pass

        # Wait a bit for any dialog to appear
        page.wait_for_timeout(3000)
        page.screenshot(path="debug_after_create_click.png")
        print("📸 Post-create screenshot saved")

        # Try to find file input with multiple strategies
        file_input = None
        file_input_selectors = [
            'input[type="file"]',
            'input[accept*="image"]', 
            'input[accept*="video"]',
            '[data-testid="new-post-file-input"]',
            'form input[type="file"]',
            'div[role="dialog"] input[type="file"]'
        ]

        for sel in file_input_selectors:
            try:
                print(f"🔍 Looking for file input: {sel}")
                file_input = page.wait_for_selector(sel, timeout=10000, state='attached')
                if file_input:
                    print(f"✅ Found file input with: {sel}")
                    break
            except PWTimeout:
                continue
            except Exception as e:
                print(f"⚠️ Error finding file input {sel}: {e}")
                continue

        if not file_input:
            # Last resort: try to find any input element and check if it's for files
            print("🔍 Last resort: looking for any input elements...")
            all_inputs = page.query_selector_all('input')
            for input_elem in all_inputs:
                try:
                    input_type = input_elem.get_attribute('type')
                    accept_attr = input_elem.get_attribute('accept')
                    if input_type == 'file' or (accept_attr and ('image' in accept_attr or 'video' in accept_attr)):
                        file_input = input_elem
                        print("✅ Found file input through search")
                        break
                except Exception:
                    continue

        if not file_input:
            # Debug: save page content and screenshot
            page.screenshot(path="debug_no_file_input.png")
            page_content = page.content()
            with open("debug_page_content.html", "w", encoding="utf-8") as f:
                f.write(page_content)
            print("❌ Could not find file input after trying all methods")
            print("📸 Debug files saved: debug_no_file_input.png, debug_page_content.html")

            # Try alternative approach: look for drag-drop area
            drop_areas = [
                '[data-testid="new-post-photo-section"]',
                '.x1i10hfl[role="button"]',
                'div[data-visualcompletion="css-img"]',
                'button[type="button"]:has-text("Select from computer")',
                'div:has-text("Drag photos and videos here")',
                'div:has-text("Select From Computer")'
            ]

            for sel in drop_areas:
                try:
                    drop_area = page.query_selector(sel)
                    if drop_area:
                        print(f"🎯 Found potential drop area: {sel}")
                        # Try clicking it to trigger file dialog
                        drop_area.click()
                        time.sleep(2)
                        # Try finding file input again
                        file_input = page.query_selector('input[type="file"]')
                        if file_input:
                            print("✅ File input appeared after clicking drop area")
                            break
                except Exception:
                    continue

            if not file_input:
                raise RuntimeError("Upload input not found after exhaustive search. Instagram interface may have changed.")

        # Upload the file
        print(f"📤 Uploading file: {local_video_path}")
        file_input.set_input_files(str(local_video_path.resolve()))
        time.sleep(3)

        # Wait for upload to process and look for Next button
        print("⏳ Waiting for file processing...")
        next_clicked = False

        for attempt in range(5):  # Try up to 5 times
            next_selectors = [
                'div[role="dialog"] button:has-text("Next")',
                'button:has-text("Next")',
                '[data-testid="new-post-next-button"]',
                'div[role="dialog"] div[role="button"]:has-text("Next")',
                'button[type="button"]:has-text("Next")'
            ]

            for sel in next_selectors:
                try:
                    next_btn = page.query_selector(sel)
                    if next_btn and next_btn.is_visible():
                        next_btn.click()
                        next_clicked = True
                        print(f"✅ Clicked Next button (attempt {attempt + 1})")
                        time.sleep(2)
                        break
                except Exception:
                    continue

            if next_clicked:
                break

            print(f"⏳ Next button not ready, waiting... (attempt {attempt + 1})")
            time.sleep(3)

        # Navigate through the post creation flow
        # Click Next again if needed (for editing screen)
        try:
            time.sleep(2)
            next_btn = page.query_selector('div[role="dialog"] button:has-text("Next")')
            if next_btn and next_btn.is_visible():
                next_btn.click()
                time.sleep(2)
        except Exception:
            pass

        # Fill caption
        caption_selectors = [
            "textarea[aria-label='Write a caption…']",
            "textarea[aria-label='Write a caption...']", 
            "div[contenteditable='true'][data-testid='caption-input']",
            "textarea[placeholder*='caption']",
            "div[role='textbox']",
            "textarea"
        ]

        caption_done = False
        for sel in caption_selectors:
            try:
                caption_elem = page.query_selector(sel)
                if caption_elem and caption_elem.is_visible():
                    caption_elem.fill(caption)
                    caption_done = True
                    print("✅ Caption added successfully")
                    break
            except Exception:
                continue

        if not caption_done:
            print("⚠️ Could not add caption, continuing without it...")

        # Click Share/Publish
        share_selectors = [
            'div[role="dialog"] button:has-text("Share")',
            'button:has-text("Share")',
            'button:has-text("Publish")',
            'button:has-text("Post")',
            '[data-testid="new-post-share-button"]'
        ]

        shared = False
        for sel in share_selectors:
            try:
                share_btn = page.query_selector(sel)
                if share_btn and share_btn.is_visible():
                    share_btn.click()
                    shared = True
                    print("✅ Post shared successfully")
                    break
            except Exception:
                continue

        if not shared:
            print("⚠️ Could not find Share button, trying Enter key...")
            try:
                page.keyboard.press("Enter")
                shared = True
            except Exception:
                raise RuntimeError("Could not complete post sharing")

        # Wait for post to finish processing
        print("⏳ Waiting for post to finish processing...")
        page.wait_for_timeout(10000)

        # Take final screenshot
        page.screenshot(path="debug_post_complete.png")
        print("📸 Final screenshot saved")
        print("✅ Upload flow completed successfully")

    except Exception as e:
        # Enhanced error handling with debugging
        error_msg = f"Upload failed: {e}"
        print(f"❌ {error_msg}")

        # Save debugging information
        try:
            page.screenshot(path="debug_error.png")
            page_content = page.content()
            with open("debug_error_content.html", "w", encoding="utf-8") as f:
                f.write(page_content)
            print("📸 Error debugging files saved")
        except Exception:
            pass

        raise RuntimeError(error_msg)

# === Main ===
def main():
    print("=== Instagram Auto Poster (Enhanced Error Handling) ===")

    # Path to storage_state.json
    storage_state_path = os.getenv("IG_STORAGE_STATE_PATH", "storage_state.json")

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

    # Get hashtags
    try:
        tags = get_trending_hashtags()
        if isinstance(tags, (list, tuple)):
            hashtags_text = " ".join(f"#{t.lstrip('#')}" for t in tags[:20])
        else:
            hashtags_text = str(tags)
    except Exception as e:
        print("⚠️ Hashtags fetch failed, using fallback:", e)
        hashtags_text = "#instagood #picoftheday #motivation #viral"

    caption = f"Reminder – Day {current_day}\n\n{hashtags_text}"
    print("Caption preview:", caption[:160])

    # Playwright automation
    try:
        with sync_playwright() as p:
            # Get browser configuration
            is_headless = get_browser_config()

            # Enhanced browser arguments
            browser_args = [
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-dev-shm-usage",
                "--disable-blink-features=AutomationControlled",
                "--disable-infobars",
                "--window-size=1280,800",
                "--disable-web-security",
                "--disable-features=VizDisplayCompositor",
                "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            ]

            if is_headless:
                browser_args.extend([
                    "--disable-gpu",
                    "--no-first-run",
                    "--disable-extensions",
                    "--hide-scrollbars",
                    "--mute-audio"
                ])

            print(f"🚀 Launching browser (headless={is_headless})...")

            browser = p.chromium.launch(
                headless=is_headless,
                args=browser_args,
            )

            context_kwargs = {
                "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "viewport": {"width": 1280, "height": 800},
                "locale": "en-US",
                "timezone_id": "Asia/Karachi",
            }

            # Use storage state if available
            if Path(storage_state_path).exists():
                print("Using storage state from:", storage_state_path)
                context = browser.new_context(storage_state=str(storage_state_path), **context_kwargs)
            else:
                print("⚠️ No storage state found, creating new context")
                context = browser.new_context(**context_kwargs)

            page = context.new_page()

            # Set longer timeouts
            page.set_default_timeout(60000)

            # Upload post
            upload_video(page, video_path, caption)

            # Increment day counter only on success
            next_day = current_day + 1
            write_next_day(next_day)
            print("✅ Wrote next day:", next_day)

            # Cleanup
            try:
                if VIDEO_LOCAL.exists():
                    VIDEO_LOCAL.unlink()
                    print("🧹 Video file cleaned up")
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
