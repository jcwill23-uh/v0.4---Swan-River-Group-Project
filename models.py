from app import db

'''class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    role = db.Column(db.String(50), default="basicuser")
    status = db.Column(db.String(20), default="active")  # "active" or "deactivated"

    def __repr__(self):
        return f"<User {self.name}>"


def is_admin(user_email):
    user = User.query.filter_by(email=user_email).first()
    return user and user.role == "admin"'''
  
