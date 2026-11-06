GOOSE ?= .toolchain/goose/build/goose
.NOTPARALLEL:
.PHONY: setup format check test test-debug test-sanitize bench-smoke
setup:
	./scripts/setup-goose.sh
format:
	$(GOOSE) format terminal.goose tests examples bench
check:
	$(GOOSE) format --check terminal.goose tests examples bench
	$(GOOSE) check terminal.goose
	$(GOOSE) check tests/api.goose
test:
	mkdir -p .build
	$(GOOSE) run tests/api.goose
	$(GOOSE) build tests/api.goose -O2 -o .build/api
	./.build/api
test-debug:
	mkdir -p .build
	$(GOOSE) build tests/api.goose --debug --no-bce -o .build/api-debug
	./.build/api-debug
	$(GOOSE) build tests/oracle.goose --debug --no-bce -o .build/oracle-debug
	python3 tests/oracle.py .build/oracle-debug

.PHONY: test-oracle
test-oracle:
	mkdir -p .build
	$(GOOSE) build tests/oracle.goose -O2 -o .build/oracle
	python3 tests/oracle.py .build/oracle
