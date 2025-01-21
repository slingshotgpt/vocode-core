import os 
import uuid 
from datetime import datetime, timedelta 
from vocode.streaming.models.synthesizer import AZURE_SYNTHESIZER_DEFAULT_VOICE_NAME

LANGUAGE_CONFIG = {
    "en-in": {
        "initial_message": "Welcome to Slingshot AI. How can I assist you today?",
        "prompt_preamble": "",
        "transcriber_language": "en-US",
        "synthesizer_language_code": "en-US",
        "synthesizer_voice_name": AZURE_SYNTHESIZER_DEFAULT_VOICE_NAME,
    },
    "en-out": {
        "initial_message": "Hello, this call is from Slingshot AI. I am calling to assist you with processing your payment", 
        "prompt_preamble": "",
        "transcriber_language": "en-US",
        "synthesizer_language_code": "en-US",
        "synthesizer_voice_name": AZURE_SYNTHESIZER_DEFAULT_VOICE_NAME,
    },
    "kr-in": {
        "initial_message": "안녕하세요 슬링샷 AI 입니다. 무엇을 도와드릴까요?",
        "prompt_preamble": "당신은 한국말 도우미 입니다.",
        "transcriber_language": "ko-KR",
        "synthesizer_language_code": "ko-KR",
        "synthesizer_voice_name": "ko-KR-SunHiNeural",
    },
    "kr-out": {
        "initial_message": "안녕하세요 슬링샷 AI에서 전화드립니다. 고객님의 결제를 도와드리려 합니다",
        "prompt_preamble": "당신은 한국말 도우미 입니다.",
        "transcriber_language": "ko-KR",
        "synthesizer_language_code": "ko-KR",
        "synthesizer_voice_name": "ko-KR-SunHiNeural",
    },
}

class Singleton(type):
    _instances = {}
    
    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            cls._instances[cls] = super(Singleton, cls).__call__(*args, **kwargs)
        return cls._instances[cls]
    
    def reinitialize(cls, *args, **kwargs):
        print("Reinitializing CallConfig")
        cls._instances[cls] = super(Singleton, cls).__call__(*args, **kwargs)
        return cls._instances[cls]
    
class CallConfig(metaclass=Singleton):
    def __init__(self):
        self.client_name = os.getenv("CLIENT_NAME") or "default"
        self.base_url = os.getenv("BASE_URL")

        self.call_metadata = {'thread_id': str(uuid.uuid4())} 
        
        self.test_metadata = {}
        self.language = os.getenv("LANGUAGE", "en")
        self.language_config = LANGUAGE_CONFIG[f'{self.language}-in']
    
    def set_call_metadata(self, value):
        self.call_metadata = value 
        
    def get_call_metadata(self):
        return self.call_metadata 
    
    def get_language_config(self, direction='in', custom_language=None):
        print(f"get langauge config: direction {direction} and custom lang {custom_language}") 
        if custom_language and custom_language.strip() in ['en', 'kr']:
            self.language_config = LANGUAGE_CONFIG[f'{custom_language}-{direction}']
            self.language = custom_language

        return self.language_config
        