from typing import Union, Any, Type

from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
import os, argon2
import re

import datetime as dt

##############################
# GLOBALS


class TH:
    """Class containing typehint Unions for readability. Postfix _n signals None allowed."""

    # date/time/datetime
    dates       = Union[str, dt.date, dt.datetime, 'VirtualDatetime']
    dates_n     = Union[dates, None]
    times       = Union[str, dt.time, dt.datetime, 'VirtualDatetime']
    times_n     = Union[times, None]
    datetimes   = Union[str, dt.datetime, 'VirtualDatetime']
    datetimes_n = Union[datetimes, None]

    # regex
    regex = list[re.Match, ...] | Type[re.error]

    # Unions
    tt_objs     = Union['Group', 'Student']
    tts_objs    = Union['Employee', 'Group', 'Student']

    user_clss   = Union['Student', 'Employee']

    @staticmethod
    def none_or(cls: Any) -> Union[Any, None]:
        return Union[cls, None]


class Cf:
    """Config class containing globals"""

    # organisational configuration
    # real life implementation would utilize a database
    # this implementation just showcases a single organisation
    demo        = True
    max_late    = 5
    max_abs     = 30
    mail_dom    = 'school.nl'
    senior      = 4  # class x and up
    year_start  = '2021/08/30'

    # date and time formatting
    d_str       = '2022/01/20'  # default date, assign to None for real date
    t_str       = '15:30'       # default time, assign to None for real time
    dt_str      = d_str + ' ' + t_str

    d_form      = '%Y/%m/%d'
    t_form      = '%H:%M'
    dt_form     = d_form + ' ' + t_form

    # regex
    # yy/mm/dd  | yy-mm-dd  = yy:[0/00-99], mm: [1/01-12], dd: [1/01-31]
    d_regex     = """^(\d{2})[\/-](0?[1-9]|1[0-2])[\/-](0?[1-9]|[1-2][0-9]|3[0-1])$"""
    # hh:mm     | hhmm      = hh:[00-23],   mm:[00-59]
    t_regex     = """^(0[0-9]|1[0-9]|2[0-3]):?([0-5][0-9])$"""

    # email_regex     = """^[\+\.@&a-zA-Z0-9À-ÖØ-öø-ÿ]+@.+\..+$"""
    # password_regex  = """.*[\.!~`@#\$%\^&\*\(\)\\-_={}\+\[\]\|'\";:\/\?><,€].*"""
    # name_regex      = """^\s*([a-zA-Z -]*?)\s*$"""
    # birthday_regex  = """^\d\d[-\/]\d\d[-\/]\d\d\d\d$"""

    # database connection
    schema      = 'organisation'
    user        = 'user'
    passwd      = 'pass'
    host        = '127.0.0.1'
    port        = 3306

    @staticmethod
    def sanitize_sql(string: str) -> TH.none_or(str):
        """Return sanitized string to prevent SQL Injection"""
        # SQLAlchemy should sanitize by default. Added for peace of mind

        forbidden   = """ ~`!#$%^&*()-_=+[]{};:'"\|,<>?/""".split()
        for str in ('select', 'from', 'where', 'drop'):
            forbidden.append(str)

        for f in forbidden:
            if f in string.lower():
                return None

        return string


