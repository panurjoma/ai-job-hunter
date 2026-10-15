"""CLI for ChatGPT-produced JSON inbox handoff and CV rendering."""
import argparse
from pathlib import Path
from .pipeline import run


def main():
    parser = argparse.ArgumentParser(description="Process structured job JSON into scored results and CVs")
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=Path("output"))
    parser.add_argument("--criteria", type=Path, default=Path("config/search_criteria.yaml"))
    parser.add_argument("--template", type=Path, default=Path("templates/master_cv_reference.html"))
    parser.add_argument("--pdf", action="store_true", help="Render PDF via Playwright Chromium")
    args = parser.parse_args()
    result = run(args.input, args.output, args.criteria, args.template, args.pdf)
    print(f"Processed {result['total']} records, {result['unique']} unique, "
          f"{result['shortlisted']} shortlisted")


if __name__ == "__main__":
    main()
