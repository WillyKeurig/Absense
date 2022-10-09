# db = SQLAlchemy db connection instance
# VD = virtual datetime class (used for static methods)
# vd = instance at runtime
# TH = class with Type Hint shortcuts (Unions)

import datetime as dt
import json
from os import path
from typing import Tuple, Iterable

# import modules
from flask import url_for
from flask_login import UserMixin  # used as class template for login functionality

# import project
from webapp import db, vd, VD, TH, Cf


################
# DECORATORS

def flask_login_id_callback_to_email(cls):
    """Decorator that overrides inherited UserMixin method .get_id(). This method is
    used by module flask_login as callback. Instead of looking through 'id' table, now
    queries 'email' table. This allows both Students and Employees to be found in case
    of identical db id's."""

    # new get_id() method. Keep same method name to stay compatible with flask_login module
    def get_email(self):
        try:
            return str(self.email)
        except AttributeError:
            raise NotImplementedError("No `email` attribute - override `get_id`") from None

    setattr(cls, 'get_id', get_email)
    return cls


################
# EXCEPTIONS

class TimetableOverlapError(Exception):

    def __init(self, id1: int, id2: int):
        self.string = f"Timetables with id's {id1} and {id2} contain overlapping dates."

    def __str__(self):
        return self.string


################
# RELATIONS

class ManyToMany:
    # many to many relations. Use of tables instead of models is recommended by Flask docs
    group_employee = db.Table(
        'group_employee_rl',
        db.Column(
            'group_id',
            db.Integer,
            db.ForeignKey('group.id'),
            primary_key=True,
        ),
        db.Column(
            'employee_id',
            db.Integer,
            db.ForeignKey('employee.id'),
            primary_key=True,
        ),
    )

    employee_title = db.Table(
        'employee_title_rl',
        db.Column(
            'employee_id',
            db.Integer,
            db.ForeignKey('employee.id'),
            primary_key=True,
        ),
        db.Column(
            'title_id',
            db.Integer,
            db.ForeignKey('title.id'),
            primary_key=True,
        ),
    )

    group_timetable = db.Table(
        'group_timetable_rl',
        db.Column(
            'group_id',
            db.Integer,
            db.ForeignKey('group.id'),
            primary_key=True,
        ),
        db.Column(
            'timetable_id',
            db.Integer,
            db.ForeignKey('timetable.id'),
            primary_key=True,
        ),
    )

    student_group = db.Table(
        'student_group_rl',
        db.Column(
            'student_id',
            db.Integer,
            db.ForeignKey('student.id'),
            primary_key=True,
        ),
        db.Column(
            'group_id',
            db.Integer,
            db.ForeignKey('group.id'),
            primary_key=True,
        ),
    )

################
# MODELS

class Cause(db.Model):
    __tablename__ = 'cause'

    def __repr__(self):
        return f'<{self.string}>'

    # cols
    id          = db.Column(db.Integer(),   primary_key=True, unique=True, autoincrement=True)
    string      = db.Column(db.String(50),  nullable=False)

    # foreign
    records     = db.relationship('Record', back_populates='cause')


@flask_login_id_callback_to_email
class Employee(db.Model, UserMixin):
    __tablename__ = 'employee'

    def __repr__(self):
        return '<' + ' '.join(filter(None,  # filter empty name_middle
            (self.name_first, self.name_middle, self.name_last))) + '>'

    # cols
    id          = db.Column(db.Integer(),   primary_key=True, unique=True, autoincrement=True)
    email       = db.Column(db.String(50),  unique=True, nullable= False)
    password    = db.Column(db.String(100))
    name_first  = db.Column(db.String(20),  nullable=False)
    name_middle = db.Column(db.String(10))
    name_last   = db.Column(db.String(20),  nullable=False)

    groups = db.relationship(
        'Group',
        secondary       = ManyToMany.group_employee,
        back_populates  = 'employees',
    )
    titles = db.relationship(
        'Title',
        secondary       = ManyToMany.employee_title,
        back_populates  = 'employees',
    )

    def name(self):
        if self.name_middle:
            return f'{self.name_first} {self.name_middle} {self.name_last}'
        else:
            return f'{self.name_first} {self.name_last}'

    @staticmethod
    def from_id(id: int) -> TH.none_or('Employee'):
        """Return Employee instance from id. Return None if not found or type(id) != int"""
        return Employee.query.filter_by(id=id).first() if type(id) == int else None

    @staticmethod
    def from_email(email: str) -> TH.none_or('Employee'):
        """Return Employee instance from email"""
        email = Cf.sanitize_sql(email)
        return Employee.query.filter_by(email=email).first() if email else None


