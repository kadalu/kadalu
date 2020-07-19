VERSION ?= "master"
PYTHON ?= python3

help:
	@echo "make help        - Show this help message"
	@echo "make gen-version - Generate Version file based on Env variable"

gen-version:
	@echo "\"\"\"Version\"\"\"" > kubectl_kadalu/version.py
	@echo "VERSION = \"${VERSION}\"" >> kubectl_kadalu/version.py

pytest:
	${PYTHON} -m pytest kubectl_kadalu

pylint:
	cd kubectl_kadalu && ${PYTHON} -m pylint --disable W0511 *.py

mypy:
	cd kubectl_kadalu && ${PYTHON} -m mypy *.py
