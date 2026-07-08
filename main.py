from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
import json
import sys
import time
from typing import Dict, Set, List
import xml.etree.ElementTree as ETree
from sentence_transformers import SentenceTransformer
from unidecode import unidecode
import requests
import csv
from argparse import ArgumentParser
from pathlib import Path
import pandas as pd

from encoder import ExpertiseMatcher

import logging
logger = logging.getLogger(__name__)

DBLP_INFO_FIELDS = [
    "url",
    "experience",
    "is_dblp_valid",
    "pid",
    "last_fetched",
    "is_disambiguation",
]

DBLP_EXPERTISE_FIELDS = ["dblp", "expertise", "auto_filled"]
COAUTHOR_FIELDS = ["pid1", "pid2", "count"]


class RateLimitError(Exception):
    def __init__(self, retry_after):
        self.retry_after = int(retry_after)
        Exception.__init__(
            self, f"DBLP rate limit exceeded, retry after: {retry_after} minutes"
        )


@dataclass
class AuthorDBLPResult:
    person_name: str
    person_pid: str
    cauthor_history: Dict[str, Dict[int, int]]
    publication_years: Set[int]
    publication_titles: List[str]
    is_disambiguation_page: bool = False


def rate_limited_get(url: str, max_retries: int | None = 3) -> requests.Response:
    retries = 0
    resp = None
    while retries < max_retries:
        resp = requests.get(url)
        if resp.status_code == 429:
            retry_after = resp.headers.get("Retry-After", 5)
            raise RateLimitError(retry_after)
        elif resp.status_code == 200:
            return resp
        retries += 1
    return resp


def xmlifyAdd(add: str):
    if add.endswith(".html"):  # if the URL format contains .html
        xml_add = add.replace(".html", ".xml")
        loc = xml_add.find("pers/")  # old URL
        if loc > 0:
            loc = loc + len("pers/")
            xml_add = xml_add[:loc] + "xx/" + xml_add[loc:]
    else:  # old URL
        xml_add = add.replace("hd", "xx")
        xml_add = xml_add + ".xml"
    return xml_add


def connectToDBLPPage(add):
    my_file = ""
    resp = rate_limited_get(add)
    if resp.status_code == 200:
        my_file = resp.text
    return my_file


def readAuthorDBLP(xml_file):
    """
    Args:
        xml_file: xml data extracted from a DBLP person page

    Returns:
        AuthorDBLPResult: structured author data
    """
    cauthor_hist_dict = defaultdict(lambda: defaultdict(int))
    temp_author_set = set()
    year_set = set()

    root = ETree.fromstring(xml_file)
    records = root.findall(".//r")  # Extract all r elements in DBLP
    person_file_name = (root.attrib["name"]).lower()  # Get name of the author in DBLP
    person_pid = root.attrib["pid"]
    person_file_name = unidecode(person_file_name)
    logger.info(f"found pid={person_file_name}")

    author = root.find(".//person")
    if author is None:
        raise f"XML content for {person_file_name} is missing!"

    if author.attrib.get("publtype") == "disambiguation":
        logger.warning("This is a disambiguation page")
        return AuthorDBLPResult(
            person_name=person_file_name,
            person_pid=person_pid,
            cauthor_history=cauthor_hist_dict,
            publication_years=year_set,
            publication_titles=[],
            is_disambiguation_page=True,
        )

    titles = []
    for record in records:
        papers = list(record)
        for paper in papers:
            year_tag = None
            info = list(paper)
            for item in info:
                if item.tag == "author" and item.attrib["pid"] != person_pid:
                    coauthor_pid = item.attrib["pid"]
                    temp_author_set.add(coauthor_pid)
                if item.tag == "year":
                    year_tag = int(item.text)
                if item.tag == "title" and item.text is not None:
                    titles.append(item.text)
            if year_tag:
                year_set.add(year_tag)
                for author in temp_author_set:
                    cauthor_hist_dict[author][year_tag] += 1
            temp_author_set.clear()
    logger.info(f"Sample of papers: {titles[:2]}")
    return AuthorDBLPResult(
        person_name=person_file_name,
        person_pid=person_pid,
        cauthor_history=cauthor_hist_dict,
        publication_years=year_set,
        publication_titles=titles,
        is_disambiguation_page=False,
    )


