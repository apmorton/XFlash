from setuptools import setup, find_packages
import sys, os

version = '1.1'

setup(name='xflash',
      version=version,
      description="Xbox360 USB SPI Flasher client",
      long_description="""\
""",
      classifiers=[], # Get strings from http://pypi.python.org/pypi?%3Aaction=list_classifiers
      keywords='',
      author='Juvenal',
      author_email='',
      url='',
      license='BSD',
      packages=find_packages(exclude=['ez_setup', 'examples', 'tests']),
      include_package_data=True,
      zip_safe=False,
      install_requires=[
          'pyusb',
          'argparse',
      ],
      entry_points="""
      [console_scripts]
      xflash = xflash.XFlash:main
      """,
      )
