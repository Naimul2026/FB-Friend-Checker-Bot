# 🤖 FB Friend Checker Bot

A powerful and efficient Telegram bot built with Python and Selenium to automate the process of checking Facebook friend counts from a list of UIDs. 

Designed to run seamlessly on Linux servers (like AWS EC2) with memory-safe operations and anti-blocking mechanisms.

## ✨ Key Features

* **🛡️ Smart Login System:** Automatically detects active sessions. If you are already logged in, it skips the login process to prevent account flags.
* **⚡ Live Progress Tracker:** Instead of spamming the chat, the bot dynamically edits a single message to show real-time progress, checked UIDs, and the Estimated Time of Arrival (ETA).
* **🧱 Security Bypass:** Uses `mbasic.facebook.com` to bypass heavy JavaScript security pop-ups ("See more on Facebook") and captchas.
* **📸 Memory-Safe Screenshots:** If a UID fails or errors out, the bot takes a screenshot and sends it directly to Telegram using `BytesIO` without saving it to the server's hard drive.
* **📝 Smart Text Input:** No need to upload `.txt` files. Just send UIDs in any format (comma-separated, spaced, or line-by-line), and the bot will parse them automatically (Max 50 at a time).

## 🛠️ Tech Stack

* **Python 3.x**
* **pyTelegramBotAPI** (Telebot)
* **Selenium WebDriver** (Headless Chrome)
* **Webdriver Manager**

## 🚀 Installation & Setup

**1. Clone the repository:**
```bash
git clone [https://github.com/Naimul2026/FB-Friend-Checker-Bot.git](https://github.com/Naimul2026/FB-Friend-Checker-Bot.git)
cd FB-Friend-Checker-Bot
2. Create and activate a Virtual Environment:

Bash
python3 -m venv venv
source venv/bin/activate  # For Linux/Mac
# venv\Scripts\activate   # For Windows
3. Install required dependencies:

Bash
pip install -r requirements.txt
4. Add your Telegram Bot Token:
Open bot.py and replace the placeholder token with your actual bot token from @BotFather:

Python
BOT_TOKEN = "YOUR_BOT_TOKEN_HERE"
💻 Usage
Run the bot using the following command:

Bash
python bot.py
(For 24/7 background running on a Linux server, it is recommended to use screen or tmux).

Telegram Commands
/start - Initialize the bot and see available options.

/login - Provide your fake/throwaway Facebook email and password to create a secure session cookie.

/check - Send your list of UIDs. The bot will start checking and give you a live update.

⚠️ Disclaimer
This tool is built strictly for educational and research purposes. Automated scraping goes against Facebook's Terms of Service. Always use a throwaway or test account. The developer is not responsible for any account bans or misuse of this tool.
