# Copyright 2020 Adap GmbH. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# ==============================================================================
from logging import WARNING, log
from typing import List, Tuple
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import serialization
import base64
from Crypto.Util.Padding import pad, unpad
from Crypto.Protocol.SecretSharing import Shamir
# from crypto.Util.Padding import pad, unpad
# from crypto.Protocol.SecretSharing import Shamir
from concurrent.futures import ThreadPoolExecutor
import os
import random
import pickle
import numpy as np

from numpy.core.fromnumeric import clip

from flwr.common.typing import Weights

# Key Generation  ====================================================================

# Generate private and public key pairs with Cryptography


def generate_key_pairs() -> Tuple[ec.EllipticCurvePrivateKey, ec.EllipticCurvePublicKey]:
    sk = ec.generate_private_key(ec.SECP384R1())
    pk = sk.public_key()
    return sk, pk

# Serialize private key


def private_key_to_bytes(sk: ec.EllipticCurvePrivateKey) -> bytes:
    return sk.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )

# Deserialize private key


def bytes_to_private_key(b: bytes) -> ec.EllipticCurvePrivateKey:
    return serialization.load_pem_private_key(data=b, password=None)

# Serialize public key


def public_key_to_bytes(pk: ec.EllipticCurvePublicKey) -> bytes:
    return pk.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )

# Deserialize public key


def bytes_to_public_key(b: bytes) -> ec.EllipticCurvePublicKey:
    return serialization.load_pem_public_key(data=b)

# Generate shared key by exchange function and key derivation function
# Key derivation function is needed to obtain final shared key of exactly 32 bytes


def generate_shared_key(
    sk: ec.EllipticCurvePrivateKey, pk: ec.EllipticCurvePublicKey
) -> bytes:
    # Generate a 32 byte urlsafe(for fernet) shared key from own private key and another public key
    sharedk = sk.exchange(ec.ECDH(), pk)
    derivedk = HKDF(
        algorithm=hashes.SHA256(),
        length=32,
        salt=None,
        info=None,
    ).derive(sharedk)
    return base64.urlsafe_b64encode(derivedk)

# Authenticated Encryption ================================================================

# Encrypt plaintext with Fernet. Key must be 32 bytes.


def encrypt(key: bytes, plaintext: bytes) -> bytes:
    # key must be url safe
    f = Fernet(key)
    return f.encrypt(plaintext)

# Decrypt ciphertext with Fernet. Key must be 32 bytes.


def decrypt(key: bytes, token: bytes):
    # key must be url safe
    f = Fernet(key)
    return f.decrypt(token)

# Shamir's Secret Sharing Scheme ============================================================

# Create shares with PyCryptodome. Each share must be processed to be a byte string with pickle for RPC


def create_shares(
    secret: bytes, threshold: int, num: int
) -> List[bytes]:
    # return list of list for each user. Each sublist contains a share for a 16 byte chunk of the secret.
    # The int part of the tuple represents the index of the share, not the index of the chunk it is representing.
    secret_padded = pad(secret, 16)
    secret_padded_chunk = [
        (threshold, num, secret_padded[i: i + 16])
        for i in range(0, len(secret_padded), 16)
    ]
    share_list = []
    for i in range(num):
        share_list.append([])

    with ThreadPoolExecutor(max_workers=10) as executor:
        for chunk_shares in executor.map(
            lambda arg: shamir_split(*arg), secret_padded_chunk
        ):
            for idx, share in chunk_shares:
                # idx start with 1
                share_list[idx - 1].append((idx, share))

    for idx, shares in enumerate(share_list):
        share_list[idx] = pickle.dumps(shares)

    return share_list


def shamir_split(threshold: int, num: int, chunk: bytes) -> List[Tuple[int, bytes]]:
    return Shamir.split(threshold, num, chunk)

# Reconstructing secret with PyCryptodome


def combine_shares(share_list: List[bytes]) -> bytes:
    for idx, share in enumerate(share_list):
        share_list[idx] = pickle.loads(share)

    chunk_num = len(share_list[0])
    secret_padded = bytearray(0)
    chunk_shares_list = []
    for i in range(chunk_num):
        chunk_shares = []
        for j in range(len(share_list)):
            chunk_shares.append(share_list[j][i])
        chunk_shares_list.append(chunk_shares)

    with ThreadPoolExecutor(max_workers=10) as executor:
        for chunk in executor.map(shamir_combine, chunk_shares_list):
            secret_padded += chunk

    secret = unpad(secret_padded, 16)
    return bytes(secret)


def shamir_combine(shares: List[Tuple[int, bytes]]) -> bytes:
    return Shamir.combine(shares)


# Random Bytes Generator =============================================================

