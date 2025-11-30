#!/usr/bin/env bash
# Simple bootstrap script to create venv and install dependencies
set -euo pipefail

PYTHON=${PYTHON:-python3}
VENV_DIR=${VENV_DIR:-my_project_env}

$PYTHON -m venv ${VENV_DIR}
source ${VENV_DIR}/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
pip install -r requirements-dev.txt

echo "Virtual environment created at ${VENV_DIR}. Activate it with: source ${VENV_DIR}/bin/activate"
