import os
import redis
import json
from google.oauth2.credentials import Credentials

def connect_to_redis():
    return redis.Redis(
    host=os.getenv('REDIS_HOST'),
    port=int(os.getenv('REDIS_PORT')),
    password=os.getenv('REDIS_PASSWORD')
)

def print_event_information():
    with connect_to_redis() as r:
        requestor_ids = [key.decode('utf-8').split(':')[1] for key in r.keys('requestor_token:*')]
        
        for requestor_id in requestor_ids:
            # Fetch requestor token and email
            requestor_token = json.loads(r.get(f'requestor_token:{requestor_id}'))
            requestor_email = r.get(f'requestor_email:{requestor_id}').decode('utf-8')

            # Fetch events created by the requestor
            events_log = [json.loads(event) for event in r.lrange(f'events_log:{requestor_id}', 0, -1)]
            
            print(f"Requestor ID: {requestor_id}")
            print(f"Requestor Email: {requestor_email}")
            print(f"Requestor Token: {requestor_token}")
            print("Events:")
            
            for event in events_log:
                print(json.dumps(event, indent=4))

            print("\n" + "="*50 + "\n")

def delete_all_data():
    with connect_to_redis() as r:
        r.flushall()
        print("All data deleted from the Redis database.")

def remove_key_by_number(key_prefix, number):
    with connect_to_redis() as r:
        key = f"{key_prefix}_{number}"
        if r.exists(key):
            r.delete(key)
            print(f"{key_prefix.capitalize()} {number} removed from the Redis database.")
        else:
            print(f"No {key_prefix} found with number {number}.")

def remove_token_by_number(number):
    remove_key_by_number('token', number)

def remove_event_by_number(number):
    remove_key_by_number('event', number)

if __name__ == '__main__':
    print_event_information()
    # delete_all_data()
    # remove_token_by_number()
    # remove_event_by_number()
