import secrets

from pwdlib import PasswordHash
from pwdlib.hashers.argon2 import Argon2Hasher

password_hash = PasswordHash((Argon2Hasher(),))


def hash_password(password: str) -> str:
    return password_hash.hash(password)


def verify_password(password: str, hashed_password: str) -> bool:
    return password_hash.verify(password, hashed_password)


UNMATCHABLE_HASH = hash_password(secrets.token_urlsafe(32))


def equalize_verification_time(password: str) -> None:
    verify_password(password, UNMATCHABLE_HASH)
