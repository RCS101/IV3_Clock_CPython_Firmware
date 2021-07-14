import time
import digitalio
from board import *
import pulseio
import busio as io
import adafruit_ds1307

i2c_bus = io.I2C(SCL, SDA)
rtc = adafruit_ds1307.DS1307(i2c_bus)

"""
Tube Segment Definitions
The shift reg's are reversed - ARGH

Tubes 1/2 (counting from the left)
A = 0xBF
B = 0x7F
C = 0xFB
D = 0xFD
E = 0xFE
F = 0xEF
G = 0xDF
DP = 0xF7

Tubes 3/4
A = 0xFD
B = 0xFE
C = 0xDF
D = 0xBF
E = 0x7F
F = 0xF7
G = 0xFB
DP = 0xEF
"""

# 0,1,2,3,4,5,6,7,8,9
theNumbers = [0x14, 0xDE, 0x38, 0x98, 0xD2, 0x91, 0x11, 0xDC, 0x10, 0x90]
theNumbers2 = [0x28, 0x7B, 0x1C, 0x19, 0x4B, 0x89, 0x88, 0x3B, 0x08, 0x09]
DP = 0xEF
_DP = 0xF7

# Define states
MAIN_TIME = 0
MAIN_MENU = 1
MENU_12_24 = 2
MENU_BRIGHT = 3
MENU_NIGHT_FADE = 4

# Shift Reg pins
OE = pulseio.PWMOut(A2, frequency=440, duty_cycle=0) # Used for brightness control

DATA = digitalio.DigitalInOut(A3)
CLOCK = digitalio.DigitalInOut(A0)
STORAGE_REG = digitalio.DigitalInOut(A1)

DATA.direction = digitalio.Direction.OUTPUT
CLOCK.direction = digitalio.Direction.OUTPUT
STORAGE_REG.direction = digitalio.Direction.OUTPUT

heat_enable = digitalio.DigitalInOut(D10)
HV_enable = digitalio.DigitalInOut(D9)

heat_enable.direction = digitalio.Direction.OUTPUT
HV_enable.direction = digitalio.Direction.OUTPUT

heat_enable.value = True
HV_enable.value = True

hourButton = digitalio.DigitalInOut(TX)
minButton = digitalio.DigitalInOut(RX)

hourButton.direction = digitalio.Direction.INPUT
minButton.direction = digitalio.Direction.INPUT

hourButton.pull = digitalio.Pull.UP
minButton.pull = digitalio.Pull.UP

time.sleep(1)

# Use this method to set the time, pass it an hour, minute and any DP
def IV3_set(hour, minute, dp):

    if hour_mode_24 == False:
        if hour > 12:
            hour = hour - 12

    hourNums = getDigits(hour)
    minNums = getDigits(minute)

    h1 = theNumbers2[hourNums[0]]
    h2 = theNumbers2[hourNums[1]]
    m1 = theNumbers[minNums[1]]
    m2 = theNumbers[minNums[0]]

    if dp[0] == True:
        h1 = (h1 & _DP)
    if dp[1] == True:
        h2 = (h2 & _DP)
    if dp[3] == True:
        m1 = (m1 & DP)
    if dp[2] == True:
        m2 = (m2 & DP)

    data = [h1, h2, m1, m2]
    shiftOut(data)

def getDigits(num):
    digits = [int(num/10), int(num%10)]
    return digits

# Writes data to the shift registers
# Send data: tube1, tube2, tube3, tube4
def shiftOut(data):
    # Re-order data because of the bad shift reg ordering
    dat = [0]*4
    dat[0] = data[2]
    dat[1] = data[3]
    dat[2] = data[0]
    dat[3] = data[1]
    # Init all shift reg pins low
    # OE.value = True # Turns off tubes
    DATA.value = False
    CLOCK.value = False
    STORAGE_REG.value = False
    
    for _ in range(4):
        bitmask = 0x80
        for i in range(8):
            if (dat[_] & bitmask) == bitmask:
                DATA.value = False
            else:
                DATA.value = True
            bitmask >>= 1

            CLOCK.value = True
            CLOCK.value = False

    DATA.value = False
    STORAGE_REG.value = True

# Start by trying to read the RTC. If it reads as zero then initialise
t = rtc.datetime
if t.tm_year == 0:
    t = time.struct_time((2021, 5, 20, 20, 4, 30, 0, -1, -1))
    rtc.datetime = t

# States
main_state = MAIN_TIME
menu_state = MENU_12_24
# Variables
last_time_check = 0
double_press = False
lastSecond = 0
dps = [False, True, False, False]
lastButt = 0
# Menu settings
night_time_fade = True
hour_mode_24 = True
brightness = 0x6FFF
time_in_menu = 0

