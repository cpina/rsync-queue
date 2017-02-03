#!/usr/bin/python3

import rsync_queue

cmd = ["rsync", "--partial", "--progress", "-vart", "--bwlimit=10k", "/home/carles/jen_thomas.jpg", "/tmp"]

rsync_queue.execute_rsync(cmd, log_command=True)