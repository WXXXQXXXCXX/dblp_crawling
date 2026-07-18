#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/.env"

ssh -i "${SSH_KEY}" ${SSH_USER}@${DB_IP} "rm -rf /tmp/new_dblp && mkdir -p /tmp/new_dblp"
tr -d '\r' < "${OUT_DIR}/expertise.csv" > "${OUT_DIR}/expertise.tmp" && mv "${OUT_DIR}/expertise.tmp" "${OUT_DIR}/expertise.csv"
scp -i "${SSH_KEY}" \
  "${OUT_DIR}/dblp_info.csv" \
  "${OUT_DIR}/coauthors.csv" \
  "${OUT_DIR}/dblp_expertise.csv" \
  "${OUT_DIR}/expertise.csv" \
  ${SSH_USER}@${DB_IP}:/tmp/new_dblp/

ssh -i "${SSH_KEY}" ${SSH_USER}@${DB_IP} "bash /opt/update-dblp.sh"