class Group(db.Model):
    __tablename__ = 'group'

    def __repr__(self):
        return f'<{self.string}>'

    # cols
    id          = db.Column(db.Integer(),   primary_key=True, unique=True, autoincrement=True)
    string      = db.Column(db.String(30),  nullable=False)
    year        = db.Column(db.Integer())
    level       = db.Column(db.String(20))

    students    = db.relationship('Student', back_populates='group')
    timetables  = db.relationship(
        'Timetable',
        secondary       = ManyToMany.group_timetable,
        back_populates  = 'groups',
    )
    employees   = db.relationship(
        'Employee',
        secondary       = ManyToMany.group_employee,
        back_populates  = 'groups'
    )

    def timetable(self, date: TH.dates_n = None) -> TH.none_or('Timetable'):
        """Return Timetable active on Date. Use virtual dt if date=None"""
        date = vd.date if not date else VD.conv_any_date(date)

        # if any timetable active
        for tt in self.timetables:
            if tt.is_active(date):
                return tt

        # has timetable but none active, return first tt starting after date
        for tt in self.timetables:
            if VD.parse_date(tt.date_start) > date:
                return tt

        # all groups have at least 1 timetable in this demo. catchall == 1st tt of group
        return self.timetables[0]

    def prev_tt(self, date: TH.dates_n = None):
        return self.timetables[self.timetables.index(self.timetable(date)) - 1]

    def next_tt(self, date: TH.dates_n = None) -> TH.none_or('Timetable'):
        return self.timetables[self.timetables.index(self.timetable(date)) + 1]

    def hours_on_date(self, date: TH.dates_n = None) -> TH.none_or(Tuple['Hour', ...]):
        """Return Hours on date if present, else None. Use virtual dt if date=None"""
        date = vd.date if not date else VD.conv_any_date(date)

        # check for overlap. prevent  unexpected behaviour
        Timetable.eck_overlap(self.timetables)

        for tt in self.timetables:
            if tt.is_active(date):
                return tt.hours_on_day(date.weekday())

        return None

    def hours_next_day(self, date: TH.dates_n = None) -> TH.none_or(Tuple['Hour', ...]):
        """Return Hours on next day with Hours. Use virtual dt if date=None"""
        date = vd.date if not date else VD.conv_any_date(date)

        # iterate days (asc.) until end of Timetable to find remaining Hours
        if self.timetable(date):
            # time between passed date and end of timetable
            delta = VD.parse_date(self.timetable(date).date_end) - date
            # iterate until reached the end of timetable
            for days in range(1, delta.days):
                # for each day check if hours
                tmp_date = date + dt.timedelta(days=days)
                if self.hours_on_date(tmp_date):
                    return self.hours_on_date(tmp_date)

            # return first day with Hours of next Timetable
            next_tt = self.next_tt(date)
            if next_tt:
                for day in range(0, 4):
                    if next_tt.hours_on_day(day):
                        return next_tt.hours_on_day(day)

        elif not self.timetable(date) and self.timetables:
            return self.hours_on_date(VD.parse_date(self.timetables[0].date_start))

        return None

    def hours_prev_day(self, date: TH.dates_n = None) -> TH.none_or(Tuple['Hour', ...]):
        """Return Hours on previous day with Hours. Use virtual dt if date=None"""

        # iterate days (desc.) until start of prev Timetable to find remaining Hours
        delta = VD.parse_dt(date) - VD.parse_dt(self.timetable(date).date_start)
        for days in range(0, delta.days):
            if self.hours_on_date(date - dt.timedelta(days=days)):
                return self.hours_on_date(date - dt.timedelta(days=days))

        # return first day (backwards) with Hours of next Timetable
        prev_tt = self.prev_tt(date)
        if prev_tt:
            for day in range(4, 0):
                if prev_tt.hours_on_day(day):
                    return prev_tt.hours_on_day(day)

        return None

    def hour_now(self, datetime: TH.datetimes_n = None) -> TH.none_or('Hour'):
        """Return current Hour based on datetime, else None. Use virtual dt if date=None"""
        datetime = vd.datetime if not datetime else VD.conv_any_dt(datetime)

        if self.hours_on_date(datetime.date()):  # if lessons today
            for hour in self.hours_on_date(datetime.date()):  # iter Hours on date
                if VD.parse_time(hour.time_start) <= datetime.time() <= VD.parse_time(hour.time_end):
                    return hour  # return hour if time between Hour start and end

        return None

    def hour_next(self, datetime: TH.datetimes_n = None) -> TH.none_or('Hour'):
        """Return next Hour based on datetime. Handles off days, weekends and time in between Hours"""
        datetime = vd.datetime if not datetime else VD.conv_any_dt(datetime)

        # if no lessons left
        if self.is_off(datetime):
            return None

        hour_current    = self.hour_now(datetime)
        hours_today     = self.hours_on_date(datetime)
        hours_next_day  = self.hours_next_day(datetime)

        # return next Hour if hours left today
        if hour_current:
            if hours_today.index(hour_current) < len(hours_today) - 1:
                return hours_today[hours_today.index(hour_current) + 1]

        # if in between hours return first Hour ending after cur time
        elif hours_today:
            for hour in hours_today:
                if VD.conv_any_time(datetime) < VD.parse_time(hour.time_end):
                    return hour

        # else return first Hour next day
        if hours_next_day:
            return hours_next_day[0]

        return None

    def hour_next_date(self, datetime: TH.datetimes_n = None) -> TH.none_or(dt.date):
        """Return date object of next Hour of Group. Use virtual dt if datetime=None"""
        datetime    = vd.datetime if not datetime else VD.conv_any_dt(datetime)

        if self.is_off(datetime):
            return None

        tt          = self.timetable(datetime)
        tt_start    = VD.conv_any_date(tt.date_start)
        next_hour   = self.hour_next(datetime)

        # if no tt active and tt in future
        if datetime.date() < tt_start:
            return tt_start

        # if next hour later in week: return date + difference until next hour
        elif datetime.weekday() <= next_hour.day_of_week:
            diff = next_hour.day_of_week - datetime.weekday()
            # if same day and no lessons left, return next day
            if not self.has_lessons() and not diff:
                diff = 1
            return datetime.date() + dt.timedelta(days=diff)

        # else hour not later in week: return date of first hour next week
        else:
            diff = 7 - (datetime.weekday() - next_hour.day_of_week)
            return datetime.date() + dt.timedelta(days=diff)

    def hour_prev(self, datetime: TH.datetimes_n = None) -> TH.none_or('Hour'):
        """Return previous Hour based on datetime. Handles off days, weekends and time in between Hours"""
        hour_current    = self.hour_now(datetime)
        hours_today     = self.hours_on_date(datetime)
        hours_prev_day  = self.hours_prev_day(datetime)

        # return prev Hour if current Hour not last Hour
        if hour_current:
            if hours_today.index[hour_current] >= 1:
                return hours_today[hours_today.index(hour_current) - 1]

        # if in between Hours return first Hour ending before cur time
        for hour in reversed(hours_today):
            if VD.parse_time(datetime) > VD.parse_time(hour.time_end):
                return hour

        # else return last Hour prev day
        if hours_prev_day:
            return hours_prev_day[-1]

        return None

    def has_lessons(self, datetime: TH.datetimes_n = None) -> bool:
        """Return True if last Hour of day starts after passed time. Else False"""
        datetime = vd.datetime if not datetime else VD.conv_any_dt(datetime)
        if self.hours_on_date(datetime.date()):
            return True if datetime.time() < VD.parse_time(self.hours_on_date(datetime.date())[-1].time_start) else False
        return False

    def is_late(self, datetime: TH.datetimes_n = None) -> bool:
        """Return True if Group is late on datetime. Use virtual dt if date=None"""
        datetime    = vd.datetime if not datetime else VD.conv_any_dt(datetime)
        cur_hour    = self.hour_now(datetime)
        hour_start  = VD.parse_time(cur_hour.time_start)
        start_dt    = dt.datetime.combine(datetime.date(), hour_start)  # dt cls to allow timedelta

        if cur_hour:
            # if current time past Hour start + late after minutes -> late
            return datetime.time() > (start_dt + dt.timedelta(minutes=Cf.max_late)).time()

    def mins_late(self, datetime: TH.datetimes_n = None) -> TH.none_or(int):
        """Return minutes past active lesson starting time. Return None if no active lesson.
        Use virtual dt if datetime=None"""
        datetime = vd.datetime if not datetime else VD.conv_any_dt(datetime)

        if not self.hour_now(datetime):
            return None

        start   = VD.parse_time(self.hour_now(datetime).time_start)
        start   = datetime.combine(datetime.date(), start)


        if start < datetime:
            # if later than max allowed in config, return diff in minutes
            return int((datetime - start).total_seconds() / 60)
        return 0

    def is_absent(self, datetime: TH.datetimes_n = None) -> bool:
        """Return True if Group is later than the last time they are allowed to enter.
        Use virtual dt if date=None"""
        datetime    = vd.datetime if not datetime else VD.conv_any_dt(datetime)
        cur_hour    = self.hour_now(datetime)
        hour_start  = VD.parse_time(cur_hour.time_start)
        start_dt    = dt.datetime.combine(datetime.date(), hour_start)  # dt cls to allow timedelta

        if cur_hour:
            # if current time past Hour start + max minutes late for absence
            return True if datetime > (start_dt + dt.timedelta(Cf.max_abs)) else False

    def is_off(self, datetime: TH.datetimes_n = None) -> bool:
        """Check if dt is past last hour of last day of last timetable. Use virtual dt if datetime=None"""
        datetime    = VD.conv_any_dt(datetime) or vd.datetime
        last_tt     = sorted(self.timetables, key=lambda x: VD.parse_date(x.date_end))[-1]

        hours       = sorted(last_tt.hours, key=lambda hour: \
            (hour.day_of_week, dt.datetime.combine(datetime.date(), VD.parse_time(hour.time_end))))
        last_hour   = hours[-1] if hours else None

        if last_tt and last_hour:
            # if datetime is past dt of last hour of last day of last timetable: return True
            if datetime > dt.datetime.combine(VD.parse_date(last_tt.date_end), VD.parse_time(last_hour.time_end)):
                return True

        return False

    @staticmethod
    def from_id(id: int) -> 'Group':
        """Return Group instance from id. Return None if not found or type(id) != int"""
        return Group.query.filter_by(id=id).first() if type(id) == int else None


