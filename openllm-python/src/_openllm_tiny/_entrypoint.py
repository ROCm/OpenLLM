from __future__ import annotations

import os, logging, traceback, pathlib, sys, fs, click, enum, inflection, bentoml, orjson, openllm, openllm_core, platform, typing as t
from ._helpers import recommended_instance_type
from openllm_core.utils import (
  DEBUG,
  DEBUG_ENV_VAR,
  QUIET_ENV_VAR,
  SHOW_CODEGEN,
  check_bool_env,
  compose,
  first_not_none,
  dantic,
  gen_random_uuid,
  get_debug_mode,
  get_quiet_mode,
  normalise_model_name,
)
from openllm_core._typing_compat import (
  LiteralQuantise,
  LiteralSerialisation,
  LiteralDtype,
  get_literal_args,
  TypedDict,
)
from openllm_cli import termui

logger = logging.getLogger(__name__)

OPENLLM_FIGLET = """
 ██████╗ ██████╗ ███████╗███╗   ██╗██╗     ██╗     ███╗   ███╗
██╔═══██╗██╔══██╗██╔════╝████╗  ██║██║     ██║     ████╗ ████║
██║   ██║██████╔╝█████╗  ██╔██╗ ██║██║     ██║     ██╔████╔██║
██║   ██║██╔═══╝ ██╔══╝  ██║╚██╗██║██║     ██║     ██║╚██╔╝██║
╚██████╔╝██║     ███████╗██║ ╚████║███████╗███████╗██║ ╚═╝ ██║
 ╚═════╝ ╚═╝     ╚══════╝╚═╝  ╚═══╝╚══════╝╚══════╝╚═╝     ╚═╝.
"""
_PACKAGE_NAME = 'openllm'
_SERVICE_FILE = pathlib.Path(os.path.abspath(__file__)).parent / '_service.py'
_SERVICE_VARS = '''\
# fmt: off
# GENERATED BY 'openllm build {__model_id__}'. DO NOT EDIT
import orjson,openllm_core.utils as coreutils
model_id='{__model_id__}'
model_name='{__model_name__}'
quantise=coreutils.getenv('quantize',default='{__model_quantise__}',var=['QUANTISE'])
serialisation=coreutils.getenv('serialization',default='{__model_serialization__}',var=['SERIALISATION'])
dtype=coreutils.getenv('dtype', default='{__model_dtype__}', var=['TORCH_DTYPE'])
trust_remote_code=coreutils.check_bool_env("TRUST_REMOTE_CODE",{__model_trust_remote_code__})
max_model_len=orjson.loads(coreutils.getenv('max_model_len', default=orjson.dumps({__max_model_len__})))
gpu_memory_utilization=orjson.loads(coreutils.getenv('gpu_memory_utilization', default=orjson.dumps({__gpu_memory_utilization__}), var=['GPU_MEMORY_UTILISATION']))
services_config=orjson.loads(coreutils.getenv('services_config',"""{__services_config__}"""))
'''


class ItemState(enum.Enum):
  NOT_FOUND = 'NOT_FOUND'
  ADDED = 'ADDED'
  EXISTS = 'EXISTS'
  OVERWRITE = 'OVERWRITE'


def parse_device_callback(
  _: click.Context, param: click.Parameter, value: tuple[tuple[str], ...] | None
) -> t.Tuple[str, ...] | None:
  if value is None:
    return value
  el: t.Tuple[str, ...] = tuple(i for k in value for i in k)
  # NOTE: --device all is a special case
  if len(el) == 1 and el[0] == 'all':
    return tuple(map(str, openllm.utils.available_devices()))
  return el


