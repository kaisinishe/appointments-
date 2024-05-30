# FastAPI Booking Application

This is a FastAPI application for managing calendar events with Google Calendar integration, Redis Cloud for data storage, and Ngrok for public access. The application allows users to authorize and manage calendar events.

## Features

- FastAPI for the backend
- Google OAuth2 for calendar access
- Redis Cloud for data storage
- Ngrok for secure public URLs
- Dockerized for easy deployment

## Prerequisites

- Docker
- Ngrok account
- Redis Cloud account
- Google Cloud Platform project for OAuth2 credentials

## Project Tree

```plaintext
├── .dockerignore
├── .env
├── Dockerfile
├── credentials.json
├── entrypoint.sh
├── main.py
├── redis_db.py
├── requirements.txt
├── static/
│   └── favicon.ico
├── templates/
│   ├── frontend.html
│   ├── no_pending_requestors.html
│   ├── target_confirmation.html
│   └── waiting_page.html
└── .venv/
```


bash
Copy code

## Getting Started

### 1. Clone the Repository

```sh
git clone https://github.com/your-username/your-repo.git
cd your-repo
2. Obtain Redis Cloud Credentials
Sign up for a Redis Cloud account at Redis Cloud.
Create a new Redis database.
Note down the Redis host, port, and password.
3. Obtain Ngrok Authtoken
Sign up for an Ngrok account at Ngrok.
Get your authtoken from the Ngrok dashboard.
Run the following command to set up Ngrok with your authtoken:
sh
Copy code
ngrok authtoken YOUR_AUTHTOKEN
4. Set Up Google OAuth2 Credentials
Go to the Google Cloud Console.
Create a new project.
Enable the "Google Calendar API" for the project.
Create OAuth 2.0 credentials.
Download the credentials.json file and place it in the project root directory.
5. Create the .env File
Create a .env file in the project root directory and add the following environment variables:

env
Copy code
REDIS_HOST=your-redis-host
REDIS_PORT=your-redis-port
REDIS_PASSWORD=your-redis-password
NGROK_TARGET_URL=https://your-ngrok-subdomain.ngrok-free.app/callback/target
NGROK_REQUESTOR_URL=https://your-ngrok-subdomain.ngrok-free.app/callback/requestor
6. Build and Run the Docker Container
Build the Docker Image
sh
Copy code
docker build -t fastapi_app .
Run the Docker Container
sh
Copy code
docker run -d -p 8000:8000 --name fastapi_app --env-file .env fastapi_app
7. Access the Application
Open your browser and navigate to:

sh
Copy code
https://your-ngrok-subdomain.ngrok-free.app
Development
Running Locally
You can also run the application locally using a virtual environment:

sh
Copy code
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload
Testing
To run tests, use:

sh
Copy code
pytest
Contributing
Fork the repository.
Create a new branch (git checkout -b feature-branch).
Make your changes.
Commit your changes (git commit -am 'Add new feature').
Push to the branch (git push origin feature-branch).
Create a new Pull Request.



License
This project is licensed under the MIT License. See the LICENSE file for details.