class Hour(db.Model):
    __tablename__ = 'hour'

    def __repr__(self):
        return '<{}, d{}, h{}>'.format(
            self.course, self.day_of_week, self.hour_of_day)

    # cols
    id              = db.Column(db.Integer(),   primary_key=True, unique=True, autoincrement=True)
    day_of_week     = db.Column(db.Integer(),   nullable=False)
    hour_of_day     = db.Column(db.Integer(),   nullable=False)
    time_start      = db.Column(db.String(5),   nullable=False)
    time_end        = db.Column(db.String(5),   nullable=False)
    course          = db.Column(db.String(20),  nullable=False)
    level           = db.Column(db.String(20),  nullable=False)

    # foreign
    timetable_id    = db.Column(db.Integer(), db.ForeignKey('timetable.id'))
    records         = db.relationship('Record', back_populates='hour', lazy=True)
    timetable       = db.relationship('Timetable', back_populates='hours')


class Record(db.Model):
    __tablename__ = 'record'

    def __repr__(self):
        return '<{}>'.format((
            self.id, self.date, self.time,
            self.absent, self.reasoning, self.delay,
            self.student_id, self.hour_id, self.cause_id))

    # cols
    id          = db.Column(db.Integer(),   primary_key=True, unique=True, autoincrement=True)
    date        = db.Column(db.String(12),  nullable=False)
    time        = db.Column(db.String(5),   nullable=False)
    absent      = db.Column(db.Boolean(),   nullable=False)
    reasoning   = db.Column(db.String(100))
    delay       = db.Column(db.Integer())
    late        = db.Column(db.Boolean(),   nullable=False)

    # foreign
    student_id  = db.Column(db.Integer, db.ForeignKey('student.id'),  nullable=False)
    hour_id     = db.Column(db.Integer, db.ForeignKey('hour.id'),     nullable=False)
    cause_id    = db.Column(db.Integer, db.ForeignKey('cause.id'))

    student     = db.relationship('Student',back_populates='records')
    hour        = db.relationship('Hour',   back_populates='records')
    cause       = db.relationship('Cause',  back_populates='records')

    def datetime(self):
        return dt.datetime.combine(VD.parse_date(self.date), VD.parse_time(self.time))


