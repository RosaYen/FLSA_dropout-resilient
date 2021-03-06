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
"""Flower type definitions."""


from dataclasses import dataclass
from typing import Dict, List, Optional, Union

import numpy as np

Weights = List[np.ndarray]

# The following union type contains Python types corresponding to ProtoBuf types that
# ProtoBuf considers to be "Scalar Value Types", even though some of them arguably do
# not conform to other definitions of what a scalar is. Source:
# https://developers.google.com/protocol-buffers/docs/overview#scalar
Scalar = Union[bool, bytes, float, int, str]

Metrics = Dict[str, Scalar]


@dataclass
class Parameters:
    """Model parameters."""

    tensors: List[bytes]
    tensor_type: str


@dataclass
class ParametersRes:
    """Response when asked to return parameters."""

    parameters: Parameters


@dataclass
class FitIns:
    """Fit instructions for a client."""

    parameters: Parameters
    config: Dict[str, Scalar]


@dataclass
class FitRes:
    """Fit response from a client."""

    parameters: Parameters
    num_examples: int
    num_examples_ceil: Optional[int] = None  # Deprecated
    fit_duration: Optional[float] = None  # Deprecated
    metrics: Optional[Metrics] = None


@dataclass
class EvaluateIns:
    """Evaluate instructions for a client."""

    parameters: Parameters
    config: Dict[str, Scalar]


@dataclass
class EvaluateRes:
    """Evaluate response from a client."""

    loss: float
    num_examples: int
    accuracy: Optional[float] = None  # Deprecated
    metrics: Optional[Metrics] = None


@dataclass
class Reconnect:
    """Reconnect message from server to client."""

    seconds: Optional[int]


@dataclass
class Disconnect:
    """Disconnect message from client to server."""

    reason: str


@dataclass
class SetupParamIns:
    sec_agg_param_dict: Dict[str, Scalar]


@dataclass
class SetupParamRes:
    pass


@dataclass
class AskKeysIns:
    pass


@dataclass
class AskKeysRes:
    """Ask Keys Stage Response from client to server"""

    pk1: bytes
    pk2: bytes


@dataclass
class ShareKeysIns:
    public_keys_dict: Dict[int, AskKeysRes]


@dataclass
class ShareKeysPacket:
    source: int
    destination: int
    ciphertext: bytes


@dataclass
class ShareKeysRes:
    share_keys_res_list: List[ShareKeysPacket]


@dataclass
class AskVectorsIns:
    ask_vectors_in_list: List[ShareKeysPacket]
    fit_ins: FitIns


@dataclass
class AskVectorsRes:
    parameters: Parameters


@dataclass
class UnmaskVectorsIns:
    available_clients: List[int]
    dropout_clients: List[int]


@dataclass
class UnmaskVectorsRes:
    share_dict: Dict[int, bytes]
