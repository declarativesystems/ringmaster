install:
	pip install -e .

example_checksums:
	$(foreach file, $(wildcard examples/*), ringmaster metadata $(file);)

	# special cases - manually include additional files
	ringmaster metadata examples/0250-aws-load-balancer --include crds.yaml
	ringmaster metadata examples/0260-ambassador --include values.yaml
test:
	pytest