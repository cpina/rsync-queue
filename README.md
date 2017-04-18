# rsync-queue

## Introduction

In the the Antarctic Circumnavigation Expedition (ACE) we wanted a system to queue files to be uploaded using the Iridium connection. This was a very slow (16 KB/s if it was working very fast) and it was very unstable so a plain rsync was getting disconnected often (that's the reason of the time out options for rsync that rsync_queue.py uses and the aggressive retry attempts).

We used this during the ACE expedition and videos for TVs, science data, photos, etc. were uploaded using this sytem. We named it as "overflow queue": people had a specific and guranteed capacity and then all the rest was used until the morning using rsync_queue.

## Features
Files could take a few nights to be uploaded (rsync_queue.py was used after other guarenteed uplods and downloads, as an overflow system). So we wanted a system that:
* we could add files in a directory and would get uploaded in a first come, first served system.
* we could check the progress in real time
* we would get an email when rsync_queue.py finished uploading a file
* we would get an email with the progress if rsync_queue.py was killed (we had a cronjob to kill it in the morning to not affect other Internet usages)
* it would upload next files when one finished
* it would retry if the connection failed


## How to use it
What we did is a folder where we copied files named following a schema:
priority_number-person_name-description.extension. E.g.:
```
010-john-photos_of_fish.zip
020-jen-video.zip
030-james-test_files.zip
```

Then rsync_queue.py starts uploading a file. It moves the file into uploading/
directory. When it's finished it moves the file into uploaded/

If a person needs to send a file before someone else it's only a matter
of adding a file with a lower number.

If rsync_queue.py is killed with the signal SIGTERM it emails with the progress
of the file to the address setup in the configuration file.

If rsynque_queue.py finished uploading a file it sends a mail with the URL.

The progress can be seen live in the file $HOME/.rsync_queue.log
(e.g. tail -f $HOME/.rsync_queue.log ) 

The configuration file is specified in the rsync_queue.py. A quick overview, it
needs to be saved in $HOME/.config/rsync_queue.conf. The contents is like:

```
[General]
notification_email_from=uploader@ace-expedition.net
notification_email_to=data@ace-expedition.net
rsync_bwlimit=10k
base_url = http://ace-expedition.net/uploaded/misc/
```

## TODO
We had many ideas during ACE that we didn't have time to implement. To mention
a few:
* easier to work with two Iridiums. We did it having two rsync_queue.py working at the same time with different names and using "uploaded1" and "uploaded2"
* should have a lock file to avoid having two rsync_queue.py running at the same time
* to finish the rsync_queue.py we had a cronjob doing "killall rsync_queue.py". Instead of this we could have had a file (same as the lock file?) with the PID to have an easier way to kill. And also to have rsync_queue.py parameter to kill any existing running queues.  d) it would be possible to have estimates to know how long it will take to upload files based on current speed, have an interface to move the files, etc. etc.
