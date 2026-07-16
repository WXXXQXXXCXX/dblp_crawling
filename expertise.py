import csv
import logging
from pathlib import Path

import numpy as np
from sentence_transformers import SentenceTransformer

from encoder import ExpertiseMatcher
from utils import Parser, read_expertise_csv
import pandas as pd


def define_args():
    parser = Parser()
    parser.add_argument("-t", "--topics", dest="topics", type=str, required=True)
    parser.add_argument("-e", "--oldTopics", dest="oldTopics", type=str, required=True)
    parser.add_argument("-o", "--outDir", dest="outDir", type=str, required=True)
    return parser


if __name__ == '__main__':
    parser = define_args()
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, filename="expertise.log")
    out_dir = args.outDir

    model = SentenceTransformer("all-mpnet-base-v2")
    matcher = ExpertiseMatcher(model, args.oldTopics)

    with open(args.topics, 'r', encoding='utf-8') as f:
        new_topics = [l.strip() for l in f if l.strip()]

    new_embs = matcher.encode(new_topics)
    similar_idx, scores = matcher.find_matches(new_embs)

    out_dir = Path(args.outDir)
    with open(out_dir / 'similar_pairs.csv', 'w') as f:
        for new_t, old_id, sim in zip(new_topics, similar_idx, scores):
            writer = csv.DictWriter(f, ['new', 'existing', 'similarity'])
            if sim >= 0.6:
                writer.writerow({
                    'new': new_t,
                    'existing': matcher.texts[old_id],
                    'similarity': sim
                })
