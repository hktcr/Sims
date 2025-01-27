import openai
import streamlit as st
import time
import datetime
import uuid
import re
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from dotenv import load_dotenv
import os
 
load_dotenv()

spreadsheet_id = os.getenv('SPREADSHEET_ID')

st.set_page_config(
    page_title="AINO",
    page_icon="🦉",
)

SCOPES = ['https://www.googleapis.com/auth/spreadsheets',
          'https://www.googleapis.com/auth/documents.readonly']

# Ange sökvägen till din servicekontonyckel
load_dotenv()
SERVICE_ACCOUNT_FILE = os.getenv('SERVICE_ACCOUNT_FILE')
api_key = os.getenv('API_KEY')
client = openai.Client(api_key=api_key)
assistant_id = os.getenv('ASSISTANT_ID')


# Använd servicekontonyckeln för att autentisera och skapa en API-klient
creds = Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=SCOPES)
service = build('sheets', 'v4', credentials=creds)
docs_service = build('docs', 'v1', credentials=creds)


st.markdown("""
  <style>
.aino-message {
    color: black; /* Black text for better readability */
    background-color: #add8e6; /* Light blue background */
    border-radius: 15px; /* Rounded corners */
    padding: 5px 10px; /* Padding inside the box */
    margin: 15px 0; /* Margin around the message */
    max-width: 80%; /* Maximum width of the message box */
    display: inline-block; /* Only as wide as necessary */
    clear: both; /* Ensuring the float doesn't affect the layout */
}

/* Style adjustments for the user's messages */
.user-message {
    color: black; /* Black text on light orange background */
    background-color: #ffedd5; /* Light orange background */
    border-radius: 15px; /* Rounded corners */
    padding: 5px 10px; /* Top and bottom padding of 5px, left and right padding of 10px */
    margin: 15px 0 5px auto; /* Margins: top 5px, right 0, bottom 5px, left auto for right alignment */
    display: inline-block; /* Inline block for wrapping content */
    max-width: 80%; /* Max width of the message box */
    clear: both; /* Clear float from both sides */
    float: right; /* Float to the right for right alignment */
}


/* Container to clear floats */
.container::after {
    content: "";
    clear: both;
    display: table;
}
/* Gör textrutan justerbar */
textarea {
    resize: both; /* Gör rutan justerbar både horisontellt och vertikalt */
    min-height: 100px; /* Minsta höjd */
    max-height: 600px; /* Maximal höjd */
}
</style>

    """, unsafe_allow_html=True)

# Then in your send_message function when you append the messages to `st.session_state.messages`, 
# make sure to specify the role as 'user' or 'assistant' accordingly, and in the display section 
# you can add classes based on the role to style them differently.

# Lägg till funktionen för att hämta och visa dokumentinnehållet
def get_document_content():
    load_dotenv()
    document_id = os.getenv('DOCUMENT_ID')
    document = docs_service.documents().get(documentId=document_id).execute()
    doc_content = read_paragraph_element(document.get('body').get('content'))
    return doc_content

def read_paragraph_element(elements):
    text = ""
    for element in elements:
        if 'paragraph' in element:
            elements = element.get('paragraph').get('elements')
            for elem in elements:
                try:
                    text += elem.get('textRun').get('content')
                except:
                    pass
    return text

# I din Streamlit-app, skapa en expanderbar box med innehållet
expander = st.expander("**Info och tips!**")
expander.markdown(get_document_content(), unsafe_allow_html=True)


# Funktion för att hämta eller skapa radindex för nuvarande session
def get_or_create_session_row():
    load_dotenv()
    spreadsheet_id = os.getenv('SPREADSHEET_ID')
    range_name = 'MASTER!C:D'

    # Get all rows in the spreadsheet
    result = service.spreadsheets().values().get(
        spreadsheetId=spreadsheet_id,
        range=range_name
    ).execute()

    values = result.get('values', [])

    # Find the first empty row after row 3
    for i, row in enumerate(values[3:], start=4):  # start enumeration from 4
        if not row or all(cell == '' for cell in row):
            return i  # Rows are 1-indexed in Google Sheets

    # If no empty row was found, append a new row at the end
    return len(values) + 1

