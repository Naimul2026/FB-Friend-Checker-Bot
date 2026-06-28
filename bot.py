import telebot
import time
import random
import os
import re
import shutil # <--- Corrupted Profile ডিলিট করার জন্য যুক্ত করা হয়েছে
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
BOT_TOKEN = "8704185513:AAFf1Yft0Gx_Pk8fEa5YYTSBLQyrVYh203k"
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
    chrome_options.add_argument("--disable-gpu") 
    
    # Facebook Anti-Bot Bypass (যাতে ফেসবুক বুঝতে না পারে এটা বট)
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option('useAutomationExtension', False)
    
    # ভার্চুয়াল প্রোফাইল সেভ করার লোকেশন
    profile_path = os.path.join(os.getcwd(), f"chrome_profile_{chat_id}")
    chrome_options.add_argument(f"--user-data-dir={profile_path}")
    
    chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    
    chrome_options.page_load_strategy = 'eager' 
    
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
        "/reset - Delete corrupted profile if you face any error\n"
    )
    bot.reply_to(message, text)

# --- 3. Reset Corrupted Profile (NEW) ---
@bot.message_handler(commands=['reset'])
def reset_profile(message):
    chat_id = message.chat.id
    profile_path = os.path.join(os.getcwd(), f"chrome_profile_{chat_id}")
    
    bot.send_message(chat_id, "⚙️ Deleting corrupted profile... please wait.")
    
    if os.path.exists(profile_path):
        try:
            shutil.rmtree(profile_path)
            bot.send_message(chat_id, "✅ Your Chrome profile has been successfully deleted! \n\nPlease use /login to create a fresh session.")
        except Exception as e:
            bot.send_message(chat_id, f"❌ Failed to delete profile. A background Chrome process might be locking it.\nError: {e}")
    else:
        bot.send_message(chat_id, "⚠️ No saved profile found to delete.")

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
    
    driver = None
    try:
        driver = setup_driver(chat_id)
        driver.get("https://www.facebook.com/") 
        
        try:
            wait = WebDriverWait(driver, 5) 
            email_field = wait.until(EC.presence_of_element_located((By.NAME, "email")))
            
            email_field.send_keys(user_credentials[chat_id]['email'])
            pass_field = driver.find_element(By.NAME, "pass")
            pass_field.send_keys(user_credentials[chat_id]['password'])
            pass_field.send_keys(Keys.RETURN)
            
            # Login হওয়ার পর Session/Cookies হার্ডডিস্কে সেভ হওয়ার জন্য পর্যাপ্ত সময় দেওয়া হলো
            time.sleep(8) 
            
            bot.send_message(chat_id, "✅ Login Successful & Profile Saved! Ebar apni /check command diye UID send korte paren.")
            
        except TimeoutException:
            bot.send_message(chat_id, "✅ You are ALREADY logged in! Session found. Ebar apni /check command diye UID send korte paren.")
            
    except Exception as e:
        error_msg = f"❌ Login Process Failed!\nError: {e}"
        bot.send_message(chat_id, error_msg)
    finally:
        if driver: 
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

    driver = None
    try:
        raw_text = message.text
        uids = [uid.strip() for uid in re.split(r'[\n\r\s,]+', raw_text) if uid.strip()]
        
        if not uids:
            bot.reply_to(message, "⚠️ No valid UIDs found in your message. Please try /check again.")
            return

        target_uids = uids[:50]
        total_count = len(target_uids)
        
        initial_text = f"⚙️ **Checking Started...**\n⏳ Progress: 0/{total_count} UIDs\n⏱️ Calculating time..."
        status_msg = bot.send_message(chat_id, initial_text)
        
        driver = setup_driver(chat_id)
        result_text = "📊 **Live Result:**\n\n"
        last_edit_time = time.time()
        
        # স্ক্রিনশট মাত্র একবার পাঠানোর জন্য ফ্ল্যাগ সেট করা হলো
        screenshot_sent = False 
        
        for index, uid in enumerate(target_uids):
            url = f"https://www.facebook.com/profile.php?id={uid}" if uid.isdigit() else f"https://www.facebook.com/{uid}"
                
            driver.get(url)
            time.sleep(random.uniform(3.0, 5.0)) # ফেসবুকের রেট লিমিট এড়াতে একটু সময় বাড়ানো হলো
            
            driver.execute_script("window.scrollBy(0, 400);")
            
            friend_text = "Hidden/Error"
            
            combined_xpath = "//a[contains(@href, 'friends') or contains(@href, 'sk=friends')] | //span[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'friends') or contains(text(), 'বন্ধুরা')] | //div[contains(@aria-label, 'Friends')]"
            
            try:
                elements = driver.find_elements(By.XPATH, combined_xpath)
                for el in elements:
                    txt = el.text.strip()
                    if txt and any(char.isdigit() for char in txt) and ("friend" in txt.lower() or "বন্ধু" in txt):
                        friend_text = txt
                        break
            except Exception:
                pass
            
            # Error পেলে শুধু প্রথমবার স্ক্রিনশট পাঠাবে
            if friend_text == "Hidden/Error":
                if not screenshot_sent:
                    try:
                        png_screenshot = driver.get_screenshot_as_png()
                        image_bytes = BytesIO(png_screenshot)
                        image_bytes.name = f"debug_{uid}.png"
                        bot.send_photo(chat_id, image_bytes, caption=f"⚠️ Error view encountered for UID: {uid}\n(Showing screenshot only once to avoid spam)")
                        screenshot_sent = True # ফ্ল্যাগ True করে দেওয়া হলো, যাতে আর ছবি না পাঠায়
                    except Exception:
                        pass 
            
            result_text += f"{uid} -> {friend_text}\n"
            
            current_count = index + 1
            remaining_uids = total_count - current_count
            eta_seconds = remaining_uids * 5.0 
            
            current_time = time.time()
            if (current_time - last_edit_time > 3.0) or (current_count == total_count):
                mins, secs = divmod(int(eta_seconds), 60)
                live_status_text = f"⏳ **Live Progress:** {current_count}/{total_count} UIDs checked.\n⏱️ **ETA:** ~{mins} min {secs} sec remaining...\n\n{result_text}"
                try:
                    bot.edit_message_text(live_status_text, chat_id, status_msg.message_id)
                    last_edit_time = current_time
                except Exception:
                    pass 
                
        final_text = f"✅ **Checking Completed!** ({total_count}/{total_count})\n\n{result_text}"
        try:
            bot.edit_message_text(final_text, chat_id, status_msg.message_id)
        except:
            bot.send_message(chat_id, final_text)
        
    except Exception as e:
        bot.reply_to(message, f"❌ Error processing UIDs: {e}")
    finally:
        if driver:
            driver.quit() 

print("Bot is running securely with Live Progress Tracker...")
bot.infinity_polling()
