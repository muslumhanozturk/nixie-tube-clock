/*
 *  avr-nixie-ctrl.c
 *
 * ATmega328p AVR interfaces with Raspberry Pi to provide two timing-critical
 * functions for the Nixie Tube clock: digit multiplexing, digit illumination intensity.
 *
 * The setup:
 * - MISO/MOSI/SCK/RST for direct programming from RPi Zero W
 * - MISO/MOSI/SCK/SS for bi-directional communication with RPi Zero W
 * - Using 74141 as Nixie Tube driver
 *   - PD0..3: BCD digit code
 *   - PD4..7: anode multiplex and dimming control
 * - {optional} With set of 10x MPSA42 transistors
 *   - PD0..7, PB0, PB1: digit cathode select
 *   - PC0..3: anode multiplex and dimming control
 * - PB6 - flashing seconds LED
 * - PC5 - analog ambient light sensor
 *
 * Raspberry Pi / AVR interfacing:
 * - RPi can remote/in-circuit program the ATmega
 * - RPi can read ADC light sensor
 * - RPi sends time as data for four digits
 * - RPi sends dimming control value
 * - ATmega controls/synchronizes multiplexing of digits and dimming
 * - ATmega operates on 3.3v like the RPi
 * - ATmega outputs are buffered through 74244 to drive transistors
 *   for protection and 3.3 to 5v logic level conversion
 *
 * ATmega AVR IO
 * ---------------
 *
 * Port B bit assignment
 *
 * b7 b6 b5 b4 b3 b2 b1 b0
 * |  |  |  |  |  |  |  |
 * |  |  |  |  |  |  |  +--- 'o' timing test point
 * |  |  |  |  |  |  +------ 'o' High voltage enable=1/disable=0
 * |  |  |  |  |  +--------- 'i' SPI-CS
 * |  |  |  |  +------------ 'i' SPI-MOSI
 * |  |  |  +--------------- 'o' SPI-MISO
 * |  |  +------------------ 'i' SPI-CLK
 * |  +--------------------- 'o' Seconds LED
 * +------------------------ 'i' n.c
 *
 * Port C bit assignment
 *
 *    b6 b5 b4 b3 b2 b1 b0
 *    |  |  |  |  |  |  |
 *    |  |  |  |  |  |  +--- 'i' n.c
 *    |  |  |  |  |  +------ 'i' n.c
 *    |  |  |  |  +--------- 'i' n.c
 *    |  |  |  +------------ 'i' n.c
 *    |  |  +--------------- 'i' n.c
 *    |  +------------------ 'i' Analog input, light sense LDR
 *    +--------------------- 'i' Reset
 *
 * Port D bit assignment
 *
 * b7 b6 b5 b4 b3 b2 b1 b0
 * |  |  |  |  |  |  |  |
 * |  |  |  |  |  |  |  +--- 'o' digit BDC b0
 * |  |  |  |  |  |  +------ 'o' digit BDC b1
 * |  |  |  |  |  +--------- 'o' digit BDC b2
 * |  |  |  |  +------------ 'o' digit BDC b3
 * |  |  |  +--------------- 'o' tube anode select b0, minutes
 * |  |  +------------------ 'o' tube anode select b1, 10s minutes
 * |  +--------------------- 'o' tube anode select b2, hours
 * +------------------------ 'o' tube anode select b3, 10s hours
 *
 * note: all references to data sheet are for ATmega 328P Rev. 8161D–AVR–10/09
 *
 */

#include    <stdint.h>

#include    <avr/io.h>
#include    <avr/interrupt.h>
#include    <avr/wdt.h>
#include    <util/delay.h>

#define     VERSION         0x10        // version 1.0

// IO port configuration
#define     PB_DDR_INIT     0x53        // port data direction
#define     PB_PUP_INIT     0x00        // port input pin pull-up
#define     PB_INIT         0x40        // port initial values

#define     PC_DDR_INIT     0x00        // port data direction
#define     PC_PUP_INIT     0x00        // port input pin pull-up
#define     PC_INIT         0x00        // port initial values