@click.group(context_settings=termui.CONTEXT_SETTINGS, name='openllm')
@click.version_option(
  None,
  '--version',
  '-v',
  package_name=_PACKAGE_NAME,
  message=f'{_PACKAGE_NAME}, %(version)s\nPython ({platform.python_implementation()}) {platform.python_version()}',
)
def cli() -> None:
  """\b
   ██████╗ ██████╗ ███████╗███╗   ██╗██╗     ██╗     ███╗   ███╗
  ██╔═══██╗██╔══██╗██╔════╝████╗  ██║██║     ██║     ████╗ ████║
  ██║   ██║██████╔╝█████╗  ██╔██╗ ██║██║     ██║     ██╔████╔██║
  ██║   ██║██╔═══╝ ██╔══╝  ██║╚██╗██║██║     ██║     ██║╚██╔╝██║
  ╚██████╔╝██║     ███████╗██║ ╚████║███████╗███████╗██║ ╚═╝ ██║
   ╚═════╝ ╚═╝     ╚══════╝╚═╝  ╚═══╝╚══════╝╚══════╝╚═╝     ╚═╝.

  \b
  An open platform for operating large language models in production.
  Fine-tune, serve, deploy, and monitor any LLMs with ease.
  """


def optimization_decorator(fn):
  # NOTE: return device, quantize, serialisation, dtype, max_model_len, gpu_memory_utilization
  optimization = [
    click.option(
      '--device',
      type=dantic.CUDA,
      multiple=True,
      envvar='CUDA_VISIBLE_DEVICES',
      callback=parse_device_callback,
      help='Assign GPU devices (if available)',
      show_envvar=True,
    ),
    click.option(
      '--dtype',
      type=str,
      envvar='DTYPE',
      default='auto',
      help="Optional dtype for casting tensors for running inference ['float16', 'float32', 'bfloat16', 'int8', 'int16']",
    ),
    click.option(
      '--quantise',
      '--quantize',
      'quantize',
      type=str,
      default=None,
      envvar='QUANTIZE',
      show_envvar=True,
      help="""Dynamic quantization for running this LLM.

    The following quantization strategies are supported:

    - ``int8``: ``LLM.int8`` for [8-bit](https://arxiv.org/abs/2208.07339) quantization.

    - ``int4``: ``SpQR`` for [4-bit](https://arxiv.org/abs/2306.03078) quantization.

    - ``gptq``: ``GPTQ`` [quantization](https://arxiv.org/abs/2210.17323)

    - ``awq``: ``AWQ`` [AWQ: Activation-aware Weight Quantization](https://arxiv.org/abs/2306.00978)

    - ``squeezellm``: ``SqueezeLLM`` [SqueezeLLM: Dense-and-Sparse Quantization](https://arxiv.org/abs/2306.07629)

    > [!NOTE] that the model can also be served with quantized weights.
    """,
    ),
    click.option(
      '--serialisation',
      '--serialization',
      'serialisation',
      type=click.Choice(get_literal_args(LiteralSerialisation)),
      default=None,
      show_default=True,
      show_envvar=True,
      envvar='OPENLLM_SERIALIZATION',
      help="""Serialisation format for save/load LLM.

    Currently the following strategies are supported:

    - ``safetensors``: This will use safetensors format, which is synonymous to ``safe_serialization=True``.

    > [!NOTE] Safetensors might not work for every cases, and you can always fallback to ``legacy`` if needed.

    - ``legacy``: This will use PyTorch serialisation format, often as ``.bin`` files. This should be used if the model doesn't yet support safetensors.
    """,
    ),
    click.option(
      '--max-model-len',
      '--max_model_len',
      'max_model_len',
      type=int,
      default=None,
      help='Maximum sequence length for the model. If not specified, we will use the default value from the model config.',
    ),
    click.option(
      '--gpu-memory-utilization',
      '--gpu_memory_utilization',
      'gpu_memory_utilization',
      default=0.9,
      help='The percentage of GPU memory to be used for the model executor',
    ),
  ]
  return compose(*optimization)(fn)


def shared_decorator(fn):
  shared = [
    click.argument(
      'model_id', type=click.STRING, metavar='[REMOTE_REPO/MODEL_ID | /path/to/local/model]', required=True
    ),
    click.option(
      '--revision',
      '--bentomodel-version',
      '--model-version',
      'model_version',
      type=click.STRING,
      default=None,
      help='Optional model revision to save for this model. It will be inferred automatically from model-id.',
    ),
    click.option(
      '--model-tag',
      '--bentomodel-tag',
      'model_tag',
      type=click.STRING,
      default=None,
      help='Optional bentomodel tag to save for this model. It will be generated automatically based on model_id and model_version if not specified.',
    ),
  ]
  return compose(*shared)(fn)


