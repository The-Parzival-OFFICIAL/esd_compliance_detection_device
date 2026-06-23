#!/usr/bin/python3

"""
==============================================================
FAST RESPONSE ESD COMPLIANCE MONITOR
LOW LATENCY VERSION
HLK-LD2410C + MCP3008 + BUZZER
==============================================================
"""

import serial
import struct
import spidev
import time
import signal
import RPi.GPIO as GPIO

# ==========================================================
# CONFIG
# ==========================================================

UART_PORT = "/dev/serial0"
UART_BAUD = 256000

ADC_CHANNEL = 0
ADC_THRESHOLD = 290
ADC_SAMPLES = 3

BUZZER_PIN = 2

# FAST RESPONSE FILTERS
PRESENT_SAMPLES = 1
ABSENT_SAMPLES = 2

BUZZER_ON_MS = 100
BUZZER_OFF_MS = 100

LOOP_DELAY = 0.02

# ==========================================================
# DETECTION THRESHOLD
# ==========================================================

MOTION_THRESHOLD = 25

# ==========================================================
# GLOBALS
# ==========================================================

running = True

# ==========================================================
# SIGNAL HANDLER
# ==========================================================

def stop_handler(signum, frame):

    global running

    running = False


signal.signal(signal.SIGINT, stop_handler)
signal.signal(signal.SIGTERM, stop_handler)

# ==========================================================
# GPIO
# ==========================================================

GPIO.setmode(GPIO.BCM)

GPIO.setup(BUZZER_PIN, GPIO.OUT)

GPIO.output(BUZZER_PIN, GPIO.LOW)

# ==========================================================
# SPI MCP3008
# ==========================================================

spi = spidev.SpiDev()

spi.open(0, 0)

spi.max_speed_hz = 1000000

# ==========================================================
# ADC FUNCTIONS
# ==========================================================

def read_adc(channel):

    adc = spi.xfer2(
        [1, (8 + channel) << 4, 0]
    )

    return ((adc[1] & 3) << 8) + adc[2]


def read_average(channel, samples):

    total = 0

    for _ in range(samples):

        total += read_adc(channel)

    return total / samples

# ==========================================================
# LD2410 DRIVER
# ==========================================================

class LD2410:

    HEADER = b'\xF4\xF3\xF2\xF1'
    FOOTER = b'\xF8\xF7\xF6\xF5'

    def __init__(self, port, baudrate):

        self.ser = serial.Serial(
            port=port,
            baudrate=baudrate,
            timeout=0.05
        )

        self.ser.reset_input_buffer()

        time.sleep(1)

    # ======================================================
    # CLOSE
    # ======================================================

    def close(self):

        self.ser.close()

    # ======================================================
    # SEND COMMAND
    # ======================================================

    def send_command(self, cmd, name="CMD"):

        print()
        print("=" * 50)
        print(name)
        print("=" * 50)

        self.ser.reset_input_buffer()

        self.ser.write(cmd)

        time.sleep(0.1)

        ack = self.ser.read(64)

        print("ACK:", ack.hex())

    # ======================================================
    # CONFIGURE RADAR
    # ======================================================

    def configure_for_fast_detection(self):

        print("\nCONFIGURING LD2410...\n")

        # --------------------------------------------------
        # ENTER CONFIG
        # --------------------------------------------------

        enter_config_cmd = bytes.fromhex(
            "FD FC FB FA 04 00 FF 00 01 00 04 03 02 01"
        )

        # --------------------------------------------------
        # ENABLE ENGINEERING MODE
        # --------------------------------------------------

        engineering_mode_cmd = bytes.fromhex(
            "FD FC FB FA 02 00 62 00 04 03 02 01"
        )

        # --------------------------------------------------
        # EXIT CONFIG
        # --------------------------------------------------

        exit_cmd = bytes.fromhex(
            "FD FC FB FA 02 00 FE 00 04 03 02 01"
        )

        # --------------------------------------------------
        # MAX GATE = 2 (~0.m)
        # NO PERSON DURATION = 1 sec
        # --------------------------------------------------

        max_gate_cmd = bytes.fromhex(
            "FD FC FB FA "
            "14 00 "
            "60 00 "

            "00 00 02 00 00 00 "
            "01 00 02 00 00 00 "
            "02 00 01 00 00 00 "

            "04 03 02 01"
        )

        # --------------------------------------------------
        # GATE 0
        # --------------------------------------------------

        gate0_cmd = bytes.fromhex(
            "FD FC FB FA "
            "14 00 "
            "64 00 "

            "00 00 00 00 00 00 "
            "01 00 28 00 00 00 "
            "02 00 28 00 00 00 "

            "04 03 02 01"
        )

        # --------------------------------------------------
        # GATE 1
        # --------------------------------------------------

        gate1_cmd = bytes.fromhex(
            "FD FC FB FA "
            "14 00 "
            "64 00 "

            "00 00 01 00 00 00 "
            "01 00 1E 00 00 00 "
            "02 00 1E 00 00 00 "

            "04 03 02 01"
        )

        # --------------------------------------------------
        # DISTANCE RESOLUTION = 0.2m PER GATE
        # --------------------------------------------------

        distance_resolution_cmd = bytes.fromhex(
            "FD FC FB FA "
            "04 00 "
            "AA 00 "
            "01 00 "
            "04 03 02 01"
        )

        # --------------------------------------------------
        # SEND COMMANDS
        # --------------------------------------------------

        self.send_command(
            enter_config_cmd,
            "ENTER CONFIG"
        )

        self.send_command(
            engineering_mode_cmd,
            "ENGINEERING MODE"
        )

        self.send_command(
            max_gate_cmd,
            "SET MAX GATE"
        )

        self.send_command(
            gate0_cmd,
            "CONFIG GATE0"
        )

        self.send_command(
            gate1_cmd,
            "CONFIG GATE1"
        )

        self.send_command(
            distance_resolution_cmd,
            "SET 0.2M RESOLUTION"
        )

        self.send_command(
            exit_cmd,
            "EXIT CONFIG"
        )

        print("\nLD2410 CONFIG COMPLETE\n")

    # ======================================================
    # READ TARGET INFO
    # ======================================================

    def read_target_info(self):

        while True:

            b = self.ser.read(1)

            if not b:
                return None

            if b == self.HEADER[:1]:

                remain = self.ser.read(3)

                if remain == self.HEADER[1:]:
                    break

        length_bytes = self.ser.read(2)

        if len(length_bytes) != 2:
            return None

        length = struct.unpack(
            "<H",
            length_bytes
        )[0]

        payload = self.ser.read(length)

        footer = self.ser.read(4)

        if footer != self.FOOTER:
            return None

        if len(payload) < 31:
            return None

        if payload[0] != 0x01:
            return None

        if payload[1] != 0xAA:
            return None

        info = {

            "target_state":
                payload[2],

            "motion_distance":
                struct.unpack(
                    "<H",
                    payload[3:5]
                )[0],

            "motion_energy":
                payload[5],

            "stationary_distance":
                struct.unpack(
                    "<H",
                    payload[6:8]
                )[0],

            "stationary_energy":
                payload[8],

            "detection_distance":
                struct.unpack(
                    "<H",
                    payload[9:11]
                )[0],

            "gate0_motion":
                payload[13],

            "gate1_motion":
                payload[14],

            "gate2_motion":
                payload[15],
        }

        return info

