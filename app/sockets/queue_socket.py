from flask_socketio import join_room, leave_room

from app.extensions import socketio


@socketio.on("join_queue_room")
def handle_join(data):
    """Client (farmer queue-status page or admin dashboard) joins a room
    scoped to a centre + date so it only receives relevant updates."""
    centre_id = data.get("centre_id")
    date = data.get("date")
    if centre_id and date:
        join_room(f"centre_{centre_id}_{date}")


@socketio.on("leave_queue_room")
def handle_leave(data):
    centre_id = data.get("centre_id")
    date = data.get("date")
    if centre_id and date:
        leave_room(f"centre_{centre_id}_{date}")