@cli.command(name='start')
@shared_decorator
@click.option('--timeout', type=int, default=360000, help='Timeout for the model executor in seconds')
@optimization_decorator
def start_command(
  model_id: str,
  model_version: str | None,
  model_tag: str | None,
  timeout: int,
  device: t.Tuple[str, ...],
  quantize: LiteralQuantise | None,
  serialisation: LiteralSerialisation | None,
  dtype: LiteralDtype | t.Literal['auto', 'float'],
  max_model_len: int | None,
  gpu_memory_utilization: float,
):
  """Start any LLM as a REST server.

  \b
  ```bash
  $ openllm <start|start-http> <model_id> --<options> ...
  ```
  """
  import transformers

  from _bentoml_impl.server import serve_http
  from bentoml._internal.service.loader import load
  from bentoml._internal.log import configure_server_logging

  configure_server_logging()

  trust_remote_code = check_bool_env('TRUST_REMOTE_CODE', False)
  try:
    # if given model_id is a private model, then we can use it directly
    bentomodel = bentoml.models.get(model_id.lower())
    model_id = bentomodel.path
  except (ValueError, bentoml.exceptions.NotFound):
    bentomodel = None
  config = transformers.AutoConfig.from_pretrained(model_id, trust_remote_code=trust_remote_code)
  for arch in config.architectures:
    if arch in openllm_core.AutoConfig._architecture_mappings:
      model_name = openllm_core.AutoConfig._architecture_mappings[arch]
      break
  else:
    raise RuntimeError(f'Failed to determine config class for {model_id}')

  llm_config = openllm_core.AutoConfig.for_model(model_name).model_construct_env()
  if serialisation is None:
    serialisation = llm_config['serialisation']

  # TODO: support LoRA adapters
  os.environ.update({
    QUIET_ENV_VAR: str(openllm.utils.get_quiet_mode()),
    DEBUG_ENV_VAR: str(openllm.utils.get_debug_mode()),
    'MODEL_ID': model_id,
    'MODEL_NAME': model_name,
    'SERIALIZATION': serialisation,
    'OPENLLM_CONFIG': llm_config.model_dump_json(),
    'DTYPE': dtype,
    'TRUST_REMOTE_CODE': str(trust_remote_code),
    'GPU_MEMORY_UTILIZATION': orjson.dumps(gpu_memory_utilization).decode(),
    'SERVICES_CONFIG': orjson.dumps(
      dict(
        resources={'gpu' if device else 'cpu': len(device) if device else 'cpu_count'}, traffic=dict(timeout=timeout)
      )
    ).decode(),
  })
  if max_model_len is not None:
    os.environ['MAX_MODEL_LEN'] = orjson.dumps(max_model_len)
  if quantize:
    os.environ['QUANTIZE'] = str(quantize)

  working_dir = os.path.abspath(os.path.dirname(__file__))
  if sys.path[0] != working_dir:
    sys.path.insert(0, working_dir)
  load('.', working_dir=working_dir).inject_config()
  serve_http('.', working_dir=working_dir, reload=check_bool_env('RELOAD', default=False), development_mode=DEBUG)


def construct_python_options(llm_config, llm_fs):
  from bentoml._internal.bento.build_config import PythonOptions
  from openllm.bundle._package import build_editable

  # TODO: Add this line back once 0.5 is out, for now depends on OPENLLM_DEV_BUILD
  # packages = ['scipy', 'bentoml[tracing]>=1.2.8', 'openllm[vllm]>0.4', 'vllm>=0.3']
  packages = ['scipy', 'bentoml[tracing]>=1.2.8', 'vllm>=0.3']
  if llm_config['requirements'] is not None:
    packages.extend(llm_config['requirements'])
  built_wheels = [build_editable(llm_fs.getsyspath('/'), p) for p in ('openllm_core', 'openllm_client', 'openllm')]
  return PythonOptions(
    packages=packages,
    wheels=[llm_fs.getsyspath(f"/{i.split('/')[-1]}") for i in built_wheels] if all(i for i in built_wheels) else None,
    lock_packages=False,
  )


