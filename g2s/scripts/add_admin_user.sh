#!/bin/bash

# Add the one and only user of Galaxy in this container to the admin_users.
# This script expects the 'mail_adress' of the user as the one and only argument

if [ $# -eq 0 ]
  then
    echo "Script expects the user's mail adress."
fi

sed -i -e "s/#admin_users = None/admin_users = $1/g" /g2s/galaxy/config/galaxy.ini_execute
