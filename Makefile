git_rev := $(shell git rev-parse --short HEAD)
# remove leading 'v'
# the currently checked out tag or nothing
git_tag := $(shell git tag --points-at HEAD 2> /dev/null | cut -c 2- | grep -E '.+')

# version number from pyproject.toml less any +GITREV
base_version := $(shell awk -F" = " '/^version/  {gsub(/"/, "") ; split($$2, a, "+"); print a[1]}' pyproject.toml)

ifdef git_tag
	# on a release tag
	final_version = $(git_tag)
else
	# snapshot build
	final_version = $(base_version)+$(git_rev)
endif


install:
	pip install -e .

example_checksums:
	$(foreach file, $(wildcard examples/*), ringmaster metadata $(file);)

	# special cases - manually include additional files
	ringmaster metadata examples/0250-aws-load-balancer --include crds.yaml
	ringmaster metadata examples/0260-ambassador --include values.yaml

test: poetry_install
	poetry run pytest --cov=ringmaster

dist: poetry_install patch_version test
	poetry build

poetry_install:
	poetry install

patch_version:
	# patch pyproject.toml with GITREV if not on a release tag
	sed -i '/^version =/ c\version = "$(final_version)"\' pyproject.toml

	# generate a regular version.py file so we can know our version
	echo "# generated file, do not edit!\n__version__ = \"$(final_version)\"" > ringmaster/version.py

clean:
	rm -rf dist