@flask_login_id_callback_to_email
class Student(db.Model, UserMixin):
    __tablename__ = 'student'

    def __repr__(self):
        return '<' + ' '.join(filter(None,  # filter empty name_middle
            (self.name_first, self.name_middle, self.name_last))) + '>'

    # cols
    id          = db.Column(db.Integer(),   primary_key=True, unique=True, autoincrement=True)
    email       = db.Column(db.String(50),  unique=True)
    password    = db.Column(db.String(100))
    code        = db.Column(db.String(20),  unique=True)
    name_first  = db.Column(db.String(20),  nullable=False)
    name_middle = db.Column(db.String(10))
    name_last   = db.Column(db.String(20),  nullable=False)
    birthdate   = db.Column(db.String(12),  nullable=False)
    year        = db.Column(db.Integer(),   nullable=False)
    level       = db.Column(db.String(20),  nullable=False)
    card_token  = db.Column(db.String(8))

    # foreign
    group_id    = db.Column(db.Integer(),   db.ForeignKey('group.id'))
    # records     = db.relationship('Record', backref='students', lazy=True)
    records     = db.relationship('Record', back_populates='student')
    group       = db.relationship('Group',  back_populates='students')

    status      = None


    # Haven't given proper portrait implementation much thought. Looks nice, though.
    def portrait_url(self):
        with open(path.join('static', 'resources', 'populate', 'portrait_mapper.json'), 'r') as f:
            return path.join(url_for('static', filename=f'media/portraits/{json.load(f)[self.code]}'))


    def name(self):
        if self.name_middle:
            return f'{self.name_first} {self.name_middle} {self.name_last}'
        else:
            return f'{self.name_first} {self.name_last}'


    def has_logged(self, datetime: TH.datetimes_n = None) -> bool:
        """Return True if student has checked in this Hour but before datetime"""
        datetime = VD.conv_any_dt(datetime) or vd.datetime

        hour_current    = self.group.hour_now(datetime)

        if hour_current:
            records = self.records
            for record in records:
                r_dt = dt.datetime.combine(datetime.date(), VD.parse_time(record.time))
                if r_dt <= datetime and record.hour_id == hour_current.id and record.student_id == self.id:
                    return True
        return False


    def check_in(self, datetime: TH.datetimes_n = None, cause: TH.none_or(int) = None, reason: TH.none_or(str) = None) -> str:
        """Try to check in the student based on datetime.
        Returns string representing the check_in status"""

        datetime = vd.datetime if not datetime else VD.conv_any_dt(datetime)

        record = Record(
            # attrs
            date        = VD.comp_date(datetime.date()),
            time        = VD.comp_time(datetime.time()),
            absent      = self.group.is_absent(datetime),
            late        = self.group.is_late(),
            delay       = self.group.mins_late(),
            # foreign
            reasoning   = reason,
            student_id  = self.id,
            hour_id     = self.group.hour_now(datetime).id,
            cause_id    = cause,
        )

        try:
            db.session.add(record)
            db.session.commit()
        except:
            return 500  # error code internal server error


        if self.group.is_absent(datetime):
            return 'absent'
        elif self.group.is_late(datetime):
            return 'late'
        else:
            return 'present'

        # 1. find current hour per student
        # 2. check if student is logged that hour
        # 3. set color to logged or set based on time


    def update_status(self, datetime: TH.datetimes_n = None) -> None:
        """Update student status at datetime. Called at student overview page-load.
        Sets self.status for reference in template. """

        datetime = VD.conv_any_dt(datetime) or vd.datetime

        if not self.group.hour_now():
            self.status = 'not_expected'
            return

        hour    = self.group.hour_now(datetime)
        records = Record.query.filter_by(
            student_id  = self.id,
            hour_id     = hour.id,
            date        = VD.comp_date(datetime.date()),
        ).all()

        # if records are found, set record to most recent record before current vd.datetime
        record = None
        for rec in reversed(records):
            r_dt = dt.datetime.combine(datetime.date(), VD.parse_time(rec.time))
            if r_dt <= vd.datetime:
                record = rec

        def dt_absent(time: str) -> dt.datetime:
            time = dt.datetime.combine(datetime.date(), VD.parse_time(time))
            return time + dt.timedelta(minutes=Cf.max_abs)

        def dt_late(time: str) -> dt.datetime:
            time = dt.datetime.combine(datetime.date(), VD.parse_time(time))
            return time + dt.timedelta(minutes=Cf.max_late)

        if record:
            if record.absent:
                self.status = 'absent_known'
                return
            elif record.late and not record.absent:
                self.status = 'late_known'
                return
            else:
                self.status = 'present_known'
                return

        else:
            if datetime > dt_absent(hour.time_start):
                self.status = 'absent_unknown'
                return
            elif datetime > dt_late(hour.time_start):
                self.status = 'late_unknown'
                return
            else:
                self.status = 'present_unknown'
                return


    @staticmethod
    def from_id(id: int) -> TH.none_or('Student'):
        """Return Student instance from id. Return None if not found or type(id) != int"""
        return Student.query.filter_by(id=id).first() if type(id) == int else None


    @staticmethod
    def from_email(email: str) -> TH.none_or('Student'):
        """Return Student instance from email. Return None if not found. Sanitizes"""
        email = Cf.sanitize_sql(email)
        return Student.query.filter_by(email=email).first() if email else None


    @staticmethod
    def from_code(code: str) -> TH.none_or('Student'):
        """Return Student instance from code. Return None if not found or code not isnumeric"""
        return Student.query.filter_by(code=code).first() if code.isnumeric() else None


