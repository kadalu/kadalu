VERSION ?= "master"
PYTHON ?= python3
PROGNAME = kubectl-kadalu

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

release: gen-version
	@rm -rf build
	@mkdir -p build/src
	@cp -r kubectl_kadalu/*.py build/src/
	@cd build/src && zip -r ../${PROGNAME}.zip *
	@echo '#!/usr/bin/env ${PYTHON}' | cat - build/${PROGNAME}.zip > build/${PROGNAME}
	@chmod +x build/${PROGNAME}
	@rm -rf build/src
	@rm -f build/${PROGNAME}.zip
	@echo "Single deployment file is ready: build/${PROGNAME}"
