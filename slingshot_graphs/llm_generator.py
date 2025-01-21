from slingshot_graphs.graph_factory import GraphManager
from call_config import CallConfig
from langchain_core.messages import HumanMessage
import re
import random

# global variables
pattern = re.compile(r"(?<!\d)([.!?])\s*(?=[A-Z]|$)")

def remove_functions_from_output(response, replace_list):
    if "functions." in response or "escalate_to_human" in response:
        response = random.choice(replace_list)
        replace_list.remove(response)
    return response, replace_list

async def chat_completion(user_response, call_metadata):
    graph_manager = GraphManager()

    print(f"Start async graph stream: with user response {user_response}")

    #if messages and messages[-1].type == "human":
    #    input = [HumanMessage(content=messages[-1].content, id=messages[-1].id)]
    #else:
    inputs = [HumanMessage(content=user_response)]

    thread_id = call_metadata.get("thread_id")
    config = {"configurable": {"thread_id": thread_id}}

    async def async_generator():
        buffer = ""
        list_of_words = [
            "Let me check that for you",
            "I'll need a moment to review this",
            "Please bear with me while I look into that",
        ]
        try:
            async for event in graph_manager.graph.astream_events({"messages": inputs}, config, version="v1"):
                kind = event["event"]
                
                if kind == "on_chat_model_end":
                    generated_message = (
                        event.get("data", {}).get("output", {}).get("generations", [[]])[0][0].get('message')
                    )
                    if generated_message:
                        print(f"generated_message is:\n{generated_message}\n")
                        text_output = generated_message.content
                        tool_calls = generated_message.tool_calls 

                        if text_output:
                            # store it to agent config
                            # store its completion to DB
                            print(f"on_chat_model_end content: {text_output}")
                            print(f"on_chat_model_end content: {tool_calls}")
                        
                elif kind == "on_chat_model_stream":
                    content = event["data"]["chunk"].content 
                    
                    if content:
                        if isinstance(content, list):
                            if content[0].get("type") != "text":
                                continue 
                            content = content[0]["text"]
                        buffer += content 
                        
                        while True: 
                            match = re.search(pattern, buffer)
                            if not match or "$" in buffer:
                                break

                            buffer, list_of_words = remove_functions_from_output(buffer, list_of_words)
                            
                            end_idx = match.end()
                            sentence = buffer[:end_idx]
                            buffer = buffer[end_idx:]
                            
                            buffer = buffer.replace("DETERMINISTIC", "").strip()

                            print(f"About to yield buffer: {sentence}")
                            sentence = sentence.replace("DETERMINISTIC", "").strip()
                            yield sentence

                elif kind == "on_tool_end":
                    content = event.get("data", {}).get("output", [])
                    if content:
                        content = content.content.strip()
                        if "DETERMINISTIC" in content:
                            yield content.replace("DETERMINISTIC", "").strip()
                            return 
                elif kind == "on_chain_end":
                    for item in event.get("data", {}).get("output", []):
                        if "sensitive_action" in item:
                            yield item["sensitive_action"]["messages"].content.replace("DETERMINISTIC", "")
                            return
            if buffer.strip():
                print(f"About to yield buffer 2: {buffer}")
                buffer, list_of_words = remove_functions_from_output(
                    buffer, list_of_words
                )
                # TODO: remove tools..
                yield buffer.strip() 
                
        except Exception as e:
            pass
    
    iterator = async_generator()
    
    first_sentence = await anext(iterator)
    
    return first_sentence, iterator, ""