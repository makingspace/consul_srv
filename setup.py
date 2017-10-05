from __future__ import print_function
from setuptools import setup

setup(
    name='consul_srv',
    version='0.4.3',
    description='Consul SRV convenience module',
    author='Zach Smith',
    author_email='zach.smith@makespace.com',
    license='BSD3',
    packages=['consul_srv'],
    install_requires=["dnspython", "requests"])
