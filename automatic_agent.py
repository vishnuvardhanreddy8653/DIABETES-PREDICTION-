import os
import imaplib
import email
import smtplib
from email.header import decode_header
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from crewai import Agent, Task, Crew

print("started.....")

# Load environment variables
load_dotenv()
EMAIL_USER = os.getenv("EMAIL_USER", "your_email@gmail.com")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD", "your_app_password")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

print(f'Loaded ENV - EMAIL_USER: {EMAIL_USER}, EMAIL_PASSWORD: {bool(EMAIL_PASSWORD)}, OPENAI_API_KEY: {bool(OPENAI_API_KEY)}')

# Email server settings
IMAP_SERVER = "imap.gmail.com"
SMTP_SERVER = "smtp.gmail.com"
IMAP_PORT = 993
SMTP_PORT = 587

# Initialize LLM
llm = ChatOpenAI(openai_api_key=OPENAI_API_KEY)

# Define the agent
reader_agent = Agent(
    role="Email Reader",
    goal="Understand and summarize incoming emails",
    backstory="You are skilled at extracting relevant information from messages.",
    llm=llm
)

# Helpers
def decode_mime_words(s):
    if not s:
        return "(No Subject)"
    decoded = decode_header(s)
    return "".join(
        part.decode(enc or 'utf-8') if isinstance(part, bytes) else part
        for part, enc in decoded
    )

def clean_text(text):
    return "".join(c if c.isalnum() or c.isspace() else '' for c in text)

def fetch_unread_emails():
    mail = imaplib.IMAP4_SSL(IMAP_SERVER, IMAP_PORT)
    mail.login(EMAIL_USER, EMAIL_PASSWORD)
    mail.select("inbox")
    status, messages = mail.search(None, 'UNSEEN')
    email_ids = messages[0].split()
    emails = []

    for eid in email_ids:
        _, msg_data = mail.fetch(eid, "(RFC822)")
        raw_email = msg_data[0][1]
        
        msg = email.message_from_bytes(raw_email)
        subject = decode_mime_words(msg["Subject"])
        from_ = msg.get("From") or "(Unknown Sender)"
        
        body = ""
        if msg.is_multipart():
            for part in msg.walk():
                if part.get_content_type() == "text/plain" and not part.get('Content-Disposition'):
                    charset = part.get_content_charset() or "utf-8"
                    body = part.get_payload(decode=True).decode(charset, errors="ignore")
                    break
        else:
            charset = msg.get_content_charset() or "utf-8"
            body = msg.get_payload(decode=True).decode(charset, errors="ignore")

        emails.append({
            "from": from_,
            "subject": subject,
            "body": clean_text(body)
        })

    mail.logout()
    return emails

def send_email(to_address, subject, reply):
    msg = MIMEMultipart()
    msg["From"] = EMAIL_USER
    msg["To"] = to_address
    msg["Subject"] = f"Re: {subject}"
    msg.attach(MIMEText(reply, "plain"))

    with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
        server.starttls()
        server.login(EMAIL_USER, EMAIL_PASSWORD)
        server.sendmail(EMAIL_USER, to_address, msg.as_string())

# Main logic
if __name__ == "__main__":
    emails = fetch_unread_emails()
    count = len(emails)

    if count == 0:
        print("No new emails.")
    else:
        print(f'You have {count} unread email(s). Sending auto-replies...\n')

        for idx, email_data in enumerate(emails):
            task = Task(
                description=f"Summarize the email content:\n{email_data['body']}",
                expected_output="Short and clean summary of the email.",
                agent=reader_agent
            )

            crew = Crew(agents=[reader_agent], tasks=[task])
            # result = crew.kickoff()
            # summary = list(result.values())[0]
            #result = crew.kickoff()
            # summary = result.results[0].output
            #summary = result["results"][0]["output"]
            result = crew.kickoff()

            # DEBUG print
            print("DEBUG result:", result)

            try:
                summary = list(result.tasks.values())[0]
                print("Summary:", summary)
            except Exception as e:
                print("Failed to extract summary:", e)


            #print(f"Summary: {summary}")


            print(f"Email #{idx + 1}")
            print(f"From: {email_data['from']}")
            #print(f"Summary: {summary}\n")

            # Auto-reply
            send_email(email_data["from"], email_data["subject"], "I'll get back to you shortly")

        print("All auto-replies sent...")
