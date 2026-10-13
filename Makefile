.PHONY: test demo run native

test:
	./scripts/test.sh

demo:
	python3 agent/nivora.py --demo

run:
	python3 agent/nivora.py

native:
	./scripts/build-native.sh