class Timetable(db.Model):
    __tablename__ = 'timetable'

    def __repr__(self):
        return f'<{self.string}: {self.date_start} - {self.date_end}>'

    id          = db.Column(db.Integer(),   primary_key=True)
    string      = db.Column(db.String(50),  nullable=False)
    date_start  = db.Column(db.String(5))
    date_end    = db.Column(db.String(5))

    # hours       = db.relationship('Hour', backref='timetable', lazy=True)
    hours       = db.relationship('Hour', back_populates='timetable')
    groups      = db.relationship(
        'Group',
        secondary       = ManyToMany.group_timetable,
        back_populates  = 'timetables',
    )


    def hours_on_day(self, day: int | str) -> Tuple['Hour', ...]:
        """Return Hours based on day of week or weekday"""
        day_of_week = VD.weekday.index(day) if day == str else day
        hours_on_day = []
        # iterate hours in table. append if day == day of week
        hours_all = sorted(self.hours, key=lambda x: (x.day_of_week, x.hour_of_day))

        for hour in hours_all:
            if hour.day_of_week == day_of_week:
                hours_on_day.append(hour)

        return tuple(hours_on_day)


    def is_active(self, date: TH.dates_n = None) -> bool:
        """Return True if this Timetable instance is active on date.
        Use virtual dt if no arg"""

        date    = vd.date if not date else VD.conv_any_date(date)
        start   = VD.parse_date(self.date_start)
        end     = VD.parse_date(self.date_end)

        return start <= date <= end


    @staticmethod
    def instantiate(id: int) -> TH.none_or('Timetable'):
        """Return Timetable instance from id"""
        return Timetable.query.filter_by(id=id).first()

    @staticmethod
    def eck_overlap(timetables: Iterable['Timetable']) -> None:
        """Error check overlap of dates in passed Timetables.
        If overlap: raise TimetableOverlapError with conflicting table ids."""

        # sort timetables by starting date
        timetables = sorted(timetables, key=lambda x: VD.parse_date(x.date_start))

        # iterate to check overlap
        for i in range(len(timetables)-1):  # -1 to skip last
            tt1_end     = VD.parse_date(timetables[i].date_end)
            tt2_start   = VD.parse_date(timetables[i + 1].date_start)

            if tt1_end > tt2_start:
                raise TimetableOverlapError(timetables[i].id, timetables[i+1].id)


class Title(db.Model):
    __tablename__ = 'title'

    def __repr__(self):
        return f'<{self.string}>'

    id          = db.Column(db.Integer(),   primary_key=True, unique=True, autoincrement=True)
    string      = db.Column(db.String(50),  nullable=False)
    admin       = db.Column(db.Boolean(),   nullable=False)
    year        = db.Column(db.Integer())
    level       = db.Column(db.String(20))
    senior      = db.Column(db.Boolean(),   default=None)

    employees = db.relationship(
        'Employee',
        secondary       = ManyToMany.employee_title,
        back_populates  = 'titles',
    )

    @staticmethod
    def from_string(string: str) -> TH.none_or('Title'):
        """Return Student instance from email. Return None if not found. Sanitizes"""
        string = Cf.sanitize_sql(string)
        return Title.query.filter_by(string=string).first() if string else None
