import RPi.GPIO as GPIO
import time
import threading
import os

FIFO_PATH = "/tmp/detection_fifo"  # FIFO path for communication

class ConveyorBelt:
    def __init__(self, step_pin=17, dir_pin=27, en_pin=22, max_speed=15.0):
        """
        Stepper motor control for a conveyor belt.

        :param step_pin: GPIO pin for step pulses.
        :param dir_pin: GPIO pin for motor direction.
        :param en_pin: GPIO pin for enabling the stepper driver.
        :param max_speed: Maximum speed in meters per second.
        """
        self.step_pin = step_pin
        self.dir_pin = dir_pin
        self.en_pin = en_pin
        self.max_speed = max_speed
        self.speed = 5.0  # Default speed in m/s
        self.steps_per_meter = 1000  # Adjust based on motor setup
        self.pulse_interval = 1 / (self.speed * self.steps_per_meter)
        self.running = False
        self.lock = threading.Lock()

        # GPIO setup
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(self.step_pin, GPIO.OUT)
        GPIO.setup(self.dir_pin, GPIO.OUT)
        GPIO.setup(self.en_pin, GPIO.OUT)

        # Default states
        GPIO.output(self.step_pin, GPIO.LOW)
        GPIO.output(self.dir_pin, GPIO.HIGH)  # Always forward
        GPIO.output(self.en_pin, GPIO.LOW)  # Enable stepper driver

        # Ensure FIFO exists
        if not os.path.exists(FIFO_PATH):
            os.mkfifo(FIFO_PATH)

    def set_speed(self, new_speed):
        """Set conveyor speed (in meters/sec)."""
        with self.lock:
            if 0.5 <= new_speed <= self.max_speed:
                self.speed = new_speed
                self.pulse_interval = 1 / (self.speed * self.steps_per_meter)
                print(f"Speed set to {self.speed:.2f} m/s")
                # Instead of blocking the main thread, use a background thread to send the speed to FIFO
                threading.Thread(target=self.send_speed_to_fifo, daemon=True).start()
            else:
                print(f"Speed out of range! (Min: 0.5 m/s, Max: {self.max_speed} m/s)")

    def adjust_speed(self, step):
        """Increase or decrease speed in 0.5 m/s increments."""
        new_speed = self.speed + step
        self.set_speed(new_speed)

    def start(self):
        """Start the conveyor belt."""
        if not self.running:
            print(f"Starting conveyor belt at {self.speed:.2f} m/s...")
            self.running = True
            threading.Thread(target=self.send_steps, daemon=True).start()
        else:
            print("Conveyor belt is already running.")

    def stop(self):
        """Stop the conveyor belt."""
        if self.running:
            print("Stopping conveyor belt...")
            self.running = False
            time.sleep(0.1)  # Small delay before disabling
            GPIO.output(self.en_pin, GPIO.HIGH)  # Disable motor
        else:
            print("Conveyor belt is already stopped.")

    def send_steps(self):
        """Continuously send step pulses to move the conveyor."""
        while self.running:
            GPIO.output(self.step_pin, GPIO.HIGH)
            time.sleep(self.pulse_interval / 2)
            GPIO.output(self.step_pin, GPIO.LOW)
            time.sleep(self.pulse_interval / 2)

    def send_speed_to_fifo(self):
        """Send the current speed to the FIFO."""
        with open(FIFO_PATH, "w") as fifo:
            fifo.write(f"Speed: {self.speed:.2f}\n")

    def cleanup(self):
        """Cleanup GPIO settings."""
        self.stop()
        GPIO.cleanup()


def control_loop(conveyor):
    """User input for conveyor control."""
    print("Controls: 's' - Start, 'e' - Stop, '+' - Increase Speed, '-' - Decrease Speed, 'q' - Quit")

    while True:
        command = input("Enter command: ").strip().lower()
        if command == "s":
            conveyor.start()
        elif command == "e":
            conveyor.stop()
        elif command == "+":
            conveyor.adjust_speed(0.5)
        elif command == "-":
            conveyor.adjust_speed(-0.5)
        elif command == "q":
            conveyor.cleanup()
            print("Exiting conveyor system.")
            break
        else:
            print("Invalid command. Try again.")


# Run the conveyor system
if __name__ == "__main__":
    conveyor = ConveyorBelt()
    try:
        control_loop(conveyor)
    except KeyboardInterrupt:
        print("\nInterrupted by user.")
    finally:
        conveyor.cleanup()
