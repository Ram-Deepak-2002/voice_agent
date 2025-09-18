#!/bin/bash
poetry lock
poetry install
#! if it is frist time then uncoment the below lines then run the script 
#!since playwright would not be inxstalled
#!playwright install
#!playwright install chromium
uvicorn voice_agent.server:app --host 0.0.0.0 --port 8000 --reload