class EnvironmentEntry(TypedDict):
  name: str
  value: str


@cli.command(name='build', context_settings={'token_normalize_func': inflection.underscore})
@shared_decorator
@click.option(
  '--bento-version',
  type=str,
  default=None,
  help='Optional bento version for this BentoLLM. Default is the the model revision.',
)
@click.option(
  '--bento-tag',
  type=str,
  default=None,
  help='Optional bento version for this BentoLLM. Default is the the model revision.',
)
@click.option('--overwrite', is_flag=True, help='Overwrite existing Bento for given LLM if it already exists.')
@click.option('--timeout', type=int, default=360000, help='Timeout for the model executor in seconds')
@optimization_decorator
@click.option(
  '-o',
  '--output',
  type=click.Choice(['tag', 'default']),
  default='default',
  show_default=True,
  help="Output log format. '-o tag' to display only bento tag.",
)
@click.pass_context
def build_command(
  ctx: click.Context,
  /,
  model_id: str,
  model_version: str | None,
  model_tag: str | None,
  bento_version: str | None,
  bento_tag: str | None,
  overwrite: bool,
  device: t.Tuple[str, ...],
  timeout: int,
  quantize: LiteralQuantise | None,
  serialisation: LiteralSerialisation | None,
  dtype: LiteralDtype | t.Literal['auto', 'float'],
  max_model_len: int | None,
  gpu_memory_utilization: float,
  output: t.Literal['default', 'tag'],
):
  """Package a given models into a BentoLLM.

  \b
  ```bash
  $ openllm build google/flan-t5-large
  ```

  \b
  > [!NOTE]
  > To run a container built from this Bento with GPU support, make sure
  > to have https://github.com/NVIDIA/nvidia-container-toolkit install locally.

  \b
  > [!IMPORTANT]
  > To build the bento with compiled OpenLLM, make sure to prepend HATCH_BUILD_HOOKS_ENABLE=1. Make sure that the deployment
  > target also use the same Python version and architecture as build machine.
  """
  import transformers
  from bentoml._internal.configuration.containers import BentoMLContainer
  from bentoml._internal.configuration import set_quiet_mode
  from bentoml._internal.log import configure_logging
  from bentoml._internal.bento.build_config import BentoBuildConfig
  from bentoml._internal.bento.build_config import DockerOptions
  from bentoml._internal.bento.build_config import ModelSpec

  if output == 'tag':
    set_quiet_mode(True)
    configure_logging()

  trust_remote_code = check_bool_env('TRUST_REMOTE_CODE', False)
  try:
    # if given model_id is a private model, then we can use it directly
    bentomodel = bentoml.models.get(model_id.lower())
    model_id = bentomodel.path
    _revision = bentomodel.tag.version
  except (ValueError, bentoml.exceptions.NotFound):
    bentomodel = None
    _revision = None

  config = transformers.AutoConfig.from_pretrained(model_id, trust_remote_code=trust_remote_code)
  for arch in config.architectures:
    if arch in openllm_core.AutoConfig._architecture_mappings:
      model_name = openllm_core.AutoConfig._architecture_mappings[arch]
      break
  else:
    raise RuntimeError(f'Failed to determine config class for {model_id}')

  llm_config: openllm_core.LLMConfig = openllm_core.AutoConfig.for_model(model_name).model_construct_env()

  _revision = first_not_none(_revision, getattr(config, '_commit_hash', None), default=gen_random_uuid())
  if serialisation is None:
    termui.warning(
      f"Serialisation format is not specified. Defaulting to '{llm_config['serialisation']}'. Your model might not work with this format. Make sure to explicitly specify the serialisation format."
    )
    serialisation = llm_config['serialisation']

  if bento_tag is None:
    _bento_version = first_not_none(bento_version, default=_revision)
    bento_tag = bentoml.Tag.from_taglike(f'{normalise_model_name(model_id)}-service:{_bento_version}'.lower().strip())
  else:
    bento_tag = bentoml.Tag.from_taglike(bento_tag)

  state = ItemState.NOT_FOUND
  try:
    bento = bentoml.get(bento_tag)
    if overwrite:
      bentoml.delete(bento_tag)
      state = ItemState.OVERWRITE
      raise bentoml.exceptions.NotFound(f'Rebuilding existing Bento {bento_tag}') from None
    state = ItemState.EXISTS
  except bentoml.exceptions.NotFound:
    if state != ItemState.OVERWRITE:
      state = ItemState.ADDED

    labels = {'library': 'vllm'}
    service_config = dict(
      resources={
        'gpu' if device else 'cpu': len(device) if device else 'cpu_count',
        'gpu_type': recommended_instance_type(model_id, bentomodel),
      },
      traffic=dict(timeout=timeout),
    )
    with fs.open_fs(f'temp://llm_{gen_random_uuid()}') as llm_fs:
      logger.debug('Generating service vars %s (dir=%s)', model_id, llm_fs.getsyspath('/'))
      script = _SERVICE_VARS.format(
        __model_id__=model_id,
        __model_name__=model_name,
        __model_quantise__=quantize,
        __model_dtype__=dtype,
        __model_serialization__=serialisation,
        __model_trust_remote_code__=trust_remote_code,
        __max_model_len__=max_model_len,
        __gpu_memory_utilization__=gpu_memory_utilization,
        __services_config__=orjson.dumps(service_config).decode(),
      )
      models = []
      if bentomodel is not None:
        models.append(ModelSpec.from_item({'tag': str(bentomodel.tag), 'alias': bentomodel.tag.name}))
      if SHOW_CODEGEN:
        logger.info('Generated _service_vars.py:\n%s', script)
      llm_fs.writetext('_service_vars.py', script)
      with _SERVICE_FILE.open('r') as f:
        service_src = f.read()
        llm_fs.writetext(llm_config['service_name'], service_src)
      bento = bentoml.Bento.create(
        version=bento_tag.version,
        build_ctx=llm_fs.getsyspath('/'),
        build_config=BentoBuildConfig(
          service=f"{llm_config['service_name']}:LLMService",
          name=bento_tag.name,
          labels=labels,
          models=models,
          envs=[
            EnvironmentEntry(name='OPENLLM_CONFIG', value=llm_config.model_dump_json()),
            EnvironmentEntry(name='NVIDIA_DRIVER_CAPABILITIES', value='compute,utility'),
          ],
          description=f"OpenLLM service for {llm_config['start_name']}",
          include=list(llm_fs.walk.files()),
          exclude=['/venv', '/.venv', '__pycache__/', '*.py[cod]', '*$py.class'],
          python=construct_python_options(llm_config, llm_fs),
          docker=DockerOptions(python_version='3.11'),
        ),
      ).save(bento_store=BentoMLContainer.bento_store.get(), model_store=BentoMLContainer.model_store.get())
  except Exception as err:
    traceback.print_exc()
    raise click.ClickException('Exception caught while building BentoLLM:\n' + str(err)) from err

  if output == 'tag':
    termui.echo(f'__tag__:{bento.tag}')
    return

  if not get_quiet_mode():
    if state != ItemState.EXISTS:
      termui.info(f"Successfully built Bento '{bento.tag}'.\n")
    elif not overwrite:
      termui.warning(f"Bento for '{model_id}' already exists [{bento}]. To overwrite it pass '--overwrite'.\n")
    if not get_debug_mode():
      termui.echo(OPENLLM_FIGLET)
      termui.echo('📖 Next steps:\n', nl=False)
      termui.echo(f'☁️  Deploy to BentoCloud:\n  $ bentoml deploy {bento.tag} -n ${{DEPLOYMENT_NAME}}\n', nl=False)
      termui.echo(
        f'☁️  Update existing deployment on BentoCloud:\n  $ bentoml deployment update --bento {bento.tag} ${{DEPLOYMENT_NAME}}\n',
        nl=False,
      )
      termui.echo(f'🐳 Containerize BentoLLM:\n  $ bentoml containerize {bento.tag} --opt progress=plain\n', nl=False)

  return bento


if __name__ == '__main__':
  cli()
