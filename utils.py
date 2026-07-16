from argparse import ArgumentParser
import ast
import csv
import sys

import numpy as np


class Parser(ArgumentParser):
    def error(self, message):
        sys.stderr.write(f"Error: {message}\n\n")
        self.print_help()
        sys.exit(2)

def read_expertise_csv(f):
    txt, embs = [], []
    with open(f, newline="", encoding="utf-8") as f:
        reader = csv.reader(f)
        for row in reader:
            txt.append(row[1])
            embs.append(ast.literal_eval(row[2]))
    return txt, embs