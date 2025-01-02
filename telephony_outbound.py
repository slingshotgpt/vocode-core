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
from common import config_manager

# customer dial client
from customer_dialers.make_call import dials as make_dials
# if running from python, this will load the local .env
# docker-compose will load the .env file by itself
load_dotenv()

configure_pretty_logging()

print("Logging at App")
app = FastAPI(docs_url=None)

# inbound
#BASE_URL = 'instance-1.lb-1.outbound.slingshotgpt-dialers.com' #os.getenv("BASE_URL")
BASE_URL = os.getenv("BASE_URL")
logger.info(BASE_URL)
# local development
#BASE_URL = os.getenv("BASE_URL")

if not BASE_URL:
    ngrok_auth = os.environ.get("NGROK_AUTH_TOKEN")
    if ngrok_auth is not None:
        ngrok.set_auth_token(ngrok_auth)
    port = sys.argv[sys.argv.index("--port") + 1] if "--port" in sys.argv else 3000

    # Open a ngrok tunnel to the dev server
    BASE_URL = ngrok.connect(port).public_url.replace("https://", "")
    logger.info('ngrok tunnel "{}" -> "http://127.0.0.1:{}"'.format(BASE_URL, port))

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
            print("Starting a dial...")
            await make_dials(base_url=BASE_URL)
            print("Dial finished. Waiting for the next cycle.")
        except Exception as e:
            logger.error(str(e))
        finally:
            # Wait before making the next dial
            await asyncio.sleep(10)

#worker_thread = threading.Thread(target=start_worker)
#worker_thread.start()
#asyncio.run(start_worker())
loop = asyncio.get_event_loop()
try:
    loop.create_task(start_worker())
    #loop.run_forever()
except KeyboardInterrupt:
    print("Worker stopped by user")
#finally:
#    loop.close()
