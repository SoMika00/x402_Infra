import logging
import json
import sys

class JsonFormatter(logging.Formatter):
    def format(self, record):
        data = {
            "level": record.levelname,
            "name": record.name,
            "message": record.getMessage(),
        }
        if hasattr(record, "request_id"):
            data["request_id"] = record.request_id
        return json.dumps(data)

def setup_logging(level="INFO"):
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.setLevel(level)
    root.handlers = [handler]
