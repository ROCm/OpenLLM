# Copyright 2023 BentoML Team. All rights reserved.
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

from __future__ import annotations

import typing as t
from collections import OrderedDict

import openllm

from .configuration_auto import CONFIG_MAPPING_NAMES
from .factory import _BaseAutoRunnerFactory, _LazyAutoMapping

MODEL_TF_MAPPING_NAMES = OrderedDict([("flan_t5", "TFFlanT5")])

MODEL_TF_WITH_TOKENIZER_MAPPING_NAMES = OrderedDict([("flan_t5", "FlaxFlanT5WithTokenizer")])

MODEL_TF_MAPPING = _LazyAutoMapping[type[openllm.LLMConfig], type[openllm.LLMRunnable[t.Any, t.Any]]](
    CONFIG_MAPPING_NAMES, MODEL_TF_MAPPING_NAMES
)

MODEL_TF_WITH_TOKENIZER_MAPPING = _LazyAutoMapping[type[openllm.LLMConfig], type[openllm.LLMRunnable[t.Any, t.Any]]](
    CONFIG_MAPPING_NAMES, MODEL_TF_WITH_TOKENIZER_MAPPING_NAMES
)


class TFLLM(_BaseAutoRunnerFactory[type[openllm.LLMRunnable[t.Any, t.Any]]]):
    _model_mapping = MODEL_TF_MAPPING


class TFLLMWithTokenizer(_BaseAutoRunnerFactory[type[openllm.LLMRunnable[t.Any, t.Any]]]):
    _model_mapping = MODEL_TF_WITH_TOKENIZER_MAPPING
