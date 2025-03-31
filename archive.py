import os
import subprocess
import traceback
from datetime import datetime
import pexpect
import asyncio
import configparser
import shutil
import urllib.request

ProjRoot_Dir = os.path.dirname(os.path.abspath(__file__))
CFG_Path = os.path.join(ProjRoot_Dir, "archive.cfg")
config = configparser.RawConfigParser()
config.read(CFG_Path)

# Define path variables
UploadQueue_Dir = os.path.join(ProjRoot_Dir, config["Directories"]["UploadQueue_Dir"])
DownloadQueue_Dir = os.path.join(
    ProjRoot_Dir, config["Directories"]["DownloadQueue_Dir"]
)
CompletedUploads_Dir = os.path.join(
    ProjRoot_Dir, config["Directories"]["CompletedUploads_Dir"]
)
MetaData_Dir = os.path.join(ProjRoot_Dir, config["Directories"]["MetaData_Dir"])
Log_Dir = os.path.join(ProjRoot_Dir, config["Directories"]["Log_Dir"])
DOWNLOAD_LOG_FILE = os.path.join(Log_Dir, "Download.log")
UPLOAD_LOG_FILE = os.path.join(Log_Dir, "UploadLog.log")
IA_LastSessionTime = None

ia_path = os.path.join(ProjRoot_Dir, "ia")

# Read credentials and settings from the config file
IA_Email = config["IA_Credentials"]["Email"]
IA_Password = config["IA_Credentials"]["Password"].strip("'")
IA_ItemID = config["IA_Settings"]["UploadItemID"].strip("'")

YT_Source = config["YT_Sources"]["Source1"]

DownloadFilePrefix = config["YT_DownloadSettings"]["DownloadFilePrefix1"]
DownloadTimeStampFormat = config["YT_DownloadSettings"]["DownloadTimeStampFormat1"]
YTUploadIndex = config["Upload_Index"]["YTUploadIndex"]
BCUploadIndex = config["Upload_Index"]["BCUploadIndex"]


def create_log_files():
    """Create log files if they do not exist."""
    for log_file in [DOWNLOAD_LOG_FILE, UPLOAD_LOG_FILE]:
        log_file_path = os.path.join(Log_Dir, log_file)
        if not os.path.exists(log_file_path):
            open(log_file_path, "w").close()


def Download_WebTools():
    """Install and update the latest yt-dlp from Alpine Linux APK."""
    try:
        # Install or update the ia tool
        ia_url = "https://archive.org/download/ia-pex/ia"
        urllib.request.urlretrieve(ia_url, ia_path)
        os.chmod(ia_path, 0o755)  # Make the file executable
        log_message("Downloaded and updated the ia tool.", UPLOAD_LOG_FILE)

        # Install or update yt-dlp using Alpine Linux APK
        subprocess.run(["apk", "add", "--no-cache", "yt-dlp"], check=True)
        log_message(
            "Installed and updated yt-dlp using Alpine Linux APK.", UPLOAD_LOG_FILE
        )

    except Exception as e:
        log_message(
            f"Failed to install or update tools: {e}\n{traceback.format_exc()}",
            UPLOAD_LOG_FILE,
        )


async def run_subprocess(
    command_str, log_file, called_process_error_msg, exception_msg
):
    "Run a subprocess command and log the output."

    log_message(f"Running command: {' '.join(command_str)}", log_file)
    try:
        # Set environment variable to force unbuffered output
        env = os.environ.copy()
        env["PYTHONUNBUFFERED"] = "1"

        # Use subprocess with unbuffered output
        process = await asyncio.create_subprocess_shell(
            " ".join(command_str),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env,
        )

        # Read stdout and stderr line by line in real-time
        async def read_stream(stream, log_file):
            while True:
                line = await stream.readline()
                if line:
                    log_message(line.decode().strip(), log_file)
                else:
                    break

        await asyncio.gather(
            read_stream(process.stdout, log_file),
            read_stream(process.stderr, log_file),
        )

        # Wait for the process to complete
        await process.wait()

        # Check if the process exited with a non-zero status
        if process.returncode != 0:
            log_message(f"{called_process_error_msg} : {process.returncode}", log_file)
    except Exception as e:
        log_message(f"{exception_msg} : {e}\n{traceback.format_exc()} ", log_file)


