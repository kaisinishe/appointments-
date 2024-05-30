import os
import redis
import json
from fastapi import FastAPI, Request, HTTPException, Form, Query
from fastapi.responses import JSONResponse, HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
from googleapiclient.errors import HttpError
from datetime import datetime
from dotenv import load_dotenv
from pydantic import BaseModel
from dateutil.parser import parse
import logging
import uuid

load_dotenv()
logging.basicConfig(level=logging.INFO)

app = FastAPI()

# Mount the directory containing favicon.ico
app.mount("/static", StaticFiles(directory="static"), name="static")

# Load client secrets from credentials.json
with open('credentials.json', 'r') as f:
    client_secrets = json.load(f)

# Define the OAuth 2.0 scopes required
SCOPES = ['openid', 'https://www.googleapis.com/auth/userinfo.email', 'https://www.googleapis.com/auth/calendar', 'https://www.googleapis.com/auth/calendar.events', 'https://www.googleapis.com/auth/calendar.readonly']

# OAuth2 flow for the target user
flow_target = Flow.from_client_config(
    client_secrets,
    scopes=SCOPES,
    redirect_uri=os.getenv('NGROK_TARGET_URL', 'https://default-target-url.ngrok-free.app/callback/target')
)

# OAuth2 flow for the requestor
flow_requestor = Flow.from_client_config(
    client_secrets,
    scopes=SCOPES,
    redirect_uri=os.getenv('NGROK_REQUESTOR_URL', 'https://default-requestor-url.ngrok-free.app/callback/requestor')
)

# Redis client
r = redis.Redis(
    host=os.getenv('REDIS_HOST'),
    port=int(os.getenv('REDIS_PORT')),
    password=os.getenv('REDIS_PASSWORD')
)

def load_html_template(filename):
    with open(f"templates/{filename}", 'r') as file:
        return file.read()

class Event(BaseModel):
    summary: str
    start_time: str
    end_time: str
    requestor_id: str  # Add requestor_id to the event model

@app.get("/")
async def root():
    frontend_html = load_html_template("frontend.html")
    return HTMLResponse(content=frontend_html.replace('REQUESTOR_ID_PLACEHOLDER', ''), status_code=200)

@app.get("/authorize/target")
def authorize_target():
    authorization_url, _ = flow_target.authorization_url(
        access_type='offline',
        include_granted_scopes='true',
        prompt='consent'
    )
    return RedirectResponse(authorization_url)

@app.get("/authorize/requestor")
def authorize_requestor():
    authorization_url, _ = flow_requestor.authorization_url(
        access_type='offline',
        include_granted_scopes='true',
        prompt='consent'
    )
    return RedirectResponse(authorization_url)

@app.get("/callback/target")
async def callback_target(request: Request):
    flow_target.fetch_token(authorization_response=str(request.url))
    credentials = flow_target.credentials
    r.set('target_token', credentials.to_json())
    return RedirectResponse(url='/target_confirmation')

def get_user_info(credentials):
    user_info_service = build('oauth2', 'v2', credentials=credentials)
    user_info = None
    try:
        user_info = user_info_service.userinfo().get().execute()
    except HttpError as e:
        logging.error('An error occurred: %s', e)
    if user_info and user_info.get('id'):
        return user_info
    else:
        raise Exception("NoUserIdException")

@app.get("/callback/requestor")
async def callback_requestor(request: Request):
    flow_requestor.fetch_token(authorization_response=str(request.url))
    credentials = flow_requestor.credentials
    
    # Generate a unique identifier for the requestor
    requestor_id = str(uuid.uuid4())
    
    # Store the requestor's token with the generated requestor_id
    r.set(f'requestor_token:{requestor_id}', credentials.to_json())
    
    # Extract the user email
    user_email = get_user_info(credentials)['email']
    
    # Store the request status as pending
    r.set(f'request_status:{requestor_id}', 'pending')
    r.set(f'requestor_email:{requestor_id}', user_email)

    # Redirect to the waiting page
    return RedirectResponse(url=f'/waiting_page?requestor_id={requestor_id}')