def process_dblp(url, matcher: ExpertiseMatcher, dblp_csv: str, dblp_expertise_csv: str, dblp_coauthor_csv: str, matching_min_cosine_similarity: float):
    logger.info(f'fetching dblp {url}')
    dblp_url = xmlifyAdd(url)
    logger.info(f"fetching dblp xml {dblp_url}")
    dblp_xml = connectToDBLPPage(dblp_url)

    ok = True
    if not dblp_xml:
        logger.warning(f"dblp {dblp_url} invalid")
        ok = False

    try:
        author_result = readAuthorDBLP(dblp_xml)
    except Exception as e:
        logger.error(f'Error parsing xml from {url}: {e}')
        ok = False

    now = datetime.now()

    if not ok:
        logger.info(f"{url} is invalid, writing to csv and exiting")
        with open(dblp_csv, mode='a', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, DBLP_INFO_FIELDS)
            writer.writerow(
                {
                    "url": url,
                    "experience": None,
                    "is_dblp_valid": False,
                    "pid": None,
                    "last_fetched": now,
                    "is_disambiguation": None,
                }
            )
        return

    if author_result.is_disambiguation_page:
        with open(dblp_csv, mode="a", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, DBLP_INFO_FIELDS)
            writer.writerow(
                {
                    "url": url,
                    "experience": None,
                    "is_dblp_valid": True,
                    "pid": None,
                    "last_fetched": now,
                    "is_disambiguation": True,
                }
            )
        return

    experience = (
        now.year - min(author_result.publication_years)
        if author_result.publication_years
        else 0
    )

    with open(dblp_coauthor_csv, mode='a', newline='', encoding='utf-8') as f:
        logger.info(f"{url}: writing coauthors")
        writer = csv.DictWriter(f, COAUTHOR_FIELDS)
        writer.writerows(
            [
                {
                    "pid1": min(author_result.person_pid, pid2),
                    "pid2": max(author_result.person_pid, pid2),
                    "count": sum(hist.values()),
                }
                for pid2, hist in author_result.cauthor_history.items()
                if pid2 != author_result.person_pid
            ]
        )

    with open(dblp_csv, mode='a', newline='', encoding='utf-8') as f:
        logger.info(f"{url}: writing dblp_info")
        writer = csv.DictWriter(f, DBLP_INFO_FIELDS)
        writer.writerow(
            {
                "url": url,
                "experience": int(experience),
                "is_dblp_valid": not author_result.is_disambiguation_page,
                "pid": author_result.person_pid,
                "last_fetched": now,
                "is_disambiguation": author_result.is_disambiguation_page,
            }
        )

    logger.info(f"{url}: calculating title embeddings")
    title_embeddings = matcher.encode(author_result.publication_titles)
    logger.info(f"{url}: found {len(title_embeddings)} titles, calculating clusters")
    cluster_avg = matcher.cluster(title_embeddings)
    logger.info(f"{url}: {len(cluster_avg)} clusters found, calculating matches")
    results = matcher.find_matches(cluster_avg, matching_min_cosine_similarity)
    valid_exps = set([i for i in results if i is not None])

    with open(dblp_expertise_csv, mode='a', encoding='utf-8') as f:
        logger.info(f"{url}: writing to dblp_expertise, total {len(valid_exps)}")
        writer = csv.DictWriter(f, DBLP_EXPERTISE_FIELDS)
        writer.writerows(
            [
                {"dblp": url, "expertise": exp, "auto_filled": True}
                for exp in valid_exps
            ]
        )

class Parser(ArgumentParser):
    def error(self, message):
        sys.stderr.write(f"Error: {message}\n\n")
        self.print_help()
        sys.exit(2)

def define_args():
    parser = Parser()
    parser.add_argument(
        "-o",
        "--outDir",
        dest="outDir",
        help="directory for all output files",
        type=str,
    )
    parser.add_argument(
        "-i",
        "--input",
        dest="input",
        help="CSV file containing a list of DBLP URLs to read",
        type=str,
    )
    parser.add_argument(
        "-c",
        "--dblpCol",
        dest="dblpCol",
        help="column inside the input file in -i that contains the URLs",
        type=str,
    )
    parser.add_argument(
        "-s",
        "--minSimilarity",
        dest="minSimilarity",
        help="Minimum similarity to match areas of expertise from DBLP pages to existing areas in -e",
        type=float,
        default=0.6,
    )
    parser.add_argument(
        "--resume",
        dest="resume",
        type=str,
        help="Resume from a previous run",
    )
    return parser

