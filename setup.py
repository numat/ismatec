"""Python driver for Ismatec RegloICC peristaltic pumps."""
from sys import version_info

from setuptools import setup

if version_info < (3, 7):
    raise ImportError("This module requires Python >=3.7.")

with open('README.md', 'r') as in_file:
    long_description = in_file.read()

setup(
    name="ismatec",
    version="0.4.0",
    description=(
        "Library for driving the Ismatec Reglo ICC peristaltic pump."
        "Communication is done over direct RS232 or through a serial server."
    ),
    author="Alex Ruddick",
    author_email="a.ruddick@numat-tech.com",
    license="GPLv3",
    url="https://githut.com/numat/ismatec",
    packages=["ismatec"],
    install_requires=[
        "pyserial",
    ],
    extras_require={
        'test': ['pytest>=6,<8',
                 'pytest-cov>=4,<5',
                 'pytest-asyncio==0.*',
                 'pytest-xdist==3.*',
                 'flake8==6.*',
                 'flake8-docstrings==1.*',
                 'mypy==1.0.1',
                 'types-pyserial']
    },
    entry_points={
        "console_scripts": [("ismatec = ismatec:command_line")]
    },
    classifiers=[
        "Development Status :: 4 - Beta",
        "License :: OSI Approved :: GNU General Public License v3 (GPLv3)",
        "Natural Language :: English",
        "Programming Language :: Python",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Topic :: Scientific/Engineering :: Human Machine Interfaces",
        "Topic :: Scientific/Engineering :: Chemistry",
    ],
)