async def download_videos():
    """Run yt-dlp to download live videos."""
    while True:
        try:
            # Read the current value of YTUploadIndex from the config
            YTFileIndex = get_upload_file_index("YTUploadIndex")

            CurrentDownloadFile = (
                f"{YTFileIndex} {DownloadFilePrefix} {DownloadTimeStampFormat}"
            )
            log_message(f"Starting YT-DLP Monitor for {YT_Source}", DOWNLOAD_LOG_FILE)

            command = [
                "yt-dlp",
                f"--paths temp:{DownloadQueue_Dir}",
                "--output",
                f'"{CurrentDownloadFile}"',
                "--wait-for-video",
                "10-60",
                "--live-from-start",
                YT_Source,
            ]
            await run_subprocess(
                command,
                DOWNLOAD_LOG_FILE,
                "yt-dlp command failed",
                "Exception in run_yt_dlp",
            )

            # Move downloaded files to UploadQueue_Dir
            for file in os.listdir(ProjRoot_Dir):
                if file.endswith((".mp4", ".mkv", ".mov", ".webm", ".html5", ".avi")):
                    log_message(f"Trying to move {file} to {UploadQueue_Dir} for upload ", UPLOAD_LOG_FILE)
                    shutil.move(os.path.join(ProjRoot_Dir, file), UploadQueue_Dir)

            log_message(f"Trying to increment download index  ", DOWNLOAD_LOG_FILE)
            # Increment the YTUploadIndex and write it back to the config
            increment_upload_file_index("YTUploadIndex")
            
            log_message(f"incremented download index successfully ", DOWNLOAD_LOG_FILE)

        except Exception as e:
            log_message(
                f"Exception in download_videos: {e}\n{traceback.format_exc()}",
                DOWNLOAD_LOG_FILE,
            )
        await asyncio.sleep(10)


async def UploadToIA(filepath):
    """Upload a video file to Internet Archive."""
    try:
        await login_ia_session(IA_Email, IA_Password)
        log_message(
            f"Attempting archive of file: {filepath} to InternetArchive",
            UPLOAD_LOG_FILE,
        )

        command = [
            "ia",
            "upload",
            f"{IA_ItemID}",
            f'"{filepath}"',
            "--retries",
            "10",
        ]

        await run_subprocess(
            command,
            UPLOAD_LOG_FILE,
            "IA archive command failed",
            "Exception in IA",
        )

        await asyncio.sleep(60)
    except (pexpect.exceptions.ExceptionPexpect, OSError) as e:
        log_message(
            f"Exception in UploadToIA: {e}\n{traceback.format_exc()}",
            UPLOAD_LOG_FILE,
        )


async def upload_videos():
    while True:
        try:
            for file in os.listdir(UploadQueue_Dir):
                if file.endswith(".mp4"):
                    filepath = os.path.join(UploadQueue_Dir, file)
                    await UploadToIA(filepath)
                    log_message(
                        f"Completed upload of file: {file} to video hosts",
                        UPLOAD_LOG_FILE,
                    )
                    shutil.move(filepath, os.path.join(CompletedUploads_Dir, file))

        except Exception as e:
            log_message(
                f"Exception in upload_videos: {e}\n{traceback.format_exc()}",
                UPLOAD_LOG_FILE,
            )
        await asyncio.sleep(10)


async def login_ia_session(email, password):
    """Login to Internet Archive session."""
    global IA_LastSessionTime
    current_time = datetime.now()

    if (
        IA_LastSessionTime
        and (current_time - IA_LastSessionTime).total_seconds() < 86400
    ):
        log_message(
            "Login attempt skipped. Already logged in within the last 24 hours.",
            UPLOAD_LOG_FILE,
        )
        return

    try:
        child = pexpect.spawn("ia configure")
        child.expect("Email address: ")
        child.sendline(email)
        child.expect("Password:")
        child.sendline(password)
        child.expect(pexpect.EOF)
        log_message(
            "Internet Archive session established successfully.", UPLOAD_LOG_FILE
        )
        IA_LastSessionTime = current_time
    except pexpect.exceptions.ExceptionPexpect as e:
        log_message(
            f"Failed to establish Internet Archive session: {e}\n{traceback.format_exc()}",
            UPLOAD_LOG_FILE,
        )


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


def get_upload_file_index(specified_index):
    """Read the current value of specified DownloadFileIndex from the config."""
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
    """Increment the value of specified DownloadFileIndex by one and save it to the config."""
    try:
        config.read(CFG_Path)
        DownloadFileIndex = int(config["Upload_Index"][specified_index])
        DownloadFileIndex += 1
        new_index = str(DownloadFileIndex)
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


async def main():
    try:
        create_log_files()
        # Download the ia tool
        Download_WebTools()

        # Start the download and upload tasks
        download_task = asyncio.create_task(download_videos())
        upload_task = asyncio.create_task(upload_videos())

        # Wait for both tasks to complete
        await asyncio.gather(download_task, upload_task)
    except Exception as e:
        log_message(
            f"Exception in main: {e}\n{traceback.format_exc()}", DOWNLOAD_LOG_FILE
        )
        log_message(
            f"Exception in main: {e}\n{traceback.format_exc()}", UPLOAD_LOG_FILE
        )


# Run the main function
asyncio.run(main())
