from flaskr.db_tables import UserCredentials
from .user_getters import get_user_by_email

from flask import current_app
import sqlalchemy
from argon2 import PasswordHasher, Type
from werkzeug.security import generate_password_hash, check_password_hash

import os
import base64


passwordHasher = PasswordHasher(
    time_cost=6, memory_cost=65536, parallelism=2, type=Type.ID
)


def valid_login(usermail: str, *, password=None, passHash=None) -> UserCredentials:
    """
    Check if the provided login information make for a successful login.

    Parameters
    ----------
    usermail : str
        Email of the user.
    password : str, optional
        Password of the user.
    passHash : str, optional
        Hash of the password. From Argon2 ID using user's salt.

    Returns
    -------
    UserCredentials : logged-in user

    Raises
    ------
    TypeError
        If the user is not registered.
    ValueError
        If the password is invalid.
    """
    usermail = usermail.lower()

    # Get the user's salt from the database
    user = get_user_by_email(usermail)

    if user is None:  # User not found
        raise TypeError("User is not registered")

    # If only the password is provided, then we need to hash it before comparing
    if passHash is None:
        # Calculate the hash of the password
        # with Argon2
        decoded_salt = base64.b64decode(user.salt)
        passHash = passwordHasher.hash(password, salt=decoded_salt)

    # Check if the passHashes coincide (db one is rehashed)
    if check_password_hash(user.passhash, passHash):
        return user
    else:
        raise ValueError("Invalid password")


def register_user(
    usermail: str,
    username: str,
    *,
    password: str = None,
    passHash: str = None,
    salt: str = None,
) -> None:
    """
    Register a user in the database.

    Either provide a password or a passHash and its salt.

    Parameters
    ----------
    usermail : str
        Email of the user.
    password : str, optional
        Password of the user.
    passHash : str, optional
        Hash of the password.
    salt : str, optional
        Salt used to hash the password.

    Raises
    ------
    ValueError
        If the user already exists.
    AssertionError
        If both password and (passHash or salt) is provided.
    """
    usermail = usermail.lower()

    # Check if the user already exists
    with current_app.Session() as sql_db:
        user = sql_db.query(UserCredentials).filter_by(email=usermail).first()
    if user is not None:
        raise ValueError("User already exists")

    # If the password is provided, create a salt and hash it
    if password:
        assert (
            passHash is None
        ), "Either password or passHash must be provided, not both."
        assert (
            salt is None
        ), "Do not provide 'salt'. It is created by the server if password is provided."
        # Create random salt
        salt = os.urandom(16)  # 16 bytes
        # Calculate the hash of the password
        # with Argon2
        passHash = passwordHasher.hash(password, salt=salt)
        # Encode the salt in base64
        salt = base64.b64encode(salt).decode("utf-8")
    elif not (passHash and salt):
        # password nor (passHash and salt) not provided
        raise RuntimeError("Either password or (passHash and salt) must be provided")

    # Create the user
    # rehash the hash, so locally we don't store the same hash as client apps
    passHash = generate_password_hash(passHash)
    try:
        new_user = UserCredentials(
            username=username,
            email=usermail,
            passhash=passHash,
            salt=salt,
        )
    except sqlalchemy.exc.DataError as e:
        raise RuntimeError("Invalid data provided") from e

    with current_app.Session() as sql_db:
        sql_db.add(new_user)
        sql_db.commit()