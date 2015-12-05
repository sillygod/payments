class AllPayException(Exception):
    """Base Allpay Exception"""


class MissingParameter(AllPayException):
    """Raised when missing some parameters needed to continue
    in redirect to allpay page
    """


class ParameterValueError(AllPayException):
    """Raised when paramter value is incorrect"""
