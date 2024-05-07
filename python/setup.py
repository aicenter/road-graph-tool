import setuptools
from setuptools import setup

setup(
	name='roadgraphtool',
	version='0.0.0',
	description='Tool for generating road network graphs from open street map data.',
	author='David Fiedler',
	author_email='david.fido.fiedler@gmail.com',
	license='GNU GPLv3',
	packages=setuptools.find_packages(),
	install_requires=[
		'numpy',
		'pandas',
		'tqdm',
		'typing',
		'pyyaml',
		'psycopg2-binary',
		'sqlalchemy',
		'sshtunnel',
		'geopandas',
	],
	python_requires='>=3.8'
)
