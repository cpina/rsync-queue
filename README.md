# rsync-queue

In the the Antarctic Circumnavigation Expedition (ACE) we wanted a system
to queue files to be uploaded using the Iridium connection. This was a very
slow (16 KB/s if it was working very fast) and it was very unstable so a plain
rsync was getting disconnected often (that's the reason of the time out
options for rsync that rsync_queue.py uses and the aggressive retry
attempts).

What we did is a folder where we copied files named following a schema:
priority_number-person_name-description.extension. E.g.:

010-john-photos_of_fish.zip
020-jen-video.zip
030-james-test_files.zip

Then rsync_queue.py starts uploading a file. It moves the file into uploading/
directory. When it's finished it moves the file into uploaded/

If a person needs to send a file before someone else it's only a matter
to add a file there with a lower priority.

If rsync_queue.py is killed with the signal SIGTERM it emails with the progress
of the file to the address setup in the configuration file.

If rsynque_queue.py finished uploading a file it sends a mail with the URL.

The progress can be seen live in the file $HOME/.rsync_queue.log
(e.g. tail -f $HOME/.rsync_queue.log ) 

The configuration file is specified in the rsync_queue.py. A quick overview, it
needs to be saved in $HOME/.config/rsync_queue.conf. The contents is like:

[General]
notification_email_from=uploader@ace-expedition.net
notification_email_to=data@ace-expedition.net
rsync_bwlimit=10k
base_url = http://ace-expedition.net/uploaded/misc/

We used this during the ACE expedition and videos for TVs, science data,
photos, etc. were uploaded using this sytem. We named it as "overflow queue":
people had a specific and guranteed capacity and then all the rest was used
until the morning using rsync_queue.
