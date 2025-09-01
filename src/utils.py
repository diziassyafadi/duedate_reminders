import smtplib
import config
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from logger import logger


def prepare_missing_duedate_comment(issue: dict, assignees: dict):
    """
    Prepare the comment from the given arguments and return it
    """

    comment = ''
    if assignees:
        for assignee in assignees:
            if assignee.get("login") and assignee["login"].strip():
                comment += f'@{assignee["login"]} '
    else:
        logger.info(f'No assignees found for issue #{issue["number"]}')

    comment += f'Kindly set the `Due Date` for this issue.'
    logger.info(f'Issue {issue["title"]} | {comment}')

    return comment


def prepare_expiring_issue_comment(issue: dict, assignees: dict, duedate):
    """
    Prepare the comment from the given arguments and return it
    """

    comment = ''
    if assignees:
        for assignee in assignees:
            if assignee.get("login") and assignee["login"].strip():
                comment += f'@{assignee["login"]} '
    else:
        logger.info(f'No assignees found for issue #{issue["number"]}')

    comment += f'The issue is due on: {duedate.strftime("%b %d, %Y")}'
    logger.info(f'Issue {issue["title"]} | {comment}')

    return comment

def prepare_overdue_issue_comment(issue: dict, assignees: dict, duedate):
    """
    Prepare the comment from the given arguments and return it
    """

    comment = ''
    if assignees:
        for assignee in assignees:
            if assignee.get("login") and assignee["login"].strip():
                comment += f'@{assignee["login"]} '
    else:
        logger.info(f'No assignees found for issue #{issue["number"]}')

    comment += f'The issue is overdue since: {duedate.strftime("%b %d, %Y")}'
    logger.info(f'Issue {issue["title"]} | {comment}')

    return comment

def prepare_missing_duedate_email_message(issue, assignees):
    """
    Prepare the email message, subject and mail_to addresses
    """
    subject = f"[Reminder: Set Due Date] {issue['title']} (#{issue['number']})"
    _assignees = ''
    mail_to = []
    if assignees:
        for assignee in assignees:
            if assignee.get("name") and assignee["name"].strip():
                _assignees += f'@{assignee["name"]} '
            if assignee.get('email') and assignee['email'].strip():
                mail_to.append(assignee['email'])
    else:
        logger.info(f'No assignees found for issue #{issue["number"]}')

    message = f'Assignees: {_assignees}' \
              f'<br>Kindly set the due date for this issue.' \
              f'<br><br>{issue["url"]}'

    return [subject, message, mail_to]


from datetime import datetime

def prepare_expiring_issue_email_message(issue, assignees, duedate):
    """
    Prepare the email message, subject and mail_to addresses
    """
    # Calculate remaining days until due date
    today = datetime.now().date()
    remaining_days = (duedate - today).days

    # if remaining_days is 0, then it is due today
    if remaining_days == 0:
        subject = f"[Reminder: Due today] {issue['title']} (#{issue['number']})"
    elif remaining_days == 1:
        subject = f"[Reminder: Due tomorrow] {issue['title']} (#{issue['number']})"
    else:
        subject = f"[Reminder: Due in {remaining_days} days] {issue['title']} (#{issue['number']})"

    _assignees = ''
    mail_to = []
    if assignees:
        for assignee in assignees:
            if assignee.get('name') and assignee['name'].strip():
                _assignees += f"@{assignee['name']} "
            if assignee.get('email') and assignee['email'].strip():
                mail_to.append(assignee['email'])
    else:
        logger.info(f"No assignees found for issue #{issue['number']}")

    # Adjust message based on remaining days
    if remaining_days == 0:
        due_text = "is due <strong>today</strong>"
    elif remaining_days == 1:
        due_text = "is due <strong>tomorrow</strong>"
    else:
        due_text = f"is due in <strong>{remaining_days} days</strong>"

    message = f"""
    <p>Reminder: The issue <strong>{issue['title']}</strong> (#{issue['number']}) {due_text} on <strong>{duedate.strftime('%b %d, %Y')}</strong>.</p>
    <p>Assignees: {_assignees.strip() if _assignees.strip() else 'No assignees'}</p>
    <p>Please ensure the due date is met.</p>
    <p><a href="{issue['url']}">View Issue</a></p>
    """

    return [subject, message, mail_to]

def prepare_overdue_issue_email_message(issue, assignees, duedate):
    """
    Prepare the email message, subject and mail_to addresses
    """

    subject = f"[Reminder: Overdue Issue] {issue['title']} (#{issue['number']})"
    
    _assignees = ''
    mail_to = []
    if assignees:
        for assignee in assignees:
            if assignee.get('name') and assignee['name'].strip():
                _assignees += f"@{assignee['name']} "
            if assignee.get('email') and assignee['email'].strip():
                mail_to.append(assignee['email'])
    else:
        logger.info(f"No assignees found for issue #{issue['number']}")

    message = f"""
    <p>Reminder: The issue <strong>{issue['title']}</strong> (#{issue['number']}) is overdue since <strong>{duedate.strftime('%b %d, %Y')}</strong>.</p>
    <p>Assignees: {_assignees.strip() if _assignees.strip() else 'No assignees'}</p>
    <p>Please ensure the issue is completed.</p>
    <p><a href="{issue['url']}">View Issue</a></p>
    """

    return [subject, message, mail_to]

def send_email(from_email: str, to_email: list, subject: str, html_body: str):
    # Filter invalid/empty emails
    to_email = [addr.strip() for addr in to_email if addr and addr.strip()]
    if not to_email:
        logger.warning(f"'{subject}' email not sent because no recipients were provided. Sending to {config.smtp_cc_email}")
        to_email = [config.smtp_cc_email]

    # Always CC this address (if valid)
    cc_email = config.smtp_cc_email.strip() if getattr(config, "smtp_cc_email", "").strip() else None

    # Create the message
    message = MIMEMultipart()
    message['From'] = from_email
    message['To'] = ", ".join(to_email)
    if cc_email:
        message['Cc'] = cc_email
    message['Subject'] = subject
    message.attach(MIMEText(html_body, 'html'))

    # Build recipients list
    recipients = to_email[:]
    if cc_email:
        recipients.append(cc_email)

    # SMTP endpoints to try
    smtp_endpoints = [
        {"port": 587, "use_ssl": False},  # STARTTLS
        {"port": 465, "use_ssl": True},   # SSL
    ]

    last_error = None
    for endpoint in smtp_endpoints:
        smtp_server = None
        try:
            if endpoint["use_ssl"]:
                smtp_server = smtplib.SMTP_SSL(config.smtp_server, endpoint["port"], timeout=10)
            else:
                smtp_server = smtplib.SMTP(config.smtp_server, endpoint["port"], timeout=10)
                try:
                    smtp_server.starttls()
                except Exception as e:
                    logger.warning(f"STARTTLS failed on port {endpoint['port']}: {e}")
                    continue

            smtp_server.login(config.smtp_username, config.smtp_password)
            smtp_server.sendmail(from_email, recipients, message.as_string())
            logger.info(f"Email '{subject}' sent via port {endpoint['port']}")
            return  # success → stop trying

        except Exception as e:
            last_error = e
            logger.warning(f"Failed to send via port {endpoint['port']} ({'SSL' if endpoint['use_ssl'] else 'STARTTLS'}): {e}")

        finally:
            if smtp_server:
                try:
                    smtp_server.close()
                except Exception:
                    pass

    # If all endpoints failed
    logger.error(f"Could not send email '{subject}'. Last error: {last_error}")
