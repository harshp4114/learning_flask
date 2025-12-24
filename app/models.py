from app import db, login
from datetime import datetime
import flask_mail
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin
from hashlib import md5
from time import time
import jwt
from flask import current_app
from app.search import add_to_index, query_index, remove_from_index
import json

followers = db.Table(
    "followers",
    db.Column("follower_id", db.Integer, db.ForeignKey("user.id")),
    db.Column("followed_id", db.Integer, db.ForeignKey("user.id")),
)


class SearchableMixin(object):
    @classmethod
    def search(cls, expression, page, per_page):
        # print("search method called")
        ids, total = query_index(cls.__tablename__, expression, page, per_page)
        # print("search result ",ids,total,range(len(ids)))

        if total == 0:
            return cls.query.filter_by(id=0), 0

        when = []
        for i in range(len(ids)):
            when.append((ids[i] == cls.id, i))

        # print(*when,cls.id==ids[0],"jfdbjbkjwenjkwfenjk ")
        return cls.query.filter(cls.id.in_(ids)).order_by(db.case(*when)), total

    @classmethod
    def before_commit(cls, session):
        # print("before commit called")
        session._changes = {
            "add": [obj for obj in session.new if isinstance(obj, cls)],
            "update": [obj for obj in session.dirty if isinstance(obj, cls)],
            "delete": [obj for obj in session.deleted if isinstance(obj, cls)],
        }
        # print("session._changes: ",session._changes['add'],session._changes['update'],session._changes['delete'])

    @classmethod
    def after_commit(cls, session):
        # print("after commit called")
        for obj in session._changes["add"]:
            add_to_index(cls.__tablename__, obj)
        for obj in session._changes["update"]:
            add_to_index(cls.__tablename__, obj)
        for obj in session._changes["delete"]:
            remove_from_index(cls.__tablename__, obj)
        session._changes = None

    @classmethod
    def reindex(cls):
        # print("reindex called")
        for obj in cls.query:
            add_to_index(cls.__tablename__, obj)


class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), index=True, unique=True)
    email = db.Column(db.String(120), index=True, unique=True)
    password_hash = db.Column(db.String(512))
    posts = db.relationship("Post", backref="author", lazy="dynamic")
    about_me = db.Column(db.String(140))
    last_seen = db.Column(db.DateTime, default=datetime.now)
    followed = db.relationship(
        "User",
        secondary=followers,
        primaryjoin=(followers.c.follower_id == id),
        secondaryjoin=(followers.c.followed_id == id),
        backref=db.backref("followers", lazy="dynamic"),
        lazy="dynamic",
    )
    messages_sent = db.relationship(
        "Message", foreign_keys="Message.sender_id", backref="author", lazy="dynamic"
    )
    messages_received = db.relationship(
        "Message",
        foreign_keys="Message.recipient_id",
        backref="recipient",
        lazy="dynamic",
    )
    last_message_read_time = db.Column(db.DateTime)
    notifications=db.relationship('Notification',backref='user',lazy='dynamic')

    def get_reset_password_token(self, expires_in=600):
        return jwt.encode(
            {"reset_password": self.id, "exp": time() + expires_in},
            current_app.config["SECRET_KEY"],
            algorithm="HS256",
        )

    @staticmethod
    def verify_reset_password_token(token):
        try:
            id = jwt.decode(
                token, current_app.config["SECRET_KEY"], algorithms=["HS256"]
            )["reset_password"]
        except:
            return
        return User.query.get(id)

    def follow(self, user):
        if not self.is_following(user):
            self.followed.append(user)

    def unfollow(self, user):
        if self.is_following(user):
            self.followed.remove(user)

    def is_following(self, user):
        return self.followed.filter(followers.c.followed_id == user.id).count() > 0

    def __repr__(self):
        return "<User {}>".format(self.username)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password_hash(self, password):
        return check_password_hash(self.password_hash, password)

    def avatar(self, size):
        digest = md5(self.email.lower().encode("utf-8")).hexdigest()
        return "https://www.gravatar.com/avatar/{}?d=identicon&s={}".format(
            digest, size
        )

    def followed_posts(self):
        followed = Post.query.join(
            followers, (followers.c.followed_id == Post.user_id)
        ).filter(followers.c.follower_id == self.id)

        return followed.union(self.posts).order_by(Post.timestamp.desc())

    def new_messages(self):
        print("bjhbcdjkbjksbnjkbnjkandj bjbsdjhabhjdasjhbdaswjhgbjhswgbjh")
        last_read_time = self.last_message_read_time or datetime(1900, 1, 1)
        return (
            Message.query.filter_by(recipient=self)
            .filter(Message.timestamp > last_read_time)
            .count()
        )
    
    def add_notifications(self,name,data):
        self.notifications.filter_by(name=name).delete()
        n=Notification(name=name,payload_json=json.dumps(data),user=self)
        db.session.add(n)
        return n

class Notification(db.Model):
    id=db.Column(db.Integer,primary_key=True)
    name=db.Column(db.String(128),index=True)
    user_id=db.Column(db.Integer,db.ForeignKey('user.id'))
    timestamp=db.Column(db.Float,index=True,default=time)
    payload_json=db.Column(db.Text)

    def get_data(self):
        return json.loads(self.payload_json)


@login.user_loader
def load_user(id):
    return User.query.get(int(id))


class Message(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    sender_id = db.Column(db.Integer, db.ForeignKey("user.id"))
    recipient_id = db.Column(db.Integer, db.ForeignKey("user.id"))
    body = db.Column(db.String(140))
    timestamp = db.Column(db.DateTime, index=True, default=datetime.now)

    def __repr__(self):
        return "<Message {}>".format(self.body)


class Post(SearchableMixin, db.Model):
    __searchable__ = ["body", "author.username"]
    id = db.Column(db.Integer, primary_key=True)
    body = db.Column(db.String(140))
    timestamp = db.Column(db.DateTime, index=True, default=datetime.now)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"))
    language = db.Column(db.String(5))

    def __repr__(self):
        return "<Post {}>".format(self.body)


db.event.listen(db.session, "before_commit", Post.before_commit)
db.event.listen(db.session, "after_commit", Post.after_commit)
