#!/usr/bin/env python3
"""Maintain _data/publications.yml for the lab website.

The YAML file is the single source of truth for the publication lists on the
project pages and the publications page. Some metadata is refreshed
automatically; title, authors, year, venue, DOI, and URL are preserved for
known entries.

Sub-commands
------------
sync     Fetch works linked to an ORCID iD from OpenAlex, update metadata of
         known entries, and append new entries (marked ``needs_review``).
check    Validate the file: every visible entry must belong to at least one
         known project. Exits non-zero on failure (used in CI).
compare  Compare a BibTeX export from Google Scholar against the file and list
         Scholar entries that the website does not include.

Fields that ``sync`` refreshes for known entries:
    oa_url, type, openalex
Fields populated from OpenAlex for new entries and preserved afterwards:
    title, authors, year, venue, doi, url
Fields that people own and ``sync`` never modifies:
    projects, featured, hidden, needs_review (sync only sets it on new entries),
    note, and any other field not listed above.
Entries are never deleted by ``sync``; to suppress one (e.g. a preprint that
has since been published), set ``hidden: true``.
"""

from __future__ import annotations

import argparse
import html
import json
import os
import re
import sys
import time
import unicodedata
import urllib.parse
import urllib.request
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
PUBS_PATH = ROOT / "_data" / "publications.yml"
PROJECTS_DIR = ROOT / "_projects"
AUTHORS_PATH = ROOT / "_data" / "authors.yml"
COAUTHORS_PATH = ROOT / "_data" / "coauthors.yml"

# Project slugs that are valid in ``projects`` but have no project page.
EXTRA_PROJECT_SLUGS = {"other"}

SYNC_FIELDS = ["oa_url", "type", "openalex"]
PRESERVED_FIELDS = ["title", "authors", "year", "venue", "doi", "url"]
FIELD_ORDER = [
    "id", "title", "authors", "year", "venue", "doi", "url", "oa_url", "type",
    "openalex", "kind", "projects", "featured", "hidden", "needs_review", "note",
    "description", "award", "pdf",
]

# Papers from this year or earlier are not listed.
MAX_EXCLUDED_YEAR = 2015

KINDS = ("journal", "conference", "workshop", "chapter", "preprint", "poster", "other")
PREPRINT_VENUES = re.compile(r"arxiv|biorxiv|osf|zenodo|peerj preprints|ssrn|research square", re.I)


def guess_kind(pub: dict) -> str:
    """Venue category used for the icon; hand-edit ``kind`` to override."""
    venue = pub.get("venue") or ""
    kind = pub.get("type") or ""
    if kind == "preprint" or PREPRINT_VENUES.search(venue):
        return "preprint"
    if kind == "book-chapter":
        return "chapter"
    if re.search(r"workshop", venue, re.I):
        return "workshop"
    if kind in ("article", "software-paper", "book-review") and not re.search(r"conference|symposium", venue, re.I):
        return "journal"
    return "conference"

HEADER = """\
# Publications shown on the website.
#
# Maintained partly by scripts/publications.py (see README section
# "Publications"). New entries are initialized from OpenAlex. For known entries,
# sync refreshes oa_url, type, and openalex, while preserving title, authors,
# year, venue, doi, and url.
# Everything else is edited by hand and is never overwritten:
#   projects:     list of project slugs (file names in _projects/), or "other"
#   featured:     true to list the paper under "Key publications" on its project page
#   hidden:       true to omit the entry (e.g. a preprint superseded by the published version)
#   needs_review: set on newly discovered entries; delete it once projects are confirmed
#   note:         free text shown after the citation
#   kind:         journal | conference | workshop | chapter | preprint | poster | other (venue icon; guessed if unset)
#   description:  informal summary shown as a tooltip on the title
#   award:        text such as "Best paper award"; shows a trophy next to the title
#   pdf:          path under assets/pdfs/ of a hosted PDF (overrides the default <slug>.pdf)
"""


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #

