import telebot
import time
import random
import os
import re
from io import BytesIO
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys
from selenium.common.exceptions import TimeoutException
from webdriver_manager.chrome import ChromeDriverManager

# 1. এখানে আপনার Telegram Bot Token দিন
BOT_TOKEN = ""
bot = telebot.TeleBot(BOT_TOKEN)

user_states = {}
user_credentials = {}

# --- Selenium Setup Function ---
def setup_driver(chat_id):
    chrome_options = Options()
    chrome_options.add_argument("--headless=new") 
    chrome_options.add_argument("--disable-notifications")
    chrome_options.add_argument("--window-size=1920,1080")
    
    # লিনাক্স সার্ভারের জন্য অতি গুরুত্বপূর্ণ ফ্ল্যাগ
    chrome_options.add_argument("--no-sandbox") 
    chrome_options.add_argument("--disable-dev-shm-usage")
    
    # ভার্চুয়াল প্রোফাইল সেভ করার লোকেশন
    profile_path = os.path.join(os.getcwd(), f"chrome_profile_{chat_id}")
    chrome_options.add_argument(f"--user-data-dir={profile_path}")
    
    chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)
    return driver

# --- Bot Handlers ---
@bot.message_handler(commands=['start'])
def send_welcome(message):
    text = (
        "Welcome to FB Friend Checker Bot! 🤖\n\n"
        "Options:\n"
        "/login - Login to your fake FB account\n"
        "/check - Send UIDs as text to check (Max 50)\n"
    )
    bot.reply_to(message, text)

# --- 1. Login Process (Smart Login) ---
@bot.message_handler(commands=['login'])
def login_start(message):
    chat_id = message.chat.id
    user_states[chat_id] = 'waiting_for_email'
    bot.send_message(chat_id, "Please send your Fake FB Email/Number:")

@bot.message_handler(func=lambda message: user_states.get(message.chat.id) == 'waiting_for_email')
def get_email(message):
    chat_id = message.chat.id
    user_credentials[chat_id] = {'email': message.text}
    user_states[chat_id] = 'waiting_for_password'
    bot.send_message(chat_id, "Now send the Password:")

@bot.message_handler(func=lambda message: user_states.get(message.chat.id) == 'waiting_for_password')
def get_password(message):
    chat_id = message.chat.id
    user_credentials[chat_id]['password'] = message.text
    user_states[chat_id] = 'normal' 
    
    bot.send_message(chat_id, "Checking login status... Please wait ⏳")
    
    try:
        driver = setup_driver(chat_id)
        driver.get("https://www.facebook.com/") 
        
        try:
            wait = WebDriverWait(driver, 10)
            email_field = wait.until(EC.presence_of_element_located((By.NAME, "email")))
            
            email_field.send_keys(user_credentials[chat_id]['email'])
            pass_field = driver.find_element(By.NAME, "pass")
            pass_field.send_keys(user_credentials[chat_id]['password'])
            pass_field.send_keys(Keys.RETURN)
            
            time.sleep(10) 
            bot.send_message(chat_id, "✅ Login Successful & Profile Saved! Ebar apni /check command diye UID send korte paren.")
            
        except TimeoutException:
            bot.send_message(chat_id, "✅ You are ALREADY logged in! Session found. Ebar apni /check command diye UID send korte paren.")
            
        driver.quit()
        
    except Exception as e:
        error_msg = f"❌ Login Process Failed!\nError: {e}"
        bot.send_message(chat_id, error_msg)
        if 'driver' in locals(): 
            driver.quit()

# --- 2. Check UIDs from Text Message (With LIVE Progress) ---
@bot.message_handler(commands=['check'])
def check_start(message):
    chat_id = message.chat.id
    user_states[chat_id] = 'waiting_for_uids'
    bot.send_message(chat_id, "📝 Please send your UIDs here.\n(You can paste them line by line, or separated by spaces/commas. Max 50):")

