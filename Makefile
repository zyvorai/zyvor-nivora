# SPDX-License-Identifier: BUSL-1.1
PORT ?= 7799
TOKEN ?=
APP := native/build/Build/Products/Release/Nivora.app

.PHONY: help check test test-one demo run native widgets app fixtures stop clean

help: ## List targets
	@grep -E '^[a-z-]+:.*## ' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  make %-10s %s\n", $$1, $$2}'

check: ## Fast loop: compile + Python unit tests
	python3 -B -m py_compile agent/*.py
	python3 -B -m unittest discover -s tests -p 'test_*.py'

test: ## Full suite (required before commit)
	./scripts/test.sh

test-one: ## One module or test: make test-one T=test_intelligence
	@test -n "$(T)" || { echo "usage: make test-one T=test_intelligence[.Class.method]"; exit 2; }
	cd tests && python3 -B -m unittest -v $(T)

demo: ## Collector + dashboard on simulated data (PORT=, TOKEN=)
	python3 -B agent/nivora.py --demo --port $(PORT) $(if $(TOKEN),--token $(TOKEN))

run: ## Real collector, no history written (PORT=, TOKEN=)
	python3 -B agent/nivora.py --no-history --port $(PORT) $(if $(TOKEN),--token $(TOKEN))

native: ## Build the unsigned native app
	./scripts/build-native.sh

widgets: ## Build the app with the WidgetKit extension (ad-hoc signed)
	./scripts/build-native-widgets.sh

app: native ## Build and launch the native app
	open $(APP)

fixtures: ## Regenerate demo snapshot fixtures after changing snapshot keys
	python3 -B agent/nivora.py --demo --once > native/Tests/Fixtures/demo-snapshot.json
	python3 -B agent/nivora.py --demo --once --no-history > web/demo-snapshot.json

stop: ## Stop dev collectors started by make
	-pkill -f "agent/nivora.py"

clean: ## Remove build output and caches
	rm -rf native/build
	find . -name __pycache__ -not -path './.git/*' -prune -exec rm -rf {} +
