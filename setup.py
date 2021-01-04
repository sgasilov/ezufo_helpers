# setup.py
from setuptools import setup

setup(name='ezufo_helpers',
    version='1.0',
    description='BMIT helper tools for uCT data processing',
    author=['Sergei Gasilov', 'Toby Bond'],
    url='https://bmit.lightsource.ca',
    packages=['ez_stitch', 'ez_mview', 'ez_360_find_overlap'],
    scripts=['bin/ezstitch', 'bin/ezmview', 'bin/ez360_find_overlap', 'bin/ez360_multi_stitch']
    )

