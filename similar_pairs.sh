#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/.env"

mkdir -p ${OUT_DIR}

CSV="${OUT_DIR}/expertise.csv"

if [ ! -f "${CSV}" ]; then
    scp -i "${SSH_KEY}" ${SSH_USER}@${DB_IP}:/tmp/expertise.csv "${CSV}"
fi

python expertise.py -t "${TOPICS}" -e "${CSV}" -o "${OUT_DIR}"
