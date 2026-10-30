"""One official KServe model binding for every accepted backend."""
import asyncio
import threading

from kserve import Model, InferRequest, InferResponse
from kserve.errors import InvalidInput, ModelNotReady

from .contract import COVARIATES, OPTIONS, encode_forecast, parse_forecast
from .upstream import Settings, UpstreamForecaster


class Unavailable(ModelNotReady):
    """Supply the public error reason required by this SDK's gRPC interceptor."""
    def __init__(self, reason):
        super().__init__('timestral',reason)
        self.reason = reason


class TimestralModel(Model):
    def __init__(self, settings: Settings, loader=UpstreamForecaster.load):
        super().__init__('timestral')
        self.settings = settings
        self._loader = loader
        self._backend = None
        self._slot = threading.Lock()

    def load(self):
        self.ready = False
        self._backend = None
        try:
            self._backend = self._loader(self.settings)
        except Exception:
            raise RuntimeError('Timestral model initialization failed') from None
        self.ready = True
        return True

    def get_input_types(self):
        return [
            {'name':'context','datatype':'FP32','shape':[-1,-1,-1]},
            {'name':'observation_mask','datatype':'BOOL','shape':[-1,-1,-1]},
            {'name':'prediction_length','datatype':'INT64','shape':[1]},
            *({'name':name,'datatype':'FP64' if name.startswith('categorical') else 'FP32','shape':[-1,-1,-1]} for name in COVARIATES),
            *({'name':name+'_mask','datatype':'BOOL','shape':[-1,-1,-1]} for name in COVARIATES),
            *({'name':name,'datatype':'BOOL','shape':[1]} for name in OPTIONS)]

    def get_output_types(self):
        return [{'name':'quantiles','datatype':'FP32','shape':[-1,-1,-1,21]},
                {'name':'median','datatype':'FP32','shape':[-1,-1,-1]},
                {'name':'quantile_levels','datatype':'FP32','shape':[21]}]

    async def predict(self, payload: InferRequest, headers=None):
        if not self.ready: raise Unavailable('model is not ready')
        if not isinstance(payload,InferRequest): raise InvalidInput('standard V2 tensors are required')
        if payload.model_name != self.name or (payload.model_version and payload.model_version != self.settings.model_revision):
            raise InvalidInput('request identity does not match the loaded model revision')
        outputs = payload.request_outputs
        if outputs:
            names = [output.name for output in outputs]
            if len(names) != len(set(names)) or not set(names) <= {'quantiles','median','quantile_levels'}:
                raise InvalidInput('unknown or duplicate requested output')
        # The SDK has already decoded transport bytes. Inspect Content-Length when
        # present; the gateway must bound streamed HTTP bodies before SDK decoding.
        if headers and 'content-length' in headers:
            try: length = int(headers['content-length'])
            except (ValueError,TypeError): raise InvalidInput('invalid content length') from None
            if length < 0 or length > 8388608: raise InvalidInput('request byte budget exceeded')
        inputs = parse_forecast(payload)
        if not self._slot.acquire(blocking=False): raise Unavailable('inference capacity is occupied')
        backend = self._backend
        started = threading.Event()

        def compute():
            started.set()
            try:
                result = backend.forecast(inputs)
                expected = (*inputs.context.shape[:2],inputs.prediction_length,21)
                if result.quantiles.shape != expected: raise RuntimeError('invalid backend result shape')
                return result
            finally:
                # The computation, not its waiter, owns capacity. This also works
                # when the caller or its asyncio task has already been cancelled.
                self._slot.release()

        task = asyncio.create_task(asyncio.to_thread(compute))
        # Retrieve detached-task exceptions without logging inputs or secrets.
        def consume(done):
            if not done.cancelled():
                error = done.exception()
                # If executor submission failed, no computation owns the slot.
                # A cancelled task is deliberately excluded: its worker may run.
                if error is not None and not started.is_set():
                    self._slot.release()
        task.add_done_callback(consume)
        try:
            result = await asyncio.shield(task)
            response = encode_forecast(result,payload.id or '',self.name)
        except InvalidInput:
            raise
        except asyncio.CancelledError:
            raise
        except Exception:
            raise RuntimeError('forecast inference failed') from None
        response.parameters.update(model_id=self.settings.model_id,
                                   model_revision=self.settings.model_revision,
                                   backend=self.settings.backend)
        if self.settings.backend == 'openvino':
            response.parameters.update(experimental=True,max_context=256,per_shot_horizon_patches=5)
            digest = getattr(self._backend,'artifact_manifest_sha256',None)
            if digest is not None:
                response.parameters['artifact_manifest_sha256'] = digest
        if outputs:
            wanted = {output.name for output in outputs}
            response.outputs = [output for output in response.outputs if output.name in wanted]
        return InferResponse(response.id, self.name, response.outputs,
                             model_version=self.settings.model_revision,
                             parameters=response.parameters,
                             from_grpc=payload.from_grpc,
                             use_binary_outputs=payload.use_binary_outputs,
                             requested_outputs=outputs)
