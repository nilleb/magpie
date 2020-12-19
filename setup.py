from setuptools import setup

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(name='magpie',
      version='0.1.1',
      description='Collect raw data about a git repository.',
      author='Ivo Bellin Salarin',
      author_email='me@nilleb.com',
      long_description=long_description,
      long_description_content_type="text/markdown",
      url="https://github.com/nilleb/magpie",
      license='MIT',
      packages=['magpie', 'magpie.plugins'],
      classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Intended Audience :: Developers",
        "Development Status :: 4 - Beta",
        "Topic :: Software Development",
        "Topic :: Software Development :: Version Control :: Git",
      ],
      install_requires=["pyyaml", "peewee", "Click","gitpython","straight.plugin"],
      zip_safe=False)
