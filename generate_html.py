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
            padding: 20px;
            border-radius: 8px;
            margin-bottom: 20px;
            box-shadow: 0 1px 3px rgba(0,0,0,0.1);
        }}
        .filter-row {{
            display: flex;
            flex-wrap: wrap;
            gap: 15px;
            align-items: center;
            margin-bottom: 15px;
        }}
        .filter-row:last-child {{ margin-bottom: 0; }}
        .filter-group {{
            display: flex;
            align-items: center;
            gap: 8px;
        }}
        .filter-group label {{
            font-weight: 500;
            color: #555;
            white-space: nowrap;
        }}
        .filter-group select, .filter-group input[type="text"] {{
            padding: 8px 12px;
            border: 1px solid #ddd;
            border-radius: 6px;
            font-size: 14px;
            background: white;
        }}
        .filter-group select {{ min-width: 150px; }}
        .search-input {{
            flex: 1;
            min-width: 200px;
            max-width: 400px;
        }}
        .checkbox-group {{
            display: flex;
            align-items: center;
            gap: 5px;
        }}
        .checkbox-group input {{ margin: 0; }}
        .results-count {{
            color: #666;
            font-size: 14px;
            margin-left: auto;
        }}
        .job-card {{
            background: white;
            padding: 20px;
            border-radius: 8px;
            margin-bottom: 15px;
            box-shadow: 0 1px 3px rgba(0,0,0,0.1);
        }}
        .job-card.hidden {{ display: none; }}
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
        .tag-remote {{ background: #e7f3ff; color: #0056b3; }}
        .tag-hybrid {{ background: #fff3cd; color: #856404; }}
        .tag-onsite {{ background: #f0f0f0; color: #555; }}
        .tag-ethics-good {{ background: #d4edda; color: #155724; }}
        .tag-ethics-neutral {{ background: #e9ecef; color: #495057; }}
        .tag-ethics-kinda_evil {{ background: #f8d7da; color: #721c24; }}
        .stats {{
            display: flex;
            gap: 20px;
            margin-bottom: 20px;
            flex-wrap: wrap;
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
        .manual-section {{
            margin-top: 40px;
            padding-top: 20px;
            border-top: 2px solid #ddd;
        }}
        .manual-section h2 {{
            color: #666;
            font-size: 18px;
            margin-bottom: 15px;
        }}
        .manual-sites {{
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
            gap: 15px;
        }}
        .manual-site {{
            background: white;
            padding: 15px 20px;
            border-radius: 8px;
            box-shadow: 0 1px 3px rgba(0,0,0,0.1);
            border-left: 4px solid #6c757d;
        }}
        .manual-site h3 {{
            margin: 0 0 8px 0;
            font-size: 16px;
        }}
        .manual-site h3 a {{
            color: #0066cc;
            text-decoration: none;
        }}
        .manual-site h3 a:hover {{
            text-decoration: underline;
        }}
        .manual-site p {{
            margin: 0;
            color: #666;
            font-size: 13px;
        }}
        @media (max-width: 600px) {{
            .filter-row {{ flex-direction: column; align-items: stretch; }}
            .filter-group {{ width: 100%; }}
            .filter-group select, .search-input {{ width: 100%; max-width: none; }}
            .results-count {{ margin-left: 0; margin-top: 10px; }}
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
        <div class="filter-row">
            <div class="filter-group">
                <label for="search">Search:</label>
                <input type="text" id="search" class="search-input" placeholder="Job title or company...">
            </div>
            <div class="filter-group checkbox-group">
                <input type="checkbox" id="filter-visa" checked>
                <label for="filter-visa">Visa-friendly only</label>
            </div>
            <span class="results-count"><span id="visible-count">{total_jobs}</span> jobs shown</span>
        </div>
        <div class="filter-row">
            <div class="filter-group">
                <label for="filter-worktype">Work type:</label>
                <select id="filter-worktype">
                    <option value="all">All</option>
                    <option value="remote">Remote</option>
                    <option value="hybrid">Hybrid</option>
                    <option value="onsite">In-person</option>
                </select>
            </div>
            <div class="filter-group">
                <label for="filter-company">Company:</label>
                <select id="filter-company">
                    <option value="all">All Companies</option>
                    {company_options}
                </select>
            </div>
            <div class="filter-group">
                <label for="sort-by">Sort by:</label>
                <select id="sort-by">
                    <option value="scraped-desc">Recently added</option>
                    <option value="scraped-asc">Oldest added</option>
                    <option value="posted-desc">Recently posted</option>
                    <option value="posted-asc">Oldest posted</option>
                    <option value="company-asc">Company A-Z</option>
                </select>
            </div>
        </div>
    </div>

    <div id="jobs">
        {jobs_html}
    </div>

    <div class="manual-section">
        <h2>Non-Automated Sites (Check Manually)</h2>
        <div class="manual-sites">
            <div class="manual-site">
                <h3><a href="https://www.revolut.com/careers/?city=Spain&team=Data" target="_blank">Revolut</a></h3>
                <p>Fintech - Data team roles in Spain</p>
            </div>
            <div class="manual-site">
                <h3><a href="https://apply.hp.com/careers?query=data+ai+machine+learning+ml&start=0&location=Barcelona%2C++CT%2C++Spain&pid=39162317&sort_by=relevance&filter_distance=80&filter_include_remote=1" target="_blank">HP</a></h3>
                <p>AI Lab - Data/ML roles in Barcelona</p>
            </div>
        </div>
    </div>

    <script>
        const searchInput = document.getElementById('search');
        const visaCheckbox = document.getElementById('filter-visa');
        const worktypeSelect = document.getElementById('filter-worktype');
        const companySelect = document.getElementById('filter-company');
        const sortSelect = document.getElementById('sort-by');
        const visibleCount = document.getElementById('visible-count');
        const jobsContainer = document.getElementById('jobs');

        searchInput.addEventListener('input', filterJobs);
        visaCheckbox.addEventListener('change', filterJobs);
        worktypeSelect.addEventListener('change', filterJobs);
        companySelect.addEventListener('change', filterJobs);
        sortSelect.addEventListener('change', sortJobs);

        function filterJobs() {{
            const searchTerm = searchInput.value.toLowerCase().trim();
            const visaOnly = visaCheckbox.checked;
            const worktype = worktypeSelect.value;
            const company = companySelect.value;

            let count = 0;
            document.querySelectorAll('.job-card').forEach(card => {{
                const hasVisa = card.dataset.visa !== 'unknown';
                const cardWorktype = card.dataset.worktype;
                const cardCompany = card.dataset.company;
                const cardTitle = card.dataset.title.toLowerCase();
                const cardCompanyName = card.dataset.companyname.toLowerCase();

                let show = true;

                // Visa filter
                if (visaOnly && !hasVisa) show = false;

                // Work type filter
                if (worktype !== 'all' && cardWorktype !== worktype) show = false;

                // Company filter
                if (company !== 'all' && cardCompany !== company) show = false;

                // Search filter
                if (searchTerm && !cardTitle.includes(searchTerm) && !cardCompanyName.includes(searchTerm)) {{
                    show = false;
                }}

                card.classList.toggle('hidden', !show);
                if (show) count++;
            }});

            visibleCount.textContent = count;
        }}

        function sortJobs() {{
            const sortBy = sortSelect.value;
            const cards = Array.from(document.querySelectorAll('.job-card'));

            cards.sort((a, b) => {{
                if (sortBy === 'scraped-desc') {{
                    return b.dataset.scraped.localeCompare(a.dataset.scraped);
                }} else if (sortBy === 'scraped-asc') {{
                    return a.dataset.scraped.localeCompare(b.dataset.scraped);
                }} else if (sortBy === 'posted-desc') {{
                    return b.dataset.posted.localeCompare(a.dataset.posted);
                }} else if (sortBy === 'posted-asc') {{
                    return a.dataset.posted.localeCompare(b.dataset.posted);
                }} else if (sortBy === 'company-asc') {{
                    return a.dataset.companyname.localeCompare(b.dataset.companyname);
                }}
                return 0;
            }});

            cards.forEach(card => jobsContainer.appendChild(card));
            filterJobs();
        }}
    </script>
</body>
</html>
"""

JOB_CARD_TEMPLATE = """
<div class="job-card" data-visa="{visa_data}" data-ethics="{ethics}" data-worktype="{worktype}" data-company="{company_id}" data-title="{title_lower}" data-companyname="{company_lower}" data-posted="{posted_sort}" data-scraped="{scraped_sort}">
    <h3><a href="{url}" target="_blank">{title}</a>{new_badge}</h3>
    <div class="company">{company}</div>
    <div class="meta">{location} · Posted: {posted_date} · Added: {scraped_date}</div>
    <div class="tags">
        <span class="tag tag-{worktype}">{worktype_label}</span>
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


def detect_work_type(location: str, description: str) -> tuple[str, str]:
    """Detect work type from location and description. Returns (type_id, label)."""
    location = (location or '').lower()
    description = (description or '').lower()
    text = location + ' ' + description

    # Check for remote indicators
    remote_keywords = ['remote', 'work from home', 'wfh', 'fully remote', '100% remote']
    hybrid_keywords = ['hybrid', 'flexible', '2 days', '3 days', 'days in office', 'days per week']

    if any(kw in text for kw in remote_keywords):
        # Check if it's actually hybrid
        if any(kw in text for kw in hybrid_keywords):
            return 'hybrid', 'Hybrid'
        return 'remote', 'Remote'
    elif any(kw in text for kw in hybrid_keywords):
        return 'hybrid', 'Hybrid'
    else:
        return 'onsite', 'In-person'


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

    # Build company options for dropdown (only companies with jobs)
    companies_with_jobs = {}
    for job in barcelona_jobs:
        cid = job['company_id']
        if cid not in companies_with_jobs:
            company_info = companies.get(cid, {})
            companies_with_jobs[cid] = company_info.get('name', cid)

    company_options = '\n'.join(
        f'<option value="{cid}">{name}</option>'
        for cid, name in sorted(companies_with_jobs.items(), key=lambda x: x[1].lower())
    )

    jobs_html = []
    for job in jobs:
        # Filter to Barcelona-only jobs
        location = (job['location'] or '').lower()
        if 'barcelona' not in location and 'spain' not in location and 'bcn' not in location:
            continue

        company_info = companies.get(job['company_id'], {})
        company_sponsors = company_info.get('known_visa_sponsor', False)
        company_name = company_info.get('name', job['company_id'])

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

        # Detect work type
        worktype, worktype_label = detect_work_type(job['location'], job.get('description_full'))

        is_new = job['scraped_date'][:10] == today
        new_badge = '<span class="new-badge">NEW</span>' if is_new else ''

        # Format dates for sorting (use 0000-00-00 for unknown to sort last)
        posted_sort = job['posted_date'] or '0000-00-00'
        scraped_sort = job['scraped_date'][:10] if job['scraped_date'] else '0000-00-00'
        scraped_display = job['scraped_date'][:10] if job['scraped_date'] else 'Unknown'

        jobs_html.append(JOB_CARD_TEMPLATE.format(
            title=job['job_title'],
            title_lower=job['job_title'].lower(),
            url=job['job_url'],
            company=company_name,
            company_id=job['company_id'],
            company_lower=company_name.lower(),
            location=job['location'] or 'Barcelona',
            posted_date=job['posted_date'] or 'Unknown',
            posted_sort=posted_sort,
            scraped_date=scraped_display,
            scraped_sort=scraped_sort,
            visa_status=visa_status,
            visa_class=visa_class,
            visa_data=visa_data,
            ethics=ethics,
            ethics_label=ethics_label,
            worktype=worktype,
            worktype_label=worktype_label,
            new_badge=new_badge,
        ))

    html = HTML_TEMPLATE.format(
        updated=datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC'),
        total_jobs=len(jobs_html),
        new_today=new_today,
        companies=unique_companies,
        company_options=company_options,
        jobs_html='\n'.join(jobs_html),
    )

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_FILE.write_text(html)
    print(f"Generated {OUTPUT_FILE} with {len(jobs_html)} Barcelona jobs")
    return len(jobs_html), new_today


if __name__ == "__main__":
    generate_html()
