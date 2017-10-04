from setuptools import setup, find_packages

setup(
    name='voobly',
    version='1.0.0',
    description='Python 3 API for Voobly, the gaming platform.',
    url='https://github.com/happyleavesaoc/python-voobly/',
    license='MIT',
    author='happyleaves',
    author_email='happyleaves.tfr@gmail.com',
    packages=find_packages(),
    install_requires=['requests==2.12.4', 'requests-cache==0.4.13', 'tablib==0.12.1'],
    classifiers=[
        'License :: OSI Approved :: MIT License',
        'Operating System :: OS Independent',
        'Programming Language :: Python :: 3',
    ]
)
