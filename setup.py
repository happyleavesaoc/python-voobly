from setuptools import setup, find_packages

setup(
    name='voobly',
    version='1.2.9',
    description='Python 3 API for Voobly, the gaming platform.',
    url='https://github.com/happyleavesaoc/python-voobly/',
    license='MIT',
    author='happyleaves',
    author_email='happyleaves.tfr@gmail.com',
    packages=find_packages(),
    package_data={'voobly': [
        'metadata/games.json',
        'metadata/ladders.json'
    ]},
    install_requires=[
        'beautifulsoup4>=4.6.3',
        'dateparser>=0.7.0',
        'requests>=2.20.0',
        'requests-cache>=0.4.13',
        'tablib>=0.12.1'
    ],
    classifiers=[
        'License :: OSI Approved :: MIT License',
        'Operating System :: OS Independent',
        'Programming Language :: Python :: 3',
    ]
)
