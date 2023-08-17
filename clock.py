#
# clock.py
#
#   Clock module for Nixie Tube clock.
#   Display driver for time, date, and "slot machine" effects.
#   Reads ambient light sensor and controls tube display intensity.
#   Configuration is controlled through parameters read from XML configuration file.
#   This module also has a GPIO and SPI initialization function and AVR watchdog reset.
#

import time
import libbcm2835._bcm2835 as soc

# SPI commands
SPI_CMD_MINUTES = 1
SPI_CMD_TENS_MINUTES = 2
SPI_CMD_HOURS = 3
SPI_CMD_TENS_HOURS = 4
SPI_CMD_BRIGHTNESS = 5
SPI_CMD_GET_LIGHT = 6
SPI_CMD_WDOG = 85
WATCH_DOG_REPLY = 170
DUMMY = 255
DIGIT_OFF = 10

# Internal variables  
display = [0,0,0,0]
gpio_initialized = 0
date_display_lock = 0
slot_machine_lock = 0

# Clock configuration variables
CFG_CLOCK_12HOUR = 0        # 12 or 24 hour time format
CFG_SLOT_MACHINE = 2        # Minute interval for slot machine effect
CFG_SHOW_DATE = 0           # Show date at top of hour
CFG_DIPLAY_OFF = (0,0)      # Turn off clock display
CFG_DISPLAY_ON = (8,0)      # Turn on clock display

def initialize():
    """
    Clock hardware initialization.
    Any exceptions raised here should not abort the program,
    but return a '0' to indicate initialization failure.
    """

    # Initialize RPi GPIO
    try:
        gpio_initialized = soc.bcm2835_init()

        # Reset the AVR and then force GPIO8, pin 24, to high to enable the AVR
        soc.bcm2835_gpio_fsel(soc.RPI_GPIO_P1_24, soc.BCM2835_GPIO_FSEL_OUTP)
        _avr_reset()
        
        # Initializing SPI
        soc.bcm2835_spi_begin()
        soc.bcm2835_spi_setBitOrder(soc.BCM2835_SPI_BIT_ORDER_MSBFIRST)
        soc.bcm2835_spi_setDataMode(soc.BCM2835_SPI_MODE0)
        soc.bcm2835_spi_setClockDivider(soc.BCM2835_SPI_CLOCK_DIVIDER_65536)
        soc.bcm2835_spi_chipSelect(soc.BCM2835_SPI_CS1)
        soc.bcm2835_spi_setChipSelectPolarity(soc.BCM2835_SPI_CS0, soc.LOW)
    except:
        gpio_initialized = 0

    return gpio_initialized

def watchdog(param={}):
    """Function that sends SPI commands to reset AVR controller watchdog time-out period."""

    soc.bcm2835_spi_transfer(SPI_CMD_WDOG)
    data_byte = soc.bcm2835_spi_transfer(DUMMY)
    if data_byte != WATCH_DOG_REPLY:
        # TODO is an AVR reset too harsh?
        _avr_reset()

def time_display(param):
    """Clock display driver."""

    global slot_machine_lock, date_display_lock
    global CFG_CLOCK_12HOUR, CFG_SLOT_MACHINE, CFG_SHOW_DATE, CFG_DIPLAY_OFF, CFG_DISPLAY_ON

    # Parse configuration changes if any
    if param['config_change'] == 'yes':

        if param['display_date'] == 'no':
            CFG_SHOW_DATE = 0
        elif param['display_date'] == 'yes':
            CFG_SHOW_DATE = 1

        if param['time_format'] == '24':
            CFG_CLOCK_12HOUR = 0
        elif param['time_format'] == '12':
            CFG_CLOCK_12HOUR = 1

        CFG_SLOT_MACHINE = int(param['slot_machine'])

        t = param['off_time_start']
        CFG_DIPLAY_OFF = (int(t.split(':')[0]), int(t.split(':')[1]))
        t = param['off_time_end']
        CFG_DIPLAY_ON = (int(t.split(':')[0]), int(t.split(':')[1]))

        param['config_change'] = 'no'

    # Get current time
    t = time.localtime()

    # Manage clock 'on' period
    tod = (t.tm_hour,t.tm_min)
    if tod >= CFG_DIPLAY_OFF and tod < CFG_DISPLAY_ON:
        _display(display, 0)
        return
        
    # Parse time and set digits
    display[2] = int(t.tm_min/10)
    display[3] = t.tm_min - display[2]*10
    
    hour = t.tm_hour
    if CFG_CLOCK_12HOUR == 1:
        if hour > 12:
            hour = hour - 12
        elif hour == 0:
            hour = 12

    display[0] = int(hour/10)
    display[1] = hour - display[0]*10

    if display[0] == 0 and CFG_CLOCK_12HOUR == 1:
        display[0] = DIGIT_OFF

    # Date display at top of hour
    if CFG_SHOW_DATE == 1 and t.tm_min == 0:
        if date_display_lock == 0:
            _show_date(t.tm_mday, t.tm_mon, t.tm_year, display)
            date_display_lock = 1
            slot_machine_lock = 1
    else:
        date_display_lock = 0

    # Periodic slot machine effect
    # TODO the lock will prohibit the effect from running on 1-min interval
    if t.tm_min % CFG_SLOT_MACHINE == 0:
        if slot_machine_lock == 0:
            _slot_machine(display)
            slot_machine_lock = 1
    else:
        slot_machine_lock = 0

    # Display time
    _display(display, _get_brightness())

