import json
from datetime import datetime, timezone
from pathlib import Path

import requests
import yaml


def discover():
    config = yaml.safe_load(Path("config/sources.yaml").read_text())["sources"]
    jobs = []
    session = requests.Session()
    session.headers.update({"User-Agent": "ai-job-hunter/0.1 (personal job discovery)"})
    if config.get("remotive", {}).get("enabled"):
        response = session.get(config["remotive"]["endpoint"], timeout=30)
        response.raise_for_status()
        for item in response.json().get("jobs", []):
            jobs.append({
                "source": "remotive",
                "id": item.get("id"),
                "title": item.get("title"),
                "company": item.get("company_name"),
                "url": item.get("url"),
                "candidate_location": item.get("candidate_required_location"),
                "salary": item.get("salary"),
                "description": item.get("description"),
            })
    return jobs


def main():
    jobs = discover()
    out = Path("output")
    out.mkdir(exist_ok=True)
    (out / "raw_jobs.json").write_text(json.dumps({
        "collected_at": datetime.now(timezone.utc).isoformat(),
        "jobs": jobs,
        "status": "unfiltered; matching and CV generation pending",
    }, indent=2))
    print(f"Collected {len(jobs)} raw job listings; not yet ranked or filtered.")


if __name__ == "__main__":
    main()