# Dictionary för att hålla reda på radindex för varje session
if 'session_rows' not in st.session_state:
    st.session_state.session_rows = {}

# Kontrollera och skapa session_id vid behov
if 'session_id' not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())
    # Anta att nästa lediga rad är längden på session_rows plus 3 (eftersom vi startar från rad 3)
    st.session_state.session_rows[st.session_state.session_id] = get_or_create_session_row()


st.markdown('# 🦉 AINO')
st.markdown('### Vad kan jag hjälpa dig med?')

if 'messages' not in st.session_state:
    st.session_state.messages = []


# Funktion för att uppdatera loggen i Google Sheets med append
def update_log(conversation):
    load_dotenv()
    row_index = st.session_state.session_rows[st.session_state.session_id]
    spreadsheet_id = os.getenv('SPREADSHEET_ID')
    range_name = f'MASTER!C{row_index}:D{row_index}'

    values = [[str(datetime.datetime.now()), conversation]]

    # Update the row in the spreadsheet
    service.spreadsheets().values().update(
        spreadsheetId=spreadsheet_id,
        range=range_name,
        valueInputOption='USER_ENTERED',
        body={'values': values}
    ).execute()


# Kontrollera och hantera session_id korrekt
if 'session_id' not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())
    st.session_state.session_rows[st.session_state.session_id] = len(st.session_state.session_rows) + 3
else:
    # Använd befintligt session_id för att fortsätta logga på samma rad
    row_index = st.session_state.session_rows[st.session_state.session_id]





def create_thread():
    if 'thread_id' not in st.session_state:
        thread = client.beta.threads.create()
        st.session_state.thread_id = thread.id

def add_message_to_thread(message, role):
    client.beta.threads.messages.create(
        thread_id=st.session_state.thread_id,
        role=role,
        content=message
    )
    st.session_state.messages.append((role, message))  # Lägg till meddelande till sessionens tillstånd

def send_message():
    if 'last_send_time' not in st.session_state:
        st.session_state.last_send_time = 0

    cooldown_period = 3  # i sekunder
    current_time = time.time()

    # Kontrollera om cooldown-perioden har löpt ut
    if current_time - st.session_state.last_send_time < cooldown_period:
        st.warning(f"Vänta {cooldown_period - (current_time - st.session_state.last_send_time):.1f} sekunder innan du skickar nästa meddelande.")
        return  # Avbryt om cooldown inte löpt ut

    user_input = st.session_state.user_input
    if user_input:
        st.session_state.last_send_time = current_time  # Uppdatera senaste skickade tidpunkt
        create_thread()
        add_message_to_thread(user_input, "user")
        with st.spinner('AINO tänker...'):
            run = client.beta.threads.runs.create(
                thread_id=st.session_state.thread_id,
                assistant_id=assistant_id
            )
            while run.status not in ["completed", "failed"]:
                time.sleep(1)
                run = client.beta.threads.runs.retrieve(
                    thread_id=st.session_state.thread_id,
                    run_id=run.id
                )
            if run.status == "completed":
                messages = client.beta.threads.messages.list(st.session_state.thread_id)
                # -------------------------------------------------------------
                # Skapa en lista över redan tillagda assistentmeddelanden så att vi inte duplicerar
                existing_assistant_contents = [msg for role, msg in st.session_state.messages if role == "assistant"]
                # -------------------------------------------------------------
                for message in messages.data:
                    if message.role == "assistant":
                        content = message.content[0].text.value
                        # -------------------------------------------------------------
                        # LÄGG TILL/ÄNDRA HÄR:
                        # Kontrollera om meddelandet redan finns för att undvika dubbletter
                        if content not in existing_assistant_contents:
                            st.session_state.messages.append(("assistant", content))
                        # -------------------------------------------------------------
                         # -------------------------------------------------------------
                # <-- LÄGG TILL DETTA FÖR LOGGNING
                # Efter att meddelanden har uppdaterats, bygg konversationen och logga den
                conversation_log = ""
                for role, msg in st.session_state.messages:
                    if role == "user":
                        conversation_log += f"Du: {msg}\n"
                    else:
                        conversation_log += f"AINO: {msg}\n"

                # Anropa update_log med hela konversationen
                update_log(conversation_log)
                # -------------------------------------------------------------
            else:
                st.error("Körningen misslyckades: " + run.last_error)
        st.session_state.user_input = ""  # Rensa textfältet efter skickat meddelande

 



