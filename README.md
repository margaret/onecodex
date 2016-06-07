# One Codex API

[![Circle CI](https://circleci.com/gh/onecodex/onecodex.png?style=badge&circle-token=d86a8fc55e54a645ee515387db9acee32068a6ad)](https://circleci.com/gh/onecodex/onecodex)

Command line interface (CLI) and Python client library for interacting with the One Codex v1 API.

**Warning**: The One Codex v1 API is currently being actively developed. While we do not expect major breaking changes (i.e., removing fields from resources currently available via the API), it should be treated as a **beta release**. If you need strong stability guarantees, we recommend using [our v0 API](docs.onecodex.com/v0/docs).

MAINTAINERS: [@bovee](https://github.com/bovee), [@boydgreenfield](https://github.com/boydgreenfield)

# Installation

This package provides 3 major pieces of functionality: (1) a core Python client library; (2) a simple CLI for interacting with the One Codex platform that uses that core library; and (3) optional extensions to the client library, which offers many features aimed at advanced users and provides functionality for use in interactive notebook environments (e.g., IPython notebooks).


### _Basic installation_
The CLI (and core Python library) may be simply installed using `pip`. To download a minimal installation (#1 and #2), simply run:
```shell
pip install onecodex
```


### _Installation with optional extensions_
To also download the optional extensions to the client library - and all of their dependencies - use the command `pip install onecodex[all]`. **Warning:** Because other packages used in the extensions rely upon `numpy` being present during their installation, `numpy` must be installed seperately first. So if you do not have `numpy` installed, and you are going to install `onecodex[all]` please do the following:
```shell
# If numpy is not installed in your environment
pip install numpy

# Once you have numpy installed
pip install onecodex[all]
```

# Using the CLI

## Logging in
The CLI supports authentication using either your One Codex API key or your One Codex username and password.
To log in using your username and password:

```shell
onecodex login
```

This command will save a credentials file at `~/.onecodex`, which will then automatically be used for authentication the next time the CLI or Python client library are used (OS X/Linux only). You can clear this file and remove your API key from your machine with `onecodex logout`.

In a shared environment, we recommend directly using your One Codex API key, rather than logging in and storing it in a credentials file. To use API key authentication, simply pass your key as an argument to the `onecodex` command:
```shell
onecodex --api-key=YOUR_API_KEY samples
```

Your API key can be found on the [One Codex settings page](https://app.onecodex.com/settings) and should be 32 character string. You may also generate a new API key on the settings page in the web application. _Note_: Because your API key provides access to all of the samples and metadata in your account, you should immediately reset your key on the website if it is ever accidentally revealed or saved (e.g., checked into a GitHub repository).

## Uploading files
The CLI supports uploading FASTA or FASTQ files (optionally gzip compressed) via the `upload` command.
```shell
onecodex upload bacterial_reads_file.fq.gz
```

Multiple files can be uploaded in a single command as well:
```shell
onecodex upload file1.fq.gz file2.fq.gz ...
```

_Note_: Files larger than **5GB** are supported, but require that you have the `aws-cli` package installed on your computer. `aws-cli` can be installed with `pip install aws-cli`.

## Resources
The CLI supports retrieving your One Codex samples and analyses. The following resources may be queried:

* Your samples (`Samples`)

* Sample metadata (`Metadata`)

* `Analyses`, which include several subtypes with additional functionality and fields:
    * `Classifications`, which are basic metagenomic classification results for your samples
    * `Markerpanels`, which are _in silico_ panels for particular genes or other functional markers ([example on One Codex](https://app.onecodex.com/markerpanel/sample))

* `Jobs`, which provide information on the name, version, and type of analysis which was performed for a given `Analyses`


Simply invoke the `onecodex` command, using one of the above resource names as a subcommand (all lowercase). For example:
```shell
# fetch all your samples
onecodex samples

# fetch a list of markerpanels based on their ids
onecodex markerpanels 0123456789abcdef 0987654321fdecba
```

# Using the Python client library

## Initalization
To load the API, use the following import:
```python
from onecodex.api import Api
```

When you instatiate the API, you will by default receive an `extended` api client (with all the IPython bells and whistles mentioned above). To create a basic api simply pass `extensions=False` to the constructor.

You should also specify an API key to use for authentication, via the `api_key` parameter.

```python
from onecodex.api import Api

# Instantiate a One Codex API object, will attempt to get credentials from ~/.onecodex
ocx = Api()

# Instantiate an API object with no extensions
ocx = Api(extensions=False)

# Instantiate an API object, manually specifying an API key
ocx = Api(api_key="YOUR_API_KEY_HERE")
```

## Resources

Resources are exposed as attributes on the API object. You can fetch a resource directly by its ID or you can fetch it using the query interface. Currently you can access resources using either `get()` or `where()`. If you need help finding the ID for a sample, its identifier is part of its url on our webpage: e.g. for an analysis at `https://app.onecodex.com/analysis/public/1d9491c5c31345b6`, the ID is `1d9491c5c31345b6`. IDs are all short unique identifiers, consisting of 16 hexadecimal characters (`0-9a-f`).

```python
all_completed_analyses = ocx.Analyses.where(complete=True)
sample_analysis = ocx.Analyses.get("1d9491c5c31345b6")
```

## Extensions

Besides basic resource fetching and querying, the extended client provides a number of other useful features:

### Analyses Extensions

The extended `Analyses` resource allows for fetching the raw hit data and adds several functions for the analysis of said data. Most of the functions are class methods on the `Analyses` class, and take one or more Analyses instances as input.

#### Results table

The raw hit data can be accessed via the `table` parameter of an analysis instance. Note that the first call to `table` will fetch the data from s3, but subsequent calls will use a cached version.

```python
analysis = ocx.Analyses.get("1d9491c5c31345b6")  # by id
table = analysis.table()
```

#### Abundances

The `abundances` command can be used to fetch a parsed/more user friendly form of the raw data. You can optionally pass an array of NCBI tax ids, to only fetch data for those ids (if present)

```python
analysis = ocx.Analyses.get("1d9491c5c31345b6")  # by id

abundance_data = analysis.abundances()
ecoli_abundance_data = analysis.abundances([694524, 694529])  # Get abundances for two E. coli strains
```

#### To OTU

A group of analyses can be converted to an OTU table [link](http://biom-format.org/documentation/format_versions/biom-1.0.html).
```python
analyses = ocx.Analyses.where(complete=True)

# returns a python dict, can be written to a file
otu_dict = ocx.Analyses.to_otu(analyses)
```

# Development

Before developing, `git` and `python` (version 2.7 or >3.3) are needed.

To download the client library from GitHub:

```shell
git clone https://github.com/onecodex/onecodex.git
cd onecodex/
```

To set up the project, first create a virtual environment and then install dependencies:

```shell
virtualenv venv
source venv/bin/activate
pip install numpy  # numpy must be installed before any of its dependencies
pip install -r requirements.txt
```

Test are run through the makefile, and call tox. Note this may take awhile at first because of installing dependencies:

```shell
make lint
make test
```
