Running the Dashboard

  If starting fresh on another machine

Prerequisites (already done)

  - Python venv: .venv/ with FastAPI, numpy, equity-shared installed
  - Node modules: frontend/node_modules/ with Next.js, lightweight-charts, GSAP



# Backend
  python3 -m venv .venv
  source .venv/bin/activate
  pip install -r backend/requirements.txt
  pip install ../equity-shared/

  # Frontend
  cd frontend && npm install

  # Config
  cp backend/config-example.yaml backend/config.yaml
  # Edit config.yaml to set correct path to facts.sqlite3

  You need two terminals (or use the combined script):

  Option 1: Combined (one terminal)

  cd /Users/ashokvenugopal/Documents/experiments/equity-experiments/equity-dashboard
  make dev

  Option 2: Separate terminals

  Terminal 1 — Backend (FastAPI on :8000)
  cd /Users/ashokvenugopal/Documents/experiments/equity-experiments/equity-dashb
  oard
  source .venv/bin/activate
  pip install ../equity-shared/
  PYTHONPATH=. python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload

  Terminal 2 — Frontend (Next.js on :3000)
  cd /Users/ashokvenugopal/Documents/experiments/equity-experiments/equity-dashboard/frontend
      #sometimes the library gets corrected, and you run this first -
      cd frontend && rm -rf .next && npm run dev 
  npm run dev


  Then open http://localhost:3000 in your browser.

  
  
  Tests

  PYTHONPATH=. .venv/bin/python -m pytest tests/ -v