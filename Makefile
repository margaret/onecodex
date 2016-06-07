test:
	flake8 --ignore E501 onecodex/
	flake8 --ignore E501 tests/
	tox
	@echo "Successfully passed all tests."

lint:
	flake8 --ignore E501 onecodex/
	flake8 --ignore E501 tests/
	@echo "Successfully linted all files."

install:
	python setup.py install