import csv
import datetime
import requests
import os

DISCORD_WEBHOOK_URL = os.environ["DISCORD_WEBHOOK_URL"]
LOG_FILE = "/home/pi/pi_script_log.csv"

def log_result(status, message):
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    payload = {"content": f"**[{status}]** {timestamp}: {message}"}
    try:
        requests.post(DISCORD_WEBHOOK_URL, json=payload, timeout=10)
    except Exception as e:
        print(f"Discord failed: {e}")

    file_exists = os.path.isfile(LOG_FILE)
    with open(LOG_FILE, mode='a', newline='') as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(["Timestamp", "Status", "Message"])
        writer.writerow([timestamp, status, message])

try:
    # MAIN SCRIPT LOGIC GOES HERE
    log_result("I'M ALIVE", "System constraints are holding steady.")

except Exception as e:
    log_result("I FAILED", f"Error encountered: {str(e)}")
