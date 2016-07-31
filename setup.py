from setuptools import setup, find_packages


with open('onecodex/version.py') as import_file:
    exec(import_file.read())


setup(
    name='onecodex',
    version=__version__,  # noqa
    packages=find_packages(exclude=['*test*']),
    install_requires=['potion-client>=2.4.1', 'requests>=2.9',
                      'click>=6.6', 'requests_toolbelt>=0.6.2'],
    include_package_data=True,
    zip_safe=False,
    extras_require={
        'all': ['numpy>=1.11.0', 'pandas>=0.18.1', 'matplotlib>1.5.1', 'networkx>=1.11']
    },
    dependency_links=[],
    setup_requires=[],
    tests_require=[
        'nose', 'flake8', 'tox', 'responses', 'httmock', 'numpy', 'pandas',
        'requests_toolbelt', 'matplotlib', 'testfixtures', 'pyfakefs', 'coverage'
    ],
    author='Kyle McChesney & Nick Greenfield & Roderick Bovee',
    author_email='opensource@onecodex.com',
    description='',
    license='MIT License',
    keywords='One Codex API Client',
    url='https://github.com/onecodex/onecodex',
    classifiers=[],
    entry_points={
        'console_scripts': ['onecodex = onecodex.cli:onecodex']
    },
    test_suite='nose.collector'
)
