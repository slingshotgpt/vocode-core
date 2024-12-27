# Standard library imports
import os
import sys

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
from vocode.streaming.telephony.config_manager.redis_config_manager import RedisConfigManager
from vocode.streaming.telephony.server.base import TelephonyServer, TwilioInboundCallConfig

# if running from python, this will load the local .env
# docker-compose will load the .env file by itself
load_dotenv()

configure_pretty_logging()

app = FastAPI(docs_url=None)

config_manager = RedisConfigManager()

BASE_URL = 'instance-1.lb-1.inbound.slingshotgpt-dialers.com' #os.getenv("BASE_URL")

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

telephony_server = TelephonyServer(
    base_url=BASE_URL,
    config_manager=config_manager,
    inbound_call_configs=[
        TwilioInboundCallConfig(
            url="/inbound_call",
            agent_config=ChatGPTAgentConfig(
            #agent_config=SlingshotGPTAgentConfig(
                initial_message=BaseMessage(text="Welcome to SlingshotGPT.  How can I assist you today?"),
                prompt_preamble="You are a helpful assistant, called Slingshot, in pitching Slingshot AI company to SPC vc partners. Upon my request to summarize SlingshotGPT's mission, please provide the following three bullet points as a summary. Please use as natural sentences as possible.  You can use a caller name, by default, Kyu-Han.  Here is a script for your information.  <script start>Slingshot AI aims to rapidly scale the development of AI agents to enterprise, delivering solutions with speed and impact.  Next, our team brings over 15 years of expertise in Deep Learning, Conversation Intelligence, and Multi-Agent Systems.  Finally, with time and speed being critical, we are poised to capitalize on the market advantage, with the help and support from SPC. <end of script>",
                generate_responses=True,
                interrupt_sensitivity="high",
                initial_message_delay=2,
            ),
            # uncomment this to use the speller agent instead
            # agent_config=SpellerAgentConfig(
            #     initial_message=BaseMessage(
            #         text="im a speller agent, say something to me and ill spell it out for you"
            #     ),
            #     generate_responses=False,
            # ),
            twilio_config=TwilioConfig(
                account_sid=os.environ["TWILIO_ACCOUNT_SID"],
                auth_token=os.environ["TWILIO_AUTH_TOKEN"],
            ),
        )
    ],
    agent_factory=SpellerAgentFactory(),
)

app.include_router(telephony_server.get_router())

# Add a health check endpoint
@app.get("/health")
async def health_check():
    # Here you can add logic to check the health of your integrations, databases, etc.
    # Currently, it just returns a simple OK message
    return {"status": "ok"}