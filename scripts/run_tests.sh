#!/usr/bin/env bash
set -euo pipefail

VENV_DIR=${VENV_DIR:-my_project_env}
if [[ -f ${VENV_DIR}/bin/activate ]]; then
  source ${VENV_DIR}/bin/activate
fi

pytest -q
