
from rover.camera_system import CameraSystem
from rover.sonar_led import SonarLEDS
import cv2
from rover.vehicle import Vehicle
from rover.drivetrain import Drivetrain
from rover.motor import Motor
from rover.sonar import Sonar
import time
import gpiozero
import signal
from rover.camera import Camera
from rover import *
import numpy as np
from rover.servo import Servo
from rover import constants

import cv2
import socket
import struct
import pickle
import threading

pan_servo = Servo(constants.CAMERA_SERVOS['pan'])
tilt_servo = Servo(constants.CAMERA_SERVOS['tilt'])
sonar_leds = SonarLEDS()

pan_angle = 90
tilt_angle = 100

angle = 90
pan_direction = 1  # 1 for right, -1 for left
count = 0

sonar = Sonar()

pan_servo.set_angle(pan_angle)
tilt_servo.set_angle(tilt_angle)

drivetrain = Drivetrain()

# ---------------------------
# Command Listener Definition
# ---------------------------
def command_listener():

    global pan_angle
    global tilt_angle 
    global angle
    global count
    global pan_direction

    command_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    command_socket.bind(("0.0.0.0", 8486))  # Listen on port 8486 for commands
    command_socket.listen(1)
    print("Command listener waiting for connection on port 8486...")
    conn, addr = command_socket.accept()
    print("Command connection from:", addr)
    count = 0
    

    pan_servo.set_angle(pan_angle)
    tilt_servo.set_angle(tilt_angle)  
    
    while True:
        try:
            
            
            # Receive command message (max 1024 bytes)
            command = conn.recv(1024).decode('utf-8').strip()
            if not command:
                break  # Connection closed
            print("Received command:", command)
            
            # Here you would translate the command into motor control or GPIO actions.
            # For example:
            if command == "PAN LEFT":
                sonar_leds.left.setPixelColor(0xFF0000)
                sonar_leds.right.setPixelColor(0x000000)
                drivetrain.set_motion(speed=0, heading=angle)
                pan_angle += 2
                if (pan_angle >= 170):
                    drivetrain.set_motion(angular_speed = 100)
                    time.sleep(0.5)
                    drivetrain.set_motion(angular_speed = 0)
                    pan_angle = 90
                pan_servo.set_angle(pan_angle)
                print("IM PANNING LEFT")
            elif command == "PAN RIGHT":
                sonar_leds.right.setPixelColor(0xFF0000)
                sonar_leds.left.setPixelColor(0x000000)
                drivetrain.set_motion(speed=0, heading=angle)
                pan_angle -= 2
                if (pan_angle <= 10):
                    pan_angle = 90
                    drivetrain.set_motion(angular_speed = -100)
                    time.sleep(0.5)
                    drivetrain.set_motion(angular_speed = 0)
                pan_servo.set_angle(pan_angle)
                print("IM PANNING RIGHT")
            if command == "PAN UP":
                sonar_leds.left.setPixelColor(0xFF0000)
                sonar_leds.right.setPixelColor(0xFF0000)
                drivetrain.set_motion(speed=0, heading=angle)
                tilt_angle += 2
                if (tilt_angle >= 170):
                    tilt_angle = 170
                tilt_servo.set_angle(tilt_angle)
                print("IM PANNING UP")
            elif command == "PAN DOWN":
                sonar_leds.left.setPixelColor(0xFF0000)
                sonar_leds.right.setPixelColor(0xFF0000)
                drivetrain.set_motion(speed=0, heading=angle)
                tilt_angle -= 2
                if (tilt_angle <= 10):
                    tilt_angle = 10
                tilt_servo.set_angle(tilt_angle)
                print("IM PANNING DOWN")
            if command == "MOVE BACK":
                sonar_leds.left.setPixelColor(0xFFFF00)
                sonar_leds.right.setPixelColor(0xFFFF00)
                drivetrain.set_motion(speed = 50, heading = (180 + pan_angle) % 360)
                time.sleep(0.5)
                drivetrain.set_motion(speed = 0, heading = 90)
                
                
                print("RUH ROH I WANNA LEAVE")
            elif command == "TAKE PICTURE":
                sonar_leds.left.setPixelColor(0x00FF00)
                sonar_leds.right.setPixelColor(0x00FF00)
                time.sleep(3)
                sonar_leds.left.setPixelColor(0x000000)
                sonar_leds.right.setPixelColor(0x000000)
                drivetrain.set_motion(speed = 0, heading = 0)
                
            elif command == "EMAIL SENT":
                sonar_leds.left.setPixelColor(0x00FF00)
                sonar_leds.right.setPixelColor(0x00FF00)
                time.sleep(3)
                sonar_leds.left.setPixelColor(0x000000)
                sonar_leds.right.setPixelColor(0x000000)
                drivetrain.set_motion(angular_speed = 100)
                time.sleep(3)
                drivetrain.set_motion(angular_speed = 0)
                print("Moving backward and left")
            elif command == "DOWN_RIGHT":
                # Move backward and right
                print("Moving backward and right")
            elif command == "STOP":
                # Stop the vehicle
                print("Stopping")
            elif command == "ROAM":
                #Do da roaming:
                sonar_leds.left.setPixelColor(0x0000FF)
                sonar_leds.right.setPixelColor(0x0000FF)
                count += 1
                drivetrain.set_motion(speed=40, heading=angle)
                
                val = sonar.get_distance()
                
                pan_angle += 10 * pan_direction
                if pan_angle >= 160:  # Right limit
                    pan_angle = 160
                    pan_direction = -1
                elif pan_angle <= 20:  # Left limit
                    pan_angle = 20
                    pan_direction = 1
                pan_servo.set_angle(pan_angle)
    
                time.sleep(0.1)  # Smooth loop timing
                
                if (val < 400):
                    angle = (angle + 180) % 360
                    drivetrain.set_motion(speed=70, heading= angle)
                    time.sleep(1)
                    drivetrain.set_motion(speed = 0, angular_speed = 100)
                    time.sleep(0.5)
                    drivetrain.set_motion(angular_speed = 0)
                
                
        except Exception as e:
            print("Error in command listener:", e)
            break
    
    conn.close()
    command_socket.close()

# Run the command listener in a separate thread so it doesn't block video streaming.
command_thread = threading.Thread(target=command_listener, daemon=True)
command_thread.start()

# ---------------------------
# Video Streaming Server
# ---------------------------
cap = cv2.VideoCapture(0)  # Use Pi's camera; adjust index if needed

# Create socket for video streaming
video_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
video_socket.bind(("0.0.0.0", 8485))  # Listen on port 8485 for video stream
video_socket.listen(5)
print("Waiting for video connection on port 8485...")
conn, addr = video_socket.accept()
print("Video connection from:", addr)

# Prepare for sending frames
payload_size = struct.calcsize("Q")

while True:
    ret, frame = cap.read()
    if not ret:
        break

    # Serialize the frame using pickle
    data = pickle.dumps(frame)
    # Pack the size of the frame before sending
    message_size = struct.pack("Q", len(data))
    
    try:
        # Send the frame size followed by the frame data
        conn.sendall(message_size + data)
    except Exception as e:
        print("Video stream error:", e)
        break

cap.release()
conn.close()
video_socket.close()

