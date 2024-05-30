#!/bin/bash

# Add your Ngrok authtoken
ngrok authtoken YOUR_NGROK_AUTHTOKEN

# Start Ngrok with your custom domain
ngrok http 8000 --hostname=your-ngrok-subdomain.ngrok-free.app.ngrok-free.app --log=stdout &

# Wait for Ngrok to start
sleep 10

# Start the FastAPI application
exec uvicorn main:app --host 0.0.0.0 --port 8000
