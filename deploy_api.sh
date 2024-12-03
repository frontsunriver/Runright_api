#!/bin/bash
branch_name=$(git symbolic-ref -q HEAD)
if [ "$branch_name" != "refs/heads/master" ]
then
    echo "You're not on the master branch. Don't do this."
    exit 1
fi

echo 'Syncing Files'
rsync -r -q -i ~/.ssh/id_rsa --info=progress2 . AvaAdmin@52.142.148.46:/home/AvaAdmin/AvacloneAPIPython
echo 'Restarting Avaclone Service'
ssh AvaAdmin@52.142.148.46 sudo systemctl restart avaclone
echo 'Restarting Envoy Service'
ssh AvaAdmin@52.142.148.46 sudo systemctl restart envoy
echo 'Deployment Complete'