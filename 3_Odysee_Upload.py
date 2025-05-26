import os
import time
import traceback
from datetime import datetime
import configparser
import shutil
from selenium import webdriver
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.firefox.service import Service
from selenium.webdriver.firefox.options import Options as FirefoxOptions
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys
import xml.etree.ElementTree as ET

ProjRoot_Dir = os.path.dirname(os.path.abspath(__file__))
geckodriver_bin_path = os.path.join(ProjRoot_Dir, "geckodriver")
CompletedUploads_Dir = os.path.join(ProjRoot_Dir, "_CompletedUploads")
UploadQueue_Dir = os.path.join(ProjRoot_Dir, "_UploadQueue")
Meta_Dir = os.path.join(ProjRoot_Dir, "_Meta")
Default_Meta = os.path.join(Meta_Dir, "Default.xml")
Default_Meta_Thumbnail = os.path.join(Meta_Dir, "Thumbnail.png")

CFG_Path = os.path.join(os.path.dirname(__file__), "pjarchive.cfg")
config = configparser.RawConfigParser()
config.read(CFG_Path)
OD_User = config["OD_Credentials"].get("User").strip("'")
OD_Pass = config["OD_Credentials"].get("Password").strip("'")
Log_Dir = os.path.join(ProjRoot_Dir, config["Directories"]["Log_Dir"])

DOWNLOAD_LOG_FILE = os.path.join(Log_Dir, "Download.log")
UPLOAD_LOG_FILE = os.path.join(Log_Dir, "UploadLog.log")
LOG_FILE_NAME = UPLOAD_LOG_FILE  # Define a global variable for the log file name


platform = "windows"
# platform ="linux"
upload_count = 0


def element_interaction(
    driver, by, value, send_keys_value=None, action=None, waitdelay=0
):
    try:
        element = driver.find_element(by, value)
        if action == "sendkeys" and send_keys_value is not None:
            element.send_keys(send_keys_value)
        elif action == "click":
            element.click()

        if waitdelay > 0:
            time.sleep(waitdelay)
        return element
    except Exception as e:
        log_message(f"Element not found: {value} - {e}", LOG_FILE_NAME)
        return None


def Init_OD_Bot(platform):
    try:
        options = FirefoxOptions()
        if platform == "windows":
            service = Service(r"C:\Program Files\Mozilla Firefox\geckodriver.exe")
            options.binary_location = r"C:\Program Files\Mozilla Firefox\firefox.exe"
            options.add_argument("--disable-infobars")
            options.add_argument("--disable-extensions")
            options.add_argument("--disable-popup-blocking")
            options.add_argument("--disable-notifications")
            options.add_argument("--disable-status-bar")

        elif platform == "linux":
            service = Service(r"geckodriver")
            options.binary_location = r"/usr/lib/firefox/firefox"
            options.add_argument("-headless")
        else:
            raise ValueError("Unsupported platform. Use 'windows' or 'linux'.")

        driver = webdriver.Firefox(service=service, options=options)
        Login_OD_Service(driver)
    except Exception as e:
        log_message(f"Failed to initialize RM Bot: {e}", LOG_FILE_NAME)
        print(f"Failed to initialize RM Bot: {e}\n{traceback.format_exc()}")


def Login_OD_Service(driver):
    try:
        time.sleep(4)
        driver.get("https://odysee.com/$/signin")
        time.sleep(4)

        element_interaction(
            driver,
            By.NAME,
            "sign_in_email",
            send_keys_value=OD_User,
            action="sendkeys",
            waitdelay=2,
        )
        login_button = driver.find_element(
            By.XPATH,
            "//button[@aria-label='Log In' and @class='button button--primary' and @type='submit']",
        )
        login_button.click()

        time.sleep(4)

        element_interaction(
            driver,
            By.NAME,
            "sign_in_password",
            send_keys_value=OD_Pass,
            action="sendkeys",
            waitdelay=2,
        )

        continue_button = driver.find_element(
            By.XPATH,
            "//button[@aria-label='Continue' and @class='button button--primary' and @type='submit']",
        )
        continue_button.click()

        log_message(f"Login to OD Service Successful", LOG_FILE_NAME)
        Bulk_Upload_Videos(driver)
    except Exception as e:
        log_message(f"Failed to login to OD Service: {e}", LOG_FILE_NAME)
        print(f"Failed to login to OD Service: {e}\n{traceback.format_exc()}")


def Bulk_Upload_Videos(driver):
    global upload_count
    while True:
        upload_index = get_upload_file_index("oduploadindex")
        prefix = str(upload_index).zfill(2)
        log_message(f"Next Upload based on files starting with {prefix}", LOG_FILE_NAME)
        if upload_index is None:
            log_message(f"Unable to Get Upload File Index", LOG_FILE_NAME)
            break

        if upload_count == 0:
            # Get the next file to upload
            upload_index = get_upload_file_index("oduploadindex")
        files_to_upload = [
            f
            for f in os.listdir(CompletedUploads_Dir)
            if f.startswith(prefix + " ") and f.endswith(".mp4")
        ]

        if not files_to_upload:
            log_message(f"Next Upload file {file} Not Found, Exiting", LOG_FILE_NAME)
            break

        for file in files_to_upload:
            Upload_Video(driver, file)


