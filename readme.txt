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
      rm -rf .next && npm run dev 
        cd frontend && rm -rf .next && npm run dev 
       #if there is issues with modules may need to reinstall 
        rm -rf .next node_modules package-lock.json && npm install &&
      # If that still fails, the Next.js 16.2.3 installation itself may be corrupted. You can also try downgrading to a known-stable version: 
        npm install next@15.3.1 && npm run dev                                        
  npm run dev  
  npm run dev
      what would be cleaned OR   cd frontend && rm -rf .next node_modules && npm install && npm run dev OR   npm run dev -- --webpack                                           
      Trade-off:
      - Turbopack: Faster HMR (~50-200ms), but buggy cache layer (your current
      issue)
      - Webpack: Slower HMR (~500ms-2s), but no cache corruption issues

      ***what is the difference running the npm run dev - with dev? why dev? what 
      changes if you dont use dev? what other options are there? prod?         
                                                                              
      npm run dev runs the script named dev defined in package.json under         
      "scripts". For Next.js, that's typically next dev.                          
                                                                              
      The common Next.js scripts:                                                 
                                                                              
      ┌──────────┬─────────┬───────────────────────────────────────────────────┐  
      │ Command  │ What it │                      Purpose                      │
      │          │   runs  │                                                   │
      ├──────────┼─────────┼───────────────────────────────────────────────────┤
      │ npm run  │ next    │ Development mode — hot reload, error overlays, no │
      │ dev      │ dev     │  optimization, Turbopack bundler, source maps.    │
      │          │         │ Rebuilds on every file save.                      │
      ├──────────┼─────────┼───────────────────────────────────────────────────┤
      │ npm run  │ next    │ Creates an optimized production build — minified, │
      │ build    │ build   │  tree-shaken, static pages pre-rendered. No dev   │
      │          │         │ server.                                           │
      ├──────────┼─────────┼───────────────────────────────────────────────────┤
      │ npm run  │ next    │ Serves the production build from npm run build.   │
      │ start    │ start   │ No hot reload, no dev tools. This is what you'd   │
      │          │         │ run in production.                                │
      └──────────┴─────────┴───────────────────────────────────────────────────┘

      Key differences:

      - dev: Slow initial compile, fast incremental rebuilds, verbose errors,
      React strict mode double-renders, no minification. Uses Turbopack (which is
      causing your SST/black screen issues).
      - build + start: Fast page loads, minified JS, pre-rendered static pages, no
      hot reload. Much more stable.

      The Turbopack instability you're seeing only affects dev mode. If you want a
      stable local experience without hot reload, you can:

      npm run build && npm run start

      Or stay in dev mode but bypass Turbopack:

      npm run dev -- --webpack

      npm run without a script name just lists all available scripts. You can also
      define custom ones like "lint", "test", "typecheck" in package.json.

        


  Then open http://localhost:3000 in your browser.

  
  
  Tests

  PYTHONPATH=. .venv/bin/python -m pytest tests/ -v



  #NOTES
  Clean build. /anuj is listed alongside all existing pages. Here's what's on
  the page:

  1. Global Cues Strip — Compact horizontal pills showing key overnight moves:
  US indices (Dow/Nasdaq/S&P), GIFT Nifty, Dollar Index, Brent Crude, USD/INR.
  Each pill: name + close + change%. Fits in one line.

  2. FII Activity Snapshot — Single-line banner: "FII: -1,983 Cr | DII: +2,432
  Cr (4th consecutive selling day)". Computes the streak count from last 10 days
   of daily data.

  3. Nifty Technical Levels (THE CORE) — DMA-centric layout:
  - DMA 20/50/100/200 each showing: level, distance %, above/below with visual
  bar
  - 52W High/Low cards with distance %
  - Period candlestick chart (Day, 1W, 1M, MTD, 1Y, YTD) with SMA lines +
  crosshair tooltip
  - RSI with overbought/oversold
  - S&R levels (S3 to R3)

  4. Bank Nifty Technical Levels — Same layout, side-by-side with Nifty.

  5. Market Breadth — A/D ratio, 52W highs vs lows, 5-day activity bar history.

  6. Sector Rotation — Table with 1W/4W/13W returns + "vs Nifty" relative column
   showing outperformance/underperformance vs Nifty's 1M return.

  7. FII Derivatives — Compact long/short % bar with extreme warning.

  The /trade-setup page is untouched. "Anuj Setup" added to sidebar between
  "CNBC Bazaar" and "Trade Setup".