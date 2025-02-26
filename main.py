from fastapi import FastAPI, HTTPException
from imapclient import IMAPClient
from elasticsearch import Elasticsearch
import openai
import requests
import email
import json

app = FastAPI()
es = Elasticsearch("http://localhost:9200")

IMAP_HOST = "imap.gmail.com"  # Change this for different providers
EMAIL_USER = "your_email@gmail.com"
EMAIL_PASS = "your_password"

SLACK_WEBHOOK_URL = "https://hooks.slack.com/services/YOUR_SLACK_WEBHOOK"
WEBHOOK_URL = "https://webhook.site/YOUR_WEBHOOK"

openai.api_key = "your_openai_api_key"

def fetch_emails():
    with IMAPClient(IMAP_HOST) as client:
        client.login(EMAIL_USER, EMAIL_PASS)
        client.select_folder("INBOX")
        
        messages = client.search(["SINCE", "30-Oct-2023"])
        for msgid in messages:
            raw_message = client.fetch(msgid, ["RFC822"])[msgid][b"RFC822"]
            parsed_email = email.message_from_bytes(raw_message)
            email_data = {
                "from": parsed_email["From"],
                "subject": parsed_email["Subject"],
                "date": parsed_email["Date"],
                "body": parsed_email.get_payload()
            }
            store_in_elasticsearch(email_data)

def store_in_elasticsearch(email_data):
    es.index(index="emails", body=email_data)

def search_emails(query):
    return es.search(index="emails", body={"query": {"match": {"body": query}}})

def categorize_email(email_text):
    response = openai.ChatCompletion.create(
        model="gpt-4",
        messages=[{"role": "system", "content": "Classify the email into Interested, Spam, Meeting Booked, or Not Interested."},
                  {"role": "user", "content": email_text}]
    )
    return response["choices"][0]["message"]["content"]

def send_slack_notification(email_data):
    message = f"New Interested Email: {email_data['subject']} from {email_data['from']}"
    requests.post(SLACK_WEBHOOK_URL, json={"text": message})

def trigger_webhook(email_data):
    requests.post(WEBHOOK_URL, json=email_data)

@app.get("/emails")
def get_emails():
    return search_emails("*")

@app.post("/categorize")
def categorize(email_text: str):
    return {"category": categorize_email(email_text)}
