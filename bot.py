"""
FB Friend Checker Telegram Bot — v8 (Final: CSV + Hardened + Network Resilient)
============================================================================
Architecture: Persistent Global Headless Browser
Target Site:  mbasic.facebook.com
"""

import os
import re
import time
import threading
import telebot
from telebot import apihelper
from telebot import types
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    TimeoutException,
    WebDriverException,
)
from webdriver_manager.chrome import ChromeDriverManager

# ============================================================
# 🔐 CONFIG
# ============================================================
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("❌ TELEGRAM_BOT_TOKEN environment variable not set. Please set it before running the bot.")

MAX_UIDS_PER_BATCH = 50
PAGE_LOAD_DELAY = 2          # seconds between UID checks
WAIT_TIMEOUT = 8             # explicit-wait timeout

bot = telebot.TeleBot(BOT_TOKEN)

# Tell the bot to survive network drops and VPN disconnects
apihelper.RETRY_ON_ERROR = True

# ============================================================
# 🌐 GLOBAL STATE
# ============================================================
global_driver = None
user_credentials = {}        # {chat_id: {'email': ..., 'password': ...}}
credentials_lock = threading.Lock()  # Prevent race conditions on concurrent logins

# ============================================================
# 🚀 DRIVER FACTORY (Persistent Browser)
# ============================================================
def get_driver():
    global global_driver

    if global_driver is not None:
        try:
            _ = global_driver.current_url
            return global_driver
        except WebDriverException:
            print("[driver] Dead browser detected, reinitializing...")
            global_driver = None

    chrome_options = Options()
    chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--window-size=1366,768")
    
    # Force English locale to bypass regional language issues on mbasic
    chrome_options.add_argument("--lang=en-US") 
    
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option("useAutomationExtension", False)

    # Updated User-Agent to Chrome 126 to prevent "Unsupported Browser" blocks
    chrome_options.add_argument(
        "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/126.0.0.0 Safari/537.36"
    )

    service = Service(ChromeDriverManager().install())
    global_driver = webdriver.Chrome(service=service, options=chrome_options)

    global_driver.execute_cdp_cmd(
        "Page.addScriptToEvaluateOnNewDocument",
        {"source": "Object.defineProperty(navigator,'webdriver',{get:()=>undefined});"},
    )
    print("[driver] New persistent browser launched.")
    return global_driver


# ============================================================
# 🧰 HELPERS
# ============================================================
def is_session_alive(driver) -> bool:
    try:
        cookies = {c["name"] for c in driver.get_cookies()}
        return "c_user" in cookies
    except Exception:
        return False

def dismiss_interstitials(driver):
    interstitial_selectors = [
        "//a[contains(@href,'save-device') and (contains(translate(.,'NOT','not'),'not now') or contains(translate(.,'SKIP','skip'),'skip'))]",
        "//input[@value='Not Now' or @value='Not now']",
        "//button[contains(translate(.,'ACCEPT','accept'),'accept')]",
        "//a[contains(translate(.,'SKIP','skip'),'skip')]",
    ]
    for xp in interstitial_selectors:
        try:
            el = driver.find_element(By.XPATH, xp)
            el.click()
            time.sleep(1.5)
        except Exception:
            continue

def send_debug_screenshot(chat_id, caption: str):
    global global_driver
    fname = f"debug_{chat_id}_{int(time.time())}.png"
    try:
        global_driver.save_screenshot(fname)
        with open(fname, "rb") as photo:
            bot.send_photo(chat_id, photo, caption=caption, parse_mode="Markdown")
    except Exception:
        pass
    finally:
        try:
            if os.path.exists(fname):
                os.remove(fname)
        except OSError:
            pass

def parse_uids(text: str):
    raw = re.split(r"[\s,;]+", text.strip())
    return [u for u in raw if u.isdigit()]

def extract_friend_count(driver):
    """Scans the profile for the friend count and extracts ONLY the number."""
    try:
        links = driver.find_elements(By.TAG_NAME, "a")
        for link in links:
            txt = (link.text or "").strip().lower()
            if not txt:
                continue
            
            # 1. Skip action buttons that don't represent the count
            skip_words = ['add', 'ajouter', 'trouver', 'find', 'agregar', 'buscar', 'see all', 'voir', 'ver']
            if any(skip in txt for skip in skip_words):
                continue
            
            # 2. Look for language-specific friend keywords
            target_words = ['friend', 'ami', 'amigo', 'বন্ধু']
            if any(target in txt for target in target_words):
                # 3. Clean string (remove commas/dots like 1,000) and extract digits
                clean_txt = txt.replace(',', '').replace('.', '').strip()
                # Guard against empty strings after cleaning
                if not clean_txt or clean_txt.isspace():
                    continue
                nums = re.findall(r'\d+', clean_txt)
                if nums:
                    return nums[0] # Return just the number string
    except Exception:
        pass
    
    return None # Return None if hidden or no number found