#
# Private functions
#

def _scroll_rtl(digits=(0,0,0,0), digit_delay=1.0):
    """Scroll the digits into the display shifting them from right to left."""

    for shift in range(0,4):
        cmd = SPI_CMD_MINUTES
        digit_out = digits[shift]
        for d in range(0,4):
            soc.bcm2835_spi_transfer(cmd)
            digit_in = soc.bcm2835_spi_transfer(digit_out)
            digit_out = digit_in
            cmd = cmd + 1
        watchdog()
        time.sleep(digit_delay)

def _show_date(day, month, year, digits=(0,0,0,0)):
    """Display date sequence and then revert to content on 'digits'."""
    
    # Blank the display
    d = [10,10,10,10]
    _display(d)
    watchdog()
    time.sleep(1)

    # Scroll month and day
    d[0] = int(month/10)
    d[1] = month - d[0]*10
    d[2] = int(day/10)
    d[3] = day - d[2]*10
    if d[0] == 0:
        d[0] = 10
    if d[2] == 0:
        d[2] = 10
    _scroll_rtl(d)
    time.sleep(2)

     # Scroll year
    d[0] = int(year/1000)
    d[1] = int((year - d[0]*1000)/100)
    d[2] = int((year - d[0]*1000 - d[1]*100)/10)
    d[3] = int(year - d[0]*1000 - d[1]*100 - d[2]*10)
    _display(d)
    watchdog()
    time.sleep(3)

    _display(digits)

def _slot_machine(digits=(0,0,0,0)):
    """
    Produce a slot machine effect on the display to preserve tubes.
    The 'digits' tuple contain the final digits to display after the effect.
    """

    slots = [0,0,0,0]

    for effect_count in range(0,4):
        for n in range(0,10):
            for d in range(0,(4-effect_count)):
                slots[d] = n
            _display(slots,10)
            watchdog()
            time.sleep(0.2)
        slots[3-effect_count] = digits[3-effect_count]
        _display(slots,10)

def _display(digits=(0,0,0,0), brightness=-1):
    """
    Send digits passed in a tuple, one number per Nixie tube.
    Integers '0' to '9' correspond to number digits.
    Integer '10' (DIGIT_OFF) signals a blank 'off' digit.
    Integer '-1' signals skip digit update.
    'brightness' of -1 skips display brightness change.
    """
    
    # Send brightness command
    if brightness > -1:
        if brightness > 10:
            brightness = 10
        soc.bcm2835_spi_transfer(SPI_CMD_BRIGHTNESS)
        soc.bcm2835_spi_transfer(int(brightness))

    # Send digits
    cmd = SPI_CMD_TENS_HOURS
    for d in range(0,4):
        if (digits[d] >= 0 and digits[d] <= 9) or (digits[d] == DIGIT_OFF):
            soc.bcm2835_spi_transfer(cmd)
            data_byte = soc.bcm2835_spi_transfer(digits[d])
        cmd = cmd - 1

def _get_brightness():
    """Read light sensor then calculate and return brightness command value between 1 and 10."""

    # Get light sensor value, which can be between 0 and 255
    soc.bcm2835_spi_transfer(SPI_CMD_GET_LIGHT)
    light_sensor = soc.bcm2835_spi_transfer(DUMMY)

    br_cmd = int(light_sensor/20.0)
    if br_cmd > 10:
        br_cmd = 10
    elif br_cmd < 1:
        br_cmd = 1

    return br_cmd

def _avr_reset():
    """Reset the AVR through RPi GPIO8, pin 24."""

    soc.bcm2835_gpio_set(soc.RPI_GPIO_P1_24)
    soc.bcm2835_gpio_clr(soc.RPI_GPIO_P1_24)
    soc.bcm2835_gpio_set(soc.RPI_GPIO_P1_24)

