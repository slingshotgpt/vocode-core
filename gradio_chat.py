import asyncio
import os
import pprint
import uuid

import gradio as gr
#from helpers import save_prompt_completion
#from redaction import redact_transcript
#from response_generators.collections_response_generator import check_for_violation
from agent_config import AgentConfig

call_metadata = {'thread_id': str(uuid.uuid4())}
global_entities = {}
account_context = {}

first_message = f"Hello, this is Slingshot?" 

def clear():
    pass

async def respond(message, history):
    if len(history) == 0:
        clear()

    # getting chat completion from global variable
    response, stream, prompt_to_save = await AgentConfig().chat_completion(message, call_metadata)
    
    return response

def clear_btn():
    pass

with gr.Blocks() as demo:
    clear_btn = gr.Button("Clear", render=False)
    clear_btn.click(fn=clear, api_name="clear")
    chat = gr.ChatInterface(
        respond,
        #clear_btn=clear_btn,
        # description="Refresh page to reset chat!",
        #retry_btn=None,
        #undo_btn=None,
        # clear_btn=None,
        chatbot=gr.Chatbot(
            render=False,
            value=[[None, first_message]],
            height=500,
        ),
    )

    entities = gr.Textbox(label="Entities")
    expert_guidance = gr.Textbox(label="Expert Guidance")
    #demo.load(display_entities, None, entities, every=1, autoscroll=False)
    #demo.load(display_expert_guidance, None, expert_guidance, every=1, autoscroll=False)


demo.queue().launch(share=True, server_port=10000, server_name="0.0.0.0")