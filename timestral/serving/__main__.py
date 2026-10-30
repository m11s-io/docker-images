"""Official KServe server entry point. No application-owned HTTP routes."""
from kserve import ModelServer, model_server

from .kserve_model import TimestralModel
from .upstream import Settings


def main():
    # KServe parses its documented flags. A single worker owns one loaded model.
    if model_server.args.workers != 1:
        raise ValueError('Timestral requires exactly one worker per container')
    if model_server.args.grpc_max_receive_message_length > 8388608:
        raise ValueError('gRPC receive limit must be at most 8 MiB')
    model = TimestralModel(Settings.from_env())
    model.load()
    ModelServer().start([model])


if __name__ == '__main__':
    main()
