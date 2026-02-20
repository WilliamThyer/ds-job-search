"""Generic email job alerts scraper for HP, Revolut, and other companies."""

import email
import imaplib
import logging
import os
import re
from datetime import datetime, timedelta
from typing import Optional

from bs4 import BeautifulSoup
from dotenv import load_dotenv

from models import Job
from utils import is_barcelona_role, is_data_role, detect_visa_mentions

logger = logging.getLogger(__name__)

load_dotenv()

GMAIL_ADDRESS = os.getenv("GMAIL_ADDRESS")
GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD")

# Email sender patterns for each company
COMPANY_SENDERS = {
    "hp": [
        "careers@hp.com",
        "noreply@hp.com",
        "hp@talent.icims.com",
        "no-reply@eightfold.ai",
        "hp@eightfold.ai",
    ],
    "revolut": [
        "careers@revolut.com",
        "noreply@revolut.com",
        "talent@revolut.com",
        "jobs@revolut.com",
    ],
}

# URL patterns to identify job links for each company
COMPANY_URL_PATTERNS = {
    "hp": [r"apply\.hp\.com", r"hp\.com/careers", r"jobs\.hp\.com"],
    "revolut": [r"revolut\.com/careers", r"revolut\.com/.*position"],
}


def scrape_email_alerts(company_id: str, days_back: int = 7) -> list[Job]:
    """
    Scrape jobs from email alerts for a specific company.

    Args:
        company_id: Internal company identifier (hp, revolut, etc.)
        days_back: How many days of emails to check

    Returns:
        List of Job objects
    """
    if not GMAIL_ADDRESS or not GMAIL_APP_PASSWORD:
        logger.info(f"Gmail credentials not configured, skipping {company_id} email scraper")
        return []

    if company_id not in COMPANY_SENDERS:
        logger.warning(f"No email senders configured for {company_id}")
        return []

    jobs = []

    try:
        mail = imaplib.IMAP4_SSL("imap.gmail.com")
        try:
            mail.login(GMAIL_ADDRESS, GMAIL_APP_PASSWORD)
        except imaplib.IMAP4.error as e:
            logger.warning(f"Gmail authentication failed, skipping {company_id} email scraper: {e}")
            return []
        mail.select("inbox")

        since_date = (datetime.now() - timedelta(days=days_back)).strftime("%d-%b-%Y")

        for sender in COMPANY_SENDERS[company_id]:
            search_criteria = f'(FROM "{sender}" SINCE "{since_date}")'

            try:
                status, message_ids = mail.search(None, search_criteria)
                if status != "OK":
                    continue

                for msg_id in message_ids[0].split():
                    status, msg_data = mail.fetch(msg_id, "(RFC822)")
                    if status != "OK":
                        continue

                    email_body = msg_data[0][1]
                    msg = email.message_from_bytes(email_body)

                    email_jobs = _parse_job_alert_email(company_id, msg)
                    jobs.extend(email_jobs)

            except Exception as e:
                logger.debug(f"Error searching for {sender}: {e}")
                continue

        mail.logout()

    except imaplib.IMAP4.error as e:
        logger.error(f"IMAP error connecting to Gmail: {e}")
        return []
    except Exception as e:
        logger.error(f"Failed to fetch job emails for {company_id}: {e}")
        return []

    # Deduplicate by URL
    seen_urls = set()
    unique_jobs = []
    for job in jobs:
        if job.job_url not in seen_urls:
            seen_urls.add(job.job_url)
            unique_jobs.append(job)

    # Filter to matching jobs
    matching_jobs = [j for j in unique_jobs if j.is_barcelona and j.is_data_role]

    logger.info(f"Email Alerts [{company_id}]: Found {len(matching_jobs)} matching jobs from {len(unique_jobs)} total")
    return matching_jobs


def _parse_job_alert_email(company_id: str, msg: email.message.Message) -> list[Job]:
    """Parse jobs from a job alert email."""
    jobs = []

    # Get email body (prefer HTML)
    body = ""
    if msg.is_multipart():
        for part in msg.walk():
            content_type = part.get_content_type()
            if content_type == "text/html":
                payload = part.get_payload(decode=True)
                if payload:
                    body = payload.decode("utf-8", errors="ignore")
                    break
            elif content_type == "text/plain" and not body:
                payload = part.get_payload(decode=True)
                if payload:
                    body = payload.decode("utf-8", errors="ignore")
    else:
        payload = msg.get_payload(decode=True)
        if payload:
            body = payload.decode("utf-8", errors="ignore")

    if not body:
        return jobs

    soup = BeautifulSoup(body, "html.parser")

    # Find job links matching company URL patterns
    url_patterns = COMPANY_URL_PATTERNS.get(company_id, [])
    combined_pattern = "|".join(url_patterns) if url_patterns else company_id

    job_links = soup.find_all("a", href=re.compile(combined_pattern, re.IGNORECASE))

    for link in job_links:
        href = link.get("href", "")
        if not href or "unsubscribe" in href.lower() or "privacy" in href.lower():
            continue

        title = link.get_text(strip=True)

        # Skip non-job links
        if not title or len(title) < 5:
            parent = link.find_parent(["tr", "div", "td"])
            if parent:
                title_elem = parent.find(["h2", "h3", "h4", "strong", "b"])
                if title_elem:
                    title = title_elem.get_text(strip=True)
                else:
                    continue
            else:
                continue

        if title.lower() in ["view job", "apply", "learn more", "see all jobs", "view all"]:
            continue

        location = _extract_location_near_link(link)
        job = _create_job(company_id, title, href, location)
        if job:
            jobs.append(job)

    return jobs


def _extract_location_near_link(link) -> str:
    """Try to extract location from elements near the job link."""
    parent = link.find_parent(["tr", "div", "td", "li"])
    if not parent:
        return ""

    text = parent.get_text()
    location_patterns = [
        r"Barcelona",
        r"Sant Cugat",
        r"Spain",
        r"Madrid",
        r"Remote",
        r"Hybrid",
    ]

    for pattern in location_patterns:
        if re.search(pattern, text, re.IGNORECASE):
            match = re.search(
                r"([A-Za-z\s,]+(?:Spain|Barcelona|Madrid|Sant Cugat|Remote)[A-Za-z\s,]*)",
                text,
            )
            if match:
                return match.group(1).strip()
            return pattern

    return ""


def _create_job(company_id: str, title: str, url: str, location: str) -> Optional[Job]:
    """Create a Job object from parsed data."""
    if not title or not url:
        return None

    # Clean up the URL
    if not url.startswith("http"):
        url = "https:" + url if url.startswith("//") else "https://" + url

    # Remove tracking parameters
    url = re.sub(r"\?.*$", "", url)

    is_bcn = is_barcelona_role(location, title, "")
    is_data = is_data_role(title, "")
    mentions_visa, mentions_relocation = detect_visa_mentions("")

    return Job(
        company_id=company_id,
        job_title=title,
        job_url=url,
        location=location or "Unknown",
        department="",
        posted_date=datetime.now().strftime("%Y-%m-%d"),
        description_full="",
        is_barcelona=is_bcn,
        is_data_role=is_data,
        mentions_visa=mentions_visa,
        mentions_relocation=mentions_relocation,
    )


# Convenience functions for each company
def scrape_hp_email(company_id: str) -> list[Job]:
    """Scrape HP jobs from email alerts."""
    return scrape_email_alerts("hp")


def scrape_revolut_email(company_id: str) -> list[Job]:
    """Scrape Revolut jobs from email alerts."""
    return scrape_email_alerts("revolut")
