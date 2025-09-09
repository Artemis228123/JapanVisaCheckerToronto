import time
import random
import traceback
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from discord_webhook import DiscordWebhook, DiscordEmbed
from selenium.common.exceptions import TimeoutException

# --- Configuration ---
DISCORD_WEBHOOK_URL = "https://discord.com/api/webhooks/1415007790115721439/KUppjmg4yUTbA-KkzjPbclJOXulgJRF_pYHh6dbPrJmCN0EGl6OnDJ5cXh-GH3t-D5zC"
URL = "https://toronto.rsvsys.jp/reservations/calendar"
CHECK_INTERVAL_MIN = 50  # In seconds
CHECK_INTERVAL_MAX = 70  # In seconds
# --- End Configuration ---

def send_discord_notification(available_dates, month, is_test=False):
    """Sends a notification to Discord."""
    if not DISCORD_WEBHOOK_URL or "YOUR_DISCORD_WEBHOOK_URL" in DISCORD_WEBHOOK_URL:
        print("Discord webhook URL is not set correctly. Skipping notification.")
        return

    webhook = DiscordWebhook(url=DISCORD_WEBHOOK_URL)
    
    if is_test:
        embed = DiscordEmbed(
            title="Checker Script Started!",
            description="Successfully connected. I will now monitor for visa appointments.",
            color="0000ff"  # Blue
        )
    else:
        embed = DiscordEmbed(
            title="Visa Appointment Available!",
            description=f"Found openings in {month} on the following dates: **{', '.join(available_dates)}**",
            color="00ff00"  # Green
        )
        embed.add_embed_field(name="Link", value=f"[Book Now]({URL})")

    webhook.add_embed(embed)
    try:
        response = webhook.execute()
        if response.status_code in [200, 204]:
            print("Discord notification sent successfully!")
        else:
            print(f"Failed to send Discord notification. Status code: {response.status_code}, Response: {response.content}")
    except Exception as e:
        print(f"An error occurred while sending Discord notification: {e}")

def get_available_dates(driver, month_name):
    """Finds and returns a list of available dates for the currently displayed month."""
    available_dates = []
    try:
        # This selector robustly finds the date number inside a cell that has an 'available' circle icon.
        available_cells = driver.find_elements(By.XPATH, "//td[.//img[contains(@src, 'icon_empty.svg')]]//div[contains(@class, 'sc_cal_date')]")
        
        for cell in available_cells:
            day = cell.text.strip()
            if day.isdigit():
                available_dates.append(day)
                
    except Exception as e:
        print(f"Could not check dates for {month_name}. Reason: {e}")
        
    return available_dates

def check_for_openings():
    """Checks the website for available visa appointment openings."""
    options = webdriver.ChromeOptions()
    # Using a non-headless user agent can sometimes help avoid detection
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36")
    options.add_argument("--headless=new") # Use the modern headless mode
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1920,1080") # Set a window size in case of responsive design issues

    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
    
    try:
        print("Navigating to the website...")
        driver.get(URL)
        wait = WebDriverWait(driver, 20)

        # --- Step 1: Open and select 'VISA Application' ---
        print("Opening 'Select a category' modal...")
        wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "#event_select_field > a"))).click()
        
        print("Waiting for 'VISA Application' option to be present...")
        # Wait for the element to exist in the DOM, not necessarily be clickable.
        visa_option_element = wait.until(EC.presence_of_element_located((By.XPATH, "//div[@id='event-select']//label[@for='event-16']")))
        # Use JavaScript to force the click.
        driver.execute_script("arguments[0].click();", visa_option_element)
        
        wait.until(EC.invisibility_of_element_located((By.ID, "event-select")))
        print("Selected 'VISA Application'.")

        # --- Step 2: Open and select 'VISA Application for Canada Travel Document holders' ---
        print("Opening 'Select Application Details' modal...")
        wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "#plan_select_field > a"))).click()

        print("Waiting for 'Canada Travel Document holders' option to be present...")
        # Wait for the element to exist...
        details_option_element = wait.until(EC.presence_of_element_located((By.XPATH, "//div[@id='plan-select']//label[@for='plan-35']")))
        # ...then force the click with JavaScript.
        driver.execute_script("arguments[0].click();", details_option_element)

        wait.until(EC.invisibility_of_element_located((By.ID, "plan-select")))
        print("Selected application details. Calendar should now be visible.")
        
        # --- Step 3: Check current month ---
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, ".c_cal_navex_date .date")))
        month_year_element = driver.find_element(By.CSS_SELECTOR, ".c_cal_navex_date .date")
        current_month = month_year_element.text.replace("\n", " ").strip()
        print(f"Checking for openings in {current_month}...")

        available_dates = get_available_dates(driver, current_month)
        if available_dates:
            print(f"Success! Found available dates in {current_month}: {available_dates}")
            send_discord_notification(available_dates, current_month)
        else:
            print(f"No openings found for {current_month}.")

        # --- Step 4: Go to the next month and check ---
        print("Moving to the next month...")
        next_month_button = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "a.next01.js_change_date")))
        driver.execute_script("arguments[0].click();", next_month_button)
        
        wait.until(EC.not_(EC.text_to_be_present_in_element((By.CSS_SELECTOR, ".c_cal_navex_date .date"), current_month)))
        
        next_month_element = driver.find_element(By.CSS_SELECTOR, ".c_cal_navex_date .date")
        next_month = next_month_element.text.replace("\n", " ").strip()
        print(f"Checking for openings in {next_month}...")
        
        available_dates_next_month = get_available_dates(driver, next_month)
        if available_dates_next_month:
            print(f"Success! Found available dates in {next_month}: {available_dates_next_month}")
            send_discord_notification(available_dates_next_month, next_month)
        else:
            print(f"No openings found for {next_month}.")

    except TimeoutException:
        print("A timeout occurred. An element was not found in time. This might be due to a website change or slow load times.")
        traceback.print_exc()
    except Exception:
        print("An unexpected error occurred during the checking process.")
        traceback.print_exc()
    finally:
        print("Closing the browser.")
        driver.quit()

if __name__ == "__main__":
    send_discord_notification([], "", is_test=True)
    while True:
        check_for_openings()
        sleep_time = random.randint(CHECK_INTERVAL_MIN, CHECK_INTERVAL_MAX)
        print("--------------------------------------------------")
        print(f"Waiting for {sleep_time} seconds before the next check...")
        print("--------------------------------------------------")
        time.sleep(sleep_time)