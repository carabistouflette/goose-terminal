GOOSE ?= .toolchain/goose/build/goose
.NOTPARALLEL:
.PHONY: setup format check test test-debug test-sanitize bench-smoke
setup:
	./scripts/setup-goose.sh
format:
	$(GOOSE) format terminal.goose posix.goose tests examples bench fuzz
check:
	$(GOOSE) format --check terminal.goose posix.goose tests examples bench fuzz
	$(GOOSE) check fuzz/driver.goose
	python3 -m unittest discover -s fuzz -p 'test_*.py'
	$(GOOSE) check terminal.goose
	$(GOOSE) check posix.goose
	$(GOOSE) check tests/posix.goose
	$(GOOSE) check examples/posix_status.goose
	$(GOOSE) check tests/api.goose
	$(GOOSE) check tests/oracle.goose
	$(GOOSE) check tests/overloads.goose
	$(GOOSE) check examples/status.goose
	$(GOOSE) check bench/driver.goose
	$(GOOSE) check bench/consumer/phases.goose
	python3 -m unittest discover -s bench/consumer -p 'test_*.py'
test: test-oracle
	mkdir -p .build
	$(GOOSE) run --cc "$(CC)" tests/api.goose
	$(GOOSE) build --cc "$(CC)" tests/api.goose -O2 -o .build/api
	./.build/api
	$(GOOSE) run --cc "$(CC)" tests/overloads.goose
	python3 tests/ownership.py $(GOOSE)
	$(GOOSE) run --cc "$(CC)" examples/status.goose
test-debug:
	mkdir -p .build
	$(GOOSE) build --cc "$(CC)" tests/api.goose --debug --no-bce -o .build/api-debug
	./.build/api-debug
	$(GOOSE) build --cc "$(CC)" tests/oracle.goose --debug --no-bce -o .build/oracle-debug
	python3 tests/oracle.py .build/oracle-debug

.PHONY: test-oracle
test-oracle:
	mkdir -p .build
	$(GOOSE) build --cc "$(CC)" tests/oracle.goose -O2 -o .build/oracle
	python3 tests/oracle.py .build/oracle

test-sanitize:
	mkdir -p .build
	$(GOOSE) build tests/api.goose --standalone --debug --no-bce --cc ./scripts/sanitizer-cc.sh -o .build/api-sanitize
	./.build/api-sanitize
	$(GOOSE) build tests/oracle.goose --standalone -O2 --cc ./scripts/sanitizer-cc.sh -o .build/oracle-sanitize
	python3 tests/oracle.py .build/oracle-sanitize

bench-smoke:
	mkdir -p .build
	$(GOOSE) build bench/driver.goose -O2 --cc "$(CC)" -o .build/bench
	./.build/bench 10

.PHONY: test-posix test-posix-sanitize
test-posix:
	mkdir -p .build
	$(GOOSE) check posix.goose
	$(GOOSE) build --cc "$(CC)" tests/posix.goose -O2 -o .build/posix
	python3 tests/posix.py .build/posix
	python3 scripts/native-test.py --cc "$(CC)"
test-posix-sanitize:
	mkdir -p .build
	$(GOOSE) build tests/posix.goose --standalone --debug --no-bce --cc ./scripts/sanitizer-cc.sh -o .build/posix-sanitize
	python3 tests/posix.py .build/posix-sanitize
	python3 scripts/native-test.py --cc "$(CC)" --sanitize


.PHONY: fuzz-smoke fuzz-campaign
fuzz-smoke:
	mkdir -p .build
	campaign_dir=$$(mktemp -d .build/campaign-smoke-XXXXXX); python3 fuzz/run.py --goose "$(abspath $(GOOSE))" --seconds 3 --max-cases 1500 --output "$$campaign_dir/run"
fuzz-campaign:
	mkdir -p .build
	campaign_dir=$$(mktemp -d .build/campaign-XXXXXX); python3 fuzz/run.py --goose "$(abspath $(GOOSE))" --seconds 600 --max-cases 1000000 --output "$$campaign_dir/run"
