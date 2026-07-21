import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email.mime.text import MIMEText
from email import encoders
import os

smtp_server = "smtp.gmail.com"
smtp_port = 587
username = "alyhysycom1@gmail.com"
password = "aurk eceb ptih zrsw"

to = "support@kastcard.com"
subject = "Re: KYC - Proof of Address - Request 476575"

msg = MIMEMultipart("mixed")
msg["From"] = username
msg["To"] = to
msg["Subject"] = subject

text = MIMEText("Dear KAST,\n\nPlease find attached the POA document for request 476575.\n\nBest regards,\nAbdulhameed", "plain")
msg.attach(text)

filepath = r"C:\Users\alyhy\poa_document.pdf"
if os.path.exists(filepath):
    with open(filepath, "rb") as f:
        attachment = MIMEBase("application", "pdf")
        attachment.set_payload(f.read())
        encoders.encode_base64(attachment)
        attachment.add_header("Content-Disposition", "attachment", filename="Proof_of_Address.pdf")
        msg.attach(attachment)
        size = os.path.getsize(filepath)
        print(f"Attachment added: {size} bytes")
else:
    print(f"File not found: {filepath}")
    exit(1)

server = smtplib.SMTP(smtp_server, smtp_port)
server.starttls()
server.login(username, password)
server.sendmail(username, [to], msg.as_string())
server.quit()
print("Email sent successfully with attachment!")
