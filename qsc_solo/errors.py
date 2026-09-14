class DomainError(Exception):
    """Expected business rule violation."""

class NotFound(DomainError): pass
class Conflict(DomainError): pass
class Forbidden(DomainError): pass
class ValidationError(DomainError): pass
