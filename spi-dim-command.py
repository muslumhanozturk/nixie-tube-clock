#!/usr/bin/python
###############################################################################
# 
# spi-dim-command.py
#
#   This test cycles through dimming levels to test anode on/off timing.
#
#   November 1, 2018
#
###############################################################################

import time
import libbcm2835._bcm2835 as soc

def main():
    """Initialize SPI, send a few bytes, then close and exit."""
    
    SPI_CMD_WDOG = 85
    WATCH_DOG_REPLY = 170
    SPI_CMD_BRIGHTNESS = 5
    DUMMY = 255
    
    print 'initializing GPIO:', soc.bcm2835_init()
    
    # Reset the AVR and the force GPIO8, pin 24, to high to enable the AVR
    soc.bcm2835_gpio_fsel(soc.RPI_GPIO_P1_24, soc.BCM2835_GPIO_FSEL_OUTP)
    soc.bcm2835_gpio_set(soc.RPI_GPIO_P1_24)
    soc.bcm2835_gpio_clr(soc.RPI_GPIO_P1_24)
    soc.bcm2835_gpio_set(soc.RPI_GPIO_P1_24)
    
    time.sleep(1)
    
    print 'initializing SPI:', soc.bcm2835_spi_begin()

    soc.bcm2835_spi_setBitOrder(soc.BCM2835_SPI_BIT_ORDER_MSBFIRST)
    soc.bcm2835_spi_setDataMode(soc.BCM2835_SPI_MODE0)
    soc.bcm2835_spi_setClockDivider(soc.BCM2835_SPI_CLOCK_DIVIDER_65536)
    soc.bcm2835_spi_chipSelect(soc.BCM2835_SPI_CS1)
    soc.bcm2835_spi_setChipSelectPolarity(soc.BCM2835_SPI_CS0, soc.LOW)

    while (True):
        for i in range(0,11):
            time.sleep(1)
            
            soc.bcm2835_spi_transfer(SPI_CMD_BRIGHTNESS) # send command
            soc.bcm2835_spi_transfer(i)                  # send brightness
            
            # Periodic watch-dog 'keep alive'
            soc.bcm2835_spi_transfer(SPI_CMD_WDOG)       # send command
            data_byte = soc.bcm2835_spi_transfer(DUMMY)  # read response
            if data_byte != WATCH_DOG_REPLY:
                print 'Watchdog reply missing. received: ', data_byte
                break

    soc.bcm2835_spi_end()
    print 'closing GPIO:', soc.bcm2835_close()

###############################################################################
#
# Startup
#
if __name__ == '__main__':
    main()
