import os

#from twilio.rest import Client 
#from vocode import getenv, setenv 

from slingshot_graphs.llm_generator import chat_completion 
from supabase.client import create_async_client, create_client

#from dotenv import load_dotenv
#load_dotenv()

class Singleton(type):
    _instances = {}
    
    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            cls._instances[cls] = super(Singleton, cls).__call__(*args, **kwargs)
        return cls._instances[cls]
    
    def reinitialize(cls, *args, **kwargs):
        print("Reinitializing AgentConfig")
        cls._instances[cls] = super(Singleton, cls).__call__(*args, **kwargs)
        return cls._instances[cls]
    
class AgentConfig(metaclass=Singleton):
    def __init__(self):
        self.base_url = os.getenv("BASE_URL")

        self.chat_completion = self.init_chat_completion()
        self.supabase = self.init_supabase()
        self.supabase_async = None

        # TODO: Log or save completion

        
    def init_chat_completion(self):
        return chat_completion

    def init_supabase(self):
        return create_client(
            "https://ocdajakxsnguxbmkkxhb.supabase.co",
            os.getenv("SUPABASE_AI_AGENT_KEY")
        )

    async def get_or_create_supabase_async(self):
        if self.supabase_async:
            return self.supabase_async 

        return await create_async_client(
            "https://ocdajakxsnguxbmkkxhb.supabase.co",
            os.getenv("SUPABASE_AI_AGENT_KEY")
        )