#!/usr/bin/env python3

import serial
import struct
import spidev
import time
import signal
import RPi.GPIO as GPIO

# ==========================================================
# CONFIGURATION
# ==========================================================

UART_PORT = "/dev/serial0"
UART_BAUD = 256000

ADC_CHANNEL = 0
ADC_THRESHOLD = 290
ADC_SAMPLES = 10

BUZZER_PIN = 2

PRESENT_SAMPLES = 3
ABSENT_SAMPLES = 5

BUZZER_ON_MS = 100
BUZZER_OFF_MS = 100

LOOP_DELAY = 0.1

MAX_WORKSTATION_DISTANCE_CM = 150

GATE0_STATIC_THRESHOLD = 15
GATE1_STATIC_THRESHOLD = 15

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

# buzzer off
GPIO.output(BUZZER_PIN, GPIO.LOW)

# ==========================================================
# SPI MCP3008
# ==========================================================

spi = spidev.SpiDev()
spi.open(0, 0)
spi.max_speed_hz = 500000


def read_adc(channel):

    adc = spi.xfer2(
        [1, (8 + channel) << 4, 0]
    )

    return ((adc[1] & 3) << 8) + adc[2]


def read_average(channel, samples):

    total = 0

    for _ in range(samples):

        total += read_adc(channel)

        time.sleep(0.001)

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
            timeout=0.1
        )

    def close(self):

        self.ser.close()

    # ------------------------------------------------------
    # Generic command sender
    # ------------------------------------------------------

    def send_command(self, cmd):

        if not cmd:
            return

        self.ser.write(cmd)

        time.sleep(0.2)

        ack = self.ser.read(64)

        print("RADAR ACK:", ack.hex())

    # ------------------------------------------------------
    # Radar Configuration
    # ------------------------------------------------------

    def configure_for_esd_workstation(self):

        print("Configuring LD2410...")

        # ==================================================
        # TODO:
        # ENTER CONFIG MODE COMMAND
        # ==================================================
        enter_config_cmd = b'\xFD \xFC \xFB \xFA \x04 \x00 \xFF \x00 \x01 \x00 \x04 \x03 \x02 \x01'
        self.send_command(enter_config_cmd)

        # ==================================================
        # TODO:
        # ENABLE ENGINEERING MODE
        # ==================================================
        engineering_mode_cmd = b'\xFD \xFC \xFB \xFA \x02 \x00 \x62 \x00 \x04 \x03 \x02 \x01'
        self.send_command(engineering_mode_cmd)

        # ==================================================
        # TODO:
        # SET MAX RANGE TO 150 cm
        # ==================================================
        range_cmd = b'\xFD \xFC \xFB \xFA \x14 \x00 \x60 \x00 \x00 \x00 \x08 \x00 \x00 \x00 \x01 \x00 \x08 \x00 \x00 \x00 \x02 \x00 \x05 \x00 \x00 \x00 \x03 \x02 \x01'
        self.send_command(range_cmd)

        # ==================================================
        # TODO:
        # GATE0 STATIC SENSITIVITY
        # ==================================================
        gate0_static_cmd = b'\xFD \xFC \xFB \xFA \x14 \x00 \x64 \x00 \x00 \x00 \x00 \x00 \x00 \x00 \x01 \x00 \x00 \x00 \x00 \x00 \x02 \x00 \x28 \x00 \x00 \x00 \x04 \x03 \x02 \x01'
        self.send_command(gate0_static_cmd)

        # ==================================================
        # TODO:
        # GATE1 STATIC SENSITIVITY
        # ==================================================
        gate1_static_cmd = b'\xFD \xFC \xFB \xFA \x14 \x00 \x64 \x00 \x00 \x00 \x01 \x00 \x00 \x00 \x01 \x00 \x00 \x00 \x00 \x00 \x02 \x00 \x28 \x00 \x00 \x00 \x04 \x03 \x02 \x01'
        self.send_command(gate1_static_cmd)



        # ==================================================
        # TODO:
        # EXIT CONFIG MODE
        # ==================================================
        exit_cmd = b'\xFD \xFC \xFB \xFA \x02 \x00 \xFE \x00 \x04 \x03 \x02 \x01'
        self.send_command(exit_cmd)

        print("LD2410 configuration complete")

    # ------------------------------------------------------
    # Read Frame
    # ------------------------------------------------------

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

        if len(payload) < 11:
            return None

        data_type = payload[0]

        # --------------------------------------------------
        # NORMAL MODE
        # --------------------------------------------------

        if data_type != 0x02:
            return None

        if payload[1] != 0xAA:
            return None

        info = {

            "target_state":
                payload[2],

            "motion_distance":
                payload[3] |
                (payload[4] << 8),

            "motion_energy":
                payload[5],

            "stationary_distance":
                payload[6] |
                (payload[7] << 8),

            "stationary_energy":
                payload[8],

            "detection_distance":
                payload[9] |
                (payload[10] << 8),

            "gate0_motion": 0,
            "gate1_motion": 0,
            "gate0_static": 0,
            "gate1_static": 0
        }

        # --------------------------------------------------
        # TODO:
        # ENGINEERING MODE PARSING
        #
        # UPDATE OFFSETS BELOW AFTER
        # VERIFYING FRAME STRUCTURE
        # --------------------------------------------------

        if len(payload) > 30:

            try:

                info["gate0_motion"] = payload[13]
                info["gate1_motion"] = payload[14]

                info["gate0_static"] = payload[22]
                info["gate1_static"] = payload[23]

            except Exception:
                pass

        return info