# Tube flourish
shiftOut([0xFF,0xFF,0xFF,0xFF])
shiftOut([0x00,0xFF,0xFF,0xFF])
time.sleep(0.2)
shiftOut([0xFF,0x00,0xFF,0xFF])
time.sleep(0.2)
shiftOut([0xFF,0xFF,0xFF,0x00])
time.sleep(0.2)
shiftOut([0xFF,0xFF,0x00,0xFF])
time.sleep(0.2)

while True:
    # Main state machine, only 2 states: show the time or menu
    if main_state == MAIN_TIME:
        # Check the time every 100ms
        if time.monotonic() > (last_time_check + 0.1):
            t = rtc.datetime
            # toggle the dp on the last tube every second
            if t.tm_sec != lastSecond:
                lastSecond = t.tm_sec
                if dps[3] == True:
                    dps[3] = False
                else:
                    dps[3] = True

            if (t.tm_hour < 7) and (night_time_fade == True):
                OE.duty_cycle = 0xCFFF
            else:
                OE.duty_cycle = brightness

            IV3_set(t.tm_hour, t.tm_min, dps)

    elif main_state == MAIN_MENU:
        # Change the tubes to display the correct menu info
        if menu_state == MENU_12_24:
            if hour_mode_24 == True:
                shiftOut([0x14, 0x4B, 0xFF, 0x53])
            else:
                shiftOut([0x73, 0x1C, 0xFF, 0x53])
        elif menu_state == MENU_BRIGHT:
            shiftOut([0x08, 0xD6, 0x33, 0xDF])
        elif menu_state == MENU_NIGHT_FADE:
            if night_time_fade == True:
                shiftOut([0x8E, 0xA, 0xDE, 0xA])
            else:
                shiftOut([0x8E, 0xA, 0x14, 0xA])
        # Check menu timeout
        if time.monotonic() > (time_in_menu + 10):
            main_state = MAIN_TIME

    # Now handle all the button states
    # First the hour button:
    if hourButton.value == False:
        while hourButton.value == False:
            pass
        time.sleep(0.05) # Debounce pause

        # We're going to check for double presses, so record when the first
        # press happened. If we detect another press in the next 200ms then we
        # have a double press.
        lastButt = time.monotonic()
        while lastButt > (time.monotonic() - 0.15):
            if hourButton.value == False:
                double_press = True
                while hourButton.value == False:
                    pass

        if double_press == False:
            if main_state == MAIN_TIME:
                # Increment the hour by 1
                hour = t.tm_hour
                if hour == 23:
                    hour = 0
                else:
                    hour += 1
                t = time.struct_time((t.tm_year, t.tm_mon, t.tm_mday, hour, t.tm_min, t.tm_sec, 0, -1, -1))
                rtc.datetime = t
            else:
                # Rotate around menus
                if menu_state == MENU_12_24:
                    menu_state = MENU_BRIGHT
                elif menu_state == MENU_BRIGHT:
                    menu_state = MENU_NIGHT_FADE
                else:
                    menu_state = MENU_12_24
                time_in_menu = time.monotonic()
        else:
            # If we detect a double press switch between showing the time and the menu
            if main_state == MAIN_TIME:
                main_state = MAIN_MENU
                # set reset timeout
                time_in_menu = time.monotonic()
            else:
                main_state = MAIN_TIME

        double_press = False

    # Now check the minute button:
    if minButton.value == False:
        if main_state == MAIN_TIME:
            # Increment the time by 1 minute
            # Note: The hour does not increment
            minute = t.tm_min
            if minute == 59:
                minute = 0
            else:
                minute += 1

            t = time.struct_time((t.tm_year, t.tm_mon, t.tm_mday, t.tm_hour, minute, t.tm_sec, 0, -1, -1))
            rtc.datetime = t
            time.sleep(0.2)
            # Check if the button is being held.
            # If it is then begin fast incrementing the minutes
            while minButton.value == False:
                if minute == 59:
                    minute = 0
                else:
                    minute += 1

                t = time.struct_time((t.tm_year, t.tm_mon, t.tm_mday, t.tm_hour, minute, t.tm_sec, 0, -1, -1))
                rtc.datetime = t
                IV3_set(t.tm_hour, t.tm_min, dps)
                time.sleep(0.1)
        else:
            # Wait for the button to be released
            while minButton.value == False:
                pass
            time_in_menu = time.monotonic()

            # Change settings accordingly
            if menu_state == MENU_12_24:
                if hour_mode_24 == True:
                    hour_mode_24 = False
                else:
                    hour_mode_24 = True
            elif menu_state == MENU_BRIGHT:
                if brightness < 0xFFFF:
                    brightness = brightness + 0x1000
                else:
                    brightness = 0x6FFF
                OE.duty_cycle = brightness
            else:
                if night_time_fade == True:
                    night_time_fade = False
                else:
                    night_time_fade = True
