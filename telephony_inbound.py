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
from vocode.streaming.telephony.server.base import TelephonyServer, TwilioInboundCallConfig
from vocode.streaming.models.transcriber import (
    DeepgramTranscriberConfig,
    PunctuationEndpointingConfig,
)
from common import config_manager

from vocode.streaming.telephony.constants import (
    DEFAULT_AUDIO_ENCODING,
    DEFAULT_CHUNK_SIZE,
    DEFAULT_SAMPLING_RATE,
)
from vocode.streaming.models.synthesizer import (
    AzureSynthesizerConfig,
    AZURE_SYNTHESIZER_DEFAULT_VOICE_NAME,
    AZURE_SYNTHESIZER_DEFAULT_PITCH,
    AZURE_SYNTHESIZER_DEFAULT_RATE, 
)
from common import get_secret
from call_config import CallConfig

# if running from python, this will load the local .env
# docker-compose will load the .env file by itself
#load_dotenv()

configure_pretty_logging()

print(f"Logging at App: Mode {os.getenv('LOCALENV')}")
app = FastAPI(docs_url=None)

# inbound
if os.getenv("LOCALENV") == 'development':
    BASE_URL = os.getenv("BASE_URL", 'slingshotgpt.ngrok.app')
else:    
    BASE_URL = 'instance-1.lb-1.inbound.slingshotgpt-dialers.com' 

    secret_name = 'slingshotgpt_vocode_credentials'
    secret = get_secret(secret_name)
    
    if secret and isinstance(secret, dict):
        for key, value in secret.items():
            print(f"Read secret for {key}")
            os.environ[key] = value

logger.info(BASE_URL)

if not BASE_URL:
    raise ValueError("BASE_URL must be set in environment if not using pyngrok")

# Transcriber config (Deepgram) - language, model
# Synthesizer config (Azure) - language, model 
language_config = CallConfig().get_language_config()

telephony_server = TelephonyServer(
    base_url=BASE_URL,
    config_manager=config_manager,
    inbound_call_configs=[
        TwilioInboundCallConfig(
            url="/inbound_call",
            agent_config=ChatGPTAgentConfig(
                initial_message=BaseMessage(text=language_config["initial_message"]), 
                prompt_preamble=language_config["prompt_preamble"], 
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
            transcriber_config=DeepgramTranscriberConfig(
                language=language_config["transcriber_language"], 
                model='nova-2',
                sampling_rate=DEFAULT_SAMPLING_RATE,
                audio_encoding=DEFAULT_AUDIO_ENCODING,
                chunk_size=DEFAULT_CHUNK_SIZE,
                endpointing_config=PunctuationEndpointingConfig(),
            ),
            synthesizer_config=AzureSynthesizerConfig(
                language_code=language_config["synthesizer_language_code"], 
                voice_name=language_config["synthesizer_voice_name"], 
                sampling_rate=DEFAULT_SAMPLING_RATE,
                audio_encoding=DEFAULT_AUDIO_ENCODING,
            ),
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