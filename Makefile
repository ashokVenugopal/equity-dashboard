.PHONY: dev backend frontend test test-backend lint clean

dev:
	./scripts/dev.sh

backend:
	cd backend && python main.py

frontend:
	cd frontend && npm run dev

test: test-backend

test-backend:
	cd backend && python -m pytest ../tests/ -v

lint:
	cd backend && python -m ruff check .
	cd frontend && npm run lint

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	rm -rf frontend/.next frontend/node_modules
