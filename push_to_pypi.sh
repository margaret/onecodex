set -e

# TODO: Update to use twine, see https://packaging.python.org/distributing/#uploading-your-project-to-pypi
source venv/bin/activate
nosetests
echo "Tests successful. Pushing to PyPI..."
python setup.py sdist upload