def extract_latex(latex_string):
    # Identify LaTeX code using regex
    latex_code = re.findall(r'\\\(.*?\\\)|\\\[.*?\\\]|\[.*?\]', latex_string)
    # Remove the LaTeX delimiters and any trailing backslashes from the LaTeX code
    latex_code = [code.replace('\\(', '').replace('\\)', '').replace('\\[', '').replace('\\]', '').replace('[', '').replace(']', '').rstrip('\\') for code in latex_code]
    return latex_code

def extract_links(msg):
    # Extract all markdown links from the message
    return re.findall(r'\[.*?\]\((.*?)\)', msg)

def remove_references(msg):
    # Remove references like 【6:2†source】 using regex
    return re.sub('【.*?】', '', msg)

# Display all messages in a scrollable container
with st.container():
    for role, msg in st.session_state.messages:
        msg = remove_references(msg)
        if role == "user":
            # Apply user-message class for user messages
            st.markdown(f"<div class='user-message'>{msg}</div>", unsafe_allow_html=True)
        else:
            # Use aino-message class for AINO messages
            latex_code = extract_latex(msg)
            links = extract_links(msg)  # Extract links from the message
            if latex_code:  # Check if the message contains LaTeX
                # Split the message into parts that contain LaTeX and parts that don't
                parts = re.split(r'\\\(.*?\\\)|\\\[.*?\\\]', msg)
                for i, part in enumerate(parts):
                    if i < len(latex_code):
                        # Display the part of the message that doesn't contain LaTeX
                        st.markdown(f"<div class='aino-message'>{part}</div>", unsafe_allow_html=True)
                        # Display the LaTeX code
                        st.latex(latex_code[i])
                    else:
                        # Display the last part of the message that doesn't contain LaTeX
                        st.markdown(f"<div class='aino-message'>{part}</div>", unsafe_allow_html=True)
            elif links:  # Check if the message contains links
                # Split the message into parts that contain links and parts that don't
                parts = re.split(r'\[.*?\]\((.*?)\)', msg)
                for i, part in enumerate(parts):
                    if i < len(links):
                        # Display the part of the message that doesn't contain a link
                        st.markdown(f"<div class='aino-message'>{part}</div>", unsafe_allow_html=True)
                        # Display the link
                        st.markdown(f"<a href='{links[i]}'>[Link]</a>", unsafe_allow_html=True)
                    else:
                        # Display the last part of the message that doesn't contain a link
                        st.markdown(f"<div class='aino-message'>{part}</div>", unsafe_allow_html=True)
            else:
                st.markdown(f"<div class='aino-message'>{msg}</div>", unsafe_allow_html=True)

# Text input för nya meddelanden under historiken
user_input = st.text_area(
    "Skriv ditt meddelande här:",
    key="user_input",
    on_change=send_message
)

st.button("Skicka", on_click=send_message, key="send_button")

# Skapa ett JavaScript-snippet för att hantera Ctrl+Enter för att skicka meddelanden
st.markdown(
    """
    <script>
    const textarea = document.querySelector('.stTextInput textarea');
    textarea.addEventListener('keydown', function(e) {
        if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) {
            const event = new Event('change', { bubbles: true });
            this.dispatchEvent(event);
            document.querySelector('.stButton>button').click();
        }
    });
    </script>
    """,
    unsafe_allow_html=True,
)

# Möjlighet att rensa tråden och starta om konversationen
if st.button('Rensa konversation'):
    if 'thread_id' in st.session_state:
        client.beta.threads.delete(thread_id=st.session_state['thread_id'])
        del st.session_state['thread_id']
    st.session_state.messages = []
    st.experimental_rerun()  # Använd st.experimental_rerun()Det ser ut som att det fanns en bugg i hur meddelanden hanterades och lades till i din historik. I den reviderade koden ovan har jag lagt till en kontroll för att undvika att lägga till duplicate-meddelanden i sessionens tillstånd. Varje meddelande från assistenten kontrolleras nu mot tidigare meddelanden innan de läggs till i historiken. Detta bör förhindra att meddelanden dupliceras i framtiden.