@app.get("/target_confirmation")
async def target_confirmation():
    # Get the first pending requestor
    requestor_ids = [key.decode('utf-8').split(':')[1] for key in r.keys('request_status:*') if r.get(key) == b'pending']
    if not requestor_ids:
        no_pending_requestors_html = load_html_template("no_pending_requestors.html")
        return HTMLResponse(content=no_pending_requestors_html, status_code=200)
    
    requestor_id = requestor_ids[0]
    requestor_email = r.get(f'requestor_email:{requestor_id}').decode('utf-8')
    target_confirmation_html = load_html_template("target_confirmation.html")
    
    return HTMLResponse(content=target_confirmation_html.replace('REQUESTOR_EMAIL_PLACEHOLDER', requestor_email).replace('REQUESTOR_ID_PLACEHOLDER', requestor_id), status_code=200)

@app.post("/confirm_request")
async def confirm_request(requestor_id: str = Form(...), confirm: bool = Form(...)):
    if not r.exists(f'requestor_token:{requestor_id}'):
        raise HTTPException(status_code=400, detail="Requestor not found.")
    
    if confirm:
        if r.exists('target_token'):
            target_creds = Credentials.from_authorized_user_info(json.loads(r.get('target_token')))
            requestor_creds = Credentials.from_authorized_user_info(json.loads(r.get(f'requestor_token:{requestor_id}')))
            target_service = build('calendar', 'v3', credentials=target_creds)
            requestor_email = r.get(f'requestor_email:{requestor_id}').decode('utf-8')

            # Add requestor to target's calendar ACL
            acl_rule = {
                'role': 'writer',
                'scope': {
                    'type': 'user',
                    'value': requestor_email
                }
            }
            target_service.acl().insert(calendarId='primary', body=acl_rule).execute()
            
            # Update request status to approved
            r.set(f'request_status:{requestor_id}', 'approved')

            return JSONResponse(content={"message": "Requestor access confirmed."})
        else:
            return JSONResponse(content={"message": "Target authorization not found."})
    else:
        # Remove requestor token and update status to denied
        r.delete(f'requestor_token:{requestor_id}')
        r.set(f'request_status:{requestor_id}', 'denied')
        return JSONResponse(content={"message": "Requestor access denied."})

@app.get("/waiting_page")
async def waiting_page(requestor_id: str):
    if not r.exists(f'requestor_token:{requestor_id}'):
        raise HTTPException(status_code=400, detail="Requestor not found.")
    
    waiting_page_html = load_html_template("waiting_page.html")
    return HTMLResponse(content=waiting_page_html.replace('REQUESTOR_ID_PLACEHOLDER', requestor_id), status_code=200)

@app.get("/request_status")
async def request_status(requestor_id: str):
    status = r.get(f'request_status:{requestor_id}')
    if not status:
        raise HTTPException(status_code=400, detail="Request status not found.")
    
    return {"status": status.decode('utf-8')}

@app.get("/event_creation")
async def event_creation(requestor_id: str):
    if not r.exists(f'requestor_token:{requestor_id}'):
        raise HTTPException(status_code=400, detail="Requestor not found.")
    
    frontend_html = load_html_template("frontend.html")
    return HTMLResponse(content=frontend_html.replace('REQUESTOR_ID_PLACEHOLDER', requestor_id), status_code=200)