# ============================================================
# 🤖 COMMAND HANDLERS
# ============================================================
@bot.message_handler(commands=["start"])
def cmd_start(message):
    bot.send_message(
        message.chat.id,
        "👋 *FB Friend Checker Bot v8*\n\n"
        "📌 *Commands:*\n"
        "• /login — Sign in with your dummy FB account\n"
        "• /check — Paste UIDs (max 50) to check\n"
        "• /status — Verify session is alive\n"
        "• /reset — Kill browser & restart fresh\n",
        parse_mode="Markdown",
    )

@bot.message_handler(commands=["status"])
def cmd_status(message):
    global global_driver
    if global_driver is None:
        bot.send_message(message.chat.id, "🔴 No browser running. Use /login.")
        return
    try:
        url = global_driver.current_url
        alive = is_session_alive(global_driver)
        status = "🟢 LOGGED IN" if alive else "🟡 BROWSER ALIVE BUT NOT LOGGED IN"
        bot.send_message(message.chat.id, f"{status}\n📍 URL: `{url}`", parse_mode="Markdown")
    except Exception as e:
        bot.send_message(message.chat.id, f"🔴 Browser dead: `{e}`", parse_mode="Markdown")

@bot.message_handler(commands=["reset"])
def cmd_reset(message):
    global global_driver
    if global_driver:
        try:
            global_driver.quit()
        except Exception:
            pass
        global_driver = None
    bot.send_message(message.chat.id, "♻️ Browser killed. Use /login to start fresh.")

# ------------------------------------------------------------
# /login — multi-step conversation
# ------------------------------------------------------------
@bot.message_handler(commands=["login"])
def cmd_login(message):
    chat_id = message.chat.id
    if global_driver is not None and is_session_alive(global_driver):
        bot.send_message(chat_id, "✅ Already logged in. Use /check anytime.")
        return
    msg = bot.send_message(chat_id, "📧 Send the dummy FB *email* or phone:", parse_mode="Markdown")
    bot.register_next_step_handler(msg, get_email)

def get_email(message):
    chat_id = message.chat.id
    with credentials_lock:
        user_credentials[chat_id] = {"email": message.text.strip()}
    msg = bot.send_message(chat_id, "🔑 Now send the *password*:", parse_mode="Markdown")
    bot.register_next_step_handler(msg, get_password)

def get_password(message):
    chat_id = message.chat.id
    with credentials_lock:
        user_credentials[chat_id]["password"] = message.text.strip()
    try:
        bot.delete_message(chat_id, message.message_id)
    except Exception:
        pass

    status = bot.send_message(chat_id, "🔄 Launching browser & logging in...")

    try:
        driver = get_driver()
        driver.get("https://mbasic.facebook.com/")

        try:
            wait = WebDriverWait(driver, WAIT_TIMEOUT)
            email_field = wait.until(EC.presence_of_element_located((By.NAME, "email")))
            email_field.send_keys(user_credentials[chat_id]["email"])
            pass_field = driver.find_element(By.NAME, "pass")
            pass_field.send_keys(user_credentials[chat_id]["password"])
            pass_field.send_keys(Keys.RETURN)

            time.sleep(5)
            dismiss_interstitials(driver)
            driver.get("https://mbasic.facebook.com/")
            time.sleep(2)
            dismiss_interstitials(driver)

            if is_session_alive(driver):
                bot.edit_message_text(
                    "✅ *Login Successful!*\n🟢 Session verified via `c_user` cookie.\n🚀 Browser running in background. Use /check anytime.",
                    chat_id, status.message_id, parse_mode="Markdown"
                )
            else:
                current_url = driver.current_url
                bot.edit_message_text(f"❌ *Login Failed.*\n📍 Stuck at: `{current_url}`\n📸 Sending screenshot...", chat_id, status.message_id, parse_mode="Markdown")
                send_debug_screenshot(chat_id, "🔍 *Login failure capture.*")
                # Reset browser on login failure
                global global_driver
                if global_driver:
                    try:
                        global_driver.quit()
                    except Exception:
                        pass
                    global_driver = None

        except TimeoutException:
            if is_session_alive(driver):
                bot.edit_message_text("✅ *Already Logged In!*\n🚀 Use /check anytime.", chat_id, status.message_id, parse_mode="Markdown")
            else:
                bot.edit_message_text("⚠️ Email field not found AND no active session.", chat_id, status.message_id)

    except Exception as e:
        bot.edit_message_text(f"❌ *Login process crashed.*\nError: `{e}`", chat_id, status.message_id, parse_mode="Markdown")
    finally:
        # Clear credentials after login attempt (security)
        with credentials_lock:
            if chat_id in user_credentials:
                del user_credentials[chat_id]


