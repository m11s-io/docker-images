"""Official KServe server entry point. No application-owned HTTP routes."""
from kserve import ModelServer, model_server

from .kserve_model import TimestralModel
from .errors import configure_transport_errors
from .upstream import Settings


def main():
    # KServe parses its documented flags. A single worker owns one loaded model.
    if model_server.args.workers != 1:
        raise ValueError('Timestral requires exactly one worker per container')
    if not 1 <= model_server.args.grpc_max_receive_message_length <= 8388608:
        raise ValueError('gRPC receive limit must be positive and at most 8 MiB')
    configure_transport_errors(model_server.app)
    model = TimestralModel(Settings.from_env())
    model.load()
    ModelServer().start([model])


if __name__ == '__main__':
    main()
