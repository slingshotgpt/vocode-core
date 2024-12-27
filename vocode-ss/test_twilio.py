# Download the helper library from https://www.twilio.com/docs/python/install
import os
from twilio.rest import Client

# Set environment variables for your credentials
# Read more at http://twil.io/secure

account_sid = "AC04bf56bda02bd3e36f8ea2867f3f2ad7"
auth_token = "cd58d1ae7030fec7b4692025e8f23d7c"
client = Client(account_sid, auth_token)

call = client.calls.create(
  url="http://demo.twilio.com/docs/voice.xml",
  to="+16503907338",
  from_="+18449284092"
)

print(call.sid)
