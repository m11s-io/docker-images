"""Weight-free transport diagnostic; not numerical or hardware acceptance."""
import numpy as np
from kserve import ModelServer, model_server
from serving.errors import configure_transport_errors
from serving.contract import ForecastResult
from serving.kserve_model import TimestralModel
from serving.upstream import Settings

class Backend:
    def forecast(self, inputs):
        levels = np.array([.01,.05,.1,.15,.2,.25,.3,.35,.4,.45,.5,.55,.6,.65,.7,.75,.8,.85,.9,.95,.99],dtype=np.float32)
        return ForecastResult(np.ones((*inputs.context.shape[:2],inputs.prediction_length,21),dtype=np.float32),levels)

if __name__ == '__main__':
    configure_transport_errors(model_server.app)
    model = TimestralModel(Settings(model_revision='a'*40),loader=lambda _:Backend())
    model.load()
    ModelServer().start([model])
