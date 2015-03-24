import json
import logging

logger = logging.getLogger(__name__)

def send_ws_event(ws, event_type, data=None):
    if data is None:
        d = {"type": event_type}
    else:
        d = data.copy()
        d["type"] = event_type

    wire_str = json.dumps(d)
    ws.send(wire_str)
    logger.debug("Sent: %s", wire_str)


def receive_ws_event(ws):
    data = ws.receive()
    if data is None:
        return None

    logger.debug("Received: %s", data)
    return json.loads(data)


def send_command_fail(ws, command_id):
    send_ws_event(ws, "command_fail", {"command_id": command_id})


def send_command_success(ws, command_id):
    send_ws_event(ws, "command_success", {"command_id": command_id})


def send_query_success(ws, command_id, data):
    send_ws_event(ws, "query_success", {"command_id": command_id, "data": data})
