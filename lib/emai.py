import email
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email.mime.text import MIMEText
from email import encoders
from email.message import EmailMessage
import smtplib
import os


# SMTP_EMAIL = 'automated@avaclone.io'
# PASSWORD = 'qhzHm{1-C$6W'

SMTP_EMAIL = 'automated@runright.io'
PASSWORD = 'Jonathan12345!'


def send_email(email_address, email_contents, subject):
    msg = EmailMessage()
    msg.set_content(email_contents)

    msg['Subject'] = subject
    msg['From'] = SMTP_EMAIL
    msg['To'] = email_address
    mailserver = smtplib.SMTP_SSL('raspberry.active-ns.com',465)
    mailserver.login(SMTP_EMAIL, PASSWORD)
    mailserver.send_message(msg)
    mailserver.quit()

# def send_email_with_html_attachment(email_address, subject, filename):
#     # Create a multipart message and set headers
#     msg = MIMEMultipart()
#     msg['From'] = SMTP_EMAIL
#     msg['To'] = email_address
#     msg['Subject'] = subject

#     # Open the HTML file in binary mode and encode it
#     with open(filename, 'rb') as file:
#         part = MIMEBase('text/html', 'utf-8')
#         part.set_payload(file.read())

#     # Encode the attachment
#     encoders.encode_base64(part)

#     # Add header with filename
#     part.add_header('Content-Disposition', f'attachment; filename= {filename}',)

#     # Attach the encoded file to the message
#     msg.attach(part)

#     # Connect to the server and send the email
#     mailserver = smtplib.SMTP_SSL('raspberry.active-ns.com',465)
#     mailserver.login(SMTP_EMAIL, PASSWORD)
#     mailserver.send_message(msg.as_string())
#     mailserver.quit()
#     print("Email sent successfully")

def send_email_with_html_attachment(email_address, subject, filename):
    with open(filename, 'r', encoding='utf-8') as file:
        html_content = file.read()

    # Create a multipart message and set headers
    msg = MIMEMultipart('alternative')
    msg['From'] = 'emailreport@runright.io'
    msg['To'] = email_address
    msg['Subject'] = subject

    # Set the plain-text and HTML version of your message
    text_part = MIMEText(html_content, 'plain')
    html_part = MIMEText(html_content, 'html')

    # Attach the plain-text and HTML version of your message
    msg.attach(text_part)
    msg.attach(html_part)

    # Connect to the server and send the email
    mailserver = smtplib.SMTP_SSL('raspberry.active-ns.com', 465)
    mailserver.login('emailreport@runright.io', 'Bsh&V0G8Nof*7fO^')
    mailserver.sendmail('emailreport@runright.io', email_address, msg.as_string())
    mailserver.quit()
    
