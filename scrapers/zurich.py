"""Zurich Insurance careers scraper via J2W (Jobs2Web/SAP SuccessFactors) RSS feed."""

import logging
import time
import xml.etree.ElementTree as ET
from datetime import datetime
from email.utils import parsedate_to_datetime
from typing import Optional

import requests

from models import Job
from utils import is_barcelona_role, is_data_role, detect_visa_mentions

logger = logging.getLogger(__name__)

BASE_URL = "https://www.careers.zurich.com"
RSS_URL = f"{BASE_URL}/services/rss/job/"

# Search terms to cover all data-related roles
SEARCH_TERMS = [
    "data",
    "analytics",
    "machine learning",
    "artificial intelligence",
    "scientist",
]

RATE_LIMIT_DELAY = 1  # seconds between RSS requests


def scrape_zurich(company_id: str) -> list[Job]:
    """
    Scrape Zurich Insurance jobs via the J2W RSS feed.

    Searches multiple data-related terms and filters for Barcelona roles.

    Args:
        company_id: Internal company identifier

    Returns:
        List of Job objects matching Barcelona + data role criteria
    """
    all_job_data = {}  # url -> job_dict for deduplication

    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
    }

    for i, term in enumerate(SEARCH_TERMS):
        if i > 0:
            time.sleep(RATE_LIMIT_DELAY)

        try:
            jobs = _fetch_rss_jobs(term, headers)
            for job in jobs:
                url = job["url"]
                if url not in all_job_data:
                    all_job_data[url] = job
        except Exception as e:
            logger.error(f"Error fetching Zurich RSS for term '{term}': {e}")

    # Filter and convert to Job objects
    matching_jobs = []
    for job_data in all_job_data.values():
        job = _create_job(company_id, job_data)
        if job and job.is_barcelona and job.is_data_role:
            matching_jobs.append(job)

    logger.info(
        f"Zurich [{company_id}]: Found {len(matching_jobs)} matching jobs "
        f"from {len(all_job_data)} unique total"
    )
    return matching_jobs


def _fetch_rss_jobs(term: str, headers: dict) -> list[dict]:
    """Fetch jobs from Zurich RSS feed for a single search term."""
    params = {
        "locale": "en_US",
        "keywords": term,
    }

    resp = requests.get(RSS_URL, params=params, headers=headers, timeout=30)
    if resp.status_code != 200:
        logger.warning(f"Zurich RSS returned {resp.status_code} for term '{term}'")
        return []

    return _parse_rss(resp.text)


def _parse_rss(xml_text: str) -> list[dict]:
    """Parse RSS XML and extract job data."""
    jobs = []

    try:
        root = ET.fromstring(xml_text)
        channel = root.find("channel")
        if channel is None:
            return jobs

        for item in channel.findall("item"):
            title_elem = item.find("title")
            link_elem = item.find("link")
            desc_elem = item.find("description")
            pub_elem = item.find("pubDate")

            if title_elem is None or link_elem is None:
                continue

            title_raw = title_elem.text or ""
            link = link_elem.text or ""
            description = desc_elem.text or "" if desc_elem is not None else ""
            pub_date = pub_elem.text or "" if pub_elem is not None else ""

            # Title format: "Job Title (City, Country Code)"
            # Extract the clean title and location
            title, location = _parse_title_location(title_raw)

            if not title or not link:
                continue

            # Clean up the job URL (strip UTM params)
            clean_url = link.split("?")[0]

            jobs.append({
                "title": title,
                "url": clean_url,
                "location": location,
                "description": description,
                "posted": _parse_pub_date(pub_date),
            })

    except ET.ParseError as e:
        logger.error(f"Failed to parse Zurich RSS XML: {e}")

    return jobs


def _parse_title_location(title_raw: str) -> tuple[str, str]:
    """
    Parse title like 'Data Scientist (Barcelona, ES)' into
    ('Data Scientist', 'Barcelona, ES').
    """
    title_raw = title_raw.strip()

    # Find last parenthesized location suffix: " (City, CC)"
    if title_raw.endswith(")"):
        paren_start = title_raw.rfind("(")
        if paren_start > 0:
            location_part = title_raw[paren_start + 1:-1].strip()
            title_part = title_raw[:paren_start].strip()
            return title_part, location_part

    return title_raw, ""


def _parse_pub_date(date_str: str) -> str:
    """Parse RSS pubDate to YYYY-MM-DD."""
    if not date_str:
        return datetime.now().strftime("%Y-%m-%d")

    try:
        dt = parsedate_to_datetime(date_str.strip())
        return dt.strftime("%Y-%m-%d")
    except Exception:
        pass

    return datetime.now().strftime("%Y-%m-%d")


def _create_job(company_id: str, job_data: dict) -> Optional[Job]:
    """Create a Job object from parsed RSS data."""
    title = job_data.get("title", "")
    url = job_data.get("url", "")
    location = job_data.get("location", "")
    description = job_data.get("description", "")
    posted = job_data.get("posted", "")

    if not title or not url:
        return None

    is_bcn = is_barcelona_role(location, title, description)
    is_data = is_data_role(title, description)
    mentions_visa, mentions_relocation = detect_visa_mentions(description)

    return Job(
        company_id=company_id,
        job_title=title,
        job_url=url,
        location=location,
        department="",
        posted_date=posted,
        description_full="",
        is_barcelona=is_bcn,
        is_data_role=is_data,
        mentions_visa=mentions_visa,
        mentions_relocation=mentions_relocation,
    )
