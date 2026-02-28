#!/usr/bin/env python3
"""Generate HTML dashboard for GitHub Pages."""

import html
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote

from models import DB_PATH
from utils import is_great_fit
import sqlite3

def clean_description(text: str, max_len: int = 3000) -> str:
    if not text:
        return ''
    text = re.sub(r'<[^>]+>', ' ', text)       # strip HTML tags
    text = re.sub(r'\s+', ' ', text).strip()    # collapse whitespace
    return text[:max_len]


COMPANIES_FILE = Path(__file__).parent / "data" / "companies.json"
WORK_HISTORY_FILE = Path(__file__).parent / "data" / "master_work_history.json"
RESUME_TEMPLATE_FILE = Path(__file__).parent / "data" / "my_resume.md"
OUTPUT_FILE = Path(__file__).parent / "docs" / "index.html"
COMPANIES_OUTPUT_FILE = Path(__file__).parent / "docs" / "companies.html"
RESUME_OUTPUT_FILE = Path(__file__).parent / "docs" / "resume.html"

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
        .nav {{ margin-bottom: 20px; }}
        .nav a {{
            display: inline-block;
            padding: 8px 16px;
            background: white;
            border-radius: 6px;
            text-decoration: none;
            color: #0066cc;
            font-weight: 500;
            box-shadow: 0 1px 3px rgba(0,0,0,0.1);
            margin-right: 8px;
        }}
        .nav a:hover {{ background: #f0f0f0; }}
        .nav a.active {{ background: #0066cc; color: white; }}
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
        .greatfit-badge {{
            background: #28a745;
            color: white;
            padding: 2px 8px;
            border-radius: 10px;
            font-size: 11px;
            margin-left: 8px;
        }}
        .btn-resume {{
            display: inline-block;
            margin-top: 10px;
            padding: 4px 12px;
            background: #f0f4ff;
            border: 1px solid #c0d0f0;
            border-radius: 6px;
            color: #0066cc;
            font-size: 13px;
            text-decoration: none;
            cursor: pointer;
        }}
        .btn-resume:hover {{ background: #dde8ff; }}
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
    <div class="nav">
        <a href="index.html" class="active">Jobs</a>
        <a href="companies.html">Companies</a>
        <a href="resume.html">Resume Builder</a>
    </div>
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
            <div class="filter-group checkbox-group">
                <input type="checkbox" id="filter-greatfit">
                <label for="filter-greatfit">Great fits only</label>
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
        const greatfitCheckbox = document.getElementById('filter-greatfit');
        const worktypeSelect = document.getElementById('filter-worktype');
        const companySelect = document.getElementById('filter-company');
        const sortSelect = document.getElementById('sort-by');
        const visibleCount = document.getElementById('visible-count');
        const jobsContainer = document.getElementById('jobs');

        // Apply URL params on load
        const urlParams = new URLSearchParams(window.location.search);
        const paramCompany = urlParams.get('company');
        if (paramCompany) {{
            companySelect.value = paramCompany;
            visaCheckbox.checked = false;
            filterJobs();
        }}

        searchInput.addEventListener('input', filterJobs);
        visaCheckbox.addEventListener('change', filterJobs);
        greatfitCheckbox.addEventListener('change', filterJobs);
        worktypeSelect.addEventListener('change', filterJobs);
        companySelect.addEventListener('change', filterJobs);
        sortSelect.addEventListener('change', sortJobs);

        function filterJobs() {{
            const searchTerm = searchInput.value.toLowerCase().trim();
            const visaOnly = visaCheckbox.checked;
            const greatfitOnly = greatfitCheckbox.checked;
            const worktype = worktypeSelect.value;
            const company = companySelect.value;

            let count = 0;
            document.querySelectorAll('.job-card').forEach(card => {{
                const hasVisa = card.dataset.visa !== 'unknown';
                const isGreatFit = card.dataset.greatfit === 'true';
                const cardWorktype = card.dataset.worktype;
                const cardCompany = card.dataset.company;
                const cardTitle = card.dataset.title.toLowerCase();
                const cardCompanyName = card.dataset.companyname.toLowerCase();

                let show = true;

                // Visa filter
                if (visaOnly && !hasVisa) show = false;

                // Great fit filter
                if (greatfitOnly && !isGreatFit) show = false;

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

        function openResumeBuilder(btn) {{
            const card = btn.closest('.job-card');
            const title = card.querySelector('h3 a').textContent;
            const company = card.querySelector('.company').textContent;
            const description = card.dataset.description || '';
            sessionStorage.setItem('resumeJob', JSON.stringify({{title, company, description}}));
            window.open('resume.html', '_blank');
        }}
    </script>
</body>
</html>
"""

JOB_CARD_TEMPLATE = """
<div class="job-card" data-visa="{visa_data}" data-ethics="{ethics}" data-worktype="{worktype}" data-company="{company_id}" data-title="{title_lower}" data-companyname="{company_lower}" data-posted="{posted_sort}" data-scraped="{scraped_sort}" data-greatfit="{greatfit}" data-description="{description_attr}">
    <h3><a href="{url}" target="_blank">{title}</a>{new_badge}{greatfit_badge}</h3>
    <div class="company">{company}</div>
    <div class="meta">{location} · Posted: {posted_date} · Added: {scraped_date}</div>
    <div class="tags">
        <span class="tag tag-{worktype}">{worktype_label}</span>
        <span class="tag tag-{visa_class}">{visa_status}</span>
        <span class="tag tag-ethics-{ethics}">{ethics_label}</span>
    </div>
    <button class="btn-resume" onclick="openResumeBuilder(this)">Generate Resume</button>
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

        # Check if great fit
        great_fit = is_great_fit(job['job_title'], job.get('description_full') or '')
        greatfit_badge = '<span class="greatfit-badge">GREAT FIT</span>' if great_fit else ''

        description_attr = html.escape(clean_description(job.get('description_full') or ''), quote=True)

        jobs_html.append(JOB_CARD_TEMPLATE.format(
            title=job['job_title'],
            title_lower=job['job_title'].lower(),
            url=job['job_url'],
            company=company_name,
            company_id=job['company_id'],
            company_lower=company_name.lower(),
            description_attr=description_attr,
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
            greatfit='true' if great_fit else 'false',
            greatfit_badge=greatfit_badge,
        ))

    page = HTML_TEMPLATE.format(
        updated=datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC'),
        total_jobs=len(jobs_html),
        new_today=new_today,
        companies=unique_companies,
        company_options=company_options,
        jobs_html='\n'.join(jobs_html),
    )

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_FILE.write_text(page)
    print(f"Generated {OUTPUT_FILE} with {len(jobs_html)} Barcelona jobs")

    generate_companies_html(jobs, companies)
    generate_resume_html()

    return len(jobs_html), new_today


COMPANIES_PAGE_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Barcelona DS Jobs - Companies</title>
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
        .nav {{ margin-bottom: 20px; }}
        .nav a {{
            display: inline-block;
            padding: 8px 16px;
            background: white;
            border-radius: 6px;
            text-decoration: none;
            color: #0066cc;
            font-weight: 500;
            box-shadow: 0 1px 3px rgba(0,0,0,0.1);
            margin-right: 8px;
        }}
        .nav a:hover {{ background: #f0f0f0; }}
        .nav a.active {{ background: #0066cc; color: white; }}
        .updated {{ color: #666; font-size: 14px; margin-bottom: 20px; }}
        .table-wrap {{
            background: white;
            border-radius: 8px;
            box-shadow: 0 1px 3px rgba(0,0,0,0.1);
            overflow: auto;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            font-size: 14px;
        }}
        thead th {{
            background: #f8f9fa;
            padding: 12px 14px;
            text-align: left;
            border-bottom: 2px solid #dee2e6;
            white-space: nowrap;
            cursor: pointer;
            user-select: none;
        }}
        thead th:hover {{ background: #e9ecef; }}
        thead th.sort-asc::after {{ content: " ▲"; font-size: 10px; }}
        thead th.sort-desc::after {{ content: " ▼"; font-size: 10px; }}
        tbody tr:nth-child(even) {{ background: #fafafa; }}
        tbody tr:hover {{ background: #f0f4ff; }}
        td {{ padding: 10px 14px; border-bottom: 1px solid #f0f0f0; vertical-align: middle; }}
        td a {{ color: #0066cc; text-decoration: none; }}
        td a:hover {{ text-decoration: underline; }}
        .badge {{
            display: inline-block;
            padding: 2px 8px;
            border-radius: 10px;
            font-size: 12px;
            white-space: nowrap;
        }}
        .badge-yes {{ background: #d4edda; color: #155724; }}
        .badge-likely {{ background: #cce5ff; color: #004085; }}
        .badge-no {{ background: #f8d7da; color: #721c24; }}
        .badge-unknown {{ background: #e9ecef; color: #495057; }}
        .badge-good {{ background: #d4edda; color: #155724; }}
        .badge-neutral {{ background: #e9ecef; color: #495057; }}
        .badge-kinda_evil {{ background: #f8d7da; color: #721c24; }}
        .jobs-count {{
            font-weight: 600;
            color: #0066cc;
        }}
        .jobs-zero {{ color: #aaa; }}
        .filters {{
            background: white;
            padding: 15px 20px;
            border-radius: 8px;
            margin-bottom: 15px;
            box-shadow: 0 1px 3px rgba(0,0,0,0.1);
            display: flex;
            gap: 15px;
            align-items: center;
            flex-wrap: wrap;
        }}
        .filters label {{ font-weight: 500; color: #555; }}
        .filters input[type="text"] {{
            padding: 7px 12px;
            border: 1px solid #ddd;
            border-radius: 6px;
            font-size: 14px;
            min-width: 220px;
        }}
        .filters input[type="checkbox"] {{ margin: 0 4px 0 0; }}
        .row-count {{ color: #666; font-size: 13px; margin-left: auto; }}
    </style>
</head>
<body>
    <h1>Barcelona Data Science Jobs</h1>
    <div class="nav">
        <a href="index.html">Jobs</a>
        <a href="companies.html" class="active">Companies</a>
        <a href="resume.html">Resume Builder</a>
    </div>
    <p class="updated">Last updated: {updated} &mdash; {total_companies} companies tracked</p>

    <div class="filters">
        <label>Search: <input type="text" id="search" placeholder="Company or industry..."></label>
        <label><input type="checkbox" id="filter-visa"> Visa sponsors only</label>
        <label><input type="checkbox" id="filter-jobs"> Has open jobs only</label>
        <span class="row-count"><span id="row-count">{total_companies}</span> companies shown</span>
    </div>

    <div class="table-wrap">
        <table id="company-table">
            <thead>
                <tr>
                    <th data-col="name">Company</th>
                    <th data-col="industry">Industry</th>
                    <th data-col="hq">HQ</th>
                    <th data-col="jobs" class="sort-desc">Open Jobs</th>
                    <th data-col="greatfit">Great Fit</th>
                    <th data-col="visa">Visa</th>
                    <th data-col="ethics">Ethics</th>
                </tr>
            </thead>
            <tbody id="tbody">
{rows}
            </tbody>
        </table>
    </div>

    <script>
        const rows = Array.from(document.querySelectorAll('#tbody tr'));
        const searchInput = document.getElementById('search');
        const visaFilter = document.getElementById('filter-visa');
        const jobsFilter = document.getElementById('filter-jobs');
        const rowCount = document.getElementById('row-count');
        let sortCol = 'jobs';
        let sortDir = -1; // -1 = desc, 1 = asc

        function applyFilters() {{
            const term = searchInput.value.toLowerCase().trim();
            let count = 0;
            rows.forEach(row => {{
                const name = row.dataset.name;
                const industry = row.dataset.industry;
                const visa = row.dataset.visa;
                const jobs = parseInt(row.dataset.jobs, 10);
                let show = true;
                if (term && !name.includes(term) && !industry.includes(term)) show = false;
                if (visaFilter.checked && visa === 'no') show = false;
                if (jobsFilter.checked && jobs === 0) show = false;
                row.style.display = show ? '' : 'none';
                if (show) count++;
            }});
            rowCount.textContent = count;
        }}

        function sortTable(col) {{
            if (sortCol === col) {{
                sortDir *= -1;
            }} else {{
                sortCol = col;
                sortDir = col === 'jobs' || col === 'greatfit' ? -1 : 1;
            }}

            // Update header classes
            document.querySelectorAll('thead th').forEach(th => {{
                th.classList.remove('sort-asc', 'sort-desc');
                if (th.dataset.col === col) {{
                    th.classList.add(sortDir === 1 ? 'sort-asc' : 'sort-desc');
                }}
            }});

            const tbody = document.getElementById('tbody');
            const sorted = [...rows].sort((a, b) => {{
                let av = a.dataset[col] || '';
                let bv = b.dataset[col] || '';
                if (col === 'jobs' || col === 'greatfit') {{
                    return (parseInt(av,10) - parseInt(bv,10)) * sortDir;
                }}
                return av.localeCompare(bv) * sortDir;
            }});
            sorted.forEach(r => tbody.appendChild(r));
            applyFilters();
        }}

        document.querySelectorAll('thead th[data-col]').forEach(th => {{
            th.addEventListener('click', () => sortTable(th.dataset.col));
        }});
        searchInput.addEventListener('input', applyFilters);
        visaFilter.addEventListener('change', applyFilters);
        jobsFilter.addEventListener('change', applyFilters);
    </script>
</body>
</html>
"""

COMPANY_ROW_TEMPLATE = """                <tr data-name="{name_lower}" data-industry="{industry_lower}" data-visa="{visa_data}" data-jobs="{job_count}" data-greatfit="{greatfit_count}">
                    <td><a href="{careers_url}" target="_blank">{name}</a></td>
                    <td>{industry}</td>
                    <td>{hq}</td>
                    <td>{jobs_cell}</td>
                    <td>{greatfit_cell}</td>
                    <td><span class="badge badge-{visa_class}">{visa_label}</span></td>
                    <td><span class="badge badge-{ethics}">{ethics_label}</span></td>
                </tr>"""


def generate_companies_html(jobs: list[dict], companies: dict):
    """Generate the companies overview page."""
    # Count jobs and great fits per company
    company_job_counts: dict[str, int] = {}
    company_greatfit_counts: dict[str, int] = {}

    for job in jobs:
        location = (job['location'] or '').lower()
        if 'barcelona' not in location and 'spain' not in location and 'bcn' not in location:
            continue
        cid = job['company_id']
        company_job_counts[cid] = company_job_counts.get(cid, 0) + 1
        if is_great_fit(job['job_title'], job.get('description_full') or ''):
            company_greatfit_counts[cid] = company_greatfit_counts.get(cid, 0) + 1

    rows = []
    for cid, info in sorted(companies.items(), key=lambda x: x[1].get('name', x[0]).lower()):
        name = info.get('name', cid)
        industry = info.get('industry', '')
        hq = info.get('headquarters', '')
        careers_url = info.get('careers_url', '#')
        ethics = info.get('ethics_rating', 'neutral')
        ethics_label = {'good': 'Good', 'neutral': 'Neutral', 'kinda_evil': 'Caution'}.get(ethics, ethics)
        known_sponsor = info.get('known_visa_sponsor', False)

        job_count = company_job_counts.get(cid, 0)
        greatfit_count = company_greatfit_counts.get(cid, 0)

        # Visa classification
        if known_sponsor:
            visa_data = 'yes'
            visa_class = 'yes'
            visa_label = 'Yes'
        elif known_sponsor is False:
            visa_data = 'no'
            visa_class = 'no'
            visa_label = 'No'
        else:
            visa_data = 'unknown'
            visa_class = 'unknown'
            visa_label = 'Unknown'

        # Jobs cell with link
        if job_count > 0:
            jobs_cell = f'<a class="jobs-count" href="index.html?company={cid}">{job_count}</a>'
        else:
            jobs_cell = '<span class="jobs-zero">0</span>'

        greatfit_cell = f'<span class="jobs-count">{greatfit_count}</span>' if greatfit_count > 0 else '<span class="jobs-zero">0</span>'

        rows.append(COMPANY_ROW_TEMPLATE.format(
            name=name,
            name_lower=name.lower(),
            industry=industry,
            industry_lower=industry.lower(),
            hq=hq,
            careers_url=careers_url,
            job_count=job_count,
            greatfit_count=greatfit_count,
            jobs_cell=jobs_cell,
            greatfit_cell=greatfit_cell,
            visa_data=visa_data,
            visa_class=visa_class,
            visa_label=visa_label,
            ethics=ethics,
            ethics_label=ethics_label,
        ))

    page = COMPANIES_PAGE_TEMPLATE.format(
        updated=datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC'),
        total_companies=len(companies),
        rows='\n'.join(rows),
    )

    COMPANIES_OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    COMPANIES_OUTPUT_FILE.write_text(page)
    print(f"Generated {COMPANIES_OUTPUT_FILE} with {len(companies)} companies")


RESUME_PAGE_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Barcelona DS Jobs - Resume Builder</title>
    <style>
        * {{ box-sizing: border-box; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            max-width: 900px;
            margin: 0 auto;
            padding: 20px;
            background: #f5f5f5;
        }}
        h1 {{ color: #333; }}
        .nav {{ margin-bottom: 20px; }}
        .nav a {{
            display: inline-block;
            padding: 8px 16px;
            background: white;
            border-radius: 6px;
            text-decoration: none;
            color: #0066cc;
            font-weight: 500;
            box-shadow: 0 1px 3px rgba(0,0,0,0.1);
            margin-right: 8px;
        }}
        .nav a:hover {{ background: #f0f0f0; }}
        .nav a.active {{ background: #0066cc; color: white; }}
        .card {{
            background: white;
            padding: 24px;
            border-radius: 8px;
            box-shadow: 0 1px 3px rgba(0,0,0,0.1);
            margin-bottom: 20px;
        }}
        .card h2 {{ margin-top: 0; color: #333; font-size: 18px; }}
        label {{ display: block; font-weight: 500; color: #555; margin-bottom: 6px; }}
        .job-info {{ display: flex; gap: 12px; margin-bottom: 16px; flex-wrap: wrap; }}
        .job-info input {{
            flex: 1;
            min-width: 180px;
            padding: 8px 12px;
            border: 1px solid #ddd;
            border-radius: 6px;
            font-size: 14px;
        }}
        textarea {{
            width: 100%;
            padding: 12px;
            border: 1px solid #ddd;
            border-radius: 6px;
            font-size: 14px;
            font-family: inherit;
            resize: vertical;
        }}
        textarea#jd-input {{ height: 220px; }}
        textarea#prompt-output {{
            height: 400px;
            font-family: 'Courier New', monospace;
            font-size: 12px;
            background: #f8f9fa;
        }}
        .btn {{
            padding: 10px 24px;
            border: none;
            border-radius: 6px;
            font-size: 15px;
            font-weight: 600;
            cursor: pointer;
        }}
        .btn-primary {{ background: #0066cc; color: white; }}
        .btn-primary:hover {{ background: #0052a3; }}
        .btn-copy {{ background: #28a745; color: white; margin-left: 10px; }}
        .btn-copy:hover {{ background: #218838; }}
        .btn-copy.copied {{ background: #6c757d; }}
        .output-header {{
            display: flex;
            align-items: center;
            justify-content: space-between;
            margin-bottom: 8px;
        }}
        .output-header h2 {{ margin: 0; font-size: 18px; color: #333; }}
        .hint {{ color: #888; font-size: 13px; margin-top: 8px; }}
        .hidden {{ display: none; }}
    </style>
</head>
<body>
    <h1>Barcelona Data Science Jobs</h1>
    <div class="nav">
        <a href="index.html">Jobs</a>
        <a href="companies.html">Companies</a>
        <a href="resume.html" class="active">Resume Builder</a>
    </div>

    <div class="card">
        <h2>Generate Tailored Resume Prompt</h2>
        <p style="color:#555; margin-top:0;">Paste a job description below and click <strong>Generate Prompt</strong>.
        Copy the result into <a href="https://claude.ai" target="_blank">Claude.ai</a> to get a tailored one-page resume.</p>

        <div class="job-info">
            <div style="flex:1; min-width:180px;">
                <label for="job-title">Job Title (optional)</label>
                <input type="text" id="job-title" placeholder="e.g. Senior Data Scientist">
            </div>
            <div style="flex:1; min-width:180px;">
                <label for="job-company">Company (optional)</label>
                <input type="text" id="job-company" placeholder="e.g. Stripe">
            </div>
        </div>

        <label for="jd-input">Job Description</label>
        <textarea id="jd-input" placeholder="Paste the full job description here..."></textarea>

        <div style="margin-top: 14px;">
            <button class="btn btn-primary" onclick="generatePrompt()">Generate Prompt</button>
        </div>
    </div>

    <div class="card hidden" id="output-card">
        <div class="output-header">
            <h2>Your Claude Prompt</h2>
            <button class="btn btn-copy" id="copy-btn" onclick="copyPrompt()">Copy to Clipboard</button>
        </div>
        <textarea id="prompt-output" readonly></textarea>
        <p class="hint">Open <a href="https://claude.ai" target="_blank">claude.ai</a>, start a new chat, and paste this prompt.</p>
    </div>

    <script>
    const RESUME_TEMPLATE = {resume_template_js};
    const WORK_HISTORY_JSON = {work_history_js};

    function generatePrompt(fromJobCard = false) {{
        const jd = document.getElementById('jd-input').value.trim();
        if (!jd && !fromJobCard) {{ alert('Please paste a job description first.'); return; }}

        const title = document.getElementById('job-title').value.trim();
        const company = document.getElementById('job-company').value.trim();
        const jobLine = [title, company].filter(Boolean).join(' at ');

        const prompt = buildPrompt(jd, jobLine);
        document.getElementById('prompt-output').value = prompt;
        document.getElementById('output-card').classList.remove('hidden');
        document.getElementById('copy-btn').textContent = 'Copy to Clipboard';
        document.getElementById('copy-btn').classList.remove('copied');
        document.getElementById('output-card').scrollIntoView({{behavior: 'smooth'}});

        if (fromJobCard) {{
            navigator.clipboard.writeText(prompt).then(() => {{
                const btn = document.getElementById('copy-btn');
                btn.textContent = 'Copied!';
                btn.classList.add('copied');
                setTimeout(() => {{ btn.textContent = 'Copy to Clipboard'; btn.classList.remove('copied'); }}, 2000);
            }});
        }}
    }}

    function copyPrompt() {{
        const ta = document.getElementById('prompt-output');
        ta.select();
        navigator.clipboard.writeText(ta.value).then(() => {{
            const btn = document.getElementById('copy-btn');
            btn.textContent = 'Copied!';
            btn.classList.add('copied');
            setTimeout(() => {{
                btn.textContent = 'Copy to Clipboard';
                btn.classList.remove('copied');
            }}, 2000);
        }});
    }}

    function buildPrompt(jd, jobLine) {{
        const roleHeader = jobLine ? `Role: ${{jobLine}}\n\n` : '';
        const jdSection = jd ? jd : '[PASTE JOB DESCRIPTION HERE]';
        return `${{roleHeader}}Tailor my resume for this job description. Output the final resume markdown only — no commentary, no explanation. Make sure to use the exact formatting of the provided resume.

Rules:
- Use my current resume as the base structure and formatting (preserve all span/iconify tags exactly)
- You may swap in better-fit bullets from the work history JSON, but only use bullets that exist there — never fabricate metrics, technologies, or claims
- Lightly reword bullets to mirror JD keywords where truthful
- Keep to one page: 6-7 bullets for Cohere Health, 1 each for the other roles
- Reorder the Skills section to front-load the most JD-relevant items, never make up skills
- Mirror ATS keywords from the JD naturally in the text
- Lead with impact and quantified results wherever possible

## MY CURRENT RESUME

${{RESUME_TEMPLATE}}

## FULL WORK HISTORY (additional bullets to draw from)

${{WORK_HISTORY_JSON}}

## JOB DESCRIPTION

${{jdSection}}`;
    }}

    // Auto-fill and generate when launched from a job card
    const storedJob = sessionStorage.getItem('resumeJob');
    if (storedJob) {{
        sessionStorage.removeItem('resumeJob');
        const job = JSON.parse(storedJob);
        if (job.title) document.getElementById('job-title').value = job.title;
        if (job.company) document.getElementById('job-company').value = job.company;
        if (job.description) document.getElementById('jd-input').value = job.description;
        generatePrompt(true);
    }}
    </script>
</body>
</html>
"""


def generate_resume_html():
    resume_template = RESUME_TEMPLATE_FILE.read_text()
    work_history = WORK_HISTORY_FILE.read_text()  # raw JSON string

    # json.dumps encodes both as safe JS string literals (handles quotes, newlines, etc.)
    resume_template_js = json.dumps(resume_template)
    work_history_js = json.dumps(work_history)

    page = RESUME_PAGE_TEMPLATE.format(
        resume_template_js=resume_template_js,
        work_history_js=work_history_js,
    )
    RESUME_OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    RESUME_OUTPUT_FILE.write_text(page)
    print(f"Generated {RESUME_OUTPUT_FILE}")


if __name__ == "__main__":
    generate_html()