# Generate random bytes with os. Usually 32 bytes for Fernet
def rand_bytes(num: int = 32) -> bytes:
    return os.urandom(num)

# Pseudo Bytes Generator ==============================================================

# Pseudo random generator for creating masks.


def pseudo_rand_gen(seed: bytes, num_range: int, dimensions_list: List[Tuple]) -> Weights:
    random.seed(seed)
    output = []
    for dimension in dimensions_list:
        flat_arr = np.array([random.randrange(0, num_range)
                            for i in range(np.prod(dimension))])
        modified_arr = np.reshape(flat_arr, dimension)
        output.append(modified_arr)
    return output

# Homomorphic Pseudorandom Generator
def HPRG(seed: bytes, num_range: int, dimensions_list: List[Tuple]) -> Weights:
    random.seed(seed)
    s = random.seed(seed)
    m = dimensions_list
    mod = num_range
    output = []
    homo_output = []
    for dimension in dimensions_list:
        for i in s:
            ### 
            flat_arr = np.array([random.randrange(0, num_range)
                                for i in range(np.prod(dimension))])
            modified_arr = np.reshape(flat_arr, dimension)
            #output.append(modified_arr)
            output = output * modified_arr % num_range
        homo_output.append(output)
    return homo_output
      
# String Concatenation ===================================================================

# Unambiguous string concatenation of source, destination, and two secret shares.
def share_keys_plaintext_concat(source: int, destination: int, b_share: bytes, sk_share: bytes) -> bytes:
    return pickle.dumps([source, destination, b_share, sk_share])

# Unambiguous string splitting to obtain source, destination and two secret shares.


def share_keys_plaintext_separate(plaintext: bytes) -> Tuple[int, int, bytes, bytes]:
    return tuple(pickle.loads(plaintext))

# Weight Quantization ======================================================================

# Clip weight vector to [-clipping_range, clipping_range]
# Transform weight vector to range [0, target_range] and take floor
# If final value is target_range, take 1 from it so it is an integer from 0 to target_range-1


def quantize(weight: Weights, clipping_range: float, target_range: int) -> Weights:
    quantized_list = []
    check_clipping_range(weight, clipping_range)
    f = np.vectorize(lambda x:  min(target_range-1, (sorted((-clipping_range, x, clipping_range))
                                                     [1]+clipping_range)*target_range/(2*clipping_range)))
    for arr in weight:
        quantized_list.append(f(arr).astype(int))
    return quantized_list

# Quick check that all numbers are within the clipping range
# Throw warning if there exists numbers that exceed it


def check_clipping_range(weight: Weights, clipping_range: float):
    for arr in weight:
        for x in arr.flatten():
            if(x < -clipping_range or x > clipping_range):
                log(WARNING,
                    f"There are some numbers in the local vector that exceeds clipping range. Please increase the clipping range to account for value {x}")
                return

# Transform weight vector to range [-clipping_range, clipping_range]
# Convert to float


def reverse_quantize(weight: Weights, clipping_range: float, target_range: int) -> Weights:
    reverse_quantized_list = []
    f = np.vectorize(lambda x:  (x)/target_range*(2*clipping_range)-clipping_range)
    for arr in weight:
        reverse_quantized_list.append(f(arr.astype(float)))
    return reverse_quantized_list

# Weight Manipulation =============================================================

# Combine factor with weights


def factor_weights_combine(weights_factor: int, weights: Weights) -> Weights:
    return [np.array([weights_factor])]+weights

# Extract factor from weights


def factor_weights_extract(weights: Weights) -> Tuple[int, Weights]:
    return weights[0][0], weights[1:]

# Create dimensions list of each element in weights


def weights_shape(weights: Weights) -> List[Tuple]:
    return [arr.shape for arr in weights]

# Generate zero weights based on dimensions list


def weights_zero_generate(dimensions_list: List[Tuple]) -> Weights:
    return [np.zeros(dimensions) for dimensions in dimensions_list]

# Add two weights together


def weights_addition(a: Weights, b: Weights) -> Weights:
    return [a[idx]+b[idx] for idx in range(len(a))]

# Subtract one weight from the other


def weights_subtraction(a: Weights, b: Weights) -> Weights:
    return [a[idx]-b[idx] for idx in range(len(a))]

# Take mod of a weights with an integer


def weights_mod(a: Weights, b: int) -> Weights:
    return [a[idx] % b for idx in range(len(a))]


# Multiply weight by an integer


def weights_multiply(a: Weights, b: int) -> Weights:
    return [a[idx] * b for idx in range(len(a))]

# Divide weight by an integer


def weights_divide(a: Weights, b: int) -> Weights:
    return [a[idx] / b for idx in range(len(a))]
