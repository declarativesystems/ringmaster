install:
	pip install -e .

example_checksums:
	$(foreach file, $(wildcard examples/*), ringmaster metadata $(file);)

	# special cases - manually include additional files
	ringmaster metadata examples/0330-aws-load-balancer --include crds.yaml
	ringmaster metadata examples/0340-ambassador --include values.yaml
test:
	pytest