# ------------------------------------------------------------
# /check — UID batch processing with live progress
# ------------------------------------------------------------
@bot.message_handler(commands=["check"])
def cmd_check(message):
    chat_id = message.chat.id
    if global_driver is None or not is_session_alive(global_driver):
        bot.send_message(chat_id, "🔴 Not logged in. Run /login first.")
        return

    msg = bot.send_message(chat_id, f"📋 Paste up to *{MAX_UIDS_PER_BATCH}* UIDs.\nSeparator: space / comma / newline.", parse_mode="Markdown")
    bot.register_next_step_handler(msg, process_uids)

def process_uids(message):
    chat_id = message.chat.id
    uids = parse_uids(message.text)

    if not uids:
        bot.send_message(chat_id, "❌ No valid UIDs found.")
        return

    if len(uids) > MAX_UIDS_PER_BATCH:
        bot.send_message(chat_id, f"⚠️ Truncating to first {MAX_UIDS_PER_BATCH} UIDs.")
        uids = uids[:MAX_UIDS_PER_BATCH]

    driver = get_driver()
    total = len(uids)
    results = []
    debug_sent = False
    start_time = time.time()

    progress = bot.send_message(chat_id, f"🚀 Starting check on *{total}* UIDs...\n⏳ Initializing...", parse_mode="Markdown")

    for idx, uid in enumerate(uids, start=1):
        try:
            driver.get(f"https://mbasic.facebook.com/{uid}")
            time.sleep(PAGE_LOAD_DELAY)

            if "login" in driver.current_url.lower() or not is_session_alive(driver):
                results.append(f"{uid}, SESSION_DROPPED")
                if not debug_sent:
                    send_debug_screenshot(chat_id, "🚨 Session dropped mid-check.")
                    debug_sent = True
                break

            # Execute the smart extraction function
            count = extract_friend_count(driver)

            if count is not None:
                results.append(f"{uid}, {count}")
            else:
                results.append(f"{uid}, Hidden")
                if not debug_sent:
                    send_debug_screenshot(chat_id, f"🔍 First hidden/error UID: `{uid}`")
                    debug_sent = True

        except Exception:
            results.append(f"{uid}, Error")

        # ----- Live progress update -----
        elapsed = time.time() - start_time
        avg_per_uid = elapsed / idx
        eta_sec = int(avg_per_uid * (total - idx))
        eta_min, eta_s = divmod(eta_sec, 60)

        recent = "\n".join(results[-15:]) if results else "⏳ Processing..."
        try:
            bot.edit_message_text(
                f"📊 *Progress:* `{idx}/{total}`\n"
                f"⏱ Elapsed: `{int(elapsed)}s` | ETA: `{eta_min}m {eta_s}s`\n\n"
                f"📝 *Recent (CSV format):*\n```csv\n{recent}\n```",
                chat_id, progress.message_id, parse_mode="Markdown"
            )
        except Exception:
            pass

    # ----- Final summary & CSV Delivery -----
    total_time = int(time.time() - start_time)
    csv_content = "UID, Friends\n" + "\n".join(results)
    
    # Save as actual CSV file
    fname = f"results_{chat_id}_{int(time.time())}.csv"
    try:
        with open(fname, "w", encoding="utf-8") as f:
            f.write(csv_content)
            
        final_text = (
            f"✅ *Batch Complete!*\n"
            f"🔢 Checked: `{len(results)}/{total}`\n"
            f"⏱ Total time: `{total_time}s`\n"
        )

        try:
            # Send the raw text summary
            bot.edit_message_text(final_text, chat_id, progress.message_id, parse_mode="Markdown")
            # Send the file
            with open(fname, "rb") as f:
                bot.send_document(chat_id, f, caption="📂 Here is your CSV file.")
        except Exception:
            bot.send_message(chat_id, final_text, parse_mode="Markdown")
            with open(fname, "rb") as f:
                bot.send_document(chat_id, f, caption="📂 Here is your CSV file.")
    finally:
        # Cleanup
        try:
            if os.path.exists(fname):
                os.remove(fname)
        except OSError:
            pass


# ============================================================
# 🏃 LAUNCH
# ============================================================
if __name__ == "__main__":
    print("=" * 60)
    print("FB Friend Checker Bot v8 — CSV + Resilient Edition")
    print("=" * 60)
    try:
        # Reduced timeouts to prevent hanging dead connections
        bot.infinity_polling(timeout=20, long_polling_timeout=20)
    except KeyboardInterrupt:
        if global_driver:
            try:
                global_driver.quit()
            except Exception:
                pass
