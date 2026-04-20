.PHONY: \
	version \
	format-branch \
	check-fix-branch \
	claude-fix-lint \
	deps-upgrade

version:
	scripts/sync-versions.sh

format-branch:
	git diff -z --name-only --diff-filter=ACMR $(BASE_BRANCH)...HEAD -- '*.py' | xargs -0 sh -c 'if [ "$$#" -gt 0 ]; then uv run ruff format "$$@"; else echo "No changed Python files."; fi' sh

check-fix-branch:
	git diff -z --name-only --diff-filter=ACMR $(BASE_BRANCH)...HEAD -- '*.py' | xargs -0 sh -c 'if [ "$$#" -gt 0 ]; then uv run ruff check --fix "$$@"; else echo "No changed Python files."; fi' sh

claude-fix-lint:
	git diff -z --name-only --diff-filter=ACMR $(BASE_BRANCH)...HEAD -- '*.py' | xargs -0 sh -c 'if [ "$$#" -gt 0 ]; then uv run ruff check --fix "$$@" 2>&1 | claude -p "Fix all the ruff lint errors shown above. Edit the files in place." --allowedTools "Read,Edit,Bash"; else echo "No changed Python files."; fi' sh

deps-upgrade:
	uv lock --upgrade