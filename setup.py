from setuptools import setup, find_packages

execfile('onecodex/version.py')

setup(
    name='onecodex',
    version=__version__,  # noqa
    packages=find_packages(exclude=['*test*']),
    install_requires=['potion-client>=2.1.3', 'requests>=2.9', 'click', 'requests_toolbelt'],
    include_package_data=True,
    zip_safe=False,
    extras_require={
        'all': ['numpy', 'pandas', 'matplotlib', 'networkx']
    },
    dependency_links=[],
    setup_requires=[],
    tests_require=[
        'nose', 'flake8', 'tox', 'responses', 'httmock', 'numpy', 'pandas',
        'requests_toolbelt', 'matplotlib', 'testfixtures', 'pyfakefs', 'coverage'
    ],
    author='Kyle McChesney & Nick Greenfield & Roderick Bovee',
    author_email='kyle@onecodex.com',
    description='',
    license='Apache License Version 2.0',
    keywords='One Codex API Client',
    url='https://github.com/onecodex/onecodex',
    classifiers=[],
    entry_points={
        'console_scripts': ['onecodex = onecodex.cli:onecodex']
    },
    test_suite='nose.collector'
)
