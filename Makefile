install:
	pip install -e .

example_checksums:
	$(foreach file, $(wildcard examples/*/*), ringmaster metadata $(file);)

test:
	pytest