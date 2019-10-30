# Author: Alejandro M. Bernardis
# Email: alejandro.bernardis at gmail.com
# Created: 2019/10/12
# ~

import aysa_commands
from os import path
from io import open
from setuptools import setup, find_packages

here = path.abspath(path.dirname(__file__))

with open(path.join(here, 'readme.md'), encoding='utf-8') as f:
    long_description = f.read()

setup(
    name=aysa_commands.__title__,
    version=aysa_commands.__version__,
    description=aysa_commands.__summary__,
    long_description=long_description,
    long_description_content_type='text/markdown',
    url=aysa_commands.__uri__,
    author=aysa_commands.__author__,
    author_email=aysa_commands.__email__,
    keywords='docker registry services development',
    packages=find_packages(exclude=['contrib', 'docs', 'tests']),
    python_requires='>=3.6.*, <4',

    install_requires=[
        'bcrypt==3.1.7',
        'certifi==2019.9.11',
        'cffi==1.13.1',
        'chardet==3.0.4',
        'colorama==0.4.1',
        'cryptography==2.8',
        'docopt==0.6.2',
        'fabric==2.5.0',
        'idna==2.8',
        'invoke==1.3.0',
        'paramiko==2.6.0',
        'pycparser==2.19',
        'pynacl==1.3.0',
        'requests==2.22.0',
        'six==1.12.0',
        'urllib3==1.25.6',
        'vistir==0.4.3'
    ],

    classifiers=[
        'Development Status :: 3 - Alpha',
        'Environment :: Console',
        'Intended Audience :: Developers',
        'Topic :: Software Development :: Build Tools',
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3.8'
    ],

    entry_points={
        'console_scripts': [
            
        ],
    },

    project_urls={
        'Bug Reports': aysa_commands.__issues__,
        'Source': aysa_commands.__uri__,
    },
)