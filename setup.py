"""Python driver for Ismatec Reglo ICC peristaltic pumps."""

from setuptools import setup

with open('README.md') as in_file:
    long_description = in_file.read()

setup(
    name='ismatec-control',
    version='0.4.0',
    description="Driver for Ismatec Reglo ICC peristaltic pumps.",
    long_description=long_description,
    long_description_content_type='text/markdown',
    author='Alex Ruddick',
    author_email='a.ruddick@numat-tech.com',
    license='GPLv3',
    url='https://github.com/numat/ismatec',
    packages=['ismatec'],
    install_requires=[
        'pyserial',
    ],
    extras_require={
        'test': [
            'pytest>=6,<8',
            'pytest-cov>=4,<5',
            'pytest-asyncio==0.*',
            'pytest-xdist==3.*',
            'mypy==1.9.0',
            'types-pyserial',
            'ruff==0.3.4',
        ],
    },
    entry_points={
        'console_scripts': [('ismatec = ismatec:command_line')],
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
        "Programming Language :: Python :: 3.12",
        "Topic :: Scientific/Engineering :: Human Machine Interfaces",
        "Topic :: Scientific/Engineering :: Chemistry",
    ],
)
