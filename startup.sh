#!/bin/bash
#
# startup.sh
#
#   Shell script used to auto start the clock app in Raspberry Pi.
#   Use with crontab: '@reboot /home/pi/nixie-clock/software/startup.sh'
#

# GO_FILE='/home/pi/nixie-clock/software/go'

# Check if the 'go' file exists
if [ -f "/home/pi/nixie-clock/software/go" ]; then

    # If 'GO' file exists, then auto-start the clock app.
    cd /home/pi/nixie-clock/software
    sudo python nixie_clock.py &

# If there is no 'GO' file just exit the script
fi

