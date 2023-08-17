#!/usr/bin/python
###############################################################################
# 
# spi-send-digits.py
#
#   This test cycles through numbers on all four displays tubes to test
#   digit placement and multiplexing:
#   Minutes cycles through 0,1,2,3,4
#   10s minutes through    0,2,4,6,8
#   Hours through          1,3,5,7,9
#   !0s minutes through    5,6,7,8,9
#
#   November 20, 2018
#
###############################################################################

import time
import libbcm2835._bcm2835 as soc

def main():
    """Initialize SPI, send a few bytes, then close and exit."""
    
    SPI_CMD_WDOG = 85
    WATCH_DOG_REPLY = 170
    SPI_CMD_MINUTES = 1
    SPI_CMD_TENS_MINUTES = 2
    SPI_CMD_HOURS = 3
    SPI_CMD_TENS_HOURS = 4
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
        for i in range(0,5):
            time.sleep(1)
            
            soc.bcm2835_spi_transfer(SPI_CMD_MINUTES)       # send command
            data_byte = soc.bcm2835_spi_transfer(i)         # send digit
            
            soc.bcm2835_spi_transfer(SPI_CMD_TENS_MINUTES)  # send command
            data_byte = soc.bcm2835_spi_transfer(i*2)       # send digit

            soc.bcm2835_spi_transfer(SPI_CMD_HOURS)         # send command
            data_byte = soc.bcm2835_spi_transfer((i*2)+1)   # send digit

            soc.bcm2835_spi_transfer(SPI_CMD_TENS_HOURS)    # send command
            data_byte = soc.bcm2835_spi_transfer(i+5)       # send digit

            print 'cycle: ',i
            
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
