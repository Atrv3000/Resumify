from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField
from wtforms.validators import DataRequired, Length, Email, EqualTo, Regexp

class LoginForm(FlaskForm):
    email = StringField('Email', validators=[
        DataRequired(),
        Email(message='Enter a valid email address.')
    ])
    password = PasswordField('Password', validators=[DataRequired()])
    submit = SubmitField('Log In')


class RegisterForm(FlaskForm):
    first_name = StringField('First Name', validators=[
        DataRequired(), Length(min=2, max=30)
    ])

    last_name = StringField('Last Name', validators=[
        DataRequired(), Length(min=2, max=30)
    ])

    email = StringField('Email', validators=[
        DataRequired(),
        Email(message='Enter a valid email address.'),
        Regexp(r'^[\w\.-]+@[\w\.-]+\.\w+$', message="Invalid email format.")
    ])

    password = PasswordField('Password', validators=[
        DataRequired(), Length(min=6)
    ])

    confirm_password = PasswordField('Confirm Password', validators=[
        DataRequired(), EqualTo('password', message='Passwords must match.')
    ])

    submit = SubmitField('Register')
