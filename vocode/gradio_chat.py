import asyncio
import os
import pprint

import gradio as gr
from app_config import AppConfig
from app_config_post_call import AppConfigPostCall
from helpers import save_prompt_completion
from redaction import redact_transcript
from response_generators.collections_response_generator import check_for_violation

call_metadata = {}
global_entities = {}
account_context = {}

first_message = f"{AppConfig().intro_string} Brad Thompson?"
# first_message = "Great, thanks Brad! Are you calling in to schedule a payment?"
# first_message = "¡Perfecto, gracias Jose! ¿Está llamando para programar un pago?"


def clear():
    global call_metadata, global_entities
    print("Clear button clicked")
    if AppConfig().call_type == "welcome":
        call_metadata = AppConfig().init_test_metadata()
        global_entities = {}
    elif AppConfig().call_type in ["collections", "inbound"]:
        call_metadata = AppConfig().init_test_metadata()
        global_entities = {"confirmed_identity": True}

        call_metadata = AppConfig().init_test_metadata()

        account_context = AppConfig().test_account_context
        call_metadata.update(account_context)
    elif AppConfig().call_type == "verification":
        call_metadata = AppConfig().init_test_metadata()
        global_entities = {}


async def fake_make_autopay_setup(global_entities, call_metadata):
    call_metadata["is_auto_payment_set_up"] = True
    lightico_request_body = {
        "category": "ACH_FORM",
        "createdBy": "AI Bot",
        "accNbr": call_metadata.get("account_number"),
        "language": "English",
        "company": "C-WF",
        "inputtedPhone": call_metadata.get("phone_number"),
        "recipient": call_metadata.get("customer_full_name"),
        "relationTypeCd": "PRIM",
        "sentType": "text",
        "email": call_metadata.get("customer_email"),
        "paymentAmount": float(global_entities.get("auto_payment_amount")),
        "scheduledPaymentAmount": float(global_entities.get("auto_payment_amount")),
        "additionalAmount": 0,
        "gapRecurringFlag": "0",
        "gapPaymentAmount": 0,
        "secureOneRecurringFlag": "0",
        "secureOnePaymentAmount": 0,
        "achDueDay": global_entities.get("auto_payment_date"),
        # "achNextPaymentDate": get_autopay_date_for_day(
        #     global_entities.get("auto_payment_date")
        # ),
        "achNameOnAccount": call_metadata.get("customer_full_name"),
        "achBankAccountNumber": global_entities.get("bank_account_number"),
        "achBankAccountType": (
            "C" if "checking" in global_entities.get("bank_account_type", "") else "S"
        ),
        "achBankName": global_entities.get("bank_name"),
        "achRoutingNumber": global_entities.get("bank_routing_number"),
    }
    print(f"Hypothetical Lightico request body: {lightico_request_body}")
    return "Great! I'll shoot over a pre-filled DocuSign form to your phone. Please sign it whenever you have a moment. Is there anything else I can help you with?"


async def fake_make_westlake_payment(global_entities, call_metadata):
    call_metadata["is_payment_processing"] = True
    call_metadata["payment_confirmation_number"] = "12345678"
    return "Your payment has successfully gone through, and your confirmation number is 12345678. Once again, your confirmation number is 12345678. You will also receive this confirmation number via email. Can I help you with anything else?"


async def fake_make_due_date_change(global_entities, call_metadata):
    call_metadata["is_due_date_change_processing"] = True
    return f"Great! I've updated your account in our system, and your payments are now due on the {num2words(global_entities.get('desired_due_date'), ordinal=True)} of the month. Can I help you with anything else?"


def convert_history_to_openai(history, message):
    history_openai_format = [
        {"role": "system", "content": ""},
        {"role": "user", "content": AppConfig().hello_string},
        {
            "role": "assistant",
            "content": first_message,
        },
    ]
    for human, assistant in history:
        history_openai_format.append({"role": "user", "content": human})
        history_openai_format.append({"role": "assistant", "content": assistant})
    history_openai_format.append({"role": "user", "content": message})
    print(f"Current chat history: {history_openai_format}")
    return history_openai_format


