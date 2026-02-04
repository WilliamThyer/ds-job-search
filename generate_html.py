#!/usr/bin/env python3
"""Generate HTML dashboard for GitHub Pages."""

import json
from datetime import datetime, timezone
from pathlib import Path

from models import DB_PATH
import sqlite3

COMPANIES_FILE = Path(__file__).parent / "data" / "companies.json"
OUTPUT_FILE = Path(__file__).parent / "docs" / "index.html"

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Barcelona DS Jobs</title>
    <style>
        * {{ box-sizing: border-box; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
            background: #f5f5f5;
        }}
        h1 {{ color: #333; }}
        .updated {{ color: #666; font-size: 14px; margin-bottom: 20px; }}
        .filters {{
            background: white;
            padding: 15px;
            border-radius: 8px;
            margin-bottom: 20px;
            box-shadow: 0 1px 3px rgba(0,0,0,0.1);
        }}
        .filters label {{ margin-right: 15px; }}
        .job-card {{
            background: white;
            padding: 20px;
            border-radius: 8px;
            margin-bottom: 15px;
            box-shadow: 0 1px 3px rgba(0,0,0,0.1);
        }}
        .job-card h3 {{ margin: 0 0 10px 0; }}
        .job-card h3 a {{ color: #0066cc; text-decoration: none; }}
        .job-card h3 a:hover {{ text-decoration: underline; }}
        .company {{ font-weight: 600; color: #333; }}
        .meta {{ color: #666; font-size: 14px; margin: 5px 0; }}
        .tags {{ margin-top: 10px; }}
        .tag {{
            display: inline-block;
            padding: 3px 10px;
            border-radius: 12px;
            font-size: 12px;
            margin-right: 5px;
        }}
        .tag-visa {{ background: #d4edda; color: #155724; }}
        .tag-maybe {{ background: #fff3cd; color: #856404; }}
        .tag-likely {{ background: #cce5ff; color: #004085; }}
        .tag-unknown {{ background: #e9ecef; color: #495057; }}
        .tag-ethics-good {{ background: #d4edda; color: #155724; }}
        .tag-ethics-neutral {{ background: #e9ecef; color: #495057; }}
        .tag-ethics-kinda_evil {{ background: #f8d7da; color: #721c24; }}
        .stats {{
            display: flex;
            gap: 20px;
            margin-bottom: 20px;
        }}
        .stat {{
            background: white;
            padding: 15px 25px;
            border-radius: 8px;
            box-shadow: 0 1px 3px rgba(0,0,0,0.1);
        }}
        .stat-number {{ font-size: 32px; font-weight: bold; color: #0066cc; }}
        .stat-label {{ color: #666; font-size: 14px; }}
        .new-badge {{
            background: #dc3545;
            color: white;
            padding: 2px 8px;
            border-radius: 10px;
            font-size: 11px;
            margin-left: 8px;
        }}
    </style>
</head>
<body>
    <h1>Barcelona Data Science Jobs</h1>
    <p class="updated">Last updated: {updated}</p>

    <div class="stats">
        <div class="stat">
            <div class="stat-number">{total_jobs}</div>
            <div class="stat-label">Total Jobs</div>
        </div>
        <div class="stat">
            <div class="stat-number">{new_today}</div>
            <div class="stat-label">New Today</div>
        </div>
        <div class="stat">
            <div class="stat-number">{companies}</div>
            <div class="stat-label">Companies</div>
        </div>
    </div>

    <div class="filters">
        <strong>Filter:</strong>
        <label><input type="checkbox" id="filter-visa" checked> Visa-friendly</label>
    </div>

    <div id="jobs">
        {jobs_html}
    </div>

    <script>
        document.querySelectorAll('.filters input').forEach(cb => {{
            cb.addEventListener('change', filterJobs);
        }});

        function filterJobs() {{
            const visaOnly = document.getElementById('filter-visa').checked;

            document.querySelectorAll('.job-card').forEach(card => {{
                const hasVisa = card.dataset.visa !== 'unknown';
                card.style.display = (visaOnly && !hasVisa) ? 'none' : 'block';
            }});
        }}
    </script>
</body>
</html>
"""

JOB_CARD_TEMPLATE = """
<div class="job-card" data-visa="{visa_data}" data-ethics="{ethics}">
    <h3><a href="{url}" target="_blank">{title}</a>{new_badge}</h3>
    <div class="company">{company}</div>
    <div class="meta">{location} · Posted: {posted_date}</div>
    <div class="tags">
        <span class="tag tag-{visa_class}">{visa_status}</span>
        <span class="tag tag-ethics-{ethics}">{ethics_label}</span>
    </div>
</div>
"""


def load_company_info() -> dict:
    if not COMPANIES_FILE.exists():
        return {}
    with open(COMPANIES_FILE) as f:
        data = json.load(f)
    return {c['id']: c for c in data.get('companies', [])}


def get_all_jobs() -> list[dict]:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("""
        SELECT * FROM jobs
        WHERE is_barcelona = 1 AND is_data_role = 1
        ORDER BY scraped_date DESC
    """)
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]


def generate_html():
    jobs = get_all_jobs()
    companies = load_company_info()

    def is_barcelona(job):
        location = (job['location'] or '').lower()
        return 'barcelona' in location or 'spain' in location or 'bcn' in location

    barcelona_jobs = [j for j in jobs if is_barcelona(j)]
    today = datetime.now(timezone.utc).strftime('%Y-%m-%d')
    new_today = sum(1 for j in barcelona_jobs if j['scraped_date'][:10] == today)
    unique_companies = len(set(j['company_id'] for j in barcelona_jobs))

    jobs_html = []
    for job in jobs:
        # Filter to Barcelona-only jobs
        location = (job['location'] or '').lower()
        if 'barcelona' not in location and 'spain' not in location and 'bcn' not in location:
            continue

        company_info = companies.get(job['company_id'], {})
        company_sponsors = company_info.get('known_visa_sponsor', False)

        # Determine visa status
        if job['mentions_visa']:
            visa_status = 'Yes (job posting)'
            visa_class = 'visa'
            visa_data = 'yes'
        elif job['mentions_relocation']:
            visa_status = 'Maybe (relocation)'
            visa_class = 'maybe'
            visa_data = 'maybe'
        elif company_sponsors:
            visa_status = 'Likely (company)'
            visa_class = 'likely'
            visa_data = 'likely'
        else:
            visa_status = 'Unknown'
            visa_class = 'unknown'
            visa_data = 'unknown'

        ethics = company_info.get('ethics_rating', 'neutral')
        ethics_label = {'good': 'Good', 'neutral': 'Neutral', 'kinda_evil': 'Caution'}.get(ethics, ethics)

        is_new = job['scraped_date'][:10] == today
        new_badge = '<span class="new-badge">NEW</span>' if is_new else ''

        jobs_html.append(JOB_CARD_TEMPLATE.format(
            title=job['job_title'],
            url=job['job_url'],
            company=company_info.get('name', job['company_id']),
            location=job['location'] or 'Barcelona',
            posted_date=job['posted_date'] or 'Unknown',
            visa_status=visa_status,
            visa_class=visa_class,
            visa_data=visa_data,
            ethics=ethics,
            ethics_label=ethics_label,
            new_badge=new_badge,
        ))

    html = HTML_TEMPLATE.format(
        updated=datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC'),
        total_jobs=len(jobs_html),
        new_today=new_today,
        companies=unique_companies,
        jobs_html='\n'.join(jobs_html),
    )

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_FILE.write_text(html)
    print(f"Generated {OUTPUT_FILE} with {len(jobs_html)} Barcelona jobs")
    return len(jobs_html), new_today


if __name__ == "__main__":
    generate_html()
