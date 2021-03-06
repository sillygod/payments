try:
    from setuptools import setup
except ImportError:
    from distutils.core import setup


# https://docs.python.org/2/distutils/examples.html
# we need to explicitly describe sub module

PACKAGES = [
    'payments_extend',
    'payments_extend.alipay',
    'payments_extend.allpay',
    'payments_extend.paypal',
]

REQUIREMENTS = [
    'django-payments',
]


setup(
    name='django-payments-extend',
    author="sillygod",
    author_email="sillygod@livemail.tw",
    description="django payment extension",
    version="0.1.0",
    url='https://github.com/sillygod/payments',
    packages=PACKAGES,
    install_requires=REQUIREMENTS,
    include_package_data=True,
)