if __name__ == '__main__':
    parser = define_args()
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, filename="crawling.log")

    # check required arguments
    starting_row = 0
    if args.resume is None:
        missing = [f"--{k}" for k, v in vars(args).items() if v is None and k != 'resume']

        if missing:
            parser.error("the following arguments are required: " + ", ".join(missing))

    directory = None
    dblp_info_csv = None
    dblp_expertise_csv = None
    coauthor_csv = None
    min_similarity = None,
    input_file = None
    dblp_col = None

    if args.resume is None:
        directory = Path(args.outDir)
        if not directory.is_dir():
            raise FileNotFoundError(f"Directory {args.outDir} does not exist")

        input_file = args.input
        dblp_csv = Path(input_file)

        assert dblp_csv.is_file(), f"{input_file} does not exist."
        assert dblp_csv.suffix.lower() == '.csv', f"{dblp_csv} is not a CSV file."

        with dblp_csv.open(newline="", encoding="utf-8") as f:
            reader = csv.reader(f)
            headers = next(reader, None)

        assert headers is not None, f"{input_file} is empty."

        dblp_col = args.dblpCol
        assert dblp_col in headers, f"{dblp_col} not found in file {input_file}"

        # create output files
        logger.info("creating output files")
        dblp_info_csv = directory / 'dblp_info.csv'
        dblp_expertise_csv = directory / 'dblp_expertise.csv'
        coauthor_csv = directory / 'coauthors.csv'
        expertise_csv = directory / "expertise.csv"
        if not dblp_info_csv.exists():
            with dblp_info_csv.open("w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(DBLP_INFO_FIELDS)
        if not dblp_expertise_csv.exists():
            with dblp_expertise_csv.open("w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(DBLP_EXPERTISE_FIELDS)
        if not coauthor_csv.exists():
            with coauthor_csv.open("w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(COAUTHOR_FIELDS)

        logger.info("loading model")
        model = SentenceTransformer("all-mpnet-base-v2")
        matcher = ExpertiseMatcher(model, expertise_csv)

        min_similarity = args.minSimilarity
    else:
        with open(args.resume, encoding='utf-8') as f:
            prev = json.load(f)
            starting_row = prev['next_index']
            min_similarity = prev['min_similarity']
            directory = Path(prev['out_dir'])
            input_file = prev['input']
            dblp_col = prev['dblp_col']
            logger.info(f"resuming from row {starting_row}")

        dblp_info_csv = directory / "dblp_info.csv"
        dblp_expertise_csv = directory / "dblp_expertise.csv"
        coauthor_csv = directory / "coauthors.csv"

        logger.info("loading model")
        model = SentenceTransformer("all-mpnet-base-v2")
        matcher = ExpertiseMatcher(model, directory / "expertise.csv")

    logger.info(f"start fetching from {starting_row}")
    with open(input_file, newline="", encoding='utf-8') as f:
        reader = csv.DictReader(f)

        for idx, row in enumerate(reader):
            if idx < starting_row:
                continue

            url = row[dblp_col]
            try:
                process_dblp(
                    url,
                    matcher,
                    dblp_info_csv,
                    dblp_expertise_csv,
                    coauthor_csv,
                    min_similarity,
                )
                # reduce the chance of being rate-limited
                time.sleep(3)
            except RateLimitError as e:
                resume_dir = directory / "resume.json"
                logger.error(f"Rate limit exceeded when fetching row #{idx} {url}: {e}. Progress recorded in {resume_dir}")
                with open(resume_dir, "w", encoding='utf-8') as f:
                    json.dump({
                        'next_index': idx, 
                        "out_dir": directory, 
                        "min_similarity": min_similarity,
                        "input": input_file,
                        "dblp_col": dblp_col
                    }, f)
                break
    
    logger.info("removing duplicates")
    coauthors_df = pd.read_csv(coauthor_csv)
    dblp_info_df = pd.read_csv(dblp_info_csv).drop_duplicates(subset=["url"])
    dblp_info_df = dblp_info_df.drop_duplicates(subset=['url'])

    coauthors_df = coauthors_df.drop_duplicates(subset=['pid1', 'pid2'])
    coauthors_df.to_csv(coauthor_csv, index=False)
    dblp_info_df.to_csv(dblp_info_csv, index=False)

    dblp_expertise_df = pd.read_csv(dblp_expertise_csv).drop_duplicates(subset=['dblp', 'expertise'])
    dblp_expertise_df.to_csv(dblp_expertise_csv, index=False)
