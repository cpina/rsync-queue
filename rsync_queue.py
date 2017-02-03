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

LOG_FILE = os.path.join(os.environ["HOME"], ".rsync-queue.log")

# These variables are global because they are accessed from
# signal_term_handler when the process is terminated
LAST_PROGRESS_LINE = None
FILE_PATH = None


def mail_last_progress():
    file_name = os.path.basename(FILE_PATH)

    s = smtplib.SMTP("localhost")
    tolist = ["data@ace-expedition.net"]
    message = """From: uploader@ace-expedition.net
Subject: file uploader progress {}

The file "{}" was being uploaded but the uploader has been killed.

The last progress line from rsync is:
{}


""".format(file_name, FILE_PATH, LAST_PROGRESS_LINE)

    s.sendmail("uploader@ace-expedition.net", tolist, message)
    s.quit()


def signal_term_handler(signal, frame):
    mail_last_progress()
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

    while True:
        reads = [proc.stdout.fileno(), proc.stderr.fileno()]

        # Waits that stdout or stderr are ready to be read
        (read_fd, _, _) = select.select(reads, [], [], 1) # 1 is 1 second timeout

        for fd in read_fd:
            if fd == proc.stdout.fileno():
                line = proc.stdout.readline()
                line = line.replace("\r", "\n") # --progress uses \r
                line = line.strip()

                print(line)

                log("stdout: {}".format(line))
                update_progress(line)

            elif fd == proc.stderr.fileno():
                line = proc.stderr.readline()
                line = line.strip()

                print(line)

                log("stderr: {}".format(line))


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
    f = open(LOG_FILE, "a")
    date_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    f.write("{}: {}\n".format(date_time, text))
    f.close()


def rsync(origin, destination):
    global FILE_PATH
    FILE_PATH = origin

    ssh_options = ['-e', 'ssh -o ConnectTimeout=120 -o ServerAliveInterval=120']
    rsync_options = ["-rvt", "--progress", "--inplace", "--timeout=120", "--bwlimit=2k"]

    while True:
        retval = execute_rsync(["rsync"] + ssh_options + rsync_options + [origin] + [destination], log_command = True)
        if retval == 0:
            log("It finished uploading the file: {}".format(origin))
            break
        else:
            log("It seems that it timed out - will try again")

    return True


def file_pending_to_upload(directory):
    return len(glob.glob(os.path.join(directory, "*"))) > 0


def move_next_file(source, destination):
    # Returns True if a file has been moved. False if there aren't more files
    files = glob.glob(os.path.join(source, "*"))

    files.sort()

    if len(files) > 0:
        log("Moving file from {} to {}".format(files[0], destination))
        os.makedirs(destination, exist_ok=True)
        shutil.move(files[0], destination)
        return True

    log("No more files to upload.")
    return False


def notify_by_mail(file_path, mail):
    file_name = os.path.basename(file_path)

    s = smtplib.SMTP("localhost")
    tolist = ["data@ace-expedition.net"]
    message = """From: uploader@ace-expedition.net
Subject: file uploaded: {}

The file {} has been uploaded and now is available at:
http://ace-expedition.net/uploaded/misc/{}
""".format(file_name, file_name, urllib.parse.quote(file_name))

    s.sendmail("uploader@ace-expedition.net", tolist, message)
    s.quit()


def start_uploading(directory, rsync_dst, mail):
    pending_upload_directory = os.path.join(directory, "uploading")

    while True:
        if file_pending_to_upload(pending_upload_directory):
            file_path = glob.glob(os.path.join(pending_upload_directory, "*"))[0]
            rsync(file_path, rsync_dst)
            # if rsync finishes is that the file finished uploading
            notify_by_mail(file_path, mail)

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
    parser.add_argument("destination_mail", help="Destination mail to email when it's finished", type=str)

    args = parser.parse_args()
    signal.signal(signal.SIGTERM, signal_term_handler)
    start_uploading(args.directory, args.rsync_dst, args.destination_mail)
