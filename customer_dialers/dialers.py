from agent_config import AgentConfig
from datetime import datetime 

def get_next_customer_from_dialer():
    supabase = AgentConfig().supabase

    # TODO: need to use a cache to avoid frequent DB poll
    try: 
        next_contact = (
            supabase.table("phonebook")
            .select("id, phone_number, language")
            .filter("has_been_called", "eq", False)
            .order("id") 
            .execute()
        )
        print(f"Next contact: {str(next_contact)}")
    except Exception as e:
        print(f"supabase error {e}")
        return None, None, None

    if next_contact.data:
        phone_number = next_contact.data[0]['phone_number']
        language = next_contact.data[0]['language']
        contact_id = next_contact.data[0]['id']
        print(f"Next phone number to call: {phone_number} with {language}")
        return contact_id, phone_number, language
    else:
        return None, None, None

def mark_called_customer_from_dialer(contact_id, phone_number):
    if not contact_id:
        return 
    
    supabase = AgentConfig().supabase 
    current_datetime = datetime.utcnow().isoformat()
    
    supabase.table("phonebook").update({"has_been_called": True, "last_called": current_datetime}).eq("id", contact_id).execute()
    print(f"Phone number ({phone_number}) with ID ({contact_id}) has been marked as called at {current_datetime}")