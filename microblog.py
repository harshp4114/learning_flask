from app.models import Message, Notification, Post, User
from app import db,create_app

app=create_app()

@app.shell_context_processor
def make_shell_context():
    return {'db':db,'User':User,'Post':Post,'Message':Message,'Notifications':Notification}