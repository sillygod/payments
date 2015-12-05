class PayPalException(Exception):
    """Base PayPal Exception"""


class MissingParameter(PayPalException):
    """Raised when missing some parameters needed to continue
    in redirect to paypal page
    """


class ParameterValueError(PayPalException):
    """Raised when parameter value is incorrect"""
