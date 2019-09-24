#!/usr/bin/env python
# -*- coding: utf-8 -*-

import setuptools

with open("README.md", "r") as fh:
    long_description = fh.read()

setuptools.setup(name='pysdbus',
    version='20190924',
    description='pysdbus is a Python wrapper library for DBus inter-process communication',
    long_description=long_description,
    long_description_content_type="text/markdown",
    url='https://github.com/anyc/pysdbus/',
    download_url='https://github.com/anyc/pysdbus//archive/master.zip',
    keywords=['dbus', 'sdbus', 'IPC'],
    author='Mario Kicherer',
    author_email='dev@kicherer.org',
    license='LGPL-2.1',
    packages=setuptools.find_packages(),
    include_package_data=True,
)
