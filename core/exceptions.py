class CustomError(Exception):
    """Base exception class for all custom errors raised in the code."""
    def __init__(self, message):
        super(CustomError, self).__init__(message)


class SpecialError(Exception):
    """Base exception class for special errors that are needed special handling"""
    def __init__(self, message):
        super(SpecialError, self).__init__(message)


class ParserError(CustomError):
    """ Raised when there is an error while parsing a website"""
    def __init__(self, message):
        super(ParserError, self).__init__(message)


class ErrorConnectToNAO(CustomError):
    """Raised when there is a problem accessing the SauceNAO website"""
    def __init__(self):
        message = 'Cannot acess SauceNAO page'
        super(CustomError, self).__init__(message)


class NoContentAtNAOPage(SpecialError):
    """Raised when there is no suitable content found on the SauceNAO page"""
    def __init__(self):
        message = 'Cannot parse SauceNAO page: no suitable content'
        super(NoContentAtNAOPage, self).__init__(message)


class NoLinksFound(ParserError):
    """Raised when no links are found in the selected cells of SauceNAO table"""
    def __init__(self):
        message = 'No links in selected cells found'
        super(NoLinksFound, self).__init__(message)


class NoSimilarPics(SpecialError):
    """Raised when SauceNao didn't find any similar pictures"""
    def __init__(self):
        message = 'SauceNao didnt found similar pics'
        super(NoSimilarPics, self).__init__(message)


class SearchFailure(CustomError):
    """Raised when the reverse search fails to find any links"""
    def __init__(self):
        message = 'Reverse Search failed: no links found'
        super(SearchFailure, self).__init__(message)


class DataBaseFieldError(CustomError):
    """Raised when a database field is not found"""
    def __init__(self, field_value):
        message = f'This field is not exist: {field_value}'
        super(DataBaseFieldError, self).__init__(message)


class Restricted(CustomError):
    """Raised when trying to access restricted content"""
    def __init__(self, message):
        super(Restricted, self).__init__(f"Restricted content: {message}")


class SpecialContent(SpecialError):
    """Raised when file from user contains special content"""
    def __init__(self):
        message = 'For Anal Carnaval'
        super(SpecialContent, self).__init__(message)


class ApplyThreeReactionsKeyboard(SpecialError):
    """Raised to ignore generated capture from bot and apply special keyboard with reactions to result message"""
    def __init__(self):
        message = 'For Anal Carnaval'
        super(ApplyThreeReactionsKeyboard, self).__init__(message)


class UnsuccefulParsing(CustomError):
    """Raised when all found links have expired or been deleted"""
    def __init__(self):
        message = 'All found links had expired or deleted'
        super(UnsuccefulParsing, self).__init__(message)


class PictureAlreadyPosted(CustomError):
    """Raised when the same picture has already been posted"""
    def __init__(self, message):
        chatlink_message = f't.me{message}'
        super(PictureAlreadyPosted, self).__init__(chatlink_message)


overall_except_certain = [x for x in CustomError.__subclasses__() if
                          x.__name__ not in ['ApplyThreeReactionsKeyboard', 'NoContentAtNAOPage', 'NoSimilarPics']]
