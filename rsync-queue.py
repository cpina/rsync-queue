#!/usr/bin/python3

import argparse
import glob
import os
import shutil
import datetime
import subprocess
import smtplib

LOG_FILE=os.path.join(os.environ["HOME"], ".rsync-queue.log")

def execute(cmd, abort_if_fails=False, print_command=False):
    if print_command:
        print("** Execute: {}".format(" ".join(cmd)))

    p = subprocess.Popen(cmd)
    p.communicate()[0]
    retval = p.returncode

    if retval != 0 and abort_if_fails:
        print("Command: _{}_ failed, aborting...".format(cmd))
        exit(1)

    return retval

def log(text):
    f = open(LOG_FILE, "a")
    date_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    f.write("{}: {}".format(date_time, text))
    f.close()


def rsync(origin, destination):
    ssh_options = ['-e', 'ssh -o ConnectTimeout=120 -o ServerAliveInterval=120']
    rsync_options = ["-rvt", "--inplace", "--timeout=120", "--bwlimit=12k"]

    while True:
        retval = execute(["rsync"] + ssh_options + rsync_options + [origin] + [destination], print_command = True)
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
    message = """
From: uploader@ace-expedition.net
Subject: file uploaded

The file {} has been uploaded and now is available at:
http://ace-expedition.net/uploaded/{}
""".format(file_path, file_name)

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

    start_uploading(args.directory, args.rsync_dst, args.destination_mail)