@app.post("/add_event")
async def add_event(event: Event):
    requestor_id = event.requestor_id
    if not r.exists(f'requestor_token:{requestor_id}'):
        raise HTTPException(status_code=400, detail="Requestor must be authorized.")
    
    requestor_creds = Credentials.from_authorized_user_info(json.loads(r.get(f'requestor_token:{requestor_id}')))
    target_creds = Credentials.from_authorized_user_info(json.loads(r.get('target_token')))

    requestor_service = build('calendar', 'v3', credentials=requestor_creds)
    target_service = build('calendar', 'v3', credentials=target_creds)

    # Ensure the 'Appointments' calendar exists
    appointments_calendar = None
    calendar_list = target_service.calendarList().list().execute()
    for calendar in calendar_list['items']:
        if (calendar.get('summary', '')).lower() == 'appointments':
            appointments_calendar = calendar
            break
    
    if not appointments_calendar:
        # Create the 'Appointments' calendar if it doesn't exist
        calendar_body = {
            'summary': 'Appointments',
            'timeZone': 'Europe/Bucharest'
        }
        appointments_calendar = target_service.calendars().insert(body=calendar_body).execute()

    calendar_id = appointments_calendar['id']

    event_body = {
        'summary': event.summary,
        'start': {
            'dateTime': parse(event.start_time).isoformat(),
            'timeZone': 'Europe/Bucharest',
        },
        'end': {
            'dateTime': parse(event.end_time).isoformat(),
            'timeZone': 'Europe/Bucharest',
        },
    }

    try:
        requestor_event = requestor_service.events().insert(calendarId='primary', body=event_body).execute()
        target_event = target_service.events().insert(calendarId=calendar_id, body=event_body).execute()
    except HttpError as e:
        raise HTTPException(status_code=400, detail=str(e))

    requestor_email = r.get(f'requestor_email:{requestor_id}').decode('utf-8')

    event_details = {
        'summary': event.summary,
        'start_time': event.start_time,
        'end_time': event.end_time,
        'requestor_event_link': requestor_event.get("htmlLink"),
        'target_event_link': target_event.get("htmlLink"),
        'creation_time': datetime.now().isoformat(),
        'requestor_email': requestor_email
    }
    r.rpush(f'events_log:{requestor_id}', json.dumps(event_details))

    return {"message": f'Event created successfully'}

@app.get("/events/{requestor_id}")
async def get_events(requestor_id: str, start: str = Query(...), end: str = Query(...)):
    if not r.exists(f'requestor_token:{requestor_id}'):
        raise HTTPException(status_code=400, detail="Requestor must be authorized.")
    
    target_creds = Credentials.from_authorized_user_info(json.loads(r.get('target_token')))
    target_service = build('calendar', 'v3', credentials=target_creds)

    # Ensure the 'Appointments' calendar exists
    appointments_calendar = None
    calendar_list = target_service.calendarList().list().execute()
    for calendar in calendar_list['items']:
        if (calendar.get('summary', '')).lower() == 'appointments':
            appointments_calendar = calendar
            break
    
    if not appointments_calendar:
        return {"events": []}  # No 'Appointments' calendar means no events

    calendar_id = appointments_calendar['id']

    try:
        events_result = target_service.events().list(
            calendarId=calendar_id, 
            timeMin=start, 
            timeMax=end, 
            singleEvents=True,
            orderBy='startTime'
        ).execute()
        events = events_result.get('items', [])
    except HttpError as e:
        raise HTTPException(status_code=400, detail=str(e))

    formatted_events = [
        {
            'summary': event.get('summary', 'No title'),
            'start_time': event['start'].get('dateTime', event['start'].get('date')),
            'end_time': event['end'].get('dateTime', event['end'].get('date'))
        }
        for event in events
    ]
    
    return {"events": formatted_events}

@app.get("/target_confirmation")
async def target_confirmation():
    # Get the first pending requestor
    requestor_ids = [key.decode('utf-8').split(':')[1] for key in r.keys('request_status:*') if r.get(key) == b'pending']
    if not requestor_ids:
        no_pending_requestors_html = load_html_template("no_pending_requestors.html")
        return HTMLResponse(content=no_pending_requestors_html, status_code=200)
    
    requestor_id = requestor_ids[0]
    requestor_email = r.get(f'requestor_email:{requestor_id}').decode('utf-8')
    target_confirmation_html = load_html_template("target_confirmation.html")
    
    return HTMLResponse(content=target_confirmation_html.replace('REQUESTOR_EMAIL_PLACEHOLDER', requestor_email).replace('REQUESTOR_ID_PLACEHOLDER', requestor_id), status_code=200)

@app.get("/check_pending_requestors")
async def check_pending_requestors():
    # Check if there are any pending requestors
    requestor_ids = [key.decode('utf-8').split(':')[1] for key in r.keys('request_status:*') if r.get(key) == b'pending']
    if requestor_ids:
        return JSONResponse(content={"pending": True})
    else:
        return JSONResponse(content={"pending": False})

if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
