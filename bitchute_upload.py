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
import xml.etree.ElementTree as ET

ProjRoot_Dir = os.path.dirname(os.path.abspath(__file__))
geckodriver_bin_path = os.path.join(ProjRoot_Dir, "geckodriver")
CompletedUploads_Dir = os.path.join(ProjRoot_Dir, "_CompletedUploads")
UploadQueue_Dir = os.path.join(ProjRoot_Dir, "_UploadQueue")
Meta_Dir = os.path.join(ProjRoot_Dir, "_Meta")
Default_Meta = os.path.join(Meta_Dir, "Default.xml")
Default_Meta_Thumbnail = os.path.join(Meta_Dir, "Thumbnail.png")

CFG_Path = os.path.join(os.path.dirname(__file__), "archive.cfg")
config = configparser.RawConfigParser()
config.read(CFG_Path)
BC_User = config["BC_Credentials"].get("User").strip("'")
BC_Pass = config["BC_Credentials"].get("Password").strip("'")
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


def Init_BC_Bot(platform):
    try:
        options = FirefoxOptions()
        if platform == "windows":
            service = Service(r"C:\Program Files\Mozilla Firefox\geckodriver.exe")
            options.binary_location = r"C:\Program Files\Mozilla Firefox\firefox.exe"
        elif platform == "linux":
            service = Service(r"geckodriver")
            options.binary_location = r"/usr/lib/firefox/firefox"
            options.add_argument("-headless")
        else:
            raise ValueError("Unsupported platform. Use 'windows' or 'linux'.")

        driver = webdriver.Firefox(service=service, options=options)
        Login_BC_Service(driver)
    except Exception as e:
        log_message(f"Failed to initialize BC Bot: {e}", LOG_FILE_NAME)
        print(f"Failed to initialize BC Bot: {e}\n{traceback.format_exc()}")


def Login_BC_Service(driver):
    try:
        time.sleep(4)
        driver.get("https://account.bitchute.com/login/")
        time.sleep(4)
        element_interaction(
            driver,
            By.NAME,
            "username",
            send_keys_value=BC_User,
            action="sendkeys",
            waitdelay=2,
        )
        element_interaction(
            driver,
            By.NAME,
            "password",
            send_keys_value=BC_Pass,
            action="sendkeys",
            waitdelay=2,
        )
        element_interaction(driver, By.ID, "id_submit", action="click", waitdelay=3)
        # Navigate to the main page to close dumb banners
        driver.get("https://bitchute.com/")
        element_interaction(
            driver,
            By.CSS_SELECTOR,
            'a[href="https://old.bitchute.com/oauth/login/chutenetwork"]',
            action="click",
            waitdelay=3,
        )
        element_interaction(
            driver,
            By.CSS_SELECTOR,
            'input[type="submit"].button1[name="allow"][value="Okay"]',
            action="click",
            waitdelay=3,
        )
        Bulk_Upload_Videos(driver)
    except Exception as e:
        log_message(f"Failed to login to BC Service: {e}", LOG_FILE_NAME)
        print(f"Failed to login to BC Service: {e}\n{traceback.format_exc()}")


def Bulk_Upload_Videos(driver):
    global upload_count
    while True:
        upload_index = get_upload_file_index("bcuploadindex")
        if upload_index is None:
            log_message(f"Unable to Get Upload File Index", LOG_FILE_NAME)
            break

        if upload_count == 0:
            #increment index by 1 as we are going to upload the next file in the series
            increment_upload_file_index("bcuploadindex")
        # Get the next file to upload
        upload_index = get_upload_file_index("bcuploadindex")
        prefix = str(upload_index)
        files_to_upload = [
            f
            for f in os.listdir(CompletedUploads_Dir)
            if f.startswith(prefix) and f.endswith(".mp4")
        ]

        if not files_to_upload:
            log_message(f"Next Upload file {file} Not Found, Exiting", LOG_FILE_NAME)
            break

        for file in files_to_upload:
            Upload_Video(driver, file)
            increment_upload_file_index("bcuploadindex")
            upload_count += 1


def Upload_Video(driver, file):
    try:
        description = read_value_from_meta("Description")
        filepath = os.path.join(CompletedUploads_Dir, file)
        Title = file.replace(".mp4", "")
        log_message(f"Uploading {file} to BitChute...", LOG_FILE_NAME)
        driver.get("https://old.bitchute.com/channel/fCADpgwnG33Z/upload/")
        time.sleep(6)

        element_interaction(
            driver,
            By.ID,
            "title",
            send_keys_value=Title,
            action="sendkeys",
            waitdelay=2,
        )
        element_interaction(
            driver,
            By.ID,
            "description",
            send_keys_value=description,
            action="sendkeys",
            waitdelay=2,
        )
        element_interaction(
            driver,
            By.ID,
            "hashtags",
            send_keys_value="Peter Faik Incel",
            action="sendkeys",
            waitdelay=2,
        )
        element_interaction(
            driver,
            By.NAME,
            "thumbnailInput",
            send_keys_value=Default_Meta_Thumbnail,
            action="sendkeys",
            waitdelay=2,
        )
        element_interaction(
            driver,
            By.NAME,
            "videoInput",
            send_keys_value=filepath,
            action="sendkeys",
            waitdelay=2,
        )

        log_message(f"Waiting For Upload To Complete", LOG_FILE_NAME)
        # Wait for the upload to complete
        WebDriverWait(driver, 600).until(
            EC.text_to_be_present_in_element(
                (By.CLASS_NAME, "filepond--file-status-main"), "Upload complete"
            )
        )

        log_message(f"Upload Complete: Publishing.", LOG_FILE_NAME)
        time.sleep(4)
        # Locate the button by XPath and click it
        element_interaction(
            driver,
            By.XPATH,
            "/html/body/div[1]/form/div/div[2]/div[6]/button",
            action="click",
            waitdelay=6,
        )
        time.sleep(30)
        log_message(f"Waiting To Navigate to Next Page...", LOG_FILE_NAME)
        log_message(f"Completed File upload", LOG_FILE_NAME)
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
        log_message(
            f"Current {specified_index}: {config['Upload_Index'][specified_index]}",
            DOWNLOAD_LOG_FILE,
        )
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
        bcuploadindex = int(config["Upload_Index"][specified_index])
        bcuploadindex += 1
        new_index = str(bcuploadindex)
        log_message(
            f"Incremented {specified_index} to : {new_index}", DOWNLOAD_LOG_FILE
        )
        config["Upload_Index"][specified_index] = new_index
        with open(CFG_Path, "w") as Cfg:
            config.write(Cfg)
    except Exception as e:
        log_message(
            f"Failed to increment {specified_index}: {e}\n{traceback.format_exc()}",
            DOWNLOAD_LOG_FILE,
        )
        
#Define platform above
Init_BC_Bot(platform)