async def respond(message, history):
    if len(history) == 0:
        clear()
    message = message.strip()
    global call_metadata
    print(f"Inside Gradio respond\nmessage = {message}\n")

    openai_transcript = convert_history_to_openai(history, message)

    if AppConfig().call_type == "welcome":
        response, stream, prompt_to_save = await AppConfigPostCall().chat_completion(
            openai_transcript, call_metadata
        )
    elif AppConfig().call_type in ["collections", "inbound"]:
        response, stream, prompt_to_save = await AppConfigPostCall().chat_completion(
            openai_transcript,
            account_context,
            call_metadata,
            global_entities,
            fake_make_westlake_payment,
            fake_make_due_date_change,
            fake_make_autopay_setup,
        )
    elif AppConfig().call_type == "verification":
        (
            response,
            stream,
            prompt_to_save,
        ) = await AppConfigPostCall().chat_completion(openai_transcript, call_metadata)

    if await AppConfigPostCall().check_for_violation(response, openai_transcript):
        print(f"Violation detected for response = {response}")
        return "Apologies, but I'm having an issue on my end. I am transferring you to a live agent for further assistance."
    if stream:
        async for message in stream:
            response += " " + message
            if await AppConfigPostCall().check_for_violation(
                response, openai_transcript
            ):
                print(f"Violation detected for response = {response}")
                return "Apologies, but I'm having an issue on my end. I am transferring you to a live agent for further assistance."

    asyncio.ensure_future(
        save_prompt_completion(
            prompt=prompt_to_save,
            completion=response.strip(),
            llm_type="welcome_conversation_mixtral",
        )
    )
    call_metadata["taylor_response"] = response
    AppConfigPostCall().save_persistent_state(call_metadata)
    print(f"Call metadata: {call_metadata}")
    return response


if AppConfig().call_type == "welcome":

    def display_entities():
        global call_metadata
        return pprint.pformat(call_metadata.get("candidate_global_entities"))

    def display_expert_guidance():
        global call_metadata
        return call_metadata.get("expert_guidance")

elif AppConfig().call_type in ["collections", "inbound"]:
    top_level_intents_to_sub_entities = {
        # Extension specialist
        "wants_extension": [
            "payment_amount",
            "payment_date",
            "use_payment_method_on_file",
        ],
        # Payment history specialist
        "ask_payment_history": [],
        # Off topic specialist
        "topic_not_allowed": ["topic_name"],
        # Payment specialist
        "wants_make_payment": [
            "payment_amount",
            "payment_date",
            "use_payment_method_on_file",
            "payment_amount_still_accurate",
            "payment_date_still_accurate",
        ],
        # Insurance specialist
        "ask_insurance": [],
        # Automatic payment specialist
        "wants_set_up_automatic_payments": ["auto_payment_date", "auto_payment_amount"],
        # Payment promise specialist
        "no_need_agent_help_for_payment": ["pay_by_themselves_method"],
        # Due date change specialist
        "wants_change_due_date": ["desired_due_date"],
        # Keys without parents
        "customer_wants_supervisor": [],
        "customer_confirms_transfer": [],
        "customer_frustrated": [],
        "customer_transfer_reason": [],
        "customer_disputing_agent": [],
        "ask_due_date": [],
        "ask_payment_amount": [],
        "ask_apr": [],
        "ask_loan_term": [],
        "ask_vehicle": [],
        "ask_late_fee": [],
        "ask_nsf_fee": [],
        "ask_gap_fee": [],
        "ask_repo_fee": [],
        "ask_account_number": [],
        "ask_automatic_payments": [],
        "ask_cosigner": [],
        "ask_account_balance": [],
        "ask_payoff": [],
        "ask_grace_period": [],
        "ask_payment_methods": [],
        "ask_payment_breakdown": [],
        "ask_change_name": [],
        "ask_change_phone": [],
        "ask_late_payment_consequences": [],
        "ask_statement": [],
        "ask_why_calls": [],
        "ask_payment_processing": [],
        "ask_more_time_before_replying": [],
        "ask_repeat": [],
        "no_need_further_assistance": [],
    }

    def display_entities():
        global global_entities, first_sentence_lat
        entities_to_display = {}
        for key, value in global_entities.items():
            if key in top_level_intents_to_sub_entities.keys():
                if value:
                    entities_to_display[key] = value
            # check if key is inside the values of top_level_intents_to_sub_entities. If so, add the key to entities_to_display IF the corresponding parent key is True
            else:
                for parent_key, sub_keys in top_level_intents_to_sub_entities.items():
                    if key in sub_keys:
                        if global_entities.get(parent_key):
                            entities_to_display[key] = value

        return pprint.pformat(entities_to_display)

    def display_expert_guidance():
        global call_metadata
        return call_metadata.get("candidate_expert_guidance")


with gr.Blocks() as demo:
    clear()
    clear_btn = gr.Button("Clear", render=False)
    clear_btn.click(fn=clear, api_name="clear")
    chat = gr.ChatInterface(
        respond,
        clear_btn=clear_btn,
        # description="Refresh page to reset chat!",
        retry_btn=None,
        undo_btn=None,
        # clear_btn=None,
        chatbot=gr.Chatbot(
            render=False,
            value=[[None, first_message]],
            height=500,
        ),
    )

    entities = gr.Textbox(label="Entities")
    expert_guidance = gr.Textbox(label="Expert Guidance")
    demo.load(display_entities, None, entities, every=1, autoscroll=False)
    demo.load(display_expert_guidance, None, expert_guidance, every=1, autoscroll=False)


demo.queue().launch(share=True, server_port=10000, server_name="0.0.0.0")