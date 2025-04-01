from gpiozero import Servo
from time import sleep
from threading import Thread, Lock, Timer
import os

FIFO_PATH = "/tmp/detection_fifo"  # FIFO path for communication

class Sorter:
    def __init__(self, servo_pin=18, hold_time=3, distance_to_flapper=1.0):
        """
        Initialize the sorter with a gpiozero Servo.
        
        :param servo_pin: GPIO pin connected to the servo.
        :param hold_time: Time in seconds to hold the flapper in sorted position.
        :param distance_to_flapper: Distance from the camera to the flapper (in meters).
        """
        self.servo_pin = servo_pin
        self.hold_time = hold_time
        self.distance_to_flapper = distance_to_flapper  # Distance in meters
        self.conveyor_speed = 0.5  # Default conveyor speed in m/s
        self.speed_lock = Lock()

        # Ensure FIFO exists
        if not os.path.exists(FIFO_PATH):
            os.mkfifo(FIFO_PATH)

        # Set up the servo using gpiozero
        self.servo = Servo(self.servo_pin)
        # Move servo to the default (neutral) position
        self.move_to_position('default')

    def calculate_travel_time(self):
        """
        Calculate the travel time from the camera to the flapper based on the current conveyor speed.
        
        :return: Travel time in seconds.
        """
        with self.speed_lock:
            if self.conveyor_speed > 0:
                return self.distance_to_flapper / self.conveyor_speed
            else:
                print("Invalid conveyor speed. Cannot calculate travel time.")
                return 0

    def move_to_position(self, position):
        """
        Move the servo to a given position.
        
        :param position: A string that can be 'bolt', 'nut', or 'default'.
                         'bolt' sets the servo to maximum (clockwise),
                         'nut' sets it to minimum (counterclockwise),
                         and 'default' returns it to neutral.
        """
        if position == 'bolt':
            print("Moving servo for bolt: maximum clockwise position.")
            self.servo.max()
        elif position == 'nut':
            print("Moving servo for nut: maximum counterclockwise position.")
            self.servo.min()
        elif position == 'default':
            print("Moving servo to default (neutral) position.")
            self.servo.mid()
        else:
            print("Unknown position command.")
        sleep(0.2)

    def actuate_flapper(self, object_type):
        """
        Actuate the flapper based on the detected object type.
        
        :param object_type: Either 'bolt' or 'nut'
        """
        if object_type == "bolt":
            print("Sorting a bolt...")
            self.move_to_position('bolt')
        elif object_type == "nut":
            print("Sorting a nut...")
            self.move_to_position('nut')
        else:
            print("Unknown object type detected. Skipping sorting.")
            return

        # After hold_time, return the servo to the default position
        Timer(self.hold_time, self.move_to_position, args=('default',)).start()

    def process_fifo(self):
        """
        Listen to the FIFO for speed updates and object detection messages.
        Speed update lines should be in the format: "Speed: <value>"
        Other lines are interpreted as detected object types.
        """
        print("Listening for detections and speed updates...")
        while True:
            try:
                with open(FIFO_PATH, "r") as fifo:
                    for line in fifo:
                        line = line.strip()
                        if line.startswith("Speed:"):
                            try:
                                speed = float(line.split(":")[1].strip())
                                with self.speed_lock:
                                    self.conveyor_speed = speed
                                print(f"Updated conveyor speed to {self.conveyor_speed:.2f} m/s")
                            except Exception as e:
                                print(f"Error parsing speed: {e}")
                        else:
                            detected_object = line
                            if detected_object:
                                print(f"Received detection: {detected_object}. Processing now.")
                                travel_time = self.calculate_travel_time()
                                print(f"Calculated travel time: {travel_time:.2f} seconds")
                                Timer(travel_time, self.actuate_flapper, args=(detected_object,)).start()
            except FileNotFoundError:
                print(f"Error: FIFO path {FIFO_PATH} not found. Please ensure FIFO is created.")
                break
            except KeyboardInterrupt:
                print("\nStopping sorter...")
                break
            except Exception as e:
                print(f"Error reading FIFO: {e}")
                sleep(1)  # Delay before retrying

    def start(self):
        """
        Start the sorter system by launching the FIFO listener in a separate thread.
        """
        fifo_thread = Thread(target=self.process_fifo, daemon=True)
        fifo_thread.start()
        try:
            while True:
                sleep(1)
        except KeyboardInterrupt:
            print("\nStopping sorter...")

    def cleanup(self):
        """
        Return the servo to its default position and release servo resources.
        """
        self.move_to_position('default')
        self.servo.detach()
        print("Servo detached.")

if __name__ == "__main__":
    sorter = Sorter()
    try:
        sorter.start()
    except KeyboardInterrupt:
        print("\nStopping sorter...")
    finally:
        sorter.cleanup()
