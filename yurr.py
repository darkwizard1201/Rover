import cv2
import socket
import struct
import pickle
import threading
import torch
from ultralytics import YOLO
import time
import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.image import MIMEImage
import cv2

# Set the IP address of the Raspberry Pi and ports
PI_IP = "172.16.106.235"  # Replace with your Pi's IP address
VIDEO_PORT = 8485
COMMAND_PORT = 8486

model = YOLO("yolov8m.pt")
qr_detector = cv2.QRCodeDetector()

def send_email_with_attachment(recipient_email):
   """Send an email with an image as an attachment."""
  
   # Email account credentials
   sender_email = "uiuccarrierpigeon@gmail.com"  # Replace with your email address
   sender_password = "vorn xjxq pmxh blyy"  # Replace with your email password or app password




  
   # Create email
   msg = MIMEMultipart()
   msg['From'] = sender_email
   msg['To'] = recipient_email
   msg['Subject'] = "You received a delivery from the Carrier Pigeon"
   body = "This is a test email sent from Python."


   with open(r"CarrierPigeon.png", 'rb') as f:
       img = MIMEImage(f.read())
       msg.attach(img)


   try:
       HOST = "smtp.gmail.com"
       PORT = 587  # Make sure this is an integer, not a string
       server = smtplib.SMTP(HOST, PORT)  # Initialize with host and port
       server.starttls()  # Secure connection
       server.login(sender_email, sender_password)  # Login to the email server
       server.sendmail(sender_email, recipient_email, msg.as_string())  # Send email
       server.quit()  # Logout
       print("Email sent successfully.")
   except Exception as e:
       print(f"Failed to send email: {e}")


# Global event for clean termination
terminate_event = threading.Event()

def video_client():
    frame_skip = 5
    frame_count = 0
    picture = 0
    email = None
    scanning = False
    roam_count = 0

    """Connects to the Pi's video stream and displays frames."""
    video_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    video_socket.connect((PI_IP, VIDEO_PORT))
    data = b""
    payload_size = struct.calcsize("Q")
    
    while not terminate_event.is_set():
        try:
            # Receive enough bytes for the payload size
            while len(data) < payload_size:
                packet = video_socket.recv(4096)
                if not packet:
                    print("No video packet received.")
                    terminate_event.set()
                    return
                data += packet

            # Unpack the size of the frame data
            packed_msg_size = data[:payload_size]
            data = data[payload_size:]
            msg_size = struct.unpack("Q", packed_msg_size)[0]

            # Retrieve the actual frame data
            while len(data) < msg_size:
                data += video_socket.recv(4096)

            frame_data = data[:msg_size]
            data = data[msg_size:]

            # Deserialize the frame and display it
            frame = pickle.loads(frame_data)

            frame_count += 1

            avgs = []
            maxy = 0
            miny = 480
            if frame_count % frame_skip == 0:
                if (scanning):
                    value, pts, qr_code = qr_detector.detectAndDecode(frame)
                    cv2.imshow("Video Stream", frame)
                    if cv2.waitKey(1) & 0xFF == ord("q"):
                        terminate_event.set()
                        break
                    email = value

                    if email: 
                        send_email_with_attachment(email)
                        email = None
                        commands.append("EMAIL SENT")
                        scanning = False
                        time.sleep(5)
                    else:
                        continue

                results = model(frame)
                for result in results:
                    for box in result.boxes:
                        if int(box.cls) == 0:
                            if picture >= 10:
                                commands.append("TAKE PICTURE")
                                image_filename = "CarrierPigeon.png"
                                cv2.imwrite(image_filename, frame)
                                print(f"Image saved: {image_filename}")
                                picture = 0
                                scanning = True

                            x1, y1, x2, y2 = map(int, box.xyxy[0])
                            cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
                            avgs.append((x1 + x2)/2)
                            maxy = max(maxy, y1, y2)
                            miny = min(miny, y1, y2)
                
                
                if (len(avgs) != 0):
                    averagex = int(sum(avgs)/len(avgs))
                                
                    if (averagex < 270):
                        commands.append("PAN LEFT")
                        picture = 0
                        roam_count = 0
                    elif (averagex > 370):
                        commands.append("PAN RIGHT")
                        picture = 0
                        roam_count = 0

                    if (maxy > 460 and miny < 20):
                        commands.append("MOVE BACK")
                        picture = 0
                        roam_count = 0
                    elif (maxy > 460):
                        commands.append("PAN DOWN")
                        picture = 0
                        roam_count = 0
                    elif (miny < 20):
                        commands.append("PAN UP")
                        picture = 0
                        roam_count = 0
                    else:
                        picture += 1
                        roam_count = 0
                        
                if (len(commands) == 0 ):
                    roam_count += 1
                    if (roam_count > 4) and "ROAM" not in commands:
                        commands.append("ROAM")
            print (roam_count, commands)

            cv2.imshow("Video Stream", frame)
            if cv2.waitKey(1) & 0xFF == ord("q"):
                terminate_event.set()
                break
        except Exception as e:
            print("Video client error:", e)
            terminate_event.set()
            break

 

    video_socket.close()
    cv2.destroyAllWindows()

def command_client():
    """Connects to the Pi's command listener and sends directional commands."""
    command_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    command_socket.connect((PI_IP, COMMAND_PORT))
    print("Connected to command server.")
    
    while not terminate_event.is_set():
        try:
            while (len(commands) == 0 and not terminate_event.is_set()):
                time.sleep(0.5)
                pass
            cmd = commands[0].strip()
            print(cmd)
            if cmd.lower() == "exit":
                terminate_event.set()
                break
            command_socket.sendall(cmd.encode('utf-8'))
            commands.remove(commands[0])

        except Exception as e:
            print("Command client error:", e)
            terminate_event.set()
            break

    command_socket.close()

if __name__ == "__main__":
    # Start video and command threads

    commands = []

    video_thread = threading.Thread(target=video_client, daemon=True)
    command_thread = threading.Thread(target=command_client, daemon=True)
    
    video_thread.start()
    command_thread.start()
    
    # Wait for both threads to complete
    video_thread.join()
    command_thread.join()
    
    print("Client terminated.")






"""
import cv2
import socket
import struct
import pickle
import torch
from ultralytics import YOLO

# Create socket and connect to Raspberry Pi
client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
client_socket.connect(("172.16.106.235", 8485))  # Replace with Pi's IP address

model = YOLO("yolov8m.pt")

frame_skip = 5
frame_count = 0

data = b""
payload_size = struct.calcsize("Q")

while True:
    while len(data) < payload_size:
        packet = client_socket.recv(4096)  # Adjust buffer size if needed
        if not packet:
            break
        data += packet

    # Extract message size
    packed_msg_size = data[:payload_size]
    data = data[payload_size:]
    msg_size = struct.unpack("Q", packed_msg_size)[0]

    while len(data) < msg_size:
        data += client_socket.recv(4096)

    frame_data = data[:msg_size]
    data = data[msg_size:]

    # Deserialize frame
    frame = pickle.loads(frame_data)

    frame_count += 1

    if frame_count % frame_skip == 0:
        results = model(frame)

        for result in results:
            for box in result.boxes:
                if int(box.cls) == 0:
                    x1, y1, x2, y2 = map(int, box.xyxy[0])
                    cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)

    cv2.imshow("Raspberry Pi Stream", frame)





    if cv2.waitKey(1) & 0xFF == ord("q"):
        break

client_socket.close()
cv2.destroyAllWindows()
"""