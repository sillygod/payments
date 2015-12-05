class AlipayException(Exception):
    """Base Alipay Exception"""


class MissingParameter(AlipayException):
    """Raised when missing some parameters needed to continue
    in creating payment url process
    """


class ParameterValueError(AlipayException):
    """Raised when paramter value is incorrect"""


class TokenAuthorizationError(AlipayException):
    """The error occured when getting token"""
