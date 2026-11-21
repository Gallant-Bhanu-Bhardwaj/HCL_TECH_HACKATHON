#!/bin/bash
# Start the API.   ./run.sh        -> real LLM (Ollama must be running)
#                  ./run.sh mock   -> mock mode, no LLM needed
source .venv/bin/activate
python init_db.py                       # fresh database every start
export LLM_MODEL=${LLM_MODEL:-gemma4:e4b}
if [ "$1" = "mock" ]; then export MOCK_LLM=true; fi
uvicorn app.main:app --reload --port 8000
