import RPi.GPIO as GPIO
import time
from threading import Timer
import os

FIFO_PATH = "/tmp/detection_fifo"  # FIFO path for communication

class Sorter:
    def __init__(self, servo_pin=18, bolt_duty=7.5, nut_duty=5.5, default_duty=6.5, 
                 hold_time=3):
        self.servo_pin = servo_pin
        self.bolt_duty = bolt_duty
        self.nut_duty = nut_duty
        self.default_duty = default_duty
        self.hold_time = hold_time

        # Set up GPIO
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(self.servo_pin, GPIO.OUT)
        self.servo = GPIO.PWM(self.servo_pin, 50)  # 50Hz PWM frequency
        self.servo.start(0)  # Start PWM (stopped)

        # Move servo to default position
        self.move_to_position(self.default_duty)

    def move_to_position(self, duty_cycle):
        """Move the servo to a specific duty cycle."""
        self.servo.ChangeDutyCycle(duty_cycle)
        time.sleep(0.2)  # Allow movement
        self.servo.ChangeDutyCycle(0)  # Stop signal to servo

    def actuate_flapper(self, object_type):
        """Actuate the servo based on detected object type."""
        if object_type == "bolt":
            print("Sorting a bolt...")
            self.move_to_position(self.bolt_duty)
        elif object_type == "nut":
            print("Sorting a nut...")
            self.move_to_position(self.nut_duty)
        else:
            print("Unknown object type detected. Skipping sorting.")
            return

        # Reset servo after hold time
        Timer(self.hold_time, self.move_to_position, args=(self.default_duty,)).start()

    def process_detections(self):
        """Continuously read from the FIFO and actuate sorter."""
        print("Waiting for detections and speed...")

        while True:
            with open(FIFO_PATH, "r") as fifo:
                for line in fifo:
                    if line.startswith("Speed:"):
                        # Read speed
                        speed = float(line.strip().split(":")[1])
                        print(f"Conveyor speed received: {speed} m/s")
                    else:
                        detected_object = line.strip()
                        if detected_object:
                            print(f"Received: {detected_object}. Sorting now.")
                            self.actuate_flapper(detected_object)

    def cleanup(self):
        """Reset and clean up GPIO resources."""
        self.move_to_position(self.default_duty)
        self.servo.stop()
        GPIO.cleanup()

if __name__ == "__main__":
    sorter = Sorter()
    try:
        sorter.process_detections()
    except KeyboardInterrupt:
        print("\nStopping sorter...")
    finally:
        sorter.cleanup()