@bot.message_handler(func=lambda message: user_states.get(message.chat.id) == 'waiting_for_uids')
def process_uids_text(message):
    chat_id = message.chat.id
    user_states[chat_id] = 'normal' 
    
    profile_path = os.path.join(os.getcwd(), f"chrome_profile_{chat_id}")
    
    if not os.path.exists(profile_path):
        bot.reply_to(message, "⚠️ Age /login kore apna fake ID set korun.")
        return

    try:
        raw_text = message.text
        uids = [uid.strip() for uid in re.split(r'[\n\r\s,]+', raw_text) if uid.strip()]
        
        if not uids:
            bot.reply_to(message, "⚠️ No valid UIDs found in your message. Please try /check again.")
            return

        target_uids = uids[:50]
        total_count = len(target_uids)
        
        # লাইভ আপডেট মেসেজ তৈরি করা
        initial_text = f"⚙️ **Checking Started...**\n⏳ Progress: 0/{total_count} UIDs\n⏱️ Calculating time..."
        status_msg = bot.send_message(chat_id, initial_text)
        
        driver = setup_driver(chat_id)
        result_text = "📊 **Live Result:**\n\n"
        
        for index, uid in enumerate(target_uids):
            if uid.isdigit():
                url = f"https://www.facebook.com/profile.php?id={uid}"
            else:
                url = f"https://www.facebook.com/{uid}"
                
            driver.get(url)
            time.sleep(random.uniform(4.0, 6.0)) 
            
            driver.execute_script("window.scrollBy(0, 400);")
            time.sleep(2)
            
            friend_text = "Hidden/Error"
            
            xpaths = [
                "//a[contains(@href, 'friends')]", 
                "//a[contains(@href, 'sk=friends')]",
                "//span[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'friends')]",
                "//span[contains(text(), 'বন্ধুরা')]",
                "//div[contains(@aria-label, 'Friends')]"
            ]
            
            for xpath in xpaths:
                try:
                    elements = driver.find_elements(By.XPATH, xpath)
                    for el in elements:
                        txt = el.text.strip()
                        if txt and any(char.isdigit() for char in txt) and ("friend" in txt.lower() or "বন্ধু" in txt):
                            friend_text = txt
                            break
                    if friend_text != "Hidden/Error": break
                except:
                    continue
            
            if friend_text == "Hidden/Error":
                png_screenshot = driver.get_screenshot_as_png()
                image_bytes = BytesIO(png_screenshot)
                image_bytes.name = f"debug_{uid}.png"
                try:
                    bot.send_photo(chat_id, image_bytes, caption=f"⚠️ Error view for UID: {uid}")
                except Exception as img_err:
                    pass # ইমেজ পাঠাতে সমস্যা হলে স্কিপ করবে
            
            result_text += f"{uid} -> {friend_text}\n"
            
            # --- Live Progress Update Logic ---
            current_count = index + 1
            remaining_uids = total_count - current_count
            
            # প্রতি আইডিতে গড়ে ৮.৫ সেকেন্ড সময় ধরে হিসাব করা
            eta_seconds = remaining_uids * 8.5 
            mins = int(eta_seconds // 60)
            secs = int(eta_seconds % 60)
            
            live_status_text = f"⏳ **Live Progress:** {current_count}/{total_count} UIDs checked.\n⏱️ **ETA:** ~{mins} min {secs} sec remaining...\n\n{result_text}"
            
            # আগের মেসেজটি এডিট করে নতুন ডেটা বসানো
            try:
                bot.edit_message_text(live_status_text, chat_id, status_msg.message_id)
            except Exception:
                pass # যদি কোনো কারণে এডিট ফেইল হয়, বট ক্র্যাশ না করে কাজ চালিয়ে যাবে
            
            if index % 10 == 0 and index != 0:
                time.sleep(8)
                
        driver.quit()
        
        # একদম শেষে ফাইনাল মেসেজ আপডেট
        final_text = f"✅ **Checking Completed!** ({total_count}/{total_count})\n\n{result_text}"
        try:
            bot.edit_message_text(final_text, chat_id, status_msg.message_id)
        except:
            bot.send_message(chat_id, final_text)
        
    except Exception as e:
        bot.reply_to(message, f"❌ Error processing UIDs: {e}")
        if 'driver' in locals():
            driver.quit()

print("Bot is running securely with Live Progress Tracker...")
bot.infinity_polling()