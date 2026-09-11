#!/usr/bin/env python3
"""Render public GitHub data as self-contained SVGs; standard library only."""
import argparse
from collections import Counter
from datetime import datetime, timezone
from html import escape
import json
import os
from pathlib import Path
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
USER = 'ak74aytg'
QUERY = '''query { user(login:"ak74aytg") { contributionsCollection {
 contributionCalendar { totalContributions weeks { contributionDays { contributionCount date } } }
 totalCommitContributions totalPullRequestContributions totalIssueContributions totalPullRequestReviewContributions
} } }'''


def api(path, body=None):
    token = os.environ.get('GH_TOKEN') or os.environ.get('GITHUB_TOKEN')
    if not token:
        raise RuntimeError('Set GH_TOKEN or GITHUB_TOKEN to fetch GitHub data.')
    request = urllib.request.Request('https://api.github.com/' + path,
        data=json.dumps(body).encode() if body else None,
        headers={'Authorization': 'Bearer ' + token, 'Accept': 'application/vnd.github+json',
                 'Content-Type': 'application/json', 'User-Agent': 'ak74aytg-profile-stats'})
    with urllib.request.urlopen(request, timeout=45) as response:
        data = json.load(response)
    if isinstance(data, dict) and data.get('errors'):
        raise RuntimeError(str(data['errors']))
    return data


def txt(x, y, value, size=14, color='#9baec8', weight=400):
    return f'<text x="{x}" y="{y}" fill="{color}" font-size="{size}" font-weight="{weight}">{escape(str(value))}</text>'


def svg(height, title, content):
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="854" height="{height}" viewBox="0 0 854 {height}" role="img" aria-label="{escape(title)}">
<title>{escape(title)}</title><rect width="854" height="{height}" rx="18" fill="#0d1117"/>
<g font-family="-apple-system,BlinkMacSystemFont,Segoe UI,Arial,sans-serif">{content}</g></svg>'''


def render(repos, contributions):
    c = contributions['data']['user']['contributionsCollection']
    calendar = c['contributionCalendar']
    stamp = datetime.now(timezone.utc).strftime('%Y-%m-%d')
    counts = Counter(r['language'] for r in repos if r['language'])
    colors = {'JavaScript': '#f1e05a', 'Java': '#b07219', 'HTML': '#e34c26',
              'CSS': '#b392f0', 'Python': '#58a6ff', 'TypeScript': '#64ffda'}
    s = txt(30, 36, 'THE REPOSITORY MIX', 13, '#64ffda', 700)
    for x, number, label in [(30,len(repos),'public repositories'),
            (310,len(counts),'primary languages'), (590,sum(not r['fork'] for r in repos),'non-fork repositories')]:
        s += txt(x,88,number,38,'#e6edf3',700) + txt(x,114,label,13)
    for i,(lang,count) in enumerate(counts.most_common()):
        col,row = i%2,i//2; x=30+col*420; y=157+row*44
        s += txt(x,y,lang,13,'#e6edf3') + txt(x+345,y,count,13,'#e6edf3',700)
        s += f'<rect x="{x}" y="{y+9}" width="365" height="6" rx="3" fill="#21262d"/>'
        s += f'<rect x="{x}" y="{y+9}" width="{365*count/len(repos):.2f}" height="6" rx="3" fill="{colors.get(lang,"#9baec8")}"/>'
    missing = sum(r['language'] is None for r in repos)
    s += txt(30,289,f'One primary language per repo · {missing} without a detected language · Updated {stamp} UTC',12)
    stats = svg(312,'Public repository counts by primary language',s)
    weeks = calendar['weeks']; days=[d for w in weeks for d in w['contributionDays']]
    a=txt(30,36,'A YEAR OF SHOWING UP',13,'#64ffda',700)
    active=sum(d['contributionCount']>0 for d in days)
    peak=max(d['contributionCount'] for d in days)
    for x,number,label in [(30,calendar['totalContributions'],'contributions'),(310,active,'active days'),(590,peak,'most contributions in a day')]:
        a+=txt(x,87,number,38,'#e6edf3',700)+txt(x,112,label,13)
    last_month=None
    for wi,w in enumerate(weeks):
        for d in w['contributionDays']:
            date=datetime.strptime(d['date'],'%Y-%m-%d'); di=(date.weekday()+1)%7
            x=30+wi*15; y=150+di*15;n=d['contributionCount']
            color='#21262d' if n==0 else '#16483f' if n<=2 else '#237c67' if n<=5 else '#39b890' if n<=9 else '#64ffda'
            a+=f'<rect x="{x}" y="{y}" width="11" height="11" rx="2" fill="{color}"><title>{d["date"]}: {n} contributions</title></rect>'
            if date.day<=7 and date.month!=last_month:
                a+=txt(x,140,date.strftime('%b'),10);last_month=date.month
    a+=txt(30,279,f'{days[0]["date"]} → {days[-1]["date"]} · Public GitHub contribution data',12)
    a+=txt(30,302,f'Updated {stamp} UTC · Contributions include more than commits.',12)
    activity=svg(326,'GitHub contributions over the last year',a)
    out=ROOT/'assets';out.mkdir(exist_ok=True)
    # Both documents are built before writing; a failed API fetch preserves existing assets.
    for name,body in [('stats.svg',stats),('activity.svg',activity)]:
        (out/name).write_text(body+'\n')
    print(f'Rendered {len(repos)} repositories and {calendar["totalContributions"]} contributions.')


if __name__ == '__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--from-review',action='store_true');args=parser.parse_args()
    if args.from_review:
        repos=json.loads((ROOT/'review/repositories.json').read_text())
        contributions=json.loads((ROOT/'review/contributions.json').read_text())
    else:
        repos=[];page=1
        while True:
            batch=api(f'users/{USER}/repos?per_page=100&page={page}')
            repos.extend(batch)
            if len(batch)<100:break
            page+=1
        contributions=api('graphql',{'query':QUERY})
    render(repos,contributions)
