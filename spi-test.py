#!/usr/bin/python
###############################################################################
# 
# spi-test.py.py
#
#   Test the installation of bcm2835 library with its Python bindings.
#   The test needs to have an SPI device attached to the RPi SPI channel 1.
#
#   September 29, 2018
#
###############################################################################

import libbcm2835._bcm2835 as soc

def main():
    """Initialize SPI, send a few bytes, then close and exit."""
    
    print 'initializing GPIO:', soc.bcm2835_init()
    print 'initializing SPI:', soc.bcm2835_spi_begin()

    soc.bcm2835_spi_setBitOrder(soc.BCM2835_SPI_BIT_ORDER_MSBFIRST)
    soc.bcm2835_spi_setDataMode(soc.BCM2835_SPI_MODE0)
    soc.bcm2835_spi_setClockDivider(soc.BCM2835_SPI_CLOCK_DIVIDER_65536)
    soc.bcm2835_spi_chipSelect(soc.BCM2835_SPI_CS1)
    soc.bcm2835_spi_setChipSelectPolarity(soc.BCM2835_SPI_CS0, soc.LOW)

    for i in range(0,100):
        data_byte = soc.bcm2835_spi_transfer(i)
        print 'sent:',i,'returned:', data_byte

    soc.bcm2835_spi_end()
    print 'closing GPIO:', soc.bcm2835_close()

###############################################################################
#
# Startup
#
if __name__ == '__main__':
    main()
