#
# configuration.py
#
#   Clock configuration module for Nixie Tube clock.
#   Module that tests for XML configuration file changes and updates clock
#   configuration.
#   Call the get_clock_config() function periodically to capture configuration changes
#   and apply them at run time to the clock
#

import os.path
import xml.etree.ElementTree as ET

def get_clock_config(param):
    """Parse XML configuration file if it changed since the last check, and update clock configuration."""

    if os.path.isfile('clock.xml'):

        if param['config_file_last_mod'] != os.path.getmtime('clock.xml'):

            param['config_file_last_mod'] = os.path.getmtime('clock.xml')
            param['config_change'] = 'yes'

            tree = ET.parse('clock.xml')
            root = tree.getroot()

            if root.tag == 'clock':
                for parameter in root:
                    if parameter.tag == 'time_format':
                        param[parameter.tag] = parameter.attrib['value']                        
                    elif parameter.tag == 'effects':
                        for effect in parameter:
                            param[effect.tag] = effect.attrib['period']
                    elif parameter.tag == 'display_date':
                        param[parameter.tag] = parameter.attrib['value']
                    elif parameter.tag == 'display_off':
                        param['off_time_start'] = parameter.attrib['start_time']
                        param['off_time_end'] = parameter.attrib['end_time']

