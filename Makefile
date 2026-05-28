.PHONY: dev-setup test

dev-setup:
	uv sync --extra test
	cp dev-hooks/pre-push .git/hooks/pre-push
	chmod +x .git/hooks/pre-push
	@echo "Dev hooks installed."

test:
	uv run pytest
