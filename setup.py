#!/usr/bin/env python

import codecs
import re
import os

from setuptools import setup, find_packages


def read(*parts):
    filename = os.path.join(os.path.dirname(__file__), *parts)
    with codecs.open(filename, encoding='utf-8') as fp:
        return fp.read()


def find_version(*file_paths):
    version_file = read(*file_paths)
    version_match = re.search(r"^__version__ = ['\"]([^'\"]*)['\"]",
                              version_file, re.M)
    if version_match:
        return version_match.group(1)
    raise RuntimeError("Unable to find version string.")


setup(
    name="pdfcutter",
    version=find_version('pdfcutter/__init__.py'),
    url='https://github.com/stefanw/pdfcutter',
    license='MIT',
    description="Find and extract content in PDFs converted to XML",
    long_description=read('README.md'),
    author='Stefan Wehrmeyer',
    author_email='mail@stefanwehrmeyer.com',
    packages=find_packages(exclude=("tests",)),
    install_requires=[
        'lxml',
    ],
    include_package_data=True,
    classifiers=[
        'Environment :: Console',
        'Intended Audience :: Developers',
        'Development Status :: 4 - Beta',
        'License :: OSI Approved :: MIT License',
        'Natural Language :: English',
        'Operating System :: OS Independent',
        'Programming Language :: Python :: 3',
        'Topic :: Utilities'
    ]
)
