#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/.env"

mkdir -p ${OUT_DIR}

CSV="${OUT_DIR}/expertise.csv"
if [ ! -f "${CSV}" ]; then
    scp -i "${SSH_KEY}" ${SSH_USER}@${DB_IP}:/tmp/expertise.csv "${CSV}"
fi

if [ -z "${RESUME}" ]; then
  args=(-o "${OUT_DIR}" -i "${IN_DIR}" -s "${SIMILARITY_THRESHOLD}")
  if [[ -n "${TOPICS}" ]]; then
    args+=(-t "${TOPICS}")
  fi
  python main.py "${args[@]}"

else
  python main.py --resume "${RESUME}"
fi