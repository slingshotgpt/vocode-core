import logging
import time 
import requests
import urllib3
import os
import asyncio

from vocode.streaming.models.agent import ChatGPTAgentConfig
from vocode.streaming.models.synthesizer import AzureSynthesizerConfig
from vocode.streaming.models.telephony import TwilioConfig
from vocode.streaming.models.transcriber import (
    DeepgramTranscriberConfig,
    TimeEndpointingConfig,
    PunctuationEndpointingConfig,
)

from vocode.streaming.telephony.constants import (
    DEFAULT_AUDIO_ENCODING,
    DEFAULT_CHUNK_SIZE,
    DEFAULT_SAMPLING_RATE,
)
from vocode.streaming.telephony.conversation.outbound_call import OutboundCall
from vocode.streaming.models.message import BaseMessage


from vocode.streaming.models.synthesizer import (
    AzureSynthesizerConfig,
    AZURE_SYNTHESIZER_DEFAULT_VOICE_NAME,
    AZURE_SYNTHESIZER_DEFAULT_PITCH,
    AZURE_SYNTHESIZER_DEFAULT_RATE, 
)

from common import config_manager 

logger = logging.getLogger(__name__)
print = logger.info

#base_url = "instance-1.lb-1.outbound.slingshotgpt-dialers.com"
base_url = "slingshotgpt.ngrok.app"

async def handle_outbound_call(outbound_call, dnis, phone_number, max_call_duration=300):

    try:
        conversation_id = await outbound_call.start()
        if conversation_id is None:
            # TODO: post call process here 
            #config_manager.delete_config(conversation_id)
            print(f"Failed to start the call for phone number: {phone_number}")
            return
        
        print(f"Call started for phone number: {phone_number}")

        # Wait for the call to end with a timeout
        elapsed_time = 0
        polling_interval = 2 # interval in seconds to check the call status
        
        while True:
            call_status = await outbound_call.config_manager.get_config(conversation_id)
            if not call_status:
                try:
                    print(f"Call ended for phone number: {phone_number}")
                except Exception as e:
                    print(f"error in call status {str(e)}")
                break
            
            print(f"Call in progress for phone number: {phone_number}") #, status {str(call_status)}, telephony_id {str(telephony_id)}")
            await asyncio.sleep(polling_interval)
            elapsed_time += polling_interval
            
            # Check for timeout
            if elapsed_time >= max_call_duration:
                print(f"Call exceeded maximum duration for phone number: {phone_number}")
                break
        
        print(f"Call ended for phone number {phone_number}")

        # Post-call processing
        if conversation_id:
            config_manager.delete_config(conversation_id)
        await asyncio.sleep(2)

    except Exception as e:
        print(f"Error handling outbound call: {e}")
        raise e

async def dials(base_url=None, call_type=None, client_name=None, language=None, campaign_id=None):
    dnis = "+16507188240"
    count = 0

    while True:

        # Get customer phone number from Dial Controller
        phone_number = "+16503907338"
        
        # make a call
        outbound_call = OutboundCall(
            base_url=base_url,
            to_phone=phone_number,
            from_phone=dnis,
            transcriber_config=DeepgramTranscriberConfig(
                #language='en-US',
                language='ko-KR',
                model='nova-2',
                sampling_rate=DEFAULT_SAMPLING_RATE,
                audio_encoding=DEFAULT_AUDIO_ENCODING,
                chunk_size=DEFAULT_CHUNK_SIZE,
                endpointing_config=PunctuationEndpointingConfig(),
            ),
            synthesizer_config=AzureSynthesizerConfig(
            #    language_code="en-US", # "ko-KR"
                language_code="ko-KR",
            #    voice_name=AZURE_SYNTHESIZER_DEFAULT_VOICE_NAME, 
                voice_name="ko-KR-SunHiNeural",
            #    pitch=AZURE_SYNTHESIZER_DEFAULT_PITCH,
            #    rate=AZURE_SYNTHESIZER_DEFAULT_RATE,
                sampling_rate=DEFAULT_SAMPLING_RATE,
                audio_encoding=DEFAULT_AUDIO_ENCODING,
            ),
            config_manager=config_manager,
            agent_config=ChatGPTAgentConfig(
                initial_message=BaseMessage(text="안녕하세요. 국민은행에서 전화드립니다."), #Welcome to SlingshotGPT.  How can I assist you today?"),
                prompt_preamble="당신은 한국말 도우미 입니다.", #You are helpful assistant and answer how to develop an AI agent only.",
                generate_responses=True,
                interrupt_sensitivity="high",
                initial_message_delay=2,
            ),
            telephony_config=TwilioConfig(
                account_sid=os.environ["TWILIO_ACCOUNT_SID"],
                auth_token=os.environ["TWILIO_AUTH_TOKEN"],
            ),
        )

        try:
            # Wait until the current call is fully handled
            await handle_outbound_call(outbound_call, dnis, phone_number)
            print(f"Call #{count} to {phone_number} finished.")
        except Exception as e:
            print(f"Error during call #{count}: {e}")
            break
        
        # Optionally, delay before the next call
        await asyncio.sleep(5)
        break # for now. 

    print("Dialer finished!")