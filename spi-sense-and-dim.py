#!/usr/bin/python
###############################################################################
# 
# spi-sense-and-dim.py
#
#   This test reads the light sensor value from the AVR controller
#   and adjusts the tube anode 'on' cycle to set dimming level.
#   Each tune gets a unique set of display numbers to test correct digit
#   multiplexing order.
#
#   November 20, 2018
#
###############################################################################

import time
import libbcm2835._bcm2835 as soc

def main():
    """Initialize SPI, send a few bytes, then close and exit."""
    
    SPI_CMD_MINUTES = 1
    SPI_CMD_TENS_MINUTES = 2
    SPI_CMD_HOURS = 3
    SPI_CMD_TENS_HOURS = 4
    SPI_CMD_BRIGHTNESS = 5
    SPI_CMD_GET_LIGHT = 6
    SPI_CMD_WDOG = 85
    WATCH_DOG_REPLY = 170
    DUMMY = 255
    
    # Brightness value filter
    br = [0,0,0,0,0]
    
    print 'initializing GPIO:', soc.bcm2835_init()
    
    # Reset the AVR and the force GPIO8, pin 24, to high to enable the AVR
    soc.bcm2835_gpio_fsel(soc.RPI_GPIO_P1_24, soc.BCM2835_GPIO_FSEL_OUTP)
    soc.bcm2835_gpio_set(soc.RPI_GPIO_P1_24)
    soc.bcm2835_gpio_clr(soc.RPI_GPIO_P1_24)
    soc.bcm2835_gpio_set(soc.RPI_GPIO_P1_24)
    
    print 'initializing SPI:', soc.bcm2835_spi_begin()

    soc.bcm2835_spi_setBitOrder(soc.BCM2835_SPI_BIT_ORDER_MSBFIRST)
    soc.bcm2835_spi_setDataMode(soc.BCM2835_SPI_MODE0)
    soc.bcm2835_spi_setClockDivider(soc.BCM2835_SPI_CLOCK_DIVIDER_65536)
    soc.bcm2835_spi_chipSelect(soc.BCM2835_SPI_CS1)
    soc.bcm2835_spi_setChipSelectPolarity(soc.BCM2835_SPI_CS0, soc.LOW)
    
    while (True):
        for i in range(0,5):
            time.sleep(1)
            
            # Get light sensor value, which can be between 0 and 255
            soc.bcm2835_spi_transfer(SPI_CMD_GET_LIGHT)     # send command
            light_sensor = soc.bcm2835_spi_transfer(DUMMY)  # read response
            
            # Convert light sensor input to a 0 to 10 brightness range
            br.insert(0, int(light_sensor/20.0))
            br = br[:5]
            brightness = (br[0]+br[1]+br[2]+br[3]+br[4])/5
            if brightness > 10.0:
                brightness = 10.0
            elif brightness < 1:
                brightness = 1

            print 'Light sensor: ', light_sensor, ' Brightness: ', brightness
            
            # Send brightness command
            soc.bcm2835_spi_transfer(SPI_CMD_BRIGHTNESS)    # send command
            soc.bcm2835_spi_transfer(int(brightness))       # send brightness
            
            # Send digits
            soc.bcm2835_spi_transfer(SPI_CMD_MINUTES)       # send command
            data_byte = soc.bcm2835_spi_transfer(i)         # send digit (0,1,2,3,4)
            
            soc.bcm2835_spi_transfer(SPI_CMD_TENS_MINUTES)  # send command
            data_byte = soc.bcm2835_spi_transfer(i*2)       # send digit (0,2,4,6,8)

            soc.bcm2835_spi_transfer(SPI_CMD_HOURS)         # send command
            data_byte = soc.bcm2835_spi_transfer((i*2)+1)   # send digit (1,3,5,7,9)

            soc.bcm2835_spi_transfer(SPI_CMD_TENS_HOURS)    # send command
            data_byte = soc.bcm2835_spi_transfer(i+5)       # send digit (5,6,7,8,9)

            # Periodic watch-dog 'keep alive'
            soc.bcm2835_spi_transfer(SPI_CMD_WDOG)          # send command
            data_byte = soc.bcm2835_spi_transfer(DUMMY)     # read response
            if data_byte != WATCH_DOG_REPLY:
                print 'Watch-dog reply missing. received: ', data_byte
                break

    soc.bcm2835_spi_end()
    print 'closing GPIO:', soc.bcm2835_close()

###############################################################################
#
# Startup
#
if __name__ == '__main__':
    main()
