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
	$(GOOSE) check tests/oracle.goose
	$(GOOSE) check tests/overloads.goose
	$(GOOSE) check examples/status.goose
	$(GOOSE) check bench/driver.goose
test: test-oracle
	mkdir -p .build
	$(GOOSE) run tests/api.goose
	$(GOOSE) build tests/api.goose -O2 -o .build/api
	./.build/api
	$(GOOSE) run tests/overloads.goose
	python3 tests/ownership.py $(GOOSE)
	$(GOOSE) run examples/status.goose
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

test-sanitize:
	mkdir -p .build
	$(GOOSE) build tests/api.goose --standalone --debug --no-bce --cc ./scripts/sanitizer-cc.sh -o .build/api-sanitize
	./.build/api-sanitize
	$(GOOSE) build tests/oracle.goose --standalone -O2 --cc ./scripts/sanitizer-cc.sh -o .build/oracle-sanitize
	python3 tests/oracle.py .build/oracle-sanitize

bench-smoke:
	mkdir -p .build
	$(GOOSE) build bench/driver.goose -O2 --cc gcc -o .build/bench
	./.build/bench 10