# ==========================================================
# PRESENCE FILTER
# ==========================================================

class PresenceFilter:

    def __init__(
        self,
        present_required,
        absent_required
    ):

        self.present_required = present_required
        self.absent_required = absent_required

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

        if not self.state:

            if self.present_count >= self.present_required:

                self.state = True

        else:

            if self.absent_count >= self.absent_required:

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
# WORKSTATION DETECTION
# ==========================================================

def workstation_presence(info):

    # ------------------------------------------------------
    # Future engineering mode logic
    # ------------------------------------------------------

    if (
        info["gate0_static"] > GATE0_STATIC_THRESHOLD
        or
        info["gate1_static"] > GATE1_STATIC_THRESHOLD
    ):
        return True

    # ------------------------------------------------------
    # Current normal mode logic
    # ------------------------------------------------------

    if info["target_state"] not in (
        0x02,
        0x03
    ):
        return False

    if (
        info["detection_distance"]
        > MAX_WORKSTATION_DISTANCE_CM
    ):
        return False

    return True


# ==========================================================
# STARTUP
# ==========================================================

radar = LD2410(
    UART_PORT,
    UART_BAUD
)

# Configure radar
radar.configure_for_esd_workstation()

presence = PresenceFilter(
    PRESENT_SAMPLES,
    ABSENT_SAMPLES
)

buzzer = ActiveBuzzer(
    BUZZER_PIN
)

state_names = {
    0: "NO_TARGET",
    1: "MOVING",
    2: "STATIONARY",
    3: "MOVING+STATIONARY"
}

print()
print("========================================")
print(" ESD COMPLIANCE MONITOR STARTED")
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

        raw_presence = workstation_presence(
            info
        )

        human_present = presence.update(
            raw_presence
        )

        adc_value = read_average(
            ADC_CHANNEL,
            ADC_SAMPLES
        )

        voltage = (
            adc_value * 3.3
        ) / 1023

        if human_present:

            esd_ok = (
                adc_value <=
                ADC_THRESHOLD
            )

        else:

            esd_ok = True

        print(
            f"Human={'YES' if human_present else 'NO'} | "
            f"Radar={state_names.get(info['target_state'])} | "
            f"Dist={info['detection_distance']:3d}cm | "
            f"MoveE={info['motion_energy']:3d} | "
            f"StatE={info['stationary_energy']:3d} | "
            f"G0S={info['gate0_static']:3d} | "
            f"G1S={info['gate1_static']:3d} | "
            f"ADC={adc_value:6.1f} | "
            f"V={voltage:.2f}V | "
            f"ESD={'OK' if esd_ok else 'FAULT'}"
        )

        if human_present and not esd_ok:

            buzzer.alarm()

        else:

            buzzer.off()

        time.sleep(
            LOOP_DELAY
        )

finally:

    print("\nShutting down...")

    buzzer.off()

    radar.close()

    spi.close()

    GPIO.cleanup()