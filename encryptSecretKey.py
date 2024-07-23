from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
import os
import base64
import json
import getpass

def encrypt_secret_key(secret_key: str, password: str) -> str:
    salt = os.urandom(16)
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=100000,
        backend=default_backend()
    )
    key = kdf.derive(password.encode())

    aesgcm = AESGCM(key)
    nonce = os.urandom(12)
    encrypted_key = aesgcm.encrypt(nonce, secret_key.encode(), None)
    
    encrypted_data = {
        'salt': base64.b64encode(salt).decode(),
        'nonce': base64.b64encode(nonce).decode(),
        'encrypted_key': base64.b64encode(encrypted_key).decode()
    }

    return json.dumps(encrypted_data)

def main():
    secret_key = input("Enter your secret key: ")
    password = getpass.getpass("Enter a password to encrypt the secret key: ")

    encrypted_key = encrypt_secret_key(secret_key, password)
    
    config_path = os.path.join(os.path.dirname(__file__), "config.json")
    with open(config_path, 'r') as f:
        config = json.load(f)

    config["secret_key"] = encrypted_key
    
    with open(config_path, 'w') as f:
        json.dump(config, f, indent=4)

    print("Secret key encrypted and saved to config.json")

if __name__ == "__main__":
    main()