# ==========================================================
# PRESENCE FILTER
# ==========================================================

class PresenceFilter:

    def __init__(self):

        self.present_count = 0
        self.absent_count = 0
        self.state = False

    def update(self, detected):

        if detected:

            self.present_count += 1
            self.absent_count = 0

        else:

            self.absent_count += 1
            self.present_count = 0

        # FAST DETECT
        if not self.state:

            if self.present_count >= PRESENT_SAMPLES:

                self.state = True

        # FAST CLEAR
        else:

            if self.absent_count >= ABSENT_SAMPLES:

                self.state = False

        return self.state

# ==========================================================
# ACTIVE BUZZER
# ==========================================================

class ActiveBuzzer:

    def __init__(self, pin):

        self.pin = pin

        self.state = False

        self.last_toggle = time.monotonic()

    def off(self):

        GPIO.output(
            self.pin,
            GPIO.LOW
        )

        self.state = False

    def alarm(self):

        now = time.monotonic()

        interval = (
            BUZZER_ON_MS
            if self.state
            else BUZZER_OFF_MS
        )

        if (
            (now - self.last_toggle)
            * 1000
            >= interval
        ):

            self.state = not self.state

            GPIO.output(
                self.pin,
                GPIO.HIGH
                if self.state
                else GPIO.LOW
            )

            self.last_toggle = now

# ==========================================================
# HUMAN DETECTION
# ==========================================================

def workstation_presence(info):

    motion_score = (
        info["gate0_motion"] +
        info["gate1_motion"]
    )

    return (
        motion_score >
        MOTION_THRESHOLD
    )

# ==========================================================
# STARTUP
# ==========================================================

radar = LD2410(
    UART_PORT,
    UART_BAUD
)

radar.configure_for_fast_detection()

presence = PresenceFilter()

buzzer = ActiveBuzzer(
    BUZZER_PIN
)

print()
print("========================================")
print(" FAST ESD MONITOR STARTED")
print("========================================")
print()

# ==========================================================
# MAIN LOOP
# ==========================================================

try:

    while running:

        info = radar.read_target_info()

        if info is None:
            continue

        # --------------------------------------------------
        # HUMAN DETECTION
        # --------------------------------------------------

        raw_presence = workstation_presence(
            info
        )

        human_present = presence.update(
            raw_presence
        )

        # --------------------------------------------------
        # ADC
        # --------------------------------------------------

        adc_value = read_average(
            ADC_CHANNEL,
            ADC_SAMPLES
        )

        voltage = (
            adc_value * 3.3
        ) / 1023

        # --------------------------------------------------
        # ESD CHECK
        # --------------------------------------------------

        if human_present:

            esd_ok = (
                adc_value <=
                ADC_THRESHOLD
            )

        else:

            esd_ok = True

        # --------------------------------------------------
        # DEBUG
        # --------------------------------------------------

        print(
            f"Human={'YES' if human_present else 'NO'} | "
            f"Dist={info['detection_distance']:3d}cm | "
            f"G0={info['gate0_motion']:3d} | "
            f"G1={info['gate1_motion']:3d} | "
            f"ADC={adc_value:6.1f} | "
            f"V={voltage:.2f}V | "
            f"ESD={'OK' if esd_ok else 'FAULT'}"
        )

        # --------------------------------------------------
        # BUZZER
        # --------------------------------------------------

        if human_present and not esd_ok:

            buzzer.alarm()

        else:

            buzzer.off()

        time.sleep(
            LOOP_DELAY
        )

# ==========================================================
# CLEANUP
# ==========================================================

finally:

    print("\nShutting down...")

    buzzer.off()

    radar.close()

    spi.close()

    GPIO.cleanup()