#!/usr/bin/python3

import argparse
import glob
import os
import shutil
import datetime
import subprocess
import smtplib
import signal
import sys
import select
import urllib
import configparser
import psutil

LOG_FILE = os.path.join(os.environ["HOME"], ".rsync-queue.log")

# These variables are global because they are accessed from
# signal_term_handler when the process is terminated
LAST_PROGRESS_LINE = None
FILE_PATH = None


def print_example_config_file():
    print("Example config file to be saved in:", )
    config_file = """[General]
notification_email_from=uploader@ace-expedition.net
notification_email_to=data@ace-expedition.net
rsync_bwlimit=10k
base_url = http://ace-expedition.net/uploaded/misc/
"""
    print(config_file)


def read_config(key):
    cp = configparser.ConfigParser()
    path = os.path.join(os.getenv("HOME"), ".config", "rsync-uploader.conf")
    result = cp.read(path)

    if result == []:
        print_example_config_file()
        sys.exit(1)

    value = cp.get("General", key)

    return value


def size_mb_formatted(file_path):
    size_mb = os.path.getsize(FILE_PATH) / 1024 / 1024
    size_mb = "{:.3f}".format(size_mb)

    return size_mb


def signal_term_handler(signal, frame):
    log("SIGTERM received")
    send_mail_last_progress()

    # Kills rsync / any subprocess
    process = psutil.Process()
    for proc in process.children(recursive=True):
        proc.kill()

    sys.exit(0)


def update_progress(line):
    global LAST_PROGRESS_LINE

    if "%" in line:
        LAST_PROGRESS_LINE = line
        log("Progress update file '{}': {}".format(FILE_PATH, LAST_PROGRESS_LINE))


def execute_rsync(cmd, abort_if_fails=False, log_command=False):
    if log_command:
        command = ""
        for argument in cmd:
            command += '"{}" '.format(argument)

        log("Execute: {}".format(command))

    proc = subprocess.Popen(cmd, bufsize=1,
                            stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE,
                            universal_newlines=True)

    RSYNC_PID = proc.pid

    while True:
        reads = [proc.stdout.fileno(), proc.stderr.fileno()]

        # Waits that stdout or stderr are ready to be read
        (read_fd, _, _) = select.select(reads, [], [], 1) # 1 is 1 second timeout

        for fd in read_fd:
            if fd == proc.stdout.fileno():
                line = proc.stdout.readline()
                line = line.replace("\r", "\n") # --progress uses \r
                line = line.strip()

                log("O: {}".format(line))
                update_progress(line)

            elif fd == proc.stderr.fileno():
                line = proc.stderr.readline()
                line = line.strip()

                log("E: {}".format(line))


        # Updates proc.returncode()read
        proc.poll()

        if proc.returncode is not None:
            break

    retval = proc.returncode

    if retval != 0 and abort_if_fails:
        print("Command: _{}_ failed, aborting...".format(cmd))
        exit(1)

    return retval


def log(text):
    print(text)
    f = open(LOG_FILE, "a")
    date_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    f.write("{}: {}\n".format(date_time, text))
    f.close()


def rsync(origin, destination):
    global FILE_PATH
    FILE_PATH = origin

    ssh_options = ['-e', 'ssh -o ConnectTimeout=120 -o ServerAliveInterval=120']
    rsync_options = ["-vtaz", "--progress", "--inplace", "--timeout=120", "--bwlimit={}".format(read_config('rsync_bwlimit'))]

    while True:
        retval = execute_rsync(["rsync"] + ssh_options + rsync_options + [origin] + [destination], log_command = True)
        if retval == 0:
            log("It finished uploading the file: {}".format(origin))
            break
        else:
            log("It seems that it timed out - will try again")

    return True


def file_pending_to_upload(directory):
    return len(files_in_a_directory(directory)) > 0


def files_in_a_directory(directory):
    files = []

    for f in glob.glob(os.path.join(directory, "*")):
        if os.path.isfile(f):
            files.append(f)

    return files


def move_next_file(source, destination):
    # Returns True if a file has been moved. False if there aren't more files
    files = files_in_a_directory(source)

    files.sort()

    if len(files) > 0:
        log("Moving file from {} to {}".format(files[0], destination))
        os.makedirs(destination, exist_ok=True)
        shutil.move(files[0], destination)
        return True

    log("No more files to upload.")
    return False


def send_mail(message):
    file_name = os.path.basename(FILE_PATH)
    size_mb = size_mb_formatted(FILE_PATH)
    url = "{}/{}".format(read_config('base_url'), urllib.parse.quote(file_name))

    d = {'file_name': file_name,
         'file_path': FILE_PATH,
         'last_progress': LAST_PROGRESS_LINE,
         'url': url,
         'size_mb': size_mb,
         'from': read_config('notification_email_from')}

    message = message.format(**d)

    s = smtplib.SMTP("localhost")
    tolist = [read_config('notification_email_to')]

    log("Sending email: {}".format(message))
    s.sendmail("uploader@ace-expedition.net", tolist, message)
    s.quit()


def send_mail_last_progress():
    message = """From: {from}
Subject: file uploader progress {file_name}

The file "{file_path}" [{size_mb} MB] was being uploaded but the uploader has been killed.

The last progress line from rsync is:
{last_progress}
Size of the file: {size_mb} MB


"""
    send_mail(message)

def send_mail_file_uploaded(file_path):
    message = """From: {from}
Subject: file uploaded: {file_name}

The file {file_name} has been uploaded and now is available at:
{url} [{size_mb} MB]
"""
    send_mail(message)


def start_uploading(directory, rsync_dst):
    pending_upload_directory = os.path.join(directory, "uploading")

    while True:
        if file_pending_to_upload(pending_upload_directory):
            file_path = glob.glob(os.path.join(pending_upload_directory, "*"))[0]
            rsync(file_path, rsync_dst)
            # if rsync finishes is that the file finished uploading
            send_mail_file_uploaded(file_path)

            destination_directory = os.path.join(pending_upload_directory, "..", "uploaded")
            os.makedirs(destination_directory, exist_ok=True)
            shutil.move(file_path, destination_directory)

        else:
            moved = move_next_file(directory, pending_upload_directory)
            if not moved:
                log("No more files to be uploaded.")
                break


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("directory", help="Directory to upload", type=str)
    parser.add_argument("rsync_dst", help="rsync destination, e.g. ", type=str)

    args = parser.parse_args()
    signal.signal(signal.SIGTERM, signal_term_handler)
    start_uploading(args.directory, args.rsync_dst)
