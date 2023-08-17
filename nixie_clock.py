#!/usr/bin/python
#
# nixie_clock.py
#
#   Using a method of periodic dispatch instead of multi threading in order
#   to avoid complicated synchronization of access to common hardware resource (SPI bus)
#   from multiple threads. This also includes avoiding cases in which the Python GIL can be
#   transferred to a different thread in the middle of an SPI byte transaction, which saves
#   the complexity of making the transactions atomic.
#

import sys
import dispatcher as dsp

from clock import initialize, watchdog, time_display
from configuration import get_clock_config

parameter_init = {'config_file_last_mod':0.0, 'config_change':'no'}

def main():
    """Initialize GPIO and SPI and start clock functions."""

    if initialize() == 0:
        soc.bcm2835_close()
        sys.exit(1) 

    clock_driver = dsp.Dispatcher(parameter_init)

    clock_driver.register('watchdog', watchdog, 4)
    clock_driver.register('time_display', time_display, 1)
    clock_driver.register('configuration', get_clock_config, 600)

    #clock_driver.show()

    while True:
        clock_driver.dispatch()

    # Will not get here ever
    soc.bcm2835_close()
    sys.exit(0)

#
# Startup
#
if __name__ == '__main__':
    main()
