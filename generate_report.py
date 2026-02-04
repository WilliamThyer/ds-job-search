#!/usr/bin/env python3
"""Generate daily CSV report of new job postings."""

import json
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd

from models import get_new_jobs_since, DB_PATH

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
)
logger = logging.getLogger(__name__)

COMPANIES_FILE = Path(__file__).parent / "data" / "companies.json"
REPORTS_DIR = Path(__file__).parent / "reports"


def load_company_info() -> dict:
    """Load company metadata for enriching reports."""
    if not COMPANIES_FILE.exists():
        return {}

    with open(COMPANIES_FILE) as f:
        data = json.load(f)

    return {c['id']: c for c in data.get('companies', [])}


def generate_report(days_back: int = 1) -> Path:
    """
    Generate CSV report of jobs discovered in the last N days.

    Args:
        days_back: Number of days to look back (default: 1)

    Returns:
        Path to generated CSV file
    """
    # Calculate date threshold
    since_date = (datetime.now(timezone.utc) - timedelta(days=days_back)).isoformat()

    # Get matching jobs
    jobs = get_new_jobs_since(since_date)
    logger.info(f"Found {len(jobs)} jobs since {since_date[:10]}")

    if not jobs:
        logger.info("No new jobs to report")
        return None

    # Load company info for enrichment
    companies = load_company_info()

    # Build report data
    rows = []
    for job in jobs:
        company_info = companies.get(job['company_id'], {})

        # Determine visa status display (check both job posting and company data)
        company_sponsors = company_info.get('known_visa_sponsor', False)

        if job['mentions_visa']:
            visa_status = 'Yes (job posting)'
        elif job['mentions_relocation']:
            visa_status = 'Maybe (relocation mentioned)'
        elif company_sponsors:
            visa_status = 'Likely (company sponsors)'
        else:
            visa_status = 'Unknown'

        rows.append({
            'Company': company_info.get('name', job['company_id']),
            'Title': job['job_title'],
            'Location': job['location'],
            'Posted Date': job['posted_date'] or 'Unknown',
            'Ethics': company_info.get('ethics_rating', 'Unknown'),
            'Visa?': visa_status,
            'Apply URL': job['job_url'],
            'Notes': company_info.get('notes', ''),
        })

    # Create DataFrame and save
    df = pd.DataFrame(rows)

    # Ensure reports directory exists
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    # Generate filename with today's date
    today = datetime.now(timezone.utc).strftime('%Y-%m-%d')
    output_path = REPORTS_DIR / f"{today}_new_jobs.csv"

    df.to_csv(output_path, index=False)
    logger.info(f"Report saved to {output_path}")

    # Print summary to stdout
    print(f"\n{'='*60}")
    print(f"NEW DATA ROLES IN BARCELONA - {today}")
    print(f"{'='*60}")
    print(f"Total: {len(rows)} jobs\n")

    for row in rows:
        print(f"  [{row['Ethics']}] {row['Company']}: {row['Title']}")
        print(f"       Location: {row['Location']} | Visa: {row['Visa?']}")
        print(f"       {row['Apply URL']}\n")

    return output_path


def main():
    """Main entry point."""
    if not DB_PATH.exists():
        logger.error(f"Database not found at {DB_PATH}. Run scraper.py first.")
        return

    generate_report(days_back=1)


if __name__ == "__main__":
    main()