#define     PD_DDR_INIT     0xff        // port data direction
#define     PD_PUP_INIT     0x00        // port input pin pull-up
#define     PD_INIT         0x00        // port initial values

// SPI configuration
#define     SPCR_INIT       0b11000000  // SPI 'slave' mode, polarity idle 'lo', phase 'lo' mode-0
#define     SPSR_INIT       0b00000000
#define     DUMMY_BYTE      0xff

// Timer-0 configuration
#define     TCCR0A_INIT     0b00000010
#define     TCCR0B_INIT     0b00000010  // Fclk/8 pre-scaler
#define     OCR0A_INIT      199
#define     TIMSK0_INIT     0b00000010

// ADC configuration
#define     ADMUX_INIT      0b01100101  // AVCC reference on ADC5
#define     ADCSRA_INIT     0b11101111  // Auto trigger/start-conversion

// General definitions
#define     PWR_REDUCION    0xeb        // turn off unused peripherals: I2C, timers, UASRT, ADC
#define     TIMING_TEST     0x01
#define     HV_ENABLE       0x02
#define     SECONDS_LED     0x40
#define     ANODES_OFF      0x0f
#define     WDOG_EXPIRE     5           // number of seconds for watch-dog expiration

#define     SPI_DUMMY_BYTE  255

#define     SPI_CMD_SET_MIN     1
#define     SPI_CMD_SET_MINTEN  2
#define     SPI_CMD_SET_HR      3
#define     SPI_CMD_SET_HRTEN   4
#define     SPI_CMD_BRIGHTNESS  5
#define     SPI_CMD_GET_LIGHT   6
#define     SPI_CMD_GET_VER     7
#define     SPI_CMD_WDOG        85

// Sequence count definitions for controller actions
// The sequence count assumes that the count interval is 200uSec, which is the
// Nixie Tube recommended blanking period for multiplexed display.
// Therefore a 1sec action interval is a 5000 count, a blanking interval
// is a 1 count and so on.
#define     ONE_SEC_FLASH   2500        // 0.5[sec] 'on' and 0.5-[SEC] 'off'
#define     FAST_FLASH      625         // fast flash on errors
#define     ONESEC_INTERVAL 5000
#define     BLANKING        1           // 200uSec blanking interval
#define     DIGIT_ON        24          // 4.8mSec 'on' time
#define     DIGIT_TIME_SLOT (DIGIT_ON+BLANKING) // 'on' time + 200uSec blanking X 4 digits = 20mSec multiplex cycle
#define     MAX_DIMMING     18          // Maximum dimming time in 200uSec time-slots (must be < DIGIT_ON)

#define     NUM_DIGITS      4           // number of clock digits

/****************************************************************************
  type definitions
****************************************************************************/

/****************************************************************************
  special function prototypes
****************************************************************************/
// This function is called upon a HARDWARE RESET:
void reset(void) __attribute__((naked)) __attribute__((section(".init3")));

/****************************************************************************
  Globals
****************************************************************************/
volatile uint8_t light_sensor;
volatile uint8_t spi_data_byte;
volatile int     watch_dog_counter = 0;
volatile int     brightness_level = 1;				// Set to '1' as minimum, because '0' turns off high voltage.
volatile int     dimming_interval = MAX_DIMMING;	// Set to match minimum 'brightness_level'

// This array stores the clock digits, right to left for indexes 0 through 3.
// The array is read by the timer interrupt and the digits are multiplexed.
// the array is written to by the SPI interrupt.
volatile uint8_t digits[NUM_DIGITS] = {0, 0, 0, 0};

/* ----------------------------------------------------------------------------
 * ioinit()
 *
 *  initialize IO interfaces
 *  timer and data rates calculated based on 8MHz internal clock
 *
 */