def normalize_title(title: str) -> str:
    """Lower-case, strip accents, markup and punctuation, collapse whitespace."""
    title = html.unescape(re.sub(r"<[^>]+>", "", title or ""))
    title = unicodedata.normalize("NFKD", title)
    title = "".join(ch for ch in title if not unicodedata.combining(ch))  # drop accents
    title = re.sub(r"[^a-z0-9]+", " ", title.lower())  # punctuation, dashes -> space
    return re.sub(r"\s+", " ", title).strip()


def normalize_doi(doi: str | None) -> str | None:
    if not doi:
        return None
    doi = doi.strip().lower()
    doi = re.sub(r"^(https?://)?(dx\.)?doi\.org/", "", doi)
    return doi or None


def make_id(doi: str | None, title: str) -> str:
    if doi:
        return f"doi:{doi}"
    return "title:" + normalize_title(title).replace(" ", "-")[:80]


def load_front_matter(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    match = re.match(r"^---\s*\n(.*?)\n---\s*\n", text, re.S)
    return yaml.safe_load(match.group(1)) if match else {}


def load_projects() -> dict[str, dict]:
    projects = {}
    for path in sorted(PROJECTS_DIR.glob("*.md")):
        projects[path.stem] = load_front_matter(path) or {}
    return projects


def load_pubs(path: Path = PUBS_PATH) -> list[dict]:
    if not path.exists():
        return []
    return yaml.safe_load(path.read_text(encoding="utf-8")) or []


def sort_key(pub: dict):
    return (-(pub.get("year") or 0), normalize_title(pub.get("title", "")))


def dump_pubs(pubs: list[dict], path: Path = PUBS_PATH) -> None:
    ordered = []
    for pub in sorted(pubs, key=sort_key):
        entry = {k: pub[k] for k in FIELD_ORDER if k in pub and pub[k] not in (None, "", False)}
        entry.update({k: v for k, v in pub.items() if k not in FIELD_ORDER})
        entry.setdefault("projects", [])
        ordered.append(entry)
    body = yaml.safe_dump(ordered, sort_keys=False, allow_unicode=True, width=1000)
    # Blank line between entries for readability.
    body = re.sub(r"\n- id:", "\n\n- id:", body)
    path.write_text(HEADER + "\n" + body, encoding="utf-8")


def lab_member_keys() -> set[str]:
    """(last name, first initial) for everyone listed in _data/authors.yml."""
    keys = set()
    if AUTHORS_PATH.exists():
        for person in yaml.safe_load(AUTHORS_PATH.read_text(encoding="utf-8")) or []:
            key = name_key(str(person.get("name", "")))
            if key:
                keys.add(key)
    return keys


def name_key(name: str) -> tuple[str, str] | None:
    parts = normalize_title(name).split()
    if len(parts) < 2:
        return None
    return parts[-1], parts[0][0]


def suggest_projects(pub: dict, projects: dict[str, dict]) -> list[str]:
    haystack = f"{pub.get('title', '')} {pub.get('venue', '')}"
    hits = []
    for slug, meta in projects.items():
        for pattern in meta.get("match_keywords") or []:
            if re.search(pattern, haystack, re.I):
                hits.append(slug)
                break
    return hits


# --------------------------------------------------------------------------- #
# OpenAlex
# --------------------------------------------------------------------------- #

OPENALEX = "https://api.openalex.org/works"
SELECT = "id,doi,display_name,publication_year,type,authorships,primary_location,open_access"


def fetch_openalex(orcid: str, api_key: str | None, mailto: str | None) -> list[dict]:
    works, cursor = [], "*"
    while cursor:
        params = {
            "filter": f"author.orcid:{orcid}",
            "per-page": "200",
            "cursor": cursor,
            "select": SELECT,
        }
        if api_key:
            params["api_key"] = api_key
        if mailto:
            params["mailto"] = mailto
        url = f"{OPENALEX}?{urllib.parse.urlencode(params)}"
        request = urllib.request.Request(url, headers={"User-Agent": "lab-website-publication-sync"})
        with urllib.request.urlopen(request, timeout=60) as response:
            payload = json.load(response)
        works.extend(payload.get("results", []))
        cursor = payload.get("meta", {}).get("next_cursor")
        if not payload.get("results"):
            break
        time.sleep(0.2)
    return works


def convert_work(work: dict, lab_keys: set[str]) -> dict:
    doi = normalize_doi(work.get("doi"))
    title = html.unescape(re.sub(r"<[^>]+>", "", work.get("display_name") or "")).strip()
    location = work.get("primary_location") or {}
    source = location.get("source") or {}
    authors = []
    for authorship in work.get("authorships") or []:
        name = (authorship.get("author") or {}).get("display_name") or authorship.get("raw_author_name")
        if name:
            entry = {"name": name}
            if name_key(name) in lab_keys:
                entry["lab"] = True
            authors.append(entry)
    return {
        "title": title,
        "authors": authors,
        "year": work.get("publication_year"),
        "venue": source.get("display_name"),
        "doi": doi,
        "url": f"https://doi.org/{doi}" if doi else location.get("landing_page_url"),
        "oa_url": (work.get("open_access") or {}).get("oa_url"),
        "type": work.get("type"),
        "openalex": (work.get("id") or "").rsplit("/", 1)[-1] or None,
    }


def cmd_sync(args) -> int:
    projects = load_projects()
    pubs = load_pubs()
    lab_keys = lab_member_keys()
    api_key = os.environ.get("OPENALEX_API_KEY")
    works = fetch_openalex(args.orcid, api_key, args.mailto)

    by_doi = {normalize_doi(p.get("doi")): p for p in pubs if p.get("doi")}
    by_openalex = {p["openalex"]: p for p in pubs if p.get("openalex")}
    by_title = {normalize_title(p.get("title", "")): p for p in pubs}

    added, updated, mismatches = [], [], []
    for work in works:
        fresh = convert_work(work, lab_keys)
        if not fresh["title"] or (fresh["year"] or 0) <= MAX_EXCLUDED_YEAR:
            continue
        existing = (
            by_openalex.get(fresh["openalex"])
            or (by_doi.get(fresh["doi"]) if fresh["doi"] else None)
        )
        if existing is None:
            # Fall back to the title only for hand-entered records without
            # identifiers; otherwise a preprint and its published version
            # (same title, different DOIs) would overwrite each other.
            candidate = by_title.get(normalize_title(fresh["title"]))
            if candidate is not None and not candidate.get("doi") and not candidate.get("openalex"):
                existing = candidate
        if existing is not None:
            differing_fields = [
                key for key in PRESERVED_FIELDS
                if fresh.get(key) not in (None, "", []) and existing.get(key) != fresh[key]
            ]
            if differing_fields:
                mismatches.append((existing, differing_fields))
            before = {k: existing.get(k) for k in SYNC_FIELDS}
            for key in SYNC_FIELDS:
                # Keep a hand-entered value when OpenAlex has none.
                if fresh.get(key) not in (None, "", []):
                    existing[key] = fresh[key]
            if not existing.get("id"):
                existing["id"] = make_id(existing.get("doi"), existing["title"])
            existing.setdefault("kind", guess_kind(existing))
            if before != {k: existing.get(k) for k in SYNC_FIELDS}:
                updated.append(existing)
        else:
            new = {"id": make_id(fresh["doi"], fresh["title"]), **fresh}
            new["kind"] = guess_kind(new)
            new["projects"] = suggest_projects(new, projects)
            new["needs_review"] = True
            pubs.append(new)
            by_title[normalize_title(new["title"])] = new
            if new["doi"]:
                by_doi[new["doi"]] = new
            added.append(new)

    dump_pubs(pubs)
    report = build_report(added, updated, mismatches, pubs, len(works))
    print(report)
    if args.report:
        Path(args.report).write_text(report, encoding="utf-8")
    return 0


def build_report(added, updated, mismatches, pubs, n_works) -> str:
    lines = [f"OpenAlex returned {n_works} works. {len(added)} new, {len(updated)} updated.", ""]
    if added:
        lines += ["### New publications (please confirm projects, then delete `needs_review`)", ""]
        for pub in sorted(added, key=sort_key):
            projects = ", ".join(pub["projects"]) or "**none suggested**"
            lines.append(f"- {pub.get('year')} — {pub['title']} ({pub.get('venue') or 'no venue'}) → {projects}")
        lines.append("")
    if mismatches:
        lines += ["### Possible metadata mismatches (protected fields differ from OpenAlex)", ""]
        for pub, fields in mismatches:
            lines.append(f"- {pub.get('title') or pub.get('id')}: {', '.join(f'`{field}`' for field in fields)}")
        lines.append("")
    groups: dict[str, list[dict]] = {}
    for pub in pubs:
        if not pub.get("hidden"):
            groups.setdefault(normalize_title(pub.get("title", "")), []).append(pub)
    dupes = [g for g in groups.values() if len(g) > 1]
    if dupes:
        lines += ["### Possible duplicates (e.g. preprint and published version)", ""]
        for group in dupes:
            lines.append("- " + "; ".join(f"{p.get('venue')} {p.get('year')} ({p.get('doi')})" for p in group)
                         + f": *{group[0]['title']}* — consider `hidden: true` on one")
        lines.append("")
    return "\n".join(lines)


def cmd_coauthors(args) -> int:
    """Add non-lab authors missing from _data/coauthors.yml (url left blank)."""
    existing = {}
    if COAUTHORS_PATH.exists():
        existing = yaml.safe_load(COAUTHORS_PATH.read_text(encoding="utf-8")) or {}
    names = {a["name"] for pub in load_pubs() for a in pub.get("authors") or [] if not a.get("lab")}
    added = sorted(names - set(existing))
    for name in added:
        existing[name] = ""
    header = "# Personal websites of non-lab coauthors: exact author name -> URL.\n# Names with a blank URL are listed unlinked. Add new names with `publications.py coauthors`.\n"
    body = yaml.safe_dump(dict(sorted(existing.items(), key=lambda kv: kv[0].lower())), allow_unicode=True, width=1000, sort_keys=False)
    COAUTHORS_PATH.write_text(header + body, encoding="utf-8")
    print(f"{len(added)} names added; {sum(1 for v in existing.values() if not v)} still without a URL.")
    return 0


# --------------------------------------------------------------------------- #
# PDF hosting
# --------------------------------------------------------------------------- #

PDF_DIR = ROOT / "assets" / "pdfs"


def pdf_candidates(pub: dict) -> list[str]:
    urls = []
    if pub.get("openalex"):
        api = f"{OPENALEX}/{pub['openalex']}?select=locations,best_oa_location"
        try:
            request = urllib.request.Request(api, headers={"User-Agent": "lab-website-publication-sync"})
            with urllib.request.urlopen(request, timeout=60) as response:
                work = json.load(response)
            locations = [work.get("best_oa_location")] + (work.get("locations") or [])
            urls += [loc["pdf_url"] for loc in locations if loc and loc.get("pdf_url")]
        except Exception as exc:  # network or API error; fall back to oa_url
            print(f"  openalex lookup failed: {exc}")
    if pub.get("oa_url"):
        urls.append(pub["oa_url"])
    return list(dict.fromkeys(urls))


def cmd_pdfs(args) -> int:
    """Download open-access PDFs into assets/pdfs/ and record them in the YAML."""
    pubs = load_pubs()
    PDF_DIR.mkdir(parents=True, exist_ok=True)
    missing = []
    for pub in pubs:
        if pub.get("hidden") or pub.get("pdf"):
            continue
        slug = re.sub(r"[^a-z0-9]+", "-", re.sub(r"^\w+:", "", pub["id"]).lower()).strip("-")
        target = PDF_DIR / f"{slug}.pdf"
        if not target.exists():
            for url in pdf_candidates(pub):
                try:
                    request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 lab-website"})
                    with urllib.request.urlopen(request, timeout=60) as response:
                        data = response.read()
                except Exception:
                    continue
                if data[:5] == b"%PDF-":
                    target.write_bytes(data)
                    break
        if target.exists():
            pub["pdf"] = f"/assets/pdfs/{target.name}"
        else:
            missing.append(pub)
        time.sleep(0.3)
    dump_pubs(pubs)
    print(f"{len(missing)} publications still need a PDF (add it to assets/pdfs/ and set `pdf:`):")
    for pub in sorted(missing, key=sort_key):
        print(f"  - {pub.get('year')} {pub['title']}")
    return 0


# --------------------------------------------------------------------------- #
# Validation
# --------------------------------------------------------------------------- #

def cmd_check(args) -> int:
    valid = set(load_projects()) | EXTRA_PROJECT_SLUGS
    problems, pending = [], 0
    seen_ids = set()
    for pub in load_pubs():
        label = f"{pub.get('year')} {pub.get('title', '<no title>')}"
        if pub.get("id") in seen_ids:
            problems.append(f"duplicate id {pub.get('id')}: {label}")
        seen_ids.add(pub.get("id"))
        unknown = [p for p in pub.get("projects") or [] if p not in valid]
        if unknown:
            problems.append(f"unknown project(s) {unknown}: {label}")
        if not pub.get("hidden") and not pub.get("projects"):
            problems.append(f"no project assigned: {label}")
        if pub.get("needs_review"):
            pending += 1
    for problem in problems:
        print(f"ERROR: {problem}")
    if pending:
        print(f"note: {pending} entries still marked needs_review")
    print("OK" if not problems else f"{len(problems)} problem(s)")
    return 1 if problems else 0


# --------------------------------------------------------------------------- #
# Google Scholar comparison
# --------------------------------------------------------------------------- #

def bibtex_titles(text: str) -> list[str]:
    titles = []
    for match in re.finditer(r"\btitle\s*=\s*[{\"]", text, re.I):
        start, depth, i = match.end(), 1, match.end()
        closing = "}" if text[match.end() - 1] == "{" else '"'
        while i < len(text) and depth:
            ch = text[i]
            if closing == "}":
                depth += {"{": 1, "}": -1}.get(ch, 0)
            elif ch == '"':
                depth = 0
            i += 1
        titles.append(re.sub(r"[{}]", "", text[start:i - 1]))
    return titles


def cmd_compare(args) -> int:
    site = {normalize_title(p.get("title", "")) for p in load_pubs()}
    missing = [t for t in bibtex_titles(Path(args.bibtex).read_text(encoding="utf-8"))
               if normalize_title(t) not in site]
    print(f"{len(missing)} Scholar entries not found on the website:")
    for title in missing:
        print(f"  - {title}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    sync = sub.add_parser("sync", help="update from OpenAlex")
    sync.add_argument("--orcid", required=True)
    sync.add_argument("--mailto", help="contact address sent to OpenAlex")
    sync.add_argument("--report", help="write a Markdown summary to this path")
    sync.set_defaults(func=cmd_sync)
    coauthors = sub.add_parser("coauthors", help="list new coauthors in _data/coauthors.yml")
    coauthors.set_defaults(func=cmd_coauthors)
    pdfs = sub.add_parser("pdfs", help="download open-access PDFs to assets/pdfs/")
    pdfs.set_defaults(func=cmd_pdfs)
    check = sub.add_parser("check", help="validate project assignments")
    check.set_defaults(func=cmd_check)
    compare = sub.add_parser("compare", help="compare with a Google Scholar BibTeX export")
    compare.add_argument("bibtex")
    compare.set_defaults(func=cmd_compare)
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
