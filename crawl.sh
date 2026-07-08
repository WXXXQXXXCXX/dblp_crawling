#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/.env"

mkdir -p ${OUT_DIR}
scp -i "${SSH_KEY}" ${SSH_USER}@${DB_IP}:/tmp/expertise.csv "${OUT_DIR}/expertise.csv"

python main.py -o "${OUT_DIR}" -i "${IN_DIR}" -c ${COLUMN} -s ${SIMILARITY_THRESHOLD}

if [ -z "${RESUME}" ]; then
  python main.py -o "${OUT_DIR}" -i "${IN_DIR}" -c ${COLUMN} -s ${SIMILARITY_THRESHOLD}
else
  python main.py --resume "${RESUME}"
fi