void ioinit(void)
{
    // reconfigure system clock scaler to 8MHz
    // change clock scaler (sec 8.12.2 p.37)
    CLKPR = 0x80;
    CLKPR = 0x00;

    // power reduction setup
    //PRR   = PWR_REDUCION;

    // initialize SPI interface for master mode
    SPCR = SPCR_INIT;
    SPSR = SPSR_INIT;
    SPDR = SPI_DUMMY_BYTE;

    // initialize timer-0
    //  'Clear Timer on Compare' match (mode 2) with OCR0A
    TCNT0 = 0;
    OCR0A = OCR0A_INIT;
    TCCR0A = TCCR0A_INIT;
    TCCR0B = TCCR0B_INIT;
    TIMSK0 = TIMSK0_INIT;

    // initialize ADC
    //  ADC5 input with internal 1.1v reference
    ADMUX = ADMUX_INIT;
    ADCSRA = ADCSRA_INIT;

    // initialize general IO PB, PC and PD pins for output
    DDRB  = PB_DDR_INIT;            // PB pin directions
    PORTB = PB_INIT | PB_PUP_INIT;  // initial value of pins and input with pull-up

    DDRC  = PC_DDR_INIT;            // PC pin directions
    PORTC = PC_INIT | PC_PUP_INIT;  // initial value of pins and input with pull-up

    DDRD   = PD_DDR_INIT;           // PD data direction
    PORTD  = PD_INIT | PD_PUP_INIT; // initial value of pins and input with pull-up
}

/* ----------------------------------------------------------------------------
 * This ISR will trigger when Timer-0 compare reaches the time interval
 * - LED blink rate
 * - High voltage control
 * - Blanking and digit display multiplexing
 * - Adjust blank/display intervals according to 'brightness_level'
 *
 */
ISR(TIMER0_COMPA_vect)
{
    static int  seconds_flash_interval = 0;
    static int  digit_multiplexer = 0;
    static int  digit_index = 0;
    uint8_t     port_B_temp, port_D_temp;
    int         flash_rate;

    // Read port values
    port_B_temp = PORTB;
    port_D_temp = PORTD;

    /* One second status LED flash period
     */
    // High voltage control logic
	if ( watch_dog_counter >= WDOG_EXPIRE || brightness_level == 0 )
	{
	    port_B_temp &= ~HV_ENABLE;
	}
	else
	{
		port_B_temp |= HV_ENABLE;
	}

    // If watch dog expired
    // fast-flash the LED and turn off high voltage
	if ( watch_dog_counter >= WDOG_EXPIRE )
    {
        flash_rate = FAST_FLASH;
    }
    else
    {
        flash_rate = ONE_SEC_FLASH;
    }

    seconds_flash_interval++;

    if ( (seconds_flash_interval % flash_rate) == 0 )
    {
        port_B_temp ^= SECONDS_LED;
    }

    if ( (seconds_flash_interval % ONESEC_INTERVAL) == 0 )
    {
        seconds_flash_interval = 0;
        if ( watch_dog_counter < WDOG_EXPIRE )
            watch_dog_counter++;
    }

    /* Digit multiplexer timing
     */

    digit_multiplexer++;

    // Turn off all the anodes at end of digit time slot
    // but leave whatever digit is set for the BCD decoder.
    // Roll to next digit if done with one scan of four digits.
    if ( digit_multiplexer == DIGIT_TIME_SLOT )
    {
        port_D_temp &= ANODES_OFF;

        digit_multiplexer = 0;
        digit_index++;
        if ( digit_index >= NUM_DIGITS )
            digit_index = 0;
    }

    // Display a digit at the end of the blacking period
    else if ( digit_multiplexer == (BLANKING + dimming_interval) && digits[digit_index] <= 9 )
    {
        port_D_temp = digits[digit_index] & 0x0f;
        port_D_temp |= 0b00010000 << digit_index;
    }

    // Toggle cycle-test signal
    port_B_temp ^= TIMING_TEST;

    // Write port values
    PORTB = port_B_temp & PB_DDR_INIT;
    PORTD = port_D_temp;
}

/* ----------------------------------------------------------------------------
 * This ISR will trigger when the ADC completes a conversion.
 * Conversions are auto-triggered and this ISR will trigger at 31.25KHz
 * ADC result is left adjusted, so only ADCH needs to be read
 *
 */
ISR(ADC_vect)
{
    // ADCH read voltage from ADC register
    light_sensor = ADCH;
}

