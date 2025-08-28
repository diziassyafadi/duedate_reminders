from datetime import datetime, timedelta
from logger import logger
import config
import utils
import graphql

ALLOWED_STATUSES = ("In Progress", "In review")


def get_status(project_item):
    """Extract the Status field value from a project item."""
    status_value = None

    # Enterprise / project-based query
    if project_item.get("fieldValuesByName"):
        status_field = project_item["fieldValuesByName"].get("Status")
        if status_field:
            status_value = status_field.get("name")

    # Repo-based query
    elif project_item.get("fieldValueByName"):
        status_field = project_item["fieldValueByName"].get("Status")
        if status_field:
            status_value = status_field.get("name")

    return status_value


def should_notify(project_item):
    """Check if an item should be notified based on status."""
    status_value = get_status(project_item)
    return status_value in ALLOWED_STATUSES


def extract_project_item(issue):
    """Normalize project item extraction for both enterprise and repo issues."""
    if config.is_enterprise:
        project_item = issue
        issue = issue["content"]
    else:
        project_nodes = issue["projectItems"]["nodes"]
        if not project_nodes:
            return None, None
        project_item = next(
            (entry for entry in project_nodes if entry["project"]["number"] == config.project_number),
            None,
        )
    return project_item, issue


def notify_overdue_issues():
    issues = (
        graphql.get_project_issues(
            owner=config.repository_owner,
            owner_type=config.repository_owner_type,
            project_number=config.project_number,
            duedate_field_name=config.duedate_field_name,
            filters={"open_only": True},
        )
        if config.is_enterprise
        else graphql.get_repo_issues(
            owner=config.repository_owner,
            repository=config.repository_name,
            duedate_field_name=config.duedate_field_name,
        )
    )

    if not issues:
        logger.info("No issues have been found")
        return

    for issue in issues:
        project_item, issue = extract_project_item(issue)
        if not project_item or not project_item.get("fieldValueByName"):
            continue

        duedate = project_item["fieldValueByName"]["date"]
        duedate_obj = datetime.strptime(duedate, "%Y-%m-%d").date()

        if duedate_obj > datetime.now().date():
            continue
        if not should_notify(project_item):
            continue

        assignees = issue["assignees"]["nodes"]
        if config.notification_type == "comment":
            comment = utils.prepare_overdue_issue_comment(issue, assignees, duedate_obj)
            if not config.dry_run:
                graphql.add_issue_comment(issue["id"], comment)
            logger.info(f"Comment added to issue #{issue['number']} ({issue['id']}) with due date {duedate_obj}")
        elif config.notification_type == "email":
            subject, message, to = utils.prepare_overdue_issue_email_message(issue, assignees, duedate_obj)
            if not config.dry_run:
                utils.send_email(config.smtp_from_email, to, subject, message)
            logger.info(f"Email sent to {to} for issue #{issue['number']} with due date {duedate_obj}")


def notify_expiring_issues():
    issues = (
        graphql.get_project_issues(
            owner=config.repository_owner,
            owner_type=config.repository_owner_type,
            project_number=config.project_number,
            duedate_field_name=config.duedate_field_name,
            filters={"open_only": True},
        )
        if config.is_enterprise
        else graphql.get_repo_issues(
            owner=config.repository_owner,
            repository=config.repository_name,
            duedate_field_name=config.duedate_field_name,
        )
    )

    if not issues:
        logger.info("No issues have been found")
        return

    today = datetime.now().date()
    upcoming = {today, today + timedelta(days=1), today + timedelta(days=2)}

    for issue in issues:
        project_item, issue = extract_project_item(issue)
        if not project_item or not project_item.get("fieldValueByName"):
            continue

        duedate = project_item["fieldValueByName"]["date"]
        duedate_obj = datetime.strptime(duedate, "%Y-%m-%d").date()

        if duedate_obj not in upcoming:
            continue
        if not should_notify(project_item):
            continue

        assignees = issue["assignees"]["nodes"]
        if config.notification_type == "comment":
            comment = utils.prepare_expiring_issue_comment(issue, assignees, duedate_obj)
            if not config.dry_run:
                graphql.add_issue_comment(issue["id"], comment)
            logger.info(f"Comment added to issue #{issue['number']} ({issue['id']}) expiring {duedate_obj}")
        elif config.notification_type == "email":
            subject, message, to = utils.prepare_expiring_issue_email_message(issue, assignees, duedate_obj)
            if not config.dry_run:
                utils.send_email(config.smtp_from_email, to, subject, message)
            logger.info(f"Email sent to {to} for issue #{issue['number']} expiring {duedate_obj}")


def notify_missing_duedate():
    issues = graphql.get_project_issues(
        owner=config.repository_owner,
        owner_type=config.repository_owner_type,
        project_number=config.project_number,
        duedate_field_name=config.duedate_field_name,
        filters={"empty_duedate": True, "open_only": True},
    )

    if not issues:
        logger.info("No issues have been found")
        return

    for project_item in issues:
        issue = project_item["content"]

        if not should_notify(project_item):
            continue

        assignees = issue["assignees"]["nodes"]
        if config.notification_type == "comment":
            comment = utils.prepare_missing_duedate_comment(issue, assignees)
            if not config.dry_run:
                graphql.add_issue_comment(issue["id"], comment)
            logger.info(f"Comment added to issue #{issue['number']} ({issue['id']}) missing duedate")
        elif config.notification_type == "email":
            subject, message, to = utils.prepare_missing_duedate_email_message(issue, assignees)
            if not config.dry_run:
                utils.send_email(config.smtp_from_email, to, subject, message)
            logger.info(f"Email sent to {to} for issue #{issue['number']} missing duedate")


def main():
    logger.info("Process started...")
    if config.dry_run:
        logger.info("DRY RUN MODE ON!")

    if config.notify_for == "expiring_issues":
        notify_expiring_issues()
    elif config.notify_for == "missing_duedate":
        notify_missing_duedate()
    elif config.notify_for == "overdue_issues":
        notify_overdue_issues()
    else:
        raise Exception("Unsupported value for argument 'notify_for'")


if __name__ == "__main__":
    main()
