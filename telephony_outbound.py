# Standard library imports
import os
import sys
import asyncio
import threading
from time import sleep

from dotenv import load_dotenv

# Third-party imports
from fastapi import FastAPI
from loguru import logger
from pyngrok import ngrok

# Local application/library specific imports
from speller_agent import SpellerAgentFactory

from vocode.logging import configure_pretty_logging
from vocode.streaming.models.agent import ChatGPTAgentConfig #, SlingshotGPTAgentConfig
from vocode.streaming.models.message import BaseMessage
from vocode.streaming.models.telephony import TwilioConfig
from vocode.streaming.telephony.server.base import TelephonyServer, TwilioInboundCallConfig
from vocode.streaming.models.transcriber import DeepgramTranscriberConfig
from vocode.streaming.models.events import Event
from vocode.streaming.utils import events_manager
from common import config_manager, get_secret

# customer dial client
from customer_dialers.make_call import dials as make_dials
from agent_config import AgentConfig

# if running from python, this will load the local .env
# docker-compose will load the .env file by itself
#load_dotenv() # not for production

configure_pretty_logging()

print(f"Logging at App: Mode {os.getenv('LOCALENV')}")
app = FastAPI(docs_url=None)

# outbound
if os.getenv("LOCALENV") == 'development':
    BASE_URL = os.getenv("BASE_URL", "slingshotgpt.ngrok.app")
else:    
    BASE_URL = 'instance-1.lb-1.outbound.slingshotgpt-dialers.com' 
    secret_name = 'slingshotgpt_vocode_credentials'
    secret = get_secret(secret_name)
    
    if secret and isinstance(secret, dict):
        for key, value in secret.items():
            print(f"SECRET is being retrieved {key}")
            os.environ[key] = value

logger.info(BASE_URL)
agent_config = AgentConfig()

if not BASE_URL:
    raise ValueError("BASE_URL must be set in environment if not using pyngrok")

class CustomEventsManager(events_manager.EventsManager):
    def __init__(self):
        super().__init__(subscriptions=[])
        
    def handle_event(self, event: Event):
        return

events_manager_instance = CustomEventsManager()

async def start_event_loop():
    await events_manager_instance.start()
    
event_manager_task = asyncio.create_task(start_event_loop()) 


telephony_server = TelephonyServer(
    base_url=BASE_URL,
    config_manager=config_manager,
    #logger=logger,
    events_manager=events_manager_instance,
)

app.include_router(telephony_server.get_router())

# Add a health check endpoint
@app.get("/health")
async def health_check():
    # Here you can add logic to check the health of your integrations, databases, etc.
    # Currently, it just returns a simple OK message
    return {"status": "ok"}

async def start_worker():
    """The worker is continuously running to start dials."""
    print(f"worker started with thread id: {threading.get_ident()}")
    while True:
        try: 
            #if os.environ.get("CLIENT_NAME") is None:
            #    print("No client name found")
            #    continue
            print(f"Starting a dial...{BASE_URL}")
            await make_dials(base_url=BASE_URL)
            print("Dial finished. Waiting for the next cycle.")
        except Exception as e:
            logger.error(str(e))
        finally:
            # Wait before making the next dial
            await asyncio.sleep(10)

loop = asyncio.get_event_loop()
try:
    loop.create_task(start_worker())
except KeyboardInterrupt:
    print("Worker stopped by user")