class VD:
    """Virtual Datetime
    This class allows for easy virtual date configuration
    and manipulation. Interfaces with datetime module.

    One instance of this class will be instantiated at runtime.
    This is the simulated (virtual) datetime used for demonstration
    purposes (aka overwriting the real date/time to use app
    outside of school hours)."""

    date:           dt.date     = None
    date_str:       str         = None
    time:           dt.time     = None
    time_str:       str         = None
    datetime:       dt.datetime = None
    datetime_str:   str         = None

    weekday = [
        'monday',
        'tuesday',
        'wednesday',
        'thursday',
        'friday',
        'saturday',
        'sunday',
    ]


    ####################
    # INSTANCE METHODS #
    ####################

    def __init__(self):
        self.reset()  # set defaults from Config

    def tomorrow(self):
        return self.date + dt.timedelta(days=1)

    def yesterday(self):
        return self.date + dt.timedelta(days=-1)

    def is_default(self):
        """Attributes date and time are currently set to default"""
        return self.is_default_date() and self.is_default_time()

    def is_default_date(self):
        """Attribute date is currently set to default"""
        return self.date == VD.parse_date(Cf.d_str)

    def is_default_time(self):
        """Attribute time is currently set to default"""
        return self.time == VD.parse_time(Cf.t_str)

    def set_date_now(self) -> None:
        """Set instance date to current date"""
        self.set_date(dt.datetime.now())
        self.update()

    def set_time_now(self) -> None:
        """Set instance date to current date"""
        self.set_time(dt.datetime.now())
        self.update()

    def set_dt_now(self) -> None:
        """Set instance date to current date"""
        self.set_dt(dt.datetime.now())
        self.update()

    def reset(self) -> None:
        """Set instance date/time/datetime to default"""
        self.date       = VD.parse_date(Cf.d_str)
        self.time       = VD.parse_time(Cf.t_str)
        self.update()

    def set_date(self, date: TH.dates_n) -> None:
        """Set instance date. Use current if passed None. Updates self.datetime"""
        self.date       = VD.conv_any_date(date) if date else VD.parse_date(Cf.d_str)
        self.update()

    def set_time(self, time: TH.times_n) -> None:
        """Set instance time. Use current if passed None. Updates self.datetime"""
        self.time       = VD.conv_any_time(time) if time else VD.parse_time(Cf.t_str)
        self.update()

    def set_dt(self, datetime: TH.datetimes_n) -> None:
        """Set instance datetime and update date/time. Use current if passed None"""
        datetime        = VD.conv_any_dt(datetime) if datetime else VD.parse_dt(Cf.dt_str)
        self.date       = datetime.date()
        self.time       = datetime.time()

    def update(self) -> None:
        """Assign instance var datetime from instance vars date/time and
        assign string representations."""
        self.datetime       = dt.datetime.combine(self.date, self.time)
        self.date_str       = dt.datetime.strftime(self.datetime, Cf.d_form)
        self.time_str       = dt.datetime.strftime(self.datetime, Cf.t_form)
        self.datetime_str   = dt.datetime.strftime(self.datetime, Cf.dt_form)

    def process_form(self, data: dict) -> None:
        """Process form data. Set vd.date or vd.time based on form input. Use current if None.
        Form params must be named virtual_date and virtual_time"""
        self.set_date(VD.parse_date(VD.rx_date(data['virtual_date']))) if data['virtual_date'] else self.set_date(None)
        self.set_time(VD.parse_time(VD.rx_time(data['virtual_time']))) if data['virtual_time'] else self.set_time(None)


    ##################
    # STATIC METHODS

    @staticmethod
    def comp_date(date: dt.date) -> str:
        """Compose string from date object"""
        return dt.date.strftime(date, Cf.d_form)

    @staticmethod
    def comp_time(time: dt.time) -> str:
        """Compose string from time object"""
        return dt.time.strftime(time, Cf.t_form)

    @staticmethod
    def comp_dt(datetime: dt.datetime) -> str:
        """Compose string from datetime object"""
        return dt.datetime.strftime(datetime, Cf.dt_form)

    @staticmethod
    def parse_date(string: str) -> dt.date:
        """Parse date. If passed None, use default str from
        webapp.Config"""
        if not string:
            string = Cf.d_str
        return dt.datetime.strptime(string, Cf.d_form).date()

    @staticmethod
    def parse_time(string: str) -> dt.time:
        """Parse time. If passed None, use default str from
        webapp.Config"""
        if not string:
            string = Cf.t_str
        return dt.datetime.strptime(string, Cf.t_form).time()

    @staticmethod
    def parse_dt(string: str) -> dt.datetime:
        """Parse datetime. If passed None, use default str from
        webapp.Config"""
        if not string:
            string = Cf.dt_str
        return dt.datetime.strptime(string, Cf.dt_form)

    @staticmethod
    def conv_any_date(date: TH.dates) -> TH.none_or(dt.date):
        if isinstance(date, str):
            return VD.parse_date(date)
        elif isinstance(date, dt.datetime):
            return date.date()
        elif isinstance(date, dt.date):
            return date
        elif isinstance(date, VD):
            return date.date

    @staticmethod
    def conv_any_time(time: TH.times) -> TH.none_or(dt.time):
        if isinstance(time, str):
            return VD.parse_time(time)
        elif isinstance(time, dt.datetime):
            return time.time()
        elif isinstance(time, dt.time):
            return time
        elif isinstance(time, VD):
            return time.time

    @staticmethod
    def conv_any_dt(datetime: TH.datetimes_n = None) -> TH.none_or(dt.datetime):
        if isinstance(datetime, str):
            return VD.parse_dt(datetime)
        elif isinstance(datetime, dt.datetime):
            return datetime
        elif isinstance(datetime, VD):
            return datetime.datetime

    @staticmethod
    def rx_date(date: str) -> str:
        match = re.match(Cf.d_regex, date)
        if match:
            match = '/'.join(['20' + match.group(1), match.group(2), match.group(3)])
        return match if match else None

    @staticmethod
    def rx_time(time: str) -> str:
        match = re.match(Cf.t_regex, time)
        if match:
            match = ':'.join([match.group(1), match.group(2)])
        return match if match else None



##############################
# ARGON

argon2.DEFAULT_RANDOM_SALT_LENGTH = 16
argon2.DEFAULT_HASH_LENGTH = 16
argon2.DEFAULT_TIME_COST = 1
argon2.DEFAULT_MEMORY_COST = 8000000
argon2.DEFAULT_PARALLELISM = 4
ph = argon2.PasswordHasher()


##############################
# FLASK APP CONFIG

APP_PATH        = os.path.dirname(os.path.abspath(__file__))
STATIC_PATH     = os.path.join(APP_PATH, '../static')
TEMPLATE_PATH   = os.path.join(APP_PATH, '../templates')

app = Flask(__name__, template_folder=TEMPLATE_PATH, static_folder=STATIC_PATH)

app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = '2164e34cc6e79f2d731fd52b7e4b4858'
app.config['SQLALCHEMY_DATABASE_URI'] = \
    "mysql+pymysql://{}:{}@{}:{}/{}"    \
    .format(
        Cf.user,
        Cf.passwd,
        Cf.host,
        Cf.port,
        Cf.schema
    )


##############################
# OTHER INIT

db = SQLAlchemy(app)
login_manager = LoginManager()
login_manager.init_app(app)

vd  = VD()

# At end to prevent circular import. Encouraged by Flask docs
from webapp.models import *
from webapp.routes import *
from webapp.forms import *






















