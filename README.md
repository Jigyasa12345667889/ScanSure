# ScanSure – Fake Product Detection System

**Verify. Trust. Stay Safe.**

##  About the Project

ScanSure is an AI-based Fake Product Detection Web Application designed to identify potentially counterfeit products using image classification techniques.

The system uses a Convolutional Neural Network (CNN) with MobileNetV2 architecture to classify product images into two categories: Genuine and Fake.

##  Project Objectives

- Detect potentially fake products using AI and Machine Learning.
- Provide product authenticity predictions.
- Display prediction confidence scores.
- Maintain scan history for users.
- Help users make safer purchasing decisions.

##  Key Features

- User Registration and Login
- Product Image Upload
- Real-Time Camera Scanning
- AI-Based Product Classification
- Genuine/Fake Prediction
- Confidence Score
- User Dashboard
- Scan History
- Product Verification
- Admin Management

##  Machine Learning Model

- Algorithm: Convolutional Neural Network (CNN)
- Architecture: MobileNetV2
- Framework: TensorFlow and Keras
- Image Size: 224 × 224 pixels
- Dataset Classes: Genuine and Fake
- Training Split: 80%
- Validation Split: 20%
- Training Epochs: 10
- Batch Size: 16

##  Technologies Used

**Frontend:** HTML, CSS, JavaScript

**Backend:** Python, Flask

**Database:** MySQL

**Machine Learning:** TensorFlow, Keras, MobileNetV2

**Tools:** VS Code, XAMPP, Git, GitHub

##  Project Structure

```text
ScanSure/
│
├── ml_model/
├── static/
├── templates/
├── app.py
├── classes.json
├── requirements.txt
└── README.md
```

##  Installation and Setup

1. Clone the repository:

```bash
git clone YOUR_GITHUB_REPOSITORY_URL
```

2. Open the project folder:

```bash
cd ScanSure
```

3. Install the required dependencies:

```bash
pip install -r requirements.txt
```

4. Configure your MySQL database and credentials securely.

5. Run the Flask application:

```bash
python app.py
```

6. Open your browser and visit:

```text
http://127.0.0.1:5000
```

##  Disclaimer

ScanSure provides preliminary AI-based product classification. Its predictions should not be considered a guarantee of product authenticity.

##  Project Information

**Project Name:** ScanSure

**Project Type:** BCA AI & DS Mini Project

**Domain:** Artificial Intelligence and Machine Learning

**Developed By:** ScanSure Project Team

