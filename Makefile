.PHONY: test verify index check

test:
	python3 -m unittest discover -s tests -v

verify:
	python3 tools/verify.py

index:
	python3 tools/generate_index.py

check: test verify
