import RPi.GPIO as GPIO
import time
from threading import Thread, Lock
import os

FIFO_PATH = "/tmp/detection_fifo"  # FIFO path for communication

class Sorter:
    def __init__(self, servo_pin=18, bolt_duty=7.5, nut_duty=5.5, default_duty=6.5, 
                 hold_time=3, distance_to_flapper=1.0):
        self.servo_pin = servo_pin
        self.bolt_duty = bolt_duty
        self.nut_duty = nut_duty
        self.default_duty = default_duty
        self.hold_time = hold_time
        self.distance_to_flapper = distance_to_flapper  # Distance from camera to flapper in meters
        self.conveyor_speed = 0.5  # Default conveyor speed in m/s
        self.speed_lock = Lock()  # Lock for synchronized access to conveyor speed
        
        # Ensure FIFO exists
        if not os.path.exists(FIFO_PATH):
            os.mkfifo(FIFO_PATH)

        # Set up GPIO
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(self.servo_pin, GPIO.OUT)
        self.servo = GPIO.PWM(self.servo_pin, 50)  # 50Hz PWM frequency
        self.servo.start(0)  # Start PWM (stopped)

        # Move servo to default position
        self.move_to_position(self.default_duty)

    def calculate_travel_time(self):
        """
        Calculate the travel time from the camera to the flapper based on conveyor speed.

        :return: Travel time in seconds.
        """
        with self.speed_lock:
            if self.conveyor_speed > 0:
                return self.distance_to_flapper / self.conveyor_speed
            else:
                print("Invalid conveyor speed. Cannot calculate travel time.")
                return 0

    def move_to_position(self, duty_cycle):
        """Move the servo to a specific duty cycle."""
        self.servo.ChangeDutyCycle(duty_cycle)
        time.sleep(0.2)  # Allow movement
        self.servo.ChangeDutyCycle(0)  # Stop signal to servo

    def actuate_flapper(self, object_type):
        """Actuate the servo based on detected object type after the calculated travel time."""
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

    def process_fifo(self):
        """Listen to the FIFO for both detected objects and speed updates."""
        print("Listening for detections and speed updates...")

        while True:
            try:
                with open(FIFO_PATH, "r") as fifo:
                    for line in fifo:
                        line = line.strip()
                        
                        if line.startswith("Speed:"):
                            # Update conveyor speed
                            speed = float(line.split(":")[1].strip())
                            with self.speed_lock:
                                self.conveyor_speed = speed
                            print(f"Updated conveyor speed to {self.conveyor_speed:.2f} m/s")
                        else:
                            # Detected object
                            detected_object = line
                            if detected_object:
                                print(f"Received detection: {detected_object}. Processing now.")
                                
                                # Calculate travel time and actuate flapper
                                travel_time = self.calculate_travel_time()
                                print(f"Calculated travel time: {travel_time:.2f} seconds")
                                
                                # Wait for the calculated travel time before actuating the flapper
                                Timer(travel_time, self.actuate_flapper, args=(detected_object,)).start()

            except FileNotFoundError:
                print(f"Error: FIFO path {FIFO_PATH} not found. Please ensure FIFO is created.")
                break
            except KeyboardInterrupt:
                print("\nStopping sorter...")
                break
            except Exception as e:
                print(f"Error reading FIFO: {e}")
                time.sleep(1)  # Small delay before retrying in case of error

    def start(self):
        """Start the sorter system."""
        # Start listening for FIFO updates in a separate thread
        fifo_thread = Thread(target=self.process_fifo, daemon=True)
        fifo_thread.start()

        # Main thread can continue doing other things or sleep
        while True:
            try:
                time.sleep(1)  # Main thread can handle other tasks if necessary
            except KeyboardInterrupt:
                print("\nStopping sorter...")
                break

    def cleanup(self):
        """Reset and clean up GPIO resources."""
        self.move_to_position(self.default_duty)
        self.servo.stop()
        GPIO.cleanup()

if __name__ == "__main__":
    sorter = Sorter()
    try:
        sorter.start()
    except KeyboardInterrupt:
        print("\nStopping sorter...")
    finally:
        sorter.cleanup()
