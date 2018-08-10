from setuptools import setup, find_packages

setup(name='django_packserver',
      version='0.0.3',
      description='Integserveres Webpack and BrowserSync with Django',
      url='https://github.com/IronCountySchoolDistrict/django-packserver',
      author='Iron County School District',
      author_email='data@ironmail.org',
      license='MIT',
      packages=find_packages(),
      install_requires=[
          'env-tools',
          'colored',
          'psutil',
      ],
      zip_safe=False)
