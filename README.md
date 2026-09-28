# 🚦 AI Traffic Management System

An AI-powered traffic monitoring and violation management system built using **YOLOv8, Django, OpenCV, EasyOCR, and Python**. The system detects traffic-rule violations from images/video streams, identifies vehicle license plates, records violations, and can notify registered vehicle owners.

---

## 📌 Overview

The **AI Traffic Management System** uses computer vision and deep learning to automate traffic-rule monitoring.

The system can detect violations such as:

* 🪖 Helmet violations
* 🦺 Seatbelt violations
* 🚗 Vehicle detection
* 🔢 License plate detection
* 📷 License plate text recognition using OCR
* ⚠️ Traffic violation recording
* 👤 Vehicle-owner lookup
* 📧 Violation notification
* 💰 Fine/penalty recording

The backend is developed using **Django**, while **YOLOv8 and OpenCV** handle computer-vision processing.

---

## ✨ Features

### 1. Vehicle Detection

YOLOv8 is used to detect vehicles and other objects from images or video streams.

### 2. Helmet Violation Detection

The system analyzes detected two-wheelers and identifies whether the rider is wearing a helmet.

### 3. Seatbelt Violation Detection

The system can identify vehicles where the driver/passenger is not wearing a seatbelt.

### 4. License Plate Detection

A dedicated license-plate detection model is used to locate vehicle registration plates.

### 5. License Plate Recognition

**EasyOCR** is used to extract the registration number from the detected license plate.

### 6. Violation Management

Detected violations can be recorded in the Django database along with relevant information such as:

* Vehicle number
* Violation type
* Date and time
* Violation image
* Fine amount
* Vehicle-owner information

### 7. Owner Identification

The recognized vehicle number can be used to search the registered owner in the system.

### 8. Notification System

The system can send a notification to the registered vehicle owner when a violation is recorded.

### 9. Django Web Dashboard

The Django application provides interfaces for managing:

* Users
* Vehicle owners
* Traffic violations
* Detection results
* Administrative operations

---

## 🛠️ Technology Stack

| Technology | Purpose                        |
| ---------- | ------------------------------ |
| Python     | Core programming language      |
| Django     | Backend/Web framework          |
| YOLOv8     | Object and violation detection |
| OpenCV     | Image and video processing     |
| EasyOCR    | License plate text recognition |
| PyTorch    | Deep learning framework        |
| SQLite     | Database                       |
| HTML/CSS   | Frontend                       |
| JavaScript | Client-side functionality      |
| Git/GitHub | Version control                |

---

## 📂 Project Structure

```text
AI_Traffic/
│
├── AI_traffic/
│   ├── settings.py
│   ├── urls.py
│   ├── asgi.py
│   └── wsgi.py
│
├── detection/
│   ├── migrations/
│   ├── templates/
│   ├── ai_detection.py
│   ├── models.py
│   ├── views.py
│   ├── urls.py
│   └── ...
│
├── media/
│   ├── owner_images/
│   ├── user_images/
│   └── violation_images/
│
├── models/
│   ├── helmet_detector.pt
│   ├── seatbelt_detector.pt
│   └── number_plate_detector.pt
│
├── manage.py
├── requirements.txt
├── yolov8n.pt
├── .gitignore
└── README.md
```

> The exact files and folders may vary depending on the current project version.

---

# ⚙️ Installation

## 1. Clone the Repository

```bash
git clone https://github.com/hardikchandra60/AI_TRAFFIC_DETECTION_SYSTEM_USING_YOLOv8_AND_DJANGO.git
```

Move into the project directory:

```bash
cd AI_TRAFFIC_DETECTION_SYSTEM_USING_YOLOv8_AND_DJANGO
```

---

## 2. Create a Virtual Environment

### Windows

```bash
python -m venv venv
```

Activate it:

```bash
venv\Scripts\activate
```

---

## 3. Install Dependencies

Install the required Python packages:

```bash
pip install -r requirements.txt
```

---

## 4. Configure Environment Variables

Create a `.env` file in the project root.

Example:

```env
TWILIO_ACCOUNT_SID=your_account_sid
TWILIO_AUTH_TOKEN=your_auth_token
TWILIO_PHONE_NUMBER=your_twilio_phone_number
```

**Never commit your `.env` file to GitHub.**

The project uses environment variables so sensitive credentials are kept outside the source code.

---

# 🗄️ Database Setup

Run Django migrations:

```bash
python manage.py makemigrations
python manage.py migrate
```

Create an administrator account:

```bash
python manage.py createsuperuser
```

Follow the instructions in the terminal to create your admin account.

---

# ▶️ Running the Project

Start the Django development server:

```bash
python manage.py runserver
```

Open the application in your browser:

```text
http://127.0.0.1:8000/
```

The Django administration panel is available at:

```text
http://127.0.0.1:8000/admin/
```

---

# 🔄 System Workflow

```text
Camera / Image / Video
          │
          ▼
     OpenCV Input
          │
          ▼
       YOLOv8
          │
          ▼
   Object Detection
          │
     ┌────┴─────┐
     │          │
     ▼          ▼
 Helmet      Seatbelt
Detection    Detection
     │          │
     └────┬─────┘
          ▼
   License Plate
      Detection
          │
          ▼
       EasyOCR
          │
          ▼
   Vehicle Number
     Recognition
          │
          ▼
   Owner Database
      Lookup
          │
          ▼
 Violation Recorded
          │
          ▼
 Fine / Notification
```

---

# 🧠 AI Models

The project uses multiple trained/pre-trained models for different detection tasks.

### YOLOv8

Used for general object detection and traffic-related detection tasks.

### Helmet Detection Model

Used to identify helmet-related traffic violations.

### Seatbelt Detection Model

Used to identify seatbelt violations.

### Number Plate Detection Model

Used to locate vehicle registration plates.

### EasyOCR

Used to extract text from detected license plates.

---

# 📡 Important API Endpoints

The Django backend contains APIs for traffic-management operations.

Examples include:

```text
/api/record_violation/
/api/find_owner_by_plate/
/live_feed/
```

These endpoints support violation recording, vehicle-owner lookup, and live detection functionality.

---

# 📸 Media

The application can store images associated with:

```text
media/
├── owner_images/
├── user_images/
└── violation_images/
```

Violation images can be used as evidence associated with detected traffic violations.

---

# 🔐 Security

Sensitive information such as:

* API credentials
* Twilio credentials
* Authentication tokens
* Secret keys

should be stored in environment variables.

Example:

```python
import os

TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
```

Do not upload `.env` to GitHub.

---

# 🚀 Future Improvements

Possible future improvements include:

* Real-time multi-camera monitoring
* Improved license plate recognition accuracy
* Automatic number-plate verification
* Cloud database integration
* Mobile application
* Real-time SMS/email notifications
* Advanced traffic analytics
* Vehicle speed detection
* Red-light violation detection
* Traffic-density analysis
* Cloud deployment
* Improved AI model accuracy
* Role-based access control

---

# 🎯 Project Objective

The primary objective of this project is to demonstrate how **Artificial Intelligence and Computer Vision can be used to automate traffic-rule monitoring and violation management**.

By combining YOLOv8, OpenCV, OCR, and Django, the system provides a foundation for an automated traffic-monitoring platform capable of detecting violations and managing the resulting records.

---

# 👨‍💻 Author

**Hardik Chandra**

MCA — IILM University, Greater Noida

---

# 📄 License

This project is intended for **educational and demonstration purposes**.

Before deploying the system in a real-world traffic-management environment, additional testing, security controls, legal compliance, data protection measures, and validation would be required.