/* ----------------------------------------------------------------------------
 * This ISR will trigger when the SPI interface receives a data byte.
 * The ISR will process 2-byte commands it receives through the SPI interface.
 *
 * The SPI Command interface:
 *
 * | Command byte | Response | Second transmit byte |    Response                   |
 * |--------------|----------|----------------------|-------------------------------|
 * |    1         |  dummy   | Minutes digit        | Current Minutes digit         |
 * |    2         |  dummy   | 10s minutes digit    | Current 10s minutes digit     |
 * |    3         |  dummy   | Hours digit digit    | Current Hours digit digit     |
 * |    4         |  dummy   | 10s hours digit      | Current 10s hours digit       |
 * |    5         |  dummy   | Brightness 0 to 10   | dummy                         |
 * |    6         |  dummy   | dummy                | Ambient light sensor 0 to 255 |
 * |    7         |  dummy   | dummy                | Code rev in 2 nibbles         |
 * |   85         |  dummy   | dummy                |     170                       |
 *
 */
ISR(SPI_STC_vect)
{
    static int byte_count_seq = 0;
    static int last_command = 0;

    // SPI data input interrupt
    spi_data_byte = SPDR;

    if ( byte_count_seq == 0 )
        last_command = spi_data_byte;

    // Process SPI command
    switch ( last_command )
    {
        case SPI_CMD_SET_MIN:
            if ( byte_count_seq == 0 )
                SPDR = digits[0];
            else
                digits[0] = spi_data_byte;
            break;

        case SPI_CMD_SET_MINTEN:
            if ( byte_count_seq == 0 )
                SPDR = digits[1];
            else
                digits[1] = spi_data_byte;
            break;

        case SPI_CMD_SET_HR:
            if ( byte_count_seq == 0 )
                SPDR = digits[2];
            else
                digits[2] = spi_data_byte;
            break;

        case SPI_CMD_SET_HRTEN:
            if ( byte_count_seq == 0 )
                SPDR = digits[3];
            else
                digits[3] = spi_data_byte;
            break;

        case SPI_CMD_BRIGHTNESS:
            if ( byte_count_seq == 0 )
                SPDR = SPI_DUMMY_BYTE;
            else
                brightness_level = spi_data_byte;

            // Convert brightness level to dimming timing intervals
            // and limit to within digit time slot
            dimming_interval = (-2 * brightness_level) + 20;
            if ( dimming_interval > MAX_DIMMING )
                dimming_interval = MAX_DIMMING;
            else if ( dimming_interval < 0 )
                dimming_interval = 0;
            break;

        case SPI_CMD_GET_LIGHT:
            if ( byte_count_seq == 0 )
                SPDR = light_sensor;
            break;

        case SPI_CMD_GET_VER:
            if ( byte_count_seq == 0 )
                SPDR = VERSION;
            break;

        case SPI_CMD_WDOG:
            if ( byte_count_seq == 0 )
            {
                SPDR = 170;
                watch_dog_counter = 0;
            }
            break;

        default:;
    }

    // Track command byte sequence
    byte_count_seq++;
    if ( byte_count_seq == 2 )
        byte_count_seq = 0;
}

/* ----------------------------------------------------------------------------
 * reset()
 *
 *  Clear SREG_I on hardware reset.
 *  source: http://electronics.stackexchange.com/questions/117288/watchdog-timer-issue-avr-atmega324pa
 */
void reset(void)
{
    cli();
    // Note that for newer devices (any AVR that has the option to also
    // generate WDT interrupts), the watch-dog timer remains active even
    // after a system reset (except a power-on condition), using the fastest
    // pre-scaler value (approximately 15ms). It is therefore required
    // to turn off the watch-dog early during program startup.
    MCUSR = 0; // clear reset flags
    wdt_disable();
}

/* ----------------------------------------------------------------------------
 * main() control functions
 *
 * - Initialize IO Ports, ADC, and SPI
 * - Enter endless loop
 *
 */
int main(void)
{
	uint8_t	port_B_temp;

    // initialize peripherals
    ioinit();

    // enable interrupts
    sei();

    while (1)
    {
    }
}
