from setuptools import setup, find_packages

setup(name='django_packrat',
      version='0.0.3',
      description='Integrates Webpack and BrowserSync with Django',
      url='https://github.com/IronCountySchoolDistrict/django-packrat',
      author='Iron County School District',
      author_email='data@ironmail.org',
      license='MIT',
      packages=find_packages(),
      install_requires=[
          'env-tools',
          'colored==1.3.5',
          'psutil',

      ],
      zip_safe=False)
