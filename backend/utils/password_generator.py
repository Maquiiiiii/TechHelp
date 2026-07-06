import secrets
import string

def generate_secure_password(length: int = 10) -> str:
    """
    Generates a secure random password combining uppercase, lowercase, digits, and special characters.
    """
    if length < 8:
        length = 8
    # Conjunto de caracteres seguros definidos
    lowercase = string.ascii_lowercase
    uppercase = string.ascii_uppercase
    digits = string.digits
    symbols = "!@#$%^&*"
    all_chars = lowercase + uppercase + digits + symbols
    
    while True:
        password = ''.join(secrets.choice(all_chars) for _ in range(length))
        if (any(c in lowercase for c in password)
                and any(c in uppercase for c in password)
                and any(c in digits for c in password)
                and any(c in symbols for c in password)):
            return password