def Upload_Video(driver, file):
    try:
        description = read_value_from_meta("Description")
        filepath = os.path.join(CompletedUploads_Dir, file)
        Title = file.replace(".mp4", "")
        log_message(f"Uploading {file} to Odysee...", LOG_FILE_NAME)
        driver.get("https://odysee.com/$/upload")
        time.sleep(2)

        # Locate the hidden file input element (if accessible)
        file_input = driver.find_element(By.CSS_SELECTOR, 'input[type="file"]')
        file_input.send_keys(filepath)

        time.sleep(1)
        thumbnail_button = driver.find_element(
            By.XPATH, "//button[@aria-label='Enter a thumbnail URL']"
        )
        driver.execute_script("arguments[0].click();", thumbnail_button)

        time.sleep(1)
        element_interaction(
            driver,
            By.NAME,
            "content_thumbnail",
            send_keys_value="https://ia800806.us.archive.org/2/items/peter-faik-incel-abuser/Thumbnail.png",
            action="sendkeys",
            waitdelay=1,
        )

        element_interaction(
            driver,
            By.ID,
            "content_description",
            send_keys_value=description,
            action="sendkeys",
            waitdelay=1,
        )
        element_interaction(
            driver,
            By.CLASS_NAME,
            "tag__input",
            send_keys_value="peter, faik, incel,peter faik, xxxiiixxx, pjwins, xxxiiixxx1404, itzpjx, pfaik7, pj.faik.9, thechosenon1991111, foundmymumma, misogynist, abuser",
            action="sendkeys",
            waitdelay=1,
        )

        # Scroll to the bottom of the page
        driver.find_element(By.TAG_NAME, "body").send_keys(Keys.END)
        time.sleep(1)  # Allow time for any lazy-loaded elements to appear
        # Click the "Upload" button
        upload_button = driver.find_element(
            By.XPATH,
            "//button[@aria-label='Upload' and contains(@class, 'button--primary')]",
        )
        upload_button.click()
        time.sleep(1)
        # Click the "Confirm" button
        confirm_button = driver.find_element(
            By.XPATH,
            "//button[@aria-label='Confirm' and contains(@class, 'button--primary')]",
        )
        confirm_button.click()

        input("Press Enter to continue...")
        time.sleep(1)
        log_message(f"Completed File upload", LOG_FILE_NAME)

        # increment index by 1 on successful upload
        increment_upload_file_index("oduploadindex")
    except Exception as e:
        log_message(f"Failed to upload {file}: {e}", LOG_FILE_NAME)
        print(f"Failed to upload {file}: {e}\n{traceback.format_exc()}")


def log_message(message, log_file_name):
    """Log a message with a timestamp to the specified log file."""
    if not message or "[wait]" in message:
        return
    print(message)
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    try:
        # Ensure the log file exists
        if not os.path.exists(log_file_name):
            open(log_file_name, "w").close()
        with open(log_file_name, "a") as log_file:
            log_file.write(f"{timestamp} - {message}\n")
    except Exception as e:
        print(f"Failed to log message: {e}\n{traceback.format_exc()}")


def read_value_from_meta(xpath):
    try:
        tree = ET.parse(Default_Meta)
        root = tree.getroot()
        value = root.find(xpath)
        return value.text
    except Exception as e:
        log_message(f"Failed to read value from meta: {e}", LOG_FILE_NAME)
        print(f"Failed to read value from meta: {e}\n{traceback.format_exc()}")
        return None


def get_upload_file_index(specified_index):
    """Read the current value of specified specified index from the config."""
    try:
        config.read(CFG_Path)
        return int(config["Upload_Index"][specified_index])
    except Exception as e:
        log_message(
            f"Failed to get {specified_index}: {e}\n{traceback.format_exc()}",
            DOWNLOAD_LOG_FILE,
        )
        return None


def increment_upload_file_index(specified_index):
    """Increment the value of specified specified index by one and save it to the config."""
    try:
        config.read(CFG_Path)
        oduploadindex = int(config["Upload_Index"][specified_index])
        oduploadindex += 1
        new_index = str(oduploadindex)
        config["Upload_Index"][specified_index] = new_index
        with open(CFG_Path, "w") as Cfg:
            config.write(Cfg)
    except Exception as e:
        log_message(
            f"Failed to increment {specified_index}: {e}\n{traceback.format_exc()}",
            DOWNLOAD_LOG_FILE,
        )


# Define platform above
Init_OD_Bot(platform)
