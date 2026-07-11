.PHONY: dev stop backend frontend test test-backend lint clean

dev:
	./scripts/dev.sh

# Clear anything (usually an orphaned dev stack) holding the dev ports.
stop:
	@for port in 8000 3000; do \
		pids=$$(lsof -nP -tiTCP:$$port -sTCP:LISTEN 2>/dev/null); \
		if [ -n "$$pids" ]; then \
			echo "[INFO] Stopping port $$port (pids: $$pids)"; \
			kill $$pids 2>/dev/null || true; \
		else \
			echo "[INFO] Port $$port already free"; \
		fi; \
	done

backend:
	.venv/bin/python -m backend.main

frontend:
	cd frontend && npm run dev

test: test-backend

test-backend:
	.venv/bin/python -m pytest tests/ -v

lint:
	cd backend && python -m ruff check .
	cd frontend && npm run lint

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	rm -rf frontend/.next frontend